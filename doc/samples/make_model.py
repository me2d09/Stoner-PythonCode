#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Demo of the make_model decorator"""

from numpy import linspace
from numpy.random import normal
from Stoner import Data
from Stoner.Fit import make_model

#Make our model
@make_model
def simple_model(x,m,c):
    """A straight line"""
    return x*m+c

#Add a function to guess parameters
@simple_model.guesser
def guess_vals(y,x=None):
    """Should guess parameter values really!"""
    return (1.0,1.0) #return one value per parameter

#Create some x,y data
x=linspace(0,10,101)
y=4.5*x-2.3+normal(scale=0.4,size=len(x))

#Make The Data object
d=Data(x,y,setas="xy",column_headers=["X","Y"])

#Do the fit
d.lmfit(simple_model,result=True)

#Plot the result
d.setas="xyy"
d.plot(fmt=["r+","b-"])
d.title="Simple Model Fit"
d.annotate_fit(simple_model,x=5.0,y=10.0)