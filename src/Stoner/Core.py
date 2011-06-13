#############################################
#
# Core object of the Stoner Package
#
# $Id: Core.py,v 1.19 2011/06/13 14:40:51 cvs Exp $
#
# $Log: Core.py,v $
# Revision 1.19  2011/06/13 14:40:51  cvs
# Make the load routine handle a blank value in metadata
#
# Revision 1.18  2011/05/17 21:04:29  cvs
# Finish implementing the DataFile metadata as a new typeHintDict() dictionary that keeps track of the type hinting strings internally. This ensures that we always have a type hint string available.
#
# Revision 1.17  2011/05/16 22:43:19  cvs
# Start work on a dict child class that keeps track of type hints to use as the core class for the metadata. GB
#
# Revision 1.16  2011/05/10 22:10:31  cvs
# Workaround new behaviou of deepcopy() in Python 2.7 and improve handling when a typehint for the metadata doesn't exist (printing the DataFile will fix the typehinting).
#
# Revision 1.15  2011/05/06 22:21:42  cvs
# Add code to read Renishaw spc files and some sample Raman data. GB
#
# Revision 1.14  2011/04/23 18:23:33  cvs
# What happened here ?
#
# Revision 1.13  2011/04/22 14:44:04  cvs
# Add code to return data as a structured record and to to provide a DataFile.sort() method
#
# Revision 1.12  2011/03/02 14:56:20  cvs
# Colon missing from else command in search function (Line 591)
#
# Revision 1.11  2011/03/02 13:16:52  cvs
# Fix buglet in DataFile.search
#
# Revision 1.10  2011/02/23 21:42:16  cvs
# Experimental code for displaying grid included
#
# Revision 1.9  2011/02/17 23:36:51  cvs
# Updated doxygen comment strings
#
# Revision 1.8  2011/02/14 17:00:03  cvs
# Updated documentation. More doxygen comments
#
# Revision 1.7  2011/02/13 15:51:08  cvs
# Merge in ma gui branch back to HEAD
#
# Revision 1.6  2011/02/12 22:12:43  cvs
# Added some doxygen compatible doc strings
#
# Revision 1.5  2011/02/11 00:00:58  cvs
# Add a DataFile.unique method
#
# Revision 1.4  2011/01/17 10:12:08  cvs
# Added code for mac implementation of wx.FileDialog()
#
# Revision 1.3  2011/01/13 22:30:56  cvs
# Enable chi^2 analysi where the parameters are varied and choi^2 calculated.
# Extra comments in the ini file
# Give DataFile some file dialog boxes
#
# Revision 1.2  2011/01/12 22:56:33  cvs
# Update documentation, add support for slices in some of the DataFile methods
#
# Revision 1.1  2011/01/08 20:30:02  cvs
# Complete splitting Stoner into a package with sub-packages - Core, Analysis and Plot.
# Setup some imports in __init__ so that import Stoner still gets all the subclasses - Gavin
#
#
#############################################

# Imports

import csv
import re
import scipy
#import pdb # for debugging
import os
import sys
import numpy
import math
import copy
import linecache
import wx

class evaluatable:
    """A very simple class that is just a placeholder"""


class typeHintedDict(dict):
    """Extends a regular dict to include type hints of what each key contains."""
    _typehints=dict()

    __regexGetType = re.compile(r'([^\{]*)\{([^\}]*)\}') # Match the contents of the inner most{}
    __regexSignedInt=re.compile(r'^I\d+') # Matches all signed integers
    __regexUnsignedInt=re.compile(r'^U/d+')# Match unsigned integers
    __regexFloat=re.compile(r'^(Extended|Double|Single)\sFloat') # Match floating point types
    __regexBoolean=re.compile(r'^Boolean')
    __regexString=re.compile(r'^(String|Path|Enum)')
    __regexEvaluatable=re.compile(r'^(Cluster|\dD Array)')

    __types={'Boolean':bool, 'I32':int, 'Double Float':float, 'Cluster':dict, 'Array':numpy.ndarray, 'String':str} # This is the inverse of the __tests below - this gives the string type for standard Python classes

    __tests=[(__regexSignedInt, int), (__regexUnsignedInt, int),(__regexFloat, float) , (__regexBoolean, bool), (__regexString, str), (__regexEvaluatable, evaluatable())] # This is used to work out the correct python class for some string types



    def __init__(self, *args):
        """Calls the dict() constructor, then runs through the keys of the created dictionary and either uses the
        string type embedded in the keyname to generate the type hint (and remove the embedded string type from the keyname)
        or determines the likely type hint from the value of the dict element."""

        parent=super(typeHintedDict, self)
        parent.__init__(*args)
        for key in self: # Chekc through all the keys and see if they contain type hints. If they do, move them to the _typehint dict
            m=self.__regexGetType.search(key)
            if m is not None:
                k= m.group(1)
                t= m.group(2)
                self._typehints[k]=t
                super(typeHintedDict, self).__setitem__(k, self[key])
                del(self[key])
            else:
                self._typehints[key]=self.__findtype(parent.__getitem__(key))

    def __findtype(self,  value):
        """Determines the correct string type to return for common python classes"""
        typ="String"
        for t in self.__types:
            if isinstance(value, self.__types[t]):
                if t=="Cluster":
                    elements=[]
                    for k in  value:
                        elements.append(self.__findtype( value[k]))
                    tt=','
                    tt=tt.join(elements)
                    typ='Cluster ('+tt+')'
                elif t=='Array':
                    z=numpy.zeros(1, dtype=value.dtype)
                    typ=str(len(numpy.shape(value)))+"D Array ("+self.__findtype(z[0])+")"
                else:
                    typ=t
                break
        return typ

    def __mungevalue(self, t, value):
        """Based on a string type t, return value cast to an appropriate python class

        @param t is a string representing the type
        @param value is the data value to be munged into the correct class
        @return Returns the munged data value

        Detail: The class has a series of precompiled regular expressions that will match type strings, a list of these has been
        constructed with instances of the matching Python classes. These are tested in turn and if the type string matches
        the constructor of the associated python class is called with value as its argument."""
        for (regexp, valuetype) in self.__tests:
            m=regexp.search(t)
            if m is not None:
                if isinstance(valuetype, evaluatable):
                    return eval(str(value), globals(), locals())
                    break
                else:
                    return valuetype(value)
                    break
        return str(value)

    def __setitem__(self, name, value):
        """Provides a method to set an item in the dict, checking the key for an embedded type hint or inspecting the value as necessary.

        NB If you provide an embedded type string it is your responsibility to make sure that it correctly describes the actual data
        typehintDict does not verify that your data and type string are compatible."""
        m=self.__regexGetType.search(name)
        if m is not None:
            k= m.group(1)
            t= m.group(2)
            self._typehints[k]=t
            if len(value)==0: # Empty data so reset to string and set empty
                super(typeHintedDict, self).__setitem__(k, "")
                self._typehints[k]="String"
            else:
                super(typeHintedDict, self).__setitem__(k, self.__mungevalue(t, value))
        else:
            self._typehints[name]=self.__findtype(value)
            super(typeHintedDict, self).__setitem__(name,  self.__mungevalue(self._typehints[name], value))


    def copy(self):
        """Provides a copy method that is aware of the type hinting strings"""
        return typeHintedDict([(x+'{'+self.type(x)+'}', self[x]) for x in self])

    def type(self, key):
        """Returns the typehint for the given k(s)

        @param key Either a single string key or a iterable type containing keys
        @return the string type hint (or a list of string type hints)"""
        if isinstance(key, str):
            return self._typehints[key]
        else:
            try:
                return [self._typehints[x] for x in key]
            except TypeError:
                return self._typehints[key]


class MyForm(wx.Frame):
    """Provides an editable grid for the DataFile class to use display data"""

    #----------------------------------------------------------------------
    def __init__(self, dfile, **kwargs):
        """Constructor
        @param dfile An instance of the Stoner.DataFile object
        @ param **kwargs Keyword arguments - recognised values include"""
        import wx.grid as gridlib
        if not isinstance(dfile, DataFile):
            raise TypeError('First argument must be a Stoner.DataFile')
        cols=max(len(dfile.column_headers), 4)
        rows=max(len(dfile), 20)
        wx.Frame.__init__(self, parent=None, title="Untitled")
        self.Bind(wx.EVT_SIZE, self._OnSize)
        self.panel = wx.Panel(self)

        myGrid = gridlib.Grid(self.panel)
        myGrid.CreateGrid(rows, cols)

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(myGrid, 1, wx.EXPAND)
        self.panel.SetSizer(self.sizer)

        for i in range(len(dfile.column_headers)):
            myGrid.SetColLabelValue(i, dfile.column_headers[i])
            for j in range(len(dfile)):
                myGrid.SetCellValue(j, i, str(dfile.data[j, i]))

    def _OnSize(self, evt):
        evt.Skip()





class DataFolder(object):

    #   CONSTANTS

    #   INITIALISATION

    def __init__(self, foldername):
        self.data = [];
        self.metadata = dict();
        self.foldername = foldername;
        self.__parseFolder();

    #   PRIVATE FUNCTIONS

    def __parseFolder(self):
        path="C:/Documents and Settings/pymn/workspace/Stonerlab/src/folder/run1"  # insert the path to the directory of interest
        dirList=os.listdir(path)
        for fname in dirList:
            print(fname)

#   PUBLIC METHODS

class DataFile(object): #Now a new style class so that we can use super()
    """@b Stoner.Core.DataFile is the base class object that represents a matrix of data, associated metadata and column headers.

    @b DataFile provides the mthods to load, save, add and delete data, index and slice data, manipulate metadata and column headings.

    Authors: Matt Newman, Chris Allen and Gavin Burnell
    """
#   CONSTANTS
    defaultDumpLocation='C:\\dump.csv'

#   INITIALISATION

    def __init__(self, *args):
        """Constructor method

        various forms are recognised:
        @li DataFile('filename',<optional filetype>,<args>)
        Creates the new DataFile object and then executes the \b DataFile.load method to load data from the given \a filename
        @li DataFile(array)
        Creates a new DataFile object and assigns the \a array to the \b DataFile.data attribute.
        @li DataFile(dictionary)
        Creates the new DataFile object, but initialises the metadata with \a dictionary
        @li  DataFile(array,dictionary),
        Creates the new DataFile object and does the combination of the previous two forms.
        @li DataFile(DataFile)
        Creates the new DataFile object and initialises all data from the existing \DataFile instance. This on the face of it does the same as the assignment operator,
        but is more useful when one or other of the DataFile objects is an instance of a sub-class of DataFile

        @param *args Variable number of arguments that match one of the definitions above
        @return A new instance of the DataFile class.
        """
        self.data = numpy.array([])
        self.metadata = typeHintedDict()
        self.filename = None
        self.column_headers=list()
        # Now check for arguments t the constructor
        if len(args)==1:
            if isinstance(args[0], str): # Filename- load datafile
                self.load(args[0])
            elif isinstance(args[0], numpy.ndarray): # numpy.array - set data
                self.data=args[0]
                self.column_headers=['Column'+str(x) for x in range(numpy.shape(args[0])[1])]
            elif isinstance(args[0], dict): # Dictionary - use as metadata
                self.metadata=args[0].copy()
            elif isinstance(args[0], DataFile):
                self.metadata=args[0].metadata.copy()
                self.data=args[0].data
                self.column_headers=args[0].column_headers
        elif len(args)==2: # 2 argument forms either array,dict or dict,array
            if isinstance(args[0], numpy.ndarray):
                self.data=args[0]
            elif isinstance(args[0], dict):
                self.metadata=args[0].copy()
            elif isinstance(args[0], str) and isinstance(args[1], str):
                self.load(args[0], args[1])
            if isinstance(args[1], numpy.ndarray):
                self.data=args[1]
            elif isinstance(args[1], dict):
                self.metadata=args[1].copy()
        elif len(args)>2:
            apply(self.load, args)

# Special Methods

    def __getattr__(self, name):
        """
        Called for \bDataFile.x to handle some special pseudo attributes

        @param name The name of the attribute to be returned. These include: records
        @return For Records, returns the data as an array of structures
        """
        if name=="records":
            dtype=[(x, numpy.float64) for x in self.column_headers]
            return self.data.view(dtype=dtype).reshape(len(self))

    def __getitem__(self, name): # called for DataFile[x] returns row x if x is integer, or metadata[x] if x is string
        """Called for \b DataFile[x] to return either a row or iterm of metadata

        @param name The name, slice or number of the part of the \b DataFile to be returned.
        @return an item of metadata or row(s) of data. \li If \a name is an integer then the corresponding single row will be rturned
        \li if \a name is a slice, then the corresponding rows of data will be returned. \li If \a name is a string then the metadata dictionary item with
        the correspondoing key will be returned.

        """
        if isinstance(name, slice):
            indices=name.indices(len(self))
            name=range(*indices)
            d=self.data[name[0], :]
            d=numpy.atleast_2d(d)
            for x in range(1, len(name)):
                d=numpy.append(d, numpy.atleast_2d(self.data[x, :]), 0)
            return d
        elif isinstance(name, int):
            return self.data[name,  :]
        elif isinstance(name, str):
            return self.meta(name)
        elif isinstance(name, tuple) and len(name)==2:
            x, y=name
            if isinstance(x, str):
                return self[x][y]
            else:
                d=numpy.atleast_2d(self[x])
                y=self.find_col(y)
                r=d[:, y]
                if len(r)==1:
                    r=r[0]
                return r
        else:
            raise TypeError("Key must be either numeric of string")


    def __setitem__(self, name, value):
        """Called for \DataFile[\em name ] = \em value to write mewtadata entries.
            @param name The string key used to access the metadata
            @param value The value to be written into the metadata. Currently bool, int, float and string values are correctly handled. Everythign else is treated as a string.
            @return Nothing."""
        self.__settype__(name, value)
        self.metadata[name]=value

    def __add__(self, other):
        """ Implements a + operator to concatenate rows of data
                @param other Either a numpy array object or an instance of a \b DataFile object.
                @return A Datafile object with the rows of \a other appended to the rows of the current object.

                If \a other is a 1D numopy array with the same number of lements as their are columns in \a self.data then the numpy array is treated as a new row of data
                If \a ither is a 2D numpy array then it is appended if it has the same number of columns and \a self.data.

"""
        if isinstance(other, numpy.ndarray):
            if len(self.data)==0:
                t=numpy.atleast_2d(other)
                c=numpy.shape(t)[1]
                self.column_headers=map(lambda x:"Column_"+str(x), range(c))
                newdata=self.__class__(self)
                newdata.data=t
                return newdata
            elif len(numpy.shape(other))==1: # 1D array, so assume a single row of data
                if numpy.shape(other)[0]==numpy.shape(self.data)[1]:
                    newdata=self.__class__(self)
                    newdata.data=numpy.append(self.data, numpy.atleast_2d(other), 0)
                    return newdata
                else:
                    return NotImplemented
            elif len(numpy.shape(other))==2 and numpy.shape(other)[1]==numpy.shape(self.data)[1]: # DataFile + array with correct number of columns
                newdata=self.__class__(self)
                newdata.data=numpy.append(self.data, other, 0)
                return newdata
            else:
                return NotImplemented
        elif isinstance(other, DataFile): # Appending another DataFile
            if self.column_headers==other.column_headers:
                newdata=self.__class__(other)
                for x in self.metadata:
                    newdata[x]=self.__class__(self[x])
                newdata.data=numpy.append(self.data, other.data, 0)
                return newdata
            else:
                return NotImplemented
        else:
            return NotImplemented

    def __and__(self, other):
        """Implements the & operator to concatenate columns of data in a \b Stoner.DataFile object.

        @param other Either a numpy array or \bStoner.DataFile object
        @return A \b Stoner.DataFile object with the columns of other concatenated as new columns at the end of the self object.

        Whether \a other is a numopy array of \b Stoner.DataFile, it must have the same or fewer rows than the self object.
        The size of \a other is increased with zeros for the extra rows.
        If \a other is a 1D numpy array it is treated as a column vector.
        The new columns are given blank column headers, but the length of the \b Stoner.DataFile.column_headers is
        increased to match the actual number of columns.
        """
        if isinstance(other, numpy.ndarray):
            if len(other.shape)!=2: # 1D array, make it 2D column
                other=numpy.atleast_2d(other)
                other=other.T
            if other.shape[0]<=self.data.shape[0]: # DataFile + array with correct number of rows
                if other.shape[0]<self.data.shape[0]: # too few rows we can extend with zeros
                    other=numpy.append(other, numpy.zeros((self.data.shape[0]-other.shape[0], other.shape[1])), 0)
                newdata=self.__class__(self)
                newdata.column_headers.extend(["" for x in range(other.shape[1])])
                newdata.data=numpy.append(self.data, other, 1)
                return newdata
            else:
                return NotImplemented
        elif isinstance(other, DataFile): # Appending another datafile
            if self.data.shape[0]==other.data.shape[0]:
                newdata=self.__class__(self)
                newdata.column_headers.extend(other.column_headers)
                for x in other.metadata:
                    newdata[x]=other[x]
                newdata.data=numpy.append(self.data, other.data, 1)
                return newdata
            else:
                return NotImplemented
        else:
             return NotImplemented

    def __repr__(self):
        """Outputs the \b Stoner.DataFile object in TDI format. This allows one to print any \b Stoner.DataFile to a stream based object andgenerate a reasonable textual representation of the data.shape
       @return \a self in a textual format. """
        outp="TDI Format 1.5"+"\t"+reduce(lambda x, y: str(x)+"\t"+str(y), self.column_headers)+"\n"
        m=len(self.metadata)
        (r, c)=numpy.shape(self.data)
        md=[]
        for x in sorted(self.metadata):
            md.extend(x+"{"+self.metadata.type(x)+"}="+str(self.metadata[x]))
        for x in range(min(r, m)):
            outp=outp+md[x]+"\t"+reduce(lambda z, y: str(z)+"\t"+str(y), self.data[x])+"\n"
        if m>r: # More metadata
            for x in range(r, m):
                    outp=outp+md[x]+"\n"
        elif r>m: # More data than metadata
            for x in range(m, r):
                    outp=outp+"\t"+reduce(lambda z, y: str(z)+"\t"+str(y), self.data[x])+"\n"
        return outp

    def __len__(self):
        return numpy.shape(self.data)[0]

#   PRIVATE FUNCTIONS

    def __file_dialog(self, mode):
        from enthought.pyface.api import FileDialog, OK
        # Wildcard pattern to be used in file dialogs.
        file_wildcard = "Text file (*.txt)|*.txt|Data file (*.dat)|*.dat|All files|*"

        if mode=="r":
            mode="open"
        elif mode=="w":
            mode="save"

        if self.filename is not None:
            filename=os.path.basename(self.filename)
            dirname=os.path.dirname(self.filename)
        else:
            filename=""
            dirname=""
        dlg = FileDialog(action=mode, wildcard=file_wildcard)
        dlg.open()
        if dlg.return_code==OK:
            self.filename=dlg.path
            return self.filename
        else:
            return None

    def __parse_metadata(self, key, value):
        """Parse the metadata string, removing the type hints into a separate dictionary from the metadata

        Uses the typehint to set the type correctly in the dictionary

        NB All the clever work of managing the typehinting is done in the metadata dictionary object now.
        """
        self.metadata[key]=value

    def __parse_data(self):
        """Internal function to parse the tab deliminated text file
        """
        reader = csv.reader(open(self.filename, "rb"), delimiter='\t', quoting=csv.QUOTE_NONE)
        row=reader.next()
        assert row[0]=="TDI Format 1.5" # Bail out if not the correct format
        self.data=numpy.array([])
        headers = row[1:len(row)]
        maxcol=1
        for row in reader:
            if maxcol<len(row):
                    maxcol=len(row)
            if row[0].find('=')>-1:
                md=row[0].split('=')
                self.__parse_metadata(md[0], md[1])
            if (len(row[1:len(row)]) > 1) or len(row[1]) > 0:
                self.data=numpy.append(self.data, map(lambda x: float(x), row[1:]))
        else:
            shp=(-1, maxcol-1)
            self.data=numpy.reshape(self.data,  shp)
            self.column_headers=["" for x in range(self.data.shape[1])]
            self.column_headers[0:len(headers)]=headers

    def __parse_plain_data(self, header_line=3, data_line=7, data_delim=' ', header_delim=','):
        header_string=linecache.getline(self.filename, header_line)
        header_string=re.sub(r'["\n]', '', header_string)
        self.column_headers=map(lambda x: x.strip(),  header_string.split(header_delim))
        self.data=numpy.genfromtxt(self.filename,dtype='float',delimiter=data_delim,skip_header=data_line-1)

    def __loadVSM(self):
         """DataFile.__loadVSM(filename)

            Loads Data from a VSM file
            """
         self.__parse_plain_data()

    def __loadBigBlue(self,header_line,data_line):
        """DataFile.__loadBigBlue(filename,header_line,data_line)

        Lets you load the data from the files generated by Big Blue. Should work for any flat file
        with a standard header file and comma separated data.

        header_line/data_line=line number of header/start of data

        TODO:    Get the metadata from the header
        """
        self.__parse_plain_data(header_line,data_line, data_delim=',', header_delim=',')

#   PUBLIC METHODS

    def load(self,filename=None,fileType="TDI",*args):
        """DataFile.load(filename,type,*args)

            Loads data from file filename using routines dependent on the fileType parameter
            fileType is one on TDI,VSM,BigBlue,csv Default is TDI.

            Example: To load Big Blue file

                d.load(file,"BigBlue",8,10)

            Where "BigBlue" is filetype and 8/10 are the line numbers of the headers/start of data respectively

            TODO: Implement a filename extension check to more intelligently guess the datafile type
            """

        if filename is None:
            filename=self.__file_dialog('r')
        else:
            self.filename = filename;

        if fileType=="TDI":
            self.__parse_data()
        elif fileType=="VSM":
            self.__loadVSM()
        elif fileType=="BigBlue":
            self.__loadBigBlue(args[0], args[1])
        elif fileType=="csv":
            self.__parse_plain_data(args[0], args[1], args[2], args[3])
        elif fileType=="NewXRD":
            from .Util import read_XRD_File
            d=read_XRD_File(filename)
            self.column_headers=d.column_headers
            self.data=d.data
            self.metadata=d.metadata
        elif fileType=="Raman":
            from .Util import read_spc_File
            d=read_spc_File(filename)
            self.column_headers=d.column_headers
            self.data=d.data
            self.metadata=d.metadata


        return self

    def save(self, filename=None):
        """DataFile.save(filename)

                Saves a string representation of the current DataFile object into the file 'filename' """
        if filename is None:
            filename=self.filename
        if filename is None: # now go and ask for one
            self.__file_dialog('w')
        f=open(filename, 'w')
        f.write(repr(self))
        f.close()
        self.filename=filename
        return self



    def metadata_value(self, text):
        """Wrapper of DataFile.meta for compatibility"""
        return self.meta(text)

    def data(self):
        return self.data

    def metadata(self):
        return self.metadata

    def column_headers(self):
        return self.column_headers

    def find_col(self, col):
        if isinstance(col, int): #col is an int so pass on
            if col<0 or col>=len(self.column_headers):
                raise IndexError('Attempting to index a non-existant column')
            pass
        elif isinstance(col, str): # Ok we have a string
            if col in self.column_headers: # and it is an exact string match
                col=self.column_headers.index(col)
            else: # ok we'll try for a regular expression
                test=re.compile(col)
                possible=filter(test.search, self.column_headers)
                if len(possible)==0:
                    raise KeyError('Unable to find any possible column matches')
                col=self.column_headers.index(possible[0])
        elif isinstance(col, slice):
            indices=col.indices(numpy.shape(self.data)[1])
            col=range(*indices)
            col=self.find_col(col)
        elif isinstance(col, list):
            col=map(self.find_col, col)
        else:
            raise TypeError('Column index must be an integer or string')
        return col

    def column(self, col):
        """Extracts a column of data by index or name"""
        if isinstance(col, slice): # convert a slice into a list and then continue
            indices=col.indices(numpy.shape(self.data)[1])
            col=range(*indices)
        if isinstance(col, list):
            d=self.column(col[0])
            d=numpy.reshape(d, (len(d), 1))
            for x in range(1, len(col)):
                t=self.column(col[x])
                t=numpy.reshape(t, (len(t), 1))
                d=numpy.append(d,t , 1)
            return d
        else:
            return self.data[:, self.find_col(col)]

    def meta(self, ky):
        """Returns some metadata"""
        if isinstance(ky, str): #Ok we go at it with a string
            if ky in self.metadata:
                return self.metadata[ky]
            else:
                test=re.compile(ky)
                possible=filter(test.search, self.metadata)
                if len(possible)==0:
                    raise KeyError("No metadata with keyname: "+ky)
                elif len(possible)==1:
                    return self.metadata[possible[0]]
                else:
                    d=dict()
                    for p in possible:
                        d[p]=self.metadata[p]
                    return d
        else:
            raise TypeError("Only string are supported as search keys currently")
            # Should implement using a list of strings as well

    def dir(self, pattern=None):
        """ Return a list of keys in the metadata, filtering wiht a regular expression if necessary

                DataFile.dir(pattern) - pattern is a regular expression or None to list all keys"""
        if pattern==None:
            return self.metadata.keys()
        else:
            test=re.compile(pattern)
            possible=filter(test.search, self.metadata.keys())
            return possible

    def search(self, *args):
        """Searches in the numerica data part of the file for lines that match and returns  the corresponding rows

        Find row(s) that match the specified value in column:

        search(Column,value,columns=[list])

        Find rows that where the column is >= lower_limit and < upper_limit:

        search(Column,function ,columns=[list])

        Find rows where the function evaluates to true. Function should take two parameters x (float) and y(numpy array of floats).
        e.g. AnalysisFile.search('x',lambda x,y: x<10 and y[0]==2, ['y1','y2'])
        """

        if len(args)==2:
            col=args[0]
            targets=[]
            val=args[1]
        elif len(args)==3:
            col=args[0]
            if not isinstance(args[2],list):
                c=[args[2]]
            else:
                c=args[2]
            targets=map(self.find_col, c)
            val=args[1]
        if len(targets)==0:
            targets=range(self.data.shape[1])
        d=numpy.transpose(numpy.atleast_2d(self.column(col)))
        d=numpy.append(d, self.data[:, targets], 1)
        if callable(val):
            rows=numpy.nonzero([val(x[0], x[1:]) for x in d])[0]
        elif isinstance(val, float):
            rows=numpy.nonzero([x[0]==val for x in d])[0]
        return self.data[rows][:, targets]

    def unique(self, col, return_index=False, return_inverse=False):
        """Return the unique values from the specified column - pass through for numpy.unique"""
        return numpy.unique(self.column(col), return_index, return_inverse)

    def del_rows(self, col, val=None):
        """Searchs in the numerica data for the lines that match and deletes the corresponding rows
        del_rows(Column, value)
        del_rows(Column,function) """
        if isinstance(col, slice) and val is None:
            indices=col.indices(len(self))
            col-=range(*indices)
        if isinstance(col, list) and val is None:
            col.sort(reverse=True)
            for c in col:
                self.del_rows(c)
        elif isinstance(col,  int) and val is None:
            self.data=numpy.delete(self.data, col, 0)
        else:
            col=self.find_col(col)
            d=self.column(col)
            if callable(val):
                rows=numpy.nonzero([val(x[col], x) for x in self])[0]
            elif isinstance(val, float):
                rows=numpy.nonzero([x==val for x in d])[0]
            self.data=numpy.delete(self.data, rows, 0)
        return self

    def add_column(self,column_data,column_header=None, index=None, func_args=None, replace=False):
        """Appends a column of data or inserts a column to a datafile"""
        if index is None:
            index=len(self.column_headers)
            replace=False
            if column_header is None:
                column_header="Col"+str(index)
        else:
            index=self.find_col(index)
            if column_header is None:
                column_header=self.column_headers[index]
        if not replace:
            self.column_headers.insert(index, column_header)
        else:
            self.column_headers[index]=column_header

        # The following 2 lines make the array we are adding a
        # [1, x] array, i.e. a column by first making it 2d and
        # then transposing it.
        if isinstance(column_data, numpy.ndarray):
            numpy_data=numpy.atleast_2d(column_data)
        elif callable(column_data):
            if isinstance(func_args, dict):
                new_data=[column_data(x, **func_args) for x in self]
            else:
                new_data=[column_data(x) for x in self]
            new_data=numpy.array(new_data)
            numpy_data=numpy.atleast_2d(new_data)
        else:
            return NotImplemented
        if replace:
            self.data[:, index]=numpy_data[0, :]
        else:
            self.data=numpy.insert(self.data,index, numpy_data,1)
        return self

    def del_column(self, col):
        c=self.find_col(col)
        self.data=numpy.delete(self.data, c, 1)
        if isinstance (c, list):
            c.sort(reverse=True)
        else:
            c=[c]
        for col in c:
            del self.column_headers[col]
        return self

    def rows(self):
        """Generator method that will iterate over rows of data"""
        (r, c)=numpy.shape(self.data)
        for row in range(r):
            yield self.data[row]

    def columns(self):
        """Generator method that will iterate over columns of data"""
        (r, c)=numpy.shape(self.data)
        for col in range(c):
            yield self.data[col]

    def sort(self, order):
        """Sorts the data by column name. Sorts in place and returns a copy of the sorted data object for chaining methods
        @param order Either a scalar integer or string or a list of integer or strings that represent the sort order
        @return A copy of the sorted object
        """
        if isinstance(order, list) or isinstance(order, tuple):
            order=[self.column_headers[self.find_col(x)] for x in order]
        else:
            order=[self.column_headers[self.find_col(order)]]
        d=numpy.sort(self.records, order=order)
        print d
        self.data=d.view(dtype='f8').reshape(len(self), len(self.column_headers))
        return self


    def csvArray(self,dump_location=defaultDumpLocation):
        spamWriter = csv.writer(open(dump_location, 'wb'), delimiter=',',quotechar='|', quoting=csv.QUOTE_MINIMAL)
        i=0
        spamWriter.writerow(self.column_headers)
        while i< self.data.shape[0]:
            spamWriter.writerow(self.data[i,:])
            i+=1

    def edit(self):
        """Produce an editor window with a grid"""
        app = wx.PySimpleApp()
        frame = MyForm(self).Show()
        app.MainLoop()
        while app.IsMainLoopRunning:
            pass
