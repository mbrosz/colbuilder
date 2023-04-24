import numpy as np
import logging
from itertools import product

def find_model_connect(crystal=None,crystalcontacts_coords=None,s_model=None):
    """
    
    compares added model to connected model pairs by computing the distances between translated crosslinks.

    --

    output  :   True if added model is connected
    
    """
    connect=Connect(crystal.pdb_file)    
    t_model=crystal.get_t_matrix(s_matrix=s_model)
    model_coords={ 'add': connect.translate_model(translate_vector=t_model) }
    for ref_model in crystalcontacts_coords:
        if connect.get_model_connect(ref_model=crystalcontacts_coords[ref_model],model=model_coords['add'])==True:
            return True

def find_contact_connect(crystal=None,crystalcontacts_coords=None):  
    """
    
    generate connected model pairs by computing the distances between translated crosslinks.

    --

    output  :   list of pair-wise connected models
    
    """
    connect=Connect(crystal.pdb_file)    
    contact_pairs={ key: None for key in crystalcontacts_coords }
    for ref_model,model in product(crystalcontacts_coords,repeat=2):
        if ref_model!=model and connect.get_model_connect(ref_model=crystalcontacts_coords[ref_model],model=crystalcontacts_coords[model])==True: 
            contact_pairs[ref_model]=model
    return merge_pairs(contact_pairs)    
    

def merge_pairs(pairs=None):
    """
    
    merges pairs of connected models to reproduce total connectivity of microfibril

    --

    output  :   connections between all models 
    
    """
    model_connect={ key: [key] for key in pairs }
    for ref_key,key in product(pairs,repeat=2):
        if key==ref_key or pairs[key]==None or pairs[ref_key]==None: continue
        elif ref_key==pairs[key] or key==pairs[ref_key] or pairs[key]==pairs[ref_key]: model_connect[ref_key].append(key)
    print(model_connect)
    return model_connect

class Connect:
    """
    
    Select cartesian coordinates from the initial coordinate file
    Allows translation of initial coordinates with regard to translation matrix

    --

    -input      :  *.pdb -> coordinate file 

    -output     : ?
    
    """
    def __init__(self,pdb=str):
        self.pdb_file=pdb

    def read_crosslink(self,pdb_file=None):
        """
        
        Reads closest connection between crosslinks from pdb file 
        
        """
        if pdb_file==None: pdb_file=self.pdb_file
        try:
            self.pdb_crosslink={ }
            with open(pdb_file+'.pdb') as f:
                for l in f:
                    # problem may arise here: check syntax in pdb file
                    if l[17:20]=='LYX' and l[13:16]=='C13' or l[17:20]=='LY3' and l[13:15]=='CG': 
                        self.pdb_crosslink[int(l[6:10])]={ k:[] for k in ['resname','chain_id','position'] }
                        self.pdb_crosslink[int(l[6:10])]['resname']=l[17:20]
                        self.pdb_crosslink[int(l[6:10])]['chain_id']=l[21:22]
                        self.pdb_crosslink[int(l[6:10])]['position']=[float(l[29:38]),float(l[38:46]),float(l[46:56])]
                    elif l[17:20]=='L4Y' and l[13:15]=='CE' or l[17:20]=='L5Y' and l[13:15]=='NZ': 
                        self.pdb_crosslink[int(l[6:10])]={ k:[] for k in ['resname','chain_id','position'] }
                        self.pdb_crosslink[int(l[6:10])]['resname']=l[17:20]
                        self.pdb_crosslink[int(l[6:10])]['chain_id']=l[21:22]
                        self.pdb_crosslink[int(l[6:10])]['position']=[float(l[29:38]),float(l[38:46]),float(l[46:56])]
            f.close()
        except:
            logging.Error('Error: Can not read pdb-file. check the exact syntax of the line please.\nPotential Error might be : int('+str(l[6:10])+')')
        
        return self.pdb_crosslink
    
    def translate_model(self,pdb_file=None,translate_vector=[]):
        """
        
        Translates one model according to translation vector
        obtained from crystal & contact information 

        --

        output : dict with translated crosslinks of model
        
        """
        try:
            if pdb_file==None: pdb_crosslink=self.read_crosslink(pdb_file=pdb_file)
            return { c: self.translate_crosslink(translate_vector=translate_vector,crosslink=self.pdb_crosslink[c]['position']) for c in pdb_crosslink }
        except:
            logging.error('Error: No translate vector given to translate crosslink')
    
    def translate_crosslink(self,translate_vector=[],crosslink=[]):
        """
        
        Translates one crosslink of one model according to translation vector
        obtained from crystal & contact information

        --

        output  :  cartesian coordinates of translated crosslink [x,y,z]

        """
        try:
            return np.add(translate_vector,crosslink)
        except:
            logging.error('Error: No translate vector or crosslink coordinates given')
    
    def get_model_connect(self,ref_model=None,model=None,cut_off=2.0):
        """
        
        Calculates distance between two models 
        if distance below cut_off (2.0 A) keep models

        --

        c = crosslink of model
        cut_off = 2.0 A

        """
        for ref_c,c in product(ref_model,model):
            if np.linalg.norm(ref_model[ref_c]-model[c])<cut_off:  return True

    def run_connect(self,system=None,s_model=None):
        """
        
        Translates each modelof system according to translation vector and returns ids 
        if models are closer than cut-off, and therefore connected
        
        """
        t_crystalcontacts={ system.get_model(model_id=id).model_id : system.get_model(model_id=id).model_t for id in range(system.len_system()) }
        crystalcontacts_coords={ key: self.translate_model(translate_vector=t_crystalcontacts[key]) for key in t_crystalcontacts}

        if s_model==None: # Gets all connections within crystal contacts
            return find_contact_connect(crystal=system.crystal,crystalcontacts_coords=crystalcontacts_coords)
        
        if s_model!=None: # check if added model is connected
            return find_model_connect(crystal=system.crystal,crystalcontacts_coords=crystalcontacts_coords,s_model=s_model)