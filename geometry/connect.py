import numpy as np
from itertools import product,combinations

def merge_pairs(pairs=None):
    """
    
    Merges pairs of connected models
    
    """
    #print(pairs)
    for ref_pair,pair in combinations(pairs,2):
        if ref_pair==pairs[pair][1]: pairs[ref_pair].append(pair)
        elif pairs[ref_pair][1]==pair: pairs[ref_pair].append(pairs[pair][1])
    return pairs

def find_model_connect(crystal=None,crystal_contacts=None,model_contact=None):  
    """
    
    find_model_connect checks if models are connected by computing the distance
    between translated crosslinks.
    
    """
    if model_contact==None: model_contact=crystal_contacts.read_t_matrix()
    connect=Connect(crystal.pdb_file)

    model_coords={ key: connect.translate_model(translate_vector=model_contact[key]) for key in model_contact}
    model_pairs={ key: [] for key in model_coords }
    for ref_model,model in product(model_coords,repeat=2):
        if ref_model!=model and connect.get_model_connect(ref_model=model_coords[ref_model],model=model_coords[model])==True: 
            model_pairs[ref_model]=[ref_model,model]
    print(model_pairs)
    return merge_pairs(model_pairs)



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

    def read_crosslink(self,pdb=None):
        """
        
        Reads closest connection between crosslinks from pdb file 
        
        """
        if pdb==None: pdb=self.pdb_file
        self.pdb_model={ }
        with open(self.pdb_file+'.pdb') as f:
            for l in f:
                if l[17:20]=='LYX' and l[13:16]=='C13' or l[17:20]=='LY3' and l[13:15]=='CG': 
                    self.pdb_model[int(l[4:10])]={ k:[] for k in ['resname','chain_id','position'] }
                    self.pdb_model[int(l[4:10])]['resname']=l[17:20]
                    self.pdb_model[int(l[4:10])]['chain_id']=l[21:22]
                    self.pdb_model[int(l[4:10])]['position']=[float(l[29:38]),float(l[38:46]),float(l[46:56])]
                elif l[17:20]=='L4Y' and l[13:15]=='CE' or l[17:20]=='L5Y' and l[13:15]=='NZ': 
                    self.pdb_model[int(l[4:10])]={ k:[] for k in ['resname','chain_id','position'] }
                    self.pdb_model[int(l[4:10])]['resname']=l[17:20]
                    self.pdb_model[int(l[4:10])]['chain_id']=l[21:22]
                    self.pdb_model[int(l[4:10])]['position']=[float(l[29:38]),float(l[38:46]),float(l[46:56])]
        f.close()
        return self.pdb_model
    
    def translate_model(self,pdb_file=None,translate_vector=[]):
        """
        
        Translates one model according to translation vector
        obtained from crystal & contact information 

        --

        output : dict with translated crosslinks of model
        
        """
        if translate_vector==[]: print('Error: No translate vector given to translate crosslink')
        if pdb_file==None: pdb_model=self.read_crosslink(pdb=pdb_file)
        return { c: self.translate_crosslink(translate_vector,pdb_model[c]['position']) for c in pdb_model }
    
    def translate_crosslink(self,translate_vector=[],crosslink=[]):
        """
        
        Translates one crosslink of one model according to translation vector
        obtained from crystal & contact information

        --

        output  :  cartesian coordinates of translated crosslink [x,y,z]

        """
        if translate_vector==[]: print('Error: No translate vector given to translate crosslink')
        if crosslink==[]: print('Error: No crosslink given to translate')
        return np.add(translate_vector,crosslink)
    
    def get_model_connect(self,ref_model=None,model=None,cut_off=2.0):
        """
        
        Calculates distance between two models 
        if distance below cut_off (2.0 A) keep models

        --

        m = model
        c = crosslink of model
        cut_off = 2.0 A

        """
        for ref_c,c in product(ref_model,model):
            if np.linalg.norm(ref_model[ref_c]-model[c])<cut_off:  return True

    def run_model_connect(self,crystal_contacts=None,crystal=None,model_id=None):
        """
        
          
        Translates model according to translate vector and returns ids if
        models are closer than cut-off

        TODO: 2. connect one model with all the other models


        --


        
        """
        if model_id==None: 
            print('Crystal Contacts Connection from Chimera')
            return find_model_connect(crystal=crystal,crystal_contacts=crystal_contacts)

    
