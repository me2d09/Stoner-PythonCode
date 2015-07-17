from __future__ import print_function
from Stoner import Data
from numpy.random import normal
from numpy import linspace,meshgrid,column_stack
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.cm as cmap
import matplotlib.pyplot as plt



def plane(coord,a,b,c): # Function to define a plane
    return c-(coord[0]*a+coord[1]*b)

coeefs=[1,-0.5,-1]
col=linspace(-10,10,6)
X,Y=meshgrid(col,col)
Z=plane((X,Y),*coeefs)+normal(size=X.shape,scale=7.0)
d=Data(column_stack((X.ravel(),Y.ravel(),Z.ravel())),filename="Fitting a Plane",setas="xyz")

d.column_headers=["X","Y","Z"]
d.figure(projection="3d")
d.plot_xyz(plotter="scatter",c=cmap.jet(d.z))

d.curve_fit(plane,[0,1],2,result=True)

d.setas="xyz"
d.plot_xyz(linewidth=0,cmap=cmap.jet)

txt="$z=c-ax+by$\n"
txt+="\n".join([d.format("plane:{}".format(k),latex=True) for k in ["a","b","c"]])

ax=plt.gca(projection="3d")    
ax.text(15,5,-50,txt)
d.draw()

