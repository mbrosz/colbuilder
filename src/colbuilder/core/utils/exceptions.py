"""
Colbuilder Exceptions Module

This module defines the exception hierarchy for the Colbuilder system.
It provides structured error handling with detailed information about
errors, their severity, and suggestions for resolution.

Key Components:
    - ColbuilderError: Base exception class
    - ErrorSeverity: Error severity levels
    - ErrorCategory: Error categories
    - Specific error types for each category

Example Usage:
    try:
        raise GeometryGenerationError(
            message="Failed to generate crystal contacts",
            error_code="GEO_ERR_002"
        )
    except ColbuilderError as e:
        e.log_error()
"""

from enum import Enum, auto
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from pathlib import Path
import json
import traceback

from .logger import setup_logger
from .error_codes import (
    SEQUENCE_ERRORS,
    GEOMETRY_ERRORS,
    TOPOLOGY_ERRORS,
    CONFIGURATION_ERRORS,
    SYSTEM_ERRORS
)

LOG = setup_logger(__name__)

class ErrorSeverity(Enum):
    """
    Enumeration of error severity levels.
    
    Levels:
        INFO: Informational message
        WARNING: Warning that doesn't prevent operation
        ERROR: Error that prevents specific operation
        CRITICAL: Error that prevents system operation
    """
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()

class ErrorCategory(Enum):
    """
    Enumeration of error categories.
    
    Categories:
        SEQUENCE: Sequence generation errors
        GEOMETRY: Geometry generation errors
        TOPOLOGY: Topology generation errors
        CONFIGURATION: Configuration errors
        SYSTEM: System-level errors
    """
    SEQUENCE = auto()
    GEOMETRY = auto()
    TOPOLOGY = auto()
    CONFIGURATION = auto()
    SYSTEM = auto()

@dataclass
class ColbuilderErrorDetail:
    """
    Detailed information about an error.
    
    Attributes:
        message: Main error message
        category: Error category
        severity: Error severity level
        technical_details: Technical error information
        suggestions: List of suggested solutions
        error_code: Unique error identifier
        affected_files: List of files involved
        docs_url: Link to relevant documentation
        context: Additional contextual information
    """
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    technical_details: Optional[str] = None
    suggestions: Optional[List[str]] = None
    error_code: Optional[str] = None
    affected_files: Optional[List[Path]] = None
    docs_url: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class ColbuilderError(Exception):
    """
    Base class for Colbuilder exceptions.
    
    This class provides common functionality for all Colbuilder errors,
    including logging, serialization, and error details.
    
    Attributes:
        detail: Detailed error information
        original_error: Original exception if this wraps another error
    """
    
    def __init__(
        self, 
        detail: ColbuilderErrorDetail,
        original_error: Optional[Exception] = None
    ) -> None:
        """
        Initialize the error.
        
        Args:
            detail: Detailed error information
            original_error: Optional original exception
        """
        self.detail = detail
        self.original_error = original_error
        super().__init__(detail.message)
        
    def log_error(self) -> None:
        """
        Log the error with appropriate severity level.
        
        This method logs the error message, technical details,
        suggestions, and affected files using the appropriate
        log level based on error severity.
        """
        log_level = {
            ErrorSeverity.INFO: LOG.info,
            ErrorSeverity.WARNING: LOG.warning,
            ErrorSeverity.ERROR: LOG.error,
            ErrorSeverity.CRITICAL: LOG.critical
        }.get(self.detail.severity, LOG.error)

        # Log main error message
        log_level(f"[{self.detail.category.name}] {self.detail.message}")

        # Log technical details if available
        if self.detail.technical_details:
            LOG.debug(f"Technical details: {self.detail.technical_details}")

        # Log original error traceback if available
        if self.original_error:
            LOG.debug("Original error traceback:")
            LOG.debug(traceback.format_exception(
                type(self.original_error),
                self.original_error,
                self.original_error.__traceback__
            ))

        # Log suggestions
        if self.detail.suggestions:
            LOG.info("Suggestions for resolution:")
            for suggestion in self.detail.suggestions:
                LOG.info(f"- {suggestion}")

        # Log affected files
        if self.detail.affected_files:
            LOG.debug("Affected files:")
            for file in self.detail.affected_files:
                LOG.debug(f"- {file}")

        # Log documentation link
        if self.detail.docs_url:
            LOG.info(f"For more information, visit: {self.detail.docs_url}")
            
        # Log context if available
        if self.detail.context:
            LOG.debug("Error context:")
            for key, value in self.detail.context.items():
                LOG.debug(f"  {key}: {value}")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert error to a dictionary suitable for API responses.
        
        Returns:
            Dict containing error information
        """
        error_dict = {
            "message": self.detail.message,
            "category": self.detail.category.name,
            "severity": self.detail.severity.name,
            "error_code": self.detail.error_code
        }
        
        if self.detail.technical_details:
            error_dict["technical_details"] = self.detail.technical_details
            
        if self.detail.suggestions:
            error_dict["suggestions"] = self.detail.suggestions
            
        if self.detail.affected_files:
            error_dict["affected_files"] = [str(f) for f in self.detail.affected_files]
            
        if self.detail.docs_url:
            error_dict["documentation_url"] = self.detail.docs_url
            
        if self.detail.context:
            error_dict["context"] = self.detail.context
            
        return error_dict

    def to_json(self) -> str:
        """
        Convert error to JSON string.
        
        Returns:
            JSON string representation of the error
        """
        return json.dumps(self.to_dict(), indent=2)

class SystemError(ColbuilderError):
    """
    Exception raised for system-related errors.
    
    These are typically critical errors that affect system operation.
    """
    
    @classmethod
    def get_error_info(cls, error_code: str):
        """Get error information for a system error code."""
        return SYSTEM_ERRORS[error_code]
    
    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        error_code: str = "SYS_ERR_001",
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        error_info = SYSTEM_ERRORS[error_code]
        detail = ColbuilderErrorDetail(
            message=message,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            technical_details=str(original_error) if original_error else None,
            suggestions=error_info.suggestions,
            error_code=error_info.code,
            docs_url=error_info.docs_url,
            context=context
        )
        super().__init__(detail, original_error)

class ConfigurationError(ColbuilderError):
    """
    Exception raised for configuration-related errors.
    
    These errors occur during system configuration and setup.
    """
    
    @classmethod
    def get_error_info(cls, error_code: str):
        """Get error information for a configuration error code."""
        return CONFIGURATION_ERRORS[error_code]
    
    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        error_code: str = "CFG_ERR_001",
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        error_info = CONFIGURATION_ERRORS[error_code]
        detail = ColbuilderErrorDetail(
            message=message,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.ERROR,
            technical_details=str(original_error) if original_error else None,
            suggestions=error_info.suggestions,
            error_code=error_info.code,
            docs_url=error_info.docs_url,
            context=context
        )
        super().__init__(detail, original_error)

class SequenceGenerationError(ColbuilderError):
    """
    Exception raised for errors during sequence generation.
    
    These errors occur during the sequence processing step.
    """
    
    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        error_code: str = "SEQ_ERR_001",
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        error_info = SEQUENCE_ERRORS[error_code]
        detail = ColbuilderErrorDetail(
            message=message or error_info.message,
            category=ErrorCategory.SEQUENCE,
            severity=ErrorSeverity.ERROR,
            technical_details=str(original_error) if original_error else None,
            suggestions=error_info.suggestions,
            error_code=error_info.code,
            docs_url=error_info.docs_url,
            context=context
        )
        super().__init__(detail, original_error)

class GeometryGenerationError(ColbuilderError):
    """
    Exception raised for errors during geometry generation.
    
    These errors occur during the geometry processing step.
    """
    
    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        error_code: str = "GEO_ERR_001",
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        error_info = GEOMETRY_ERRORS[error_code]
        detail = ColbuilderErrorDetail(
            message=message or error_info.message,
            category=ErrorCategory.GEOMETRY,
            severity=ErrorSeverity.ERROR,
            technical_details=str(original_error) if original_error else None,
            suggestions=error_info.suggestions,
            error_code=error_info.code,
            docs_url=error_info.docs_url,
            context=context
        )
        super().__init__(detail, original_error)

class TopologyGenerationError(ColbuilderError):
    """
    Exception raised for errors during topology generation.
    
    These errors occur during the topology processing step.
    """
    
    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        error_code: str = "TOP_ERR_001",
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        error_info = TOPOLOGY_ERRORS[error_code]
        detail = ColbuilderErrorDetail(
            message=message or error_info.message,
            category=ErrorCategory.TOPOLOGY,
            severity=ErrorSeverity.ERROR,
            technical_details=str(original_error) if original_error else None,
            suggestions=error_info.suggestions,
            error_code=error_info.code,
            docs_url=error_info.docs_url,
            context=context
        )
        super().__init__(detail, original_error)