from collections import OrderedDict

import numpy as np

from . import space_groups as sgs

# define all symmetry operations: Mx=x'
# the inversion operator
inversion = np.array([[-1.,0.,0.],[0.,-1.,0.],[0.,0.,-1.]])
# three axial mirrors 
mirror_x = np.array([[-1,0,0],[0,1,0],[0,0,1]])
mirror_y = np.array([[1,0,0],[0,-1,0],[0,0,1]])
mirror_z = np.array([[1,0,0],[0,1,0],[0,0,-1]])
# six diagonal mirrors 
mirror_x_y = np.array([[0,-1,0],[-1,0,0],[0,0,1]])
mirror_y_z = np.array([[1,0,0],[0,0,-1],[0,-1,0]])
mirror_z_x = np.array([[0,0,-1],[0,1,0],[-1,0,0]])
mirror_nx_y = np.array([[0,1,0],[1,0,0],[0,0,1]])
mirror_ny_z = np.array([[1,0,0],[0,0,1],[0,1,0]])
mirror_nz_x = np.array([[0,0,1],[0,1,0],[1,0,0]])

# enumerate valid symmetry operations for each point group:
# note that the symmetrization algorithm retains points
# with higher h values, and then (for equal h), higher k values,
# and then (for equal h and k), higher l values.
symmetry_operations = OrderedDict.fromkeys(sgs.crystal_point_groups)

symmetry_operations['1'] = [] 
symmetry_operations['-1'] = [inversion] 
symmetry_operations['m-3m'] = [\
    mirror_x,mirror_y,mirror_z,\
    mirror_x_y,mirror_y_z,mirror_z_x,\
    mirror_nx_y,mirror_ny_z,mirror_nz_x\
    # TODO: add the 3-fold x+y+z-rotoinversion
    ]
symmetry_operations['6/mmm'] = [\
    mirror_z, mirror_x_y, mirror_nx_y,\
    # TODO: add the 6-fold z-rotation
    ]


