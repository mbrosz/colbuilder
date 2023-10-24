import subprocess
import os
from colbuilder.geometry import system
from colbuilder.topology import amber, martini, itp

def clean_directory(model_id=None):
    """
    
    delete files that are not needed anymore
    
    """
    subprocess.run('rm topol.top && rm '+str(int(model_id))+'.*.CG.pdb && rm col_'+str(int(model_id))+'.*.itp && rm \#*',shell=True)

def build_martini3(system: system.System,force_field=None,topology_file=None,go_epsilon=float) -> martini.Martini:
    """
    
    build martini 3 force field topology
    
    """
    order,map=[],[]
    cnt_model=0
    connect_size=system.get_connect_size()
    martini_=martini.Martini(system=system,force_field=force_field)
    for model_id in system.get_models():
        if system.get_model(model_id=model_id).connect!=None:
            print('-- Build microfibrillar topology: '+str(int(100 * cnt_model / connect_size))+' %' )
            itp_=itp.Itp(system=system,model_id=model_id)

            for connect_id in system.get_model(model_id=model_id).connect:

                pdb=martini_.read_pdb(pdb_id=connect_id)
                trans_pdb=martini_.translate_pdb(pdb=pdb)
                cap_pdb,cter,nter=martini_.cap_pdb(pdb=trans_pdb)
                order,map=martini_.set_pdb(pdb=cap_pdb)

                martini_.write_pdb(pdb=order,file='tmp.pdb')  
                martini_.write_pdb(pdb=map,file='map.pdb')     
                
                subprocess.run(
                'conda run -n colbuilder martinize2 -f tmp.pdb -sep -merge A,B,C -scfix '+
                '-collagen -from amber99 -o topol.top -bonds-fudge 1.4 -p backbone '+
                '-ff '+str(force_field)+'00C -x '+str(int(model_id))+'.'+str(int(connect_id))+'.CG.pdb '+
                '-nter '+str(nter)+' -cter '+str(cter)+' -govs-include -govs-moltype '+
                'col_'+str(int(model_id))+'.'+str(int(connect_id)),shell=True,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

                subprocess.run(
                './contact_map ../map.pdb > ../map.out',cwd=os.getcwd()+'/contactmap/',shell=True,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

                subprocess.run(
                'python create_goVirt.py -s '+str(int(model_id))+'.'+str(int(connect_id))+'.CG.pdb '+
                '-f map.out --moltype col_'+str(int(model_id))+'.'+str(int(connect_id))+' --go_eps '+str(go_epsilon),
                shell=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)      
            
            martini_.merge_pdbs(model_id=model_id,cnt_model=cnt_model)
            
            itp_.read_model(model_id=model_id)
            itp_.go_to_pairs(model_id=model_id)
            itp_.make_topology(model_id=model_id,cnt_model=cnt_model)

            #clean_directory(model_id=model_id)
            cnt_model+=1

    system_pdb=martini_.get_system_pdb(size=cnt_model)
    martini_.write_pdb(pdb=system_pdb,file='collagen_fibril_martini3.pdb')
    martini_.write_system_topology(size=cnt_model)

    return martini_
                                 
def build_amber99(system: system.System,force_field=None,topology_file=None) -> amber.Amber:
    """"
    
    builder amber99 force field topology
    
    """
    ff=force_field+'sb-star-ildnp'
    amber_=amber.Amber(system=system,ff=ff)
    try:
        subprocess.run('cp '+str(ff)+'.ff/residuetypes.dat .',shell=True)
        subprocess.run('cp '+str(ff)+'.ff/specbond.dat .',shell=True)
    except:
        print('Error: No force field. Get '+str(ff)+'-force field from colbuilder 1.0.')
        exit()

    print('-- Run pdb2gmx with GROMACS using '+str(ff)+'.ff --')
    for model in system.get_models():
        type_=amber_.merge_pdbs(connect_id=model)

        if type_!=None and os.path.exists(os.getcwd()+'/'+str(type_)+'/'+str(int(model))+'.merge.pdb'): 

            subprocess.run(
            'gmx pdb2gmx -f '+str(type_)+"/"+str(int(model))+'.merge.pdb -ignh '+'-merge all '+
            '-ff '+str(ff)+' -water tip3p -p col_'+str(int(model))+'.top '+
            '-o col_'+str(int(model))+'.gro '+'-i posre_'+str(int(model))+'.itp',shell=True,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

            amber_.write_itp(itp_file='col_'+str(int(model))+'.top')

    return amber_

def build_topology(system: system.System,force_field=None,top_file=None,gro_file=None,
                   go_epsilon=float) -> system.System:
    """
    
    builds topology of a system
    
    """
    if force_field=='amber99':
        ff=force_field+'sb-star-ildnp'
        print('-- Build topology based on '+str(ff)+'.ff --')

        amber_=build_amber99(system=system,force_field=force_field)
        amber_.write_topology(system=system,topology_file=top_file)
        amber_.write_gro(system=system,gro_file=gro_file)

        print('-- '+str(ff)+ ' topology generated --')
    
    if force_field=='martini3':
        ff=force_field+'C'
        print('-- Build topology based on '+str(ff)+' --')
        martini_=build_martini3(system=system,force_field=force_field,go_epsilon=go_epsilon)

        print('-- '+str(ff)+ ' topology generated --')
    
    if force_field==None:
        print('Error: Please specifify force field to generate topology, e.g., martini3 or amber99')

    return system