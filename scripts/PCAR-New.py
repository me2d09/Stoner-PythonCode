"""Python  script for Analysing PCAR data using Stoner classes and lmfit

Gavin Burnell g.burnell@leeds.ac.uk
"""
from __future__ import print_function

# Import packages

import numpy as np
from Stoner.Core import Data
from Stoner.Fit import cfg_data_from_ini,cfg_model_from_ini,quadratic
from Stoner.compat import python_v3
if python_v3:
    import configparser as ConfigParser
else:
    import ConfigParser

class working(Data):
    
    """Utility class to manipulate data and plot it"""

    def __init__(self,*args,**kargs):
        """Setup the fitting code."""
        super(working,self).__init__(*args,**kargs)
        inifile=__file__.replace(".py",".ini")

        tmp=cfg_data_from_ini(inifile,filename=False)
        self._setas=tmp.setas.clone
        self.column_headers=tmp.column_headers
        self.metadata=tmp.metadata
        self.data=tmp.data
        self.vcol=self.find_col(self.setas["x"])
        self.gcol=self.find_col(self.setas["y"])
        self.filename=tmp.filename
        
        model,p0=cfg_model_from_ini(inifile,data=self)

        if python_v3:
            config=ConfigParser.ConfigParser()
        else:
            config=ConfigParser.SafeConfigParser()
        config.read(inifile)
        self.config=config


        #Some config variables we'll need later
        self.show_plot=config.getboolean('Options', 'show_plot')
        self.save_fit=config.getboolean('Options', 'save_fit')
        self.report=config.getboolean('Options', 'print_report')
        self.fancyresults=config.has_option("Options","fancy_result") and config.getboolean("Options","fancy_result")
        self.model=model
        self.p0=p0

    def Discard(self):
        """Optionally throw out some high bias data."""        
        discard=self.config.has_option("Data","dicard") and self.config.getboolean("Data",'discard')
        if discard:
            v_limit=self.config.get("Data",'v_limit')
            print("Discarding data beyond v_limit={}".format(v_limit))
            self.del_rows(self.vcol,lambda x,y:abs(x)>v_limit)
        return self
            


    def Normalise(self):
        """Normalise the data if the relevant options are turned on in the config file.

        Use either a simple normalisation constant or go fancy and try to use a background function.
        """
        if self.config.has_option("Options", "normalise") and self.config.getboolean("Options", "normalise"):
            print("Normalising Data")
            Gn=self.config.getfloat("Data", 'Normal_conductance')
            v_scale=self.config.getfloat("Data", "v_scale")
            if self.config.has_option("Options", "fancy_normaliser") and self.config.getboolean("Options", "fancy_normaliser"):
                vmax, _ =self.max(self.vcol)
                vmin, _ =self.min(self.vcol)
                p, pv=self.curve_fit(quadratic, bounds=lambda x, y:(x>0.9*vmax) or (x<0.9*vmin))
                print("Fitted normal conductance background of G="+str(p[0])+"V^2 +"+str(p[1])+"V+"+str(p[2]))
                self["normalise.coeffs"]=p
                self["normalise.coeffs_err"]=np.sqrt(np.diag(pv))
                self.apply(lambda x:x[self.gcol]/quadratic(x[self.vcol], *p), self.gcol)
            else:
                self.apply(lambda x:x[self.gcol]/Gn, self.gcol)
            if self.config.has_option("Options", "rescale_v") and self.config.getboolean("Options", "rescale_v"):
                self.apply(lambda x:x[self.vcol]*v_scale, self.vcol)
        return self

    def offset_correct(self):
        """Centre the data.
        
        - look for peaks and troughs within 5 of the initial delta value
        take the average of these and then subtract it.
        """
        if self.config.has_option("Options", "remove_offset") and self.config.getboolean("Options", "remove_offset"):
            print("Doing offset correction")
            peaks=self.peaks(self.gcol,len(self)/20,0,xcol=self.vcol,poly=4,peaks=True,troughs=True)
            peaks=filter(lambda x: abs(x)<4*self.delta['value'], peaks)
            offset=np.mean(np.array(peaks))
            print("Mean offset ="+str(offset))
            self.apply(lambda x:x[self.vcol]-offset, self.vcol)
        return self

    def plot_results(self):
        """Do the plotting of the data and the results"""
        self.figure()# Make a new figure and show the results
        self.plot_xy(self.vcol,[self.gcol,"Fit"],fmt=['ro','b-'],label=["Data","Fit"])
        bbox_props = dict(boxstyle="square,pad=0.3", fc="white", ec="b", lw=2)
        if self.fancyresults:
            self.annotate_fit(self.model,x=0.05,y=0.65,xycoords="axes fraction",bbox=bbox_props,fontsize=11)
        return self

    def Fit(self):
        """Run the fitting code."""
        self.Discard().Normalise().offset_correct()
        chi2= self.p0.shape[0]>1
        
        fit=self.lmfit(self.model,p0=self.p0,result=True,header="Fit")

        if not chi2: # Single fit mode, consider whether to plot and save etc
            if self.show_plot:
                self.plot_results()
            if self.save_fit:
                self.save(False)
            if self.report:
                print(fit.fit_report())
        else: #chi^2 mapping mode
            ret=Data()
            ret.data=fit
            ret.metadata=self.metadata
            prefix=ret["lmfit.prefix"][-1]
            ix=0
            for ix,p in enumerate(self.model.param_names):
                if "{}{} label".format(prefix,p) in self:
                    label=self["{}{} label".format(prefix,p)]
                else:
                    label=p
                if "{}{} units".format(prefix,p) in self:
                    units="({})".format(self["{}{} units".format(prefix,p)])
                else:
                    units=""
                ret.column_headers[2*ix]="${} {}$".format(label,units)
                ret.column_headers[2*ix+1]="$\\delta{} {}$".format(label,units)
                if not ret["{}{} vary".format(prefix,p)]:
                    fixed=2*ix
            ret.column_headers[-1]="$\\chi^2$"
            ret.labels=ret.column_headers
            plots=list(range(0,ix*2+1,2))
            errors=list(range(1,ix*2+2,2))
            plots.append(ix*2+2)
            plots.remove(fixed)
            errors.remove(fixed+1)
            print(ret.column_headers,fixed,plots,errors)
            if self.show_plot:
                ret.plot_xy(fixed,plots,yerr=tuple(errors),multiple="panels")
            if self.save_fit:
                ret.filename=None
                ret.save(False)
            

if __name__=="__main__":
    d=working()
    d.Fit()









