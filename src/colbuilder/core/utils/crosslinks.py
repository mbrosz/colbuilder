# crosslinks.py
import os
import asyncio
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Any
import pandas as pd

from .data_structures import CrosslinkPosition, CrosslinkPair, OptimizationState
from .constants import (
    MAX_OPTIMIZATION_ATTEMPTS,
    MAX_TRIVALENT_DISTANCE,
    MAX_DIVALENT_DISTANCE,
    CRITICAL_DISTANCE_THRESHOLD
)
from colbuilder.core.utils.exceptions import SequenceGenerationError, SystemError
from colbuilder.core.sequence.optimize_crosslinks import optimize_structure
from colbuilder.core.utils.logger import setup_logger

LOG = setup_logger(__name__)

def parse_crosslink_position(position_str: str, residue_type: str, atom_name: str) -> Optional[CrosslinkPosition]:
    """
    Parse a position string into a CrosslinkPosition object.
    
    Args:
        position_str: String in format "number.chain"
        residue_type: Three-letter residue code
        atom_name: Atom identifier
        
    Returns:
        CrosslinkPosition object or None if position is "NONE"
        
    Raises:
        SequenceGenerationError: If position string format is invalid
    """
    try:
        if position_str == "NONE":
            return None
            
        parts = position_str.split('.')
        if len(parts) != 2:
            raise ValueError(f"Invalid position format: {position_str}")
            
        return CrosslinkPosition(
            residue_number=int(parts[0]),
            chain_id=parts[1],
            residue_type=residue_type,
            atom_name=atom_name
        )
    except (ValueError, IndexError) as e:
        raise SequenceGenerationError(
            "Invalid crosslink position format",
            original_error=e,
            error_code="SEQ_ERR_002",
            context={
                "position_str": position_str,
                "residue_type": residue_type,
                "atom_name": atom_name
            }
        )

def extract_crosslinks_from_dataframe(
    crosslinks_df: pd.DataFrame,
    terminal_type: str,
    term_type: Optional[str],
    term_combination: Optional[str]
) -> List[CrosslinkPair]:
    """
    Extract crosslink information from a DataFrame row.
    
    Args:
        crosslinks_df: DataFrame containing crosslink information
        terminal_type: 'N' or 'C' terminal
        term_type: Crosslink type
        term_combination: Residue combination string
        
    Returns:
        List of CrosslinkPair objects
        
    Raises:
        SequenceGenerationError: If crosslink data is invalid
    """
    try:
        if not term_type or not term_combination:
            return []
            
        filtered_df = crosslinks_df[
            (crosslinks_df['terminal'] == terminal_type) &
            (crosslinks_df['type'] == term_type) &
            (crosslinks_df['combination'] == term_combination)
        ]
        
        if filtered_df.empty:
            return []
            
        crosslinks = []
        for _, row in filtered_df.iterrows():
            pos1 = parse_crosslink_position(row['P1'], row['R1'], row['A1'])
            pos2 = parse_crosslink_position(row['P2'], row['R2'], row['A2'])
            
            if not pos1 or not pos2:
                continue
                
            pos3 = None
            if 'P3' in row and row['P3'] != "NONE":
                pos3 = parse_crosslink_position(row['P3'], row['R3'], row['A31'])
                
            crosslinks.append(CrosslinkPair(
                position1=pos1,
                position2=pos2,
                position3=pos3,
                terminal_type=terminal_type
            ))
            
        return crosslinks
        
    except Exception as e:
        raise SequenceGenerationError(
            "Error extracting crosslink information",
            original_error=e,
            error_code="SEQ_ERR_002",
            context={
                "terminal_type": terminal_type,
                "term_type": term_type,
                "term_combination": term_combination
            }
        )

class CrosslinkOptimizer:
    """Handles the optimization of crosslink positions."""
    
    def __init__(self, crosslink_pairs: List[CrosslinkPair], chimera_scripts_dir: Path):
        self.crosslink_pairs = crosslink_pairs
        self.chimera_scripts_dir = chimera_scripts_dir
        self.state = OptimizationState()

    def _get_distance_threshold(self) -> float:
        """Get the distance threshold based on crosslink types."""
        return MAX_TRIVALENT_DISTANCE if any(p.position3 is not None for p in self.crosslink_pairs) else MAX_DIVALENT_DISTANCE
        
    async def optimize(self, input_pdb: Path, output_pdb: Path) -> Tuple[float, Path]:
        """
        Optimize crosslink positions using Monte Carlo algorithm.
        
        Args:
            input_pdb: Path to input PDB file
            output_pdb: Path to output PDB file
            
        Returns:
            Tuple of (best_distance, optimized_pdb_path)
            
        Raises:
            SequenceGenerationError: If optimization fails
            SystemError: If Chimera process fails
        """
        try:
            generated_pdbs = await self._generate_copies(input_pdb)
            if len(generated_pdbs) < 2:
                raise SequenceGenerationError(
                    "Not enough PDB copies generated for optimization",
                    error_code="SEQ_ERR_003",
                    context={"generated_pdbs_count": len(generated_pdbs)}
                )
            
            crosslink_info = self._prepare_crosslink_info()
            
            max_total_distance = self._get_distance_threshold()
            
            current_input = input_pdb
            total_distance = float('inf')
            
            while (self.state.attempt_number < MAX_OPTIMIZATION_ATTEMPTS and 
                   total_distance > max_total_distance):
                
                total_distance, tracker = optimize_structure(
                    initial_pdb=str(current_input),
                    copy1_pdb=str(generated_pdbs[0]),
                    copy2_pdb=str(generated_pdbs[1]),
                    crosslink_info=crosslink_info,
                    optimized_pdb=str(output_pdb)
                )
                
                current_input = output_pdb
                self.state.update(total_distance) 
                self.state.increment_attempt()
                
                LOG.debug("Current distance: {:2f} Å".format(total_distance))
            
            if total_distance > CRITICAL_DISTANCE_THRESHOLD:
                raise SequenceGenerationError(
                    "Crosslinks optimization failed",
                    error_code="SEQ_ERR_003",
                    context={
                        "final_distance": total_distance,
                        "attempts": self.state.attempt_number,
                        "optimization_history": self.state.optimization_history
                    }
                )
            
            return total_distance, output_pdb
            
        finally:
            if 'generated_pdbs' in locals():
                for pdb in generated_pdbs:
                    try:
                        pdb.unlink(missing_ok=True)
                    except Exception as e:
                        LOG.warning(f"Failed to delete temporary file {pdb}: {str(e)}")
            
    async def _generate_copies(self, input_pdb: Path) -> List[Path]:
        """Generate copies using Chimera."""
        try:
            generate_copies_script = self.chimera_scripts_dir / 'generate_copies.py'
            generated_pdbs_file = Path("generated_pdbs.txt")
            
            env = os.environ.copy()
            env['INPUT_PDB'] = str(input_pdb)
            
            generate_command = ['chimera', '--nogui', '--script', str(generate_copies_script)]
            
            process = await asyncio.create_subprocess_exec(
                *generate_command,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise SystemError(
                    "Chimera process failed during copy generation",
                    error_code="SYS_ERR_001",
                    context={
                        "returncode": process.returncode,
                        "stdout": stdout.decode() if stdout else None,
                        "stderr": stderr.decode() if stderr else None,
                        "command": generate_command
                    }
                )
            
            if not generated_pdbs_file.exists():
                raise SequenceGenerationError(
                    "Generated PDBs list file not found",
                    error_code="SEQ_ERR_004",
                    context={"expected_file": str(generated_pdbs_file)}
                )
            
            with open(generated_pdbs_file, 'r') as f:
                generated_pdbs = [Path(line.strip()) for line in f]
                
            return generated_pdbs
            
        finally:
            if 'generated_pdbs_file' in locals():
                try:
                    generated_pdbs_file.unlink(missing_ok=True)
                except Exception:
                    pass
                    
    def _prepare_crosslink_info(self) -> List[Dict[str, str]]:
        """Convert CrosslinkPair objects to the format needed by optimize_structure."""
        return [
            {
                'chain1_id': pair.position1.chain_id,
                'residue1_position': str(pair.position1.residue_number),
                'residue1_type': pair.position1.residue_type,
                'atom1': pair.position1.atom_name,
                'chain2_id': pair.position2.chain_id,
                'residue2_position': str(pair.position2.residue_number),
                'residue2_type': pair.position2.residue_type,
                'atom2': pair.position2.atom_name,
                'chain3_id': pair.position3.chain_id if pair.position3 else "NONE",
                'residue3_position': str(pair.position3.residue_number) if pair.position3 else "NONE",
                'residue3_type': pair.position3.residue_type if pair.position3 else "NONE",
                'atom31': pair.position3.atom_name if pair.position3 else "NONE",
                'atom32': pair.position3.atom_name if pair.position3 else "NONE"
            }
            for pair in self.crosslink_pairs
        ]