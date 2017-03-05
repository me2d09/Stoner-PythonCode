import unittest
import sys
import os.path as path
import os
import fnmatch
from Stoner.compat import *
from importlib import import_module
import matplotlib.pyplot as plt
from traceback import format_exc

pth=path.dirname(__file__)
pth=path.realpath(path.join(pth,"../../"))
sys.path.insert(0,pth)

class DocSamples_test(unittest.TestCase):

    """Path to sample Data File"""
    datadir=path.join(pth,"doc","samples")

    def setUp(self):
        self.scripts=fnmatch.filter(os.listdir(self.datadir),"*.py")
        sys.path.insert(0,self.datadir)
        
    def test_scripts(self):
        """Import each of the sample scripts in turn and see if they ran without error"""
        for ix,filename in enumerate(self.scripts):
            script=filename[:-3]
            print("Trying script {}: {}".format(ix,filename))
            try:
                os.chdir(self.datadir)
                code=import_module(script)
                plt.close("all")
            except Exception as e:
                print("Failed with\n{}".format(format_exc()))
                self.assertTrue(False,"Script file {} failed with {}".format(filename,e))
                
if __name__=="__main__": # Run some tests manually to allow debugging
    test=DocSamples_test("test_scripts")
    test.setUp()
    test.test_scripts()
                
            