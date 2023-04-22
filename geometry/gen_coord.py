import numpy as np
import subprocess

class Crystal:
    """
    
    Reads crystal information, determines symmetric translation-rotation matrix and
    to converts between unit-cell shift and transformation matrix for fine-tuning.
    
    --
    
    input:  -f     crystal contacts file
   
    output: -o     symmetrized crystal contacts file      
        
    """
    def __init__(self,contact=[],pdb=None):
        self.file_contact=contact
        self.pdb_file=pdb
        self.contacts=[]
        self.crystal={k:None for k in ['a','b','c','alpha','beta','gamma']}
        self.r_matrix=[]
        self.t_matrix={ }
        self.s_matrix={ }
        self.plane=[]
    
    def read_contacts(self):
        """
        
        Read crystal contacts from chimera output-file
        
        """
        self.contacts=open(self.file_contact+'.txt','r').readlines()
    
    def read_crystal(self):
        """
        
        Read crystallographic information from pdb-file
        
        """
        self.crystal=dict(zip(self.crystal,open(self.pdb_file+'.pdb').readline().split()[1:]))

    def read_spacegroup(self):
        """
        
        Read space-group from crystallographic information from pdb-file
        
        """
        return int(open(self.pdb_file+'.pdb').readline().split()[-2])

    def read_r_matrix(self):
        """
        
        Compute rotation matrix R based on crystalgraphic information & space group 
        
        """
        self.read_crystal()
        if self.read_spacegroup()==1:
            ax,ay,az=float(self.crystal['a']),0,0        
            bx=float(self.crystal['b']) * np.cos(np.deg2rad(float(self.crystal['gamma'])))
            by=float(self.crystal['b']) * np.sin(np.deg2rad(float(self.crystal['gamma'])))
            bz=0        
            cx=float(self.crystal['c']) * np.cos(np.deg2rad(float(self.crystal['beta'])))
            cy=float(self.crystal['c']) * ( np.cos(np.deg2rad(float(self.crystal['alpha']))) 
                                      - np.cos(np.deg2rad(float(self.crystal['beta']))) 
                                      * np.cos(np.deg2rad(float(self.crystal['gamma'])))  
                                      / np.sin(np.deg2rad(float(self.crystal['gamma']))) ) 
            cz=np.sqrt( np.power(float(self.crystal['c']),2) - 
                   np.power(cx,2) - np.power(cy,2) )
            self.r_matrix=np.array([[ax,bx,cx],[ay,by,cy],[az,bz,cz]])
        return self.r_matrix
    
    def read_t_matrix(self):
        """
        
        Read transformation matrix T from contact file 
        
        """
        self.read_contacts()
        for idx in range(0,len(self.contacts),4):
            self.t_matrix[float(self.contacts[idx].split(' ')[1])]=[   
                float(self.contacts[idx+1].split(' ')[-1]),
                float(self.contacts[idx+2].split(' ')[-1]),
                float(self.contacts[idx+3].split(' ')[-1])]
        return self.t_matrix
    
    def get_s_matrix(self):
        """
        
        Get shift matrix S from transformation matrix T using rotation matrix R: S = T \ R
        
        """
        self.read_t_matrix()
        self.read_r_matrix()
        for key in self.t_matrix.keys(): self.s_matrix[key]=np.linalg.solve(self.r_matrix,self.t_matrix[key]).astype(int)
        return self.s_matrix
    
    def get_t_matrix(self,s_matrix):
        """
        
        Get transformation matrix T from shift matrix S using rotation matrix R: T = S x R
        
        """
        self.read_r_matrix()  
        if s_matrix!=None:
            self.s_matrix=s_matrix
        for key in self.s_matrix.keys(): self.t_matrix[key]=np.dot(self.r_matrix,self.s_matrix[key])
        return self.t_matrix

        
    def write_contacts(self):
        """
        
        Writes updated crystal contacts for chimera input-file: chimera outputfile_sym.txt
        
        """
        with open(self.file_contact+'_sym.txt','w') as f:
            for key,value in self.t_matrix.items():
                f.write(str(key)+'\n')
                f.write('         1 0 0 %s\n' % (round(value[0],3)))
                f.write('         1 0 0 %s\n' % (round(value[1],3)))
                f.write('         1 0 0 %s\n\n' % (round(value[2],3)))
        f.close()

    def get_plane(self,z_p):
        """
        
        Get (x,y) meshgrid at specific z-pos from shift matrix S 
        
        """
        return np.array([[c[0],c[1],z_p] for c in self.s_matrix.values() if c[2]==z_p])
    
    def extend_plane(self,z_p=0,d_x=0,d_y=0):
        """
        
        Update mesh-grid (x,y) at specific z-pos by adding nodes or filling up the meshgrid 
        from -i_max-d_ij to i_max+d_ij with i,j=(x,y) with i!=j
        
        """        
        x_max=np.max(self.get_plane(z_p)[:,0])
        y_max=np.max(self.get_plane(z_p)[:,1])       
        x_mesh=np.linspace(-x_max-d_x,x_max+d_x,2*(x_max+d_x)+1)
        y_mesh=np.linspace(-y_max-d_y,y_max+d_y,2*(y_max+d_y)+1)        
        return np.transpose(np.vstack(list(map(np.ravel,np.meshgrid(x_mesh,y_mesh,z_p)))))
    
    def get_nodes(self,z_p,d_x,d_y):
        """

        Compare nodes before & after plane extension step and update shift matrix S

        Symmetric difference between sets: self.get_plane ^ self.extend_plane

        Append extended models && point-mirror models to shift matrix dictonary 

        """
        for node in (set(map(tuple,self.get_plane(z_p)))^set(map(tuple,self.extend_plane(z_p,d_x,d_y)))):
            self.plane.append(node)
        return self.plane
    
    def set_meshgrid(self):
        """
        
        Set up new meshgrid with more nodes to fill-up gaps at each z-pos
        
        """
        self.s_matrix=self.get_s_matrix()
        d_x,d_y,z_p=0,1,np.max(list(self.s_matrix.values()),axis=0)[2]
        return self.get_nodes(z_p,d_x,d_y)


class Fibril:
    """
    
    Generate collagen microfibril with the "crystal contacts" command from UCSF 
    Chimera. Chimera needs to be installed beforehand from:
    
    https://www.cgl.ucsf.edu/chimera/download.html
    
    Important: Install Chimera (python 2.7 based) and not ChimeraX (python 3.)
    
    ---
    
    input:  -f     pdb-file with single triple helix
            -nocc  number of crystal contacts
           
    output: -cc    crystal-contacts.txt      

    ---

    matrixget:  Calls Chimera via Python 2.7 script from terminal    
    
                -> Gets transformation matrices based on crystal contacts 
                   (e.g. no_cc = 60) to setup skeleton of microfibril
                
    matrixset:  Call Chimera via Python 2.7 script frpm terminal    
    
                -> set pdb-models based on updated, symmetriyzed transformation
                   matrices.
    
    
    """
    def __init__(self,path_geo,path,file_name,contact_distance,cut_off):
        self.path_geo=path_geo
        self.path=path
        self.pdb=file_name
        self.d_contact=contact_distance
        self.contacts='crystal_contacts'
        self.sym_contacts=''
        self.cut_off=cut_off
        self.nu_fibril=0   
    
    def matrixget(self):
        return subprocess.run(
            'chimera --nogui --silent --script '+'"'+str(self.path_geo)+
            'matrixget.py '+str(self.path)+' '+str(self.pdb)+'.pdb '+
            str(self.d_contact)+' '+str(self.contacts)+'"',shell=True)        
    
    def matrixset(self):
        return subprocess.run(
            'chimera --nogui --silent --script '+'"'+str(self.path_geo)+
            'matrixset.py '+str(self.path)+' '+str(self.pdb)+'.pdb '+
            ' '+str(self.sym_contacts)+' '+str(self.nu_fibril)+' '+
            str(self.cut_off)+'"',shell=True)
    