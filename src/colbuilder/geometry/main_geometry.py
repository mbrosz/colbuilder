import subprocess
from colbuilder.geometry import (
    crystal, crystalcontacts, chimera, model, system, connect, caps, 
    optimize, mix, mutate, fibril
)

def build_geometry(path_wd=str,pdb_file=None,contact_distance=float,crystalcontacts_file=str,
                   crystalcontacts_optimize=bool,fibril_length=float,pdb_out=str) -> system.System:
    """
    
    build system of models from input
    
    """
    if pdb_file==None: print('Error: No pdb-file given to build collagen microfibril')

    print('-- Read crystallographic symmetry from '+str(pdb_file)+'.pdb --')
    crystal_=crystal.Crystal(pdb_file)

    path_pdb_file=path_wd+'/'+pdb_file
    chimera_=chimera.Chimera(path_pdb_file)

    if pdb_file!=None and contact_distance!=None and crystalcontacts_file=='crystalcontacts':
        system_,crystalcontacts_,connect_=build_from_contactdistance(path_wd=path_wd,pdb_file=pdb_file,contact_distance=contact_distance,
                                            crystalcontacts_file=crystalcontacts_file,chimera=chimera_,crystal=crystal_)

    elif pdb_file!=None and contact_distance==None:
        system_,crystalcontacts_,connect_=build_from_crystalcontacts(crystalcontacts_file=crystalcontacts_file,
                                            crystal=crystal_,crystalcontacts_optimize=crystalcontacts_optimize)
    else:
        print('Error: Please provide either Contact Distance or CrystalContacts and not both.')
        return exit()
    
    print('-- Write '+str(crystalcontacts_.crystalcontacts_file)+' --')
    crystalcontacts_.write_crystalcontacts(system=system_,crystalcontacts_file=crystalcontacts_.crystalcontacts_file)

    print('-- Generate system from '+str(crystalcontacts_.crystalcontacts_file)+' --')
    print('-- Please wait, this may take some time ... --')
    
    chimera_.matrixset(pdb=pdb_file,crystalcontacts=crystalcontacts_.crystalcontacts_file,
                       system_size=system_.get_size(system=system_),fibril_length=fibril_length)   
    
    print('-- Cut system to '+str(fibril_length)+' nm --')
    system_=matrixset_system(system=system_,crystalcontacts_file=crystalcontacts_.crystalcontacts_file)

    print('-- Write '+str(crystalcontacts_file)+'_connect --')
    connect_.write_connect(system=system_,connect_file=crystalcontacts_file+'_connect')

    print('-- Add caps --')
    subprocess.run('rm -r '+path_wd+'/'+system_.get_model(model_id=0.0).type,shell=True)
    subprocess.run('mkdir '+path_wd+'/'+system_.get_model(model_id=0.0).type,shell=True)
    cap_system(system=system_)
    subprocess.run('mv *.caps.pdb '+system_.get_model(model_id=0.0).type,shell=True)

    print('-- Write '+str(pdb_out)+' --')
    system_.write_pdb(pdb_out=pdb_out)

    return system_

def mutate_geometry(path_wd=str,setup_mutate=None,system=system.System,
                    fibril_length=float,pdb_out=str) -> system.System:
    """
    
    built system is mutated according to user-input parameters.
    mutation is random, however constrained to ensure at least one connection

    """
    print('-- Mutate system --')
    mutate_=mutate.Mutate(mutate_ratio=setup_mutate,system=system,fibril_length=fibril_length)
    system_=mutate_.run_mutate(system=system)

    mutate_.write_mutate(system=system_,mutation_file='mutation')  

    print('-- Please wait, this may take some time ... --')
    chimera_=chimera.Chimera(path_wd+'/'+system_.crystal.pdb_file)
    chimera_.swapaa(mutation='mutation',system_type=system_.get_model(model_id=0.0).type)

    system_.write_pdb(pdb_out=pdb_out)

    return system_

def mix_geometry(path_wd=str,crystalcontacts_file=str,crystalcontacts_optimize=None,fibril_length=float,
                 pdb_files=[],setup_mix=None,system=system.System,pdb_out=str) -> system.System:
    """
    
    mix system according to user-input parameters.
    
    """
    mix_setup={ idx.split(':')[0]:idx.split(':')[1] for idx in setup_mix }
    mix_pdb=dict(zip(mix_setup.keys(),pdb_files))

    print('-- Prepare mix '+str(setup_mix)+' --')
    # TODO: crystalcontacts file is stored in system?
    if crystalcontacts_optimize: crystalcontacts_file=system.crystalcontacts.crystalcontacts_file #    crystalcontacts_file+'_opt'

    mix_setup={ idx.split(':')[0]:idx.split(':')[1] for idx in setup_mix }
    mix_pdb=dict(zip(mix_setup.keys(),pdb_files))

    chimera_=chimera.Chimera(path_wd+'/'+pdb_files[0])
    for key in list(mix_pdb.keys())[1:]:
        subprocess.run('mkdir '+path_wd+'/'+key,shell=True)

        print('-- Generate '+str(key)+' system from '+str(mix_pdb[key])+' --')
        chimera_.matrixset(pdb=mix_pdb[key],crystalcontacts=system_.crystalcontacts.crystalcontacts_file,
                    system_size=system.get_size(system=system),fibril_length=fibril_length)
        
        print('-- Add caps --')
        cap_system(system=system)

        subprocess.run('mv *.caps.pdb '+key,shell=True)

    system_=mix.Mix(setup=mix_setup,system=system).add_mix()

    print('-- Mix system --')
    connect.Connect(system=system_).write_connect(system=system_,
                    connect_file=system_.crystalcontacts.crystalcontacts_file.replace('.opt','')+'_connect_mix')

    system_.write_pdb(pdb_out=pdb_out)

    return system_

def build_system(crystal: crystal.Crystal,
                 crystalcontacts: crystalcontacts.CrystalContacts) -> system.System:
    """
    
    build a system of models
    
    """
    system_=system.System(crystal=crystal,crystalcontacts=crystalcontacts)

    transformation=system_.crystalcontacts.read_t_matrix()
    unit_cell={ k:system_.crystal.get_s_matrix(t_matrix=transformation[k]) for k in transformation }

    for key_m in transformation:
        model_=model.Model(id=key_m,transformation=transformation[key_m],unit_cell=unit_cell[key_m],pdb_file=crystal.pdb_file)
        system_.add_model(model=model_)
    return system_

def connect_system(system: system.System) -> tuple[system.System, connect.Connect]:
    """
    
    identify connections within a build system 
    
    """
    connect_=connect.Connect(system=system)
    system_connect=connect_.run_connect(system=system)
    for key_m in system_connect:
        system.get_model(model_id=key_m).add_connect(connect_id=key_m,connect=system_connect[key_m])
    return system,connect_

def cap_system(system: system.System) -> caps.Caps:
    """
    
    cap each model of system
    
    """
    caps_=caps.Caps(system=system)
    for idx in system.get_models():
        caps_.read_residues(pdb_id=int(idx))
        caps_.add_caps(pdb_id=int(idx))
    return caps_

def matrixset_system(system: system.System,crystalcontacts_file=str) -> system.System:
    """
    
    set system after the matrixset command in chimera
    
    """
    contacts=[float(i.split(' ')[1]) for i in open(crystalcontacts_file.replace('_opt','')+'_id.txt','r').readlines()]
    for model in system.get_models():
        if model not in contacts: system.delete_model(model_id=model)
        elif system.get_model(model_id=model).connect!=None:
            for connect in system.get_model(model_id=model).connect:
                if connect not in contacts: system.get_model(model_id=model).delete_connect(connect_id=connect)
    return system

def build_from_contactdistance(path_wd=str,pdb_file=None,contact_distance=float,crystalcontacts_file=str,
                               chimera=chimera.Chimera,crystal=crystal.Crystal) -> tuple[system.System, crystalcontacts.CrystalContacts, connect.Connect]:
    """

    generate system of models based on contact distance and PDB-file
    
    """
    path_pdb_file=path_wd+'/'+pdb_file

    print('-- Get CrystalContacts for contact distance '+str(contact_distance)+' A --')
    print('-- Please wait, this may take some time ... --')
    chimera.matrixget(pdb=path_pdb_file,contact_distance=contact_distance,
                       crystalcontacts=crystalcontacts_file)

    print('-- Write '+str(crystalcontacts_file)+' --')
    crystalcontacts_=crystalcontacts.CrystalContacts(crystalcontacts_file)

    print('-- Build system --')
    system_=build_system(crystal=crystal,crystalcontacts=crystalcontacts_)
        
    print('-- Connect system --')
    system_,connect_=connect_system(system=system_)

    print('-- Optimize system --')
    system_=optimize.Optimizer(system=system_).run_optimize(system=system_,connect=connect_)
    system_,connect_=connect_system(system=system_)

    crystalcontacts_.crystalcontacts_file=crystalcontacts_.crystalcontacts_file+'_opt'

    return system_,crystalcontacts_,connect_

def build_from_crystalcontacts(crystalcontacts_file=str,crystal=crystal.Crystal,
                               crystalcontacts_optimize=bool) -> tuple[system.System, crystalcontacts.CrystalContacts, connect.Connect]:
    """
    
    generate system of models based on CrystalContacts and PDB-file 

    """
    crystalcontacts_=crystalcontacts.CrystalContacts(crystalcontacts_file)
    
    print('-- Build system --')
    system_=build_system(crystal=crystal,crystalcontacts=crystalcontacts_)

    print('-- Connect system --')
    system_,connect_=connect_system(system=system_)
   
    if crystalcontacts_optimize:
        print('-- Optimize system --')
        system_=optimize.Optimizer(system=system_).run_optimize(system=system_,connect=connect_)
        system_,connect_=connect_system(system=system_)

        crystalcontacts_.crystalcontacts_file=crystalcontacts_.crystalcontacts_file+'_opt'

    return system_,crystalcontacts_,connect_

def build_fibril(pdb_file=None) -> system.System:
    """"
    
    build a system from colbuilder 1.0 fibril
    
    """
    system_=system.System(pdb_fibril=pdb_file)

    print('-- Read fibril '+str(pdb_file)+' from colbuilder 1.0 --')
    fibril_=fibril.Fibril(system=system_,pdb_file=pdb_file)

    print('-- Separate system --')
    fibril_.seperate_system(pdb_file=pdb_file)

    print('-- Build system --')
    system_=fibril_.build_system(system=system_)

    print('-- Connect system --')
    system_,connect_=connect_system(system=system_)

    print('-- Write fibril_connect --')
    fibril_.write_connect(system=system_,connect_file='fibril_connect')

    return system_