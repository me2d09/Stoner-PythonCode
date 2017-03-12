"""
 FStoner.Folders : Classes for working collections of data files

 Classes:
     :py:class:`objectFolder` - manages a list of individual data files (e.g. from a directory tree)
"""

__all__ = ["objectFolder","DataFolder","PlotFolder"]
from .compat import *
import os
import re
import os.path as path
import fnmatch
import numpy as _np_
from copy import copy,deepcopy
import unicodedata
import string
from collections import Iterable,MutableSequence,MutableMapping,OrderedDict
from inspect import ismethod
from itertools import islice
import matplotlib.pyplot as plt
from .Core import metadataObject,DataFile


regexp_type=(re._pattern_type,)

class regexpDict(OrderedDict):
    """An ordered dictionary that permits looks up by regular expression."""
    def __init__(self,*args,**kargs):
        super(regexpDict,self).__init__(*args,**kargs)

    def __lookup__(self,name):
        """Lookup name and find a matching key or raise KeyError.

        Parameters:
            name (str, re._pattern_type): The name to be searched for

        Returns:
            Canonical key matching the specified name.

        Raises:
            KeyError: if no key matches name.
        """
        if super(regexpDict,self).__contains__(name):
            return name
        if isinstance(name,string_types):
            try:
                nm=re.compile(name)
            except:
                nm=name
        elif isinstance(name,int_types): #We can do this because we're an OrderedDict!
            return list(self.keys())[name]
        else:
            nm=name
        if isinstance(nm,re._pattern_type):
            for n in self.keys():
                if nm.match(n):
                        return n

        raise KeyError("{} is not a match to any key.".format(name))


    def __getitem__(self,name):
        """Adds a lookup via regular expression when retrieving items."""
        return super(regexpDict,self).__getitem__(self.__lookup__(name))

    def __setitem__(self,name,value):
        """Overwrites any matching key, or if not found adds a new key."""
        try:
            key=self.__lookup__(name)
        except KeyError:
            if not isinstance(name,string_types):
                raise KeyError("{} is not a match to any key.".format(name))
            key=name
        OrderedDict.__setitem__(self, key, value)

    def __delitem__(self,name):
        """Deletes keys that match by regular expression as well as exact matches"""
        super(regexpDict,self).__delitem__(self.__lookup__(name))

    def __contains__(self,name):
        """Returns True if name either is an exact key or matches when interpreted as a regular experssion."""
        try:
            name=self.__lookup__(name)
            return True
        except KeyError:
            return False
        
    def has_key(self,name):
        """"Key is definitely in dictionary as literal"""
        return super(regexpDict,self).__contains__(name)

class baseFolder(MutableSequence):
    """A base class for objectFolders that supports both a sequence of objects and a mapping of instances of itself.

    Attributes:
        groups(regexpDict): A dictionary of similar baseFolder instances
        objects(regexptDict): A dictionary of metadataObjects
        _index(list): An index of the keys associated with objects
        
    Properties:
        depth (int): The maximum number of levels of nested groups in the folder
        files (list of str or metadataObject): the indivdual objects or their names if they are not loaded
        instance (metadataObject): an empty instance of the data type stored in the folder
        loaded (generator of (str name, metadataObject value): iterate over only the loaded into memory items of the folder
        ls (list of str): the names of the objects in the folder, loaded or not
        lsgrp (list of str): the names of all the groups in the folder
        mindepth (int): the minimum level of nesting groups in the folder.
        not_empty (iterator of metadaaObject): iterates over all members of the folder that have non-zero length
        type (subclass of metadtaObject): the class of objects sotred in this folder
    """

    
    def __new__(cls,*args,**kargs):
        """The __new__ method is used to create the underlying storage attributes.
        
        We do this in __new__ so that the mixin classes can access baseFolders state storage before baseFolder does further __init__() work.
        """
        if python_v3:            
            self=super(baseFolder,cls).__new__(cls)
        else:
            self=super(baseFolder,cls).__new__(cls,*args,**kargs)
        self.debug=kargs.pop("debug",False)
        self._object_attrs=dict()
        self._last_name=0
        self._groups=regexpDict()
        self._objects=regexpDict()
        self._instance=None
        self._object_attrs=dict()
        self.key=None
        self._type=metadataObject
        return self
        

    def __init__(self,*args,**kargs):
        """Initialise the baseFolder.

        Notes:
            - Creates empty groups and objects stres
            - Sets all keyword arguments as attributes unless otherwise overwriting an existing attribute
            - stores other arguments in self.args
            - iterates over the multuiple inheritance tree and eplaces any interface methods with ones from
                the mixin classes
            - calls the mixin init methods.
            """
        self.args=copy(args)
        self.kargs=copy(kargs)
        #List of routines that define the interface for manipulating the objects stored in the folder
        for k in list(self.kargs.keys()): # Store keyword parameters as attributes
            if not hasattr(self,k) or k in ["type","kargs","args"]:
                value=kargs.pop(k,None)
                self.__setattr__(k,value)
                if self.debug: print("Setting self.{} to {}".format(k,value))
        if python_v3:
            super(baseFolder,self).__init__()
        else:
            super(baseFolder,self).__init__(*args,**kargs)
                
    ###########################################################################
    ################### Properties of baseFolder ##############################

    @property
    def depth(self):
        """Gives the maximum number of levels of group below the current objectFolder."""
        if len(self.groups)==0:
            r=0
        else:
            r=1
            for g in self.groups:
                r=max(r,self.groups[g].depth+1)
        return r

    @property
    def files(self):
        """Return an iterator of potentially unloaded named objects."""
        return [self.__getter__(i,instantiate=None) for i in range(len(self))]

    @files.setter
    def files(self,value):
        """Just a wrapper to clear and then set the objects."""
        if isinstance(value,Iterable):
            self.__clear__()
            for i,v in enumerate(value):
                self.insert(i,v)
                
    @property
    def groups(self):
        return self._groups
    
    @groups.setter
    def groups(self,value):
        if not isinstance(value,regexpDict):
            self._groups=regexpDict(value)
        else:
            self._groups=value

    @property
    def instance(self):
        if self._instance is None:
            self._instance=self._type()
        return self._instance
                
    @property
    def loaded(self):
        """An iterator that indicates wether the contents of the :py:class:`Stoner.Folders.objectFolder` has been
        loaded into memory."""
        for f in self.__names__():
            val=self.__getter__(f,instantiate=None)
            if isinstance(val,self.type):
                return f,val

    @property
    def ls(self):
        return self.__names__()

    @property
    def lsgrp(self):
        """Returns a list of the groups as a generator."""
        for k in self.groups.keys():
            yield k

    @property
    def mindepth(self):
        """Gives the minimum number of levels of group below the current objectFolder."""
        if len(self.groups)==0:
            r=0
        else:
            r=1E6
            for g in self.groups:
                r=min(r,self.groups[g].depth+1)
        return r

    @property
    def not_empty(self):
        """An iterator for objectFolder that checks whether the loaded metadataObject objects have any data.

        Returns the next non-empty DatFile member of the objectFolder.

        Note:
            not_empty will also silently skip over any cases where loading the metadataObject object will raise
            and exception."""
        for i in range(len(self)):
            try:
                d=self[i]
            except:
                continue
            if len(d)==0:
                continue
            yield(d)

    @property
    def objects(self):
        return self._objects
    
    @objects.setter
    def objects(self,value):
        if not isinstance(value,regexpDict):
            self._objects=regexpDict(value)
        else:
            self._objects=value


    @property
    def type(self):
        """Defines the (sub)class of the :py:class:`Stoner.Core.metadataObject` instances."""
        return self._type

    @type.setter
    def type(self,value):
        """Ensures that type is a subclass of metadataObject."""
        if issubclass(value,metadataObject):
            self._type=value
        elif isinstance(value,metadataObject):
            self._type=value.__class__
        else:
            raise TypeError("{} os neither a subclass nor instance of metadataObject".format(type(value)))
        self._instance=None #Reset the instance cache 

    ################### Methods for subclasses to override to handle storage #####
    def __lookup__(self,name):
        """Stub for other classes to implement.
        Parameters:
            name(str): Name of an object

        Returns:
            A key in whatever form the :py:meth:`baseFolder.__getter__` will accept.
            
        Note:
            We're in the base class here, so we don't call super() if we can't handle this, then we're stuffed!
        """
        if isinstance(name,int_types):
            name=list(self.objects.keys())[name]
        elif name not in self.__names__():
            name=None
        return name

    def __names__(self):
        """Stub method to return a list of names of all objects that can be indexed for __getter__.
        
        Note:
            We're in the base class here, so we don't call super() if we can't handle this, then we're stuffed!
        """

        return list(self.objects.keys())

    def __getter__(self,name,instantiate=True):
        """Stub method to do whatever is needed to transform a key to a metadataObject.

        Parameters:
            name (key type): The canonical mapping key to get the dataObject. By default
                the baseFolder class uses a :py:class:`regexpDict` to store objects in.

        Keyword Arguments:
            instatiate (bool): If True (default) then always return a metadataObject. If False,
                the __getter__ method may return a key that can be used by it later to actually get the
                metadataObject. If None, then will return whatever is helf in the object cache, either instance or name.

        Returns:
            (metadataObject): The metadataObject

            Note:
            We're in the base class here, so we don't call super() if we can't handle this, then we're stuffed!

            
            """
        name=self.__lookup__(name)
        if instantiate is None:
            return self.objects[name]
        elif not instantiate:
            return name
        else:
            name=self.objects[name]
            if not isinstance(name,self._type):
                raise KeyError("{} is not a valid {}".format(name,self._type))
        return self._update_from_object_attrs(name)

    def __setter__(self,name,value):
        """Stub to setting routine to store a metadataObject.
        Parameters:
            name (string) the named object to write - may be an existing or new name
            value (metadataObject) the value to store.
            
        Note:
            We're in the base class here, so we don't call super() if we can't handle this, then we're stuffed!            
            """
        if name is None:
            name=self.make_name()
        self.objects[name]=value

    def __deleter__(self,ix):
        """Deletes an object from the baseFolder.

        Parameters:
            ix(str): Index to delete, should be within +- the lengthe length of the folder.

        Note:
            We're in the base class here, so we don't call super() if we can't handle this, then we're stuffed!
            
            """
        del self.objects[ix]

    def __clear__(self):
        """"Clears all stored :py:class:`Stoner.Core.metadataObject` instances stored.
        
        Note:
            We're in the base class here, so we don't call super() if we can't handle this, then we're stuffed!
        
        """
        for n in self.__names__():
            self.__deleter__(self.__lookup__(n))

    def __clone__(self,other=None):
        """Do whatever is necessary to copy attributes from self to other.

        Note:
            We're in the base class here, so we don't call super() if we can't handle this, then we're stuffed!
        
        
        """
        if other is None:
            other=self.__class__()
        other.args=self.args
        other.kargs=self.kargs
        other.type=self.type
        for k in self.kargs:
            if not hasattr(other,k):
                setattr(other,k,self.kargs[k])
        return other

    ###########################################################################
    ######## Methods to implement the MutableMapping abstract methods #########
    ######## And to provide a mapping interface that mainly access groups #####

    def __getitem__(self,name):
        """Try to get either a group or an object.

        Parameters:
            name(str, int,slice): Which objects to return from the folder.

        Returns:
            Either a baseFolder instance or a metadataObject instance or raises KeyError
            
        How the indexing works depends on the data type of the parameter *name*:
            
            - str, regexp
                Then it is checked first against the groups and then against the objects 
                dictionaries - both will fall back to a regular expression if necessary. 
                
            - int
                Then the _index attribute is used to find a matching object key.
                
            - slice
                Then a new :py:class:`baseFolder` is constructed by cloning he current one, but without
                any groups or files. The new :py:class:`baseFolder` is populated with entries 
                from the current folder according tot he usual slice definition. This has the advantage
                of not loading the objects in the folder into memory if a :py:class:`DiskBasedFolder` is
                used.
        """
        if isinstance(name,string_types+regexp_type):
            if name in self.groups:
                return self.groups[name]
            elif name in self.objects:
                name=self.__lookup__(name)
                return self.__getter__(name)
            else:
                name=self.__lookup__(name)
                return self.__getter__(name)
        elif isinstance(name,int_types):
            if -len(self)<name<len(self):
                return self.__getter__(self.__lookup__(name),instantiate=True)
            else:
                raise IndexError("{} is out of range.".format(name))
        elif isinstance(name,slice): #Possibly ought to return another Folder?
            other=self.__clone__()
            for iname in islice(self.__names__(),name.start,name.stop,name.step):
                other.__setter__(iname,self.__getter__(iname))
            return other
        else:
            raise KeyError("Can't index the baseFolder with {}",format(name))

    def __setitem__(self,name,value):
        """Attempts to store a value in either the groups or objects.

        Parameters:
            name(str or int): If the name is a string and the value is a baseFolder, then assumes we're accessing a group.
                if name is an integer, then it must be a metadataObject.
            value (baseFolder,metadataObject,str): The value to be storred.
        """
        if isinstance(name,string_types):
            if isinstance(value,baseFolder):
                self.groups[name]=value
            else:
                self.__setter__(self.__lookup__(name),value)
        elif isinstance(name,int_types):
            if -len(self)<name<len(self):
                self.__setter__(self.__lookup__(name),value)
            else:
                raise IndexError("{} is out of range".format(name))
        else:
            raise KeyError("{} is not a valid key for baseFolder".format(name))

    def __delitem__(self,name):
        """Attempt to delete an item from either a group or list of files.

        Parameters:
            name(str,int): IF name is a string, then it is checked first against the groups and then
                against the objects. If name is an int then it s checked against the _index.
        """
        if isinstance(name,string_types):
            if name in self.groups:
                del self.groups[name]
            elif name in self.objects:
                self.__deleter__(self.__lookup__(name))
            else:
                raise KeyError("{} doesn't match either a group or object.".format(name))
        elif isinstance(name,int_types):
            if -len(self)<name<=len(self):
                self.__deleter__(self.__lookup__(name))
            else:
                raise IndexError("{} is out of range.".format(name))
        else:
            raise KeyError("Can't use {} as a key to delete from baseFolder.".format(name))

    def __contains__(self,name):
        """Check whether name is in a list of groups or in the list of names"""
        return name in self.groups or name in self.__names__()

    def __len__(self):
        return len(self.__names__())
        
    def __add_core__(self,result,other):
        """Implements the core logic of the addition operator.

        Note:
            We're in the base class here, so we don't call super() if we can't handle this, then we're stuffed!  
        """
        if isinstance(other,baseFolder):
            if issubclass(other.type,self.type):
                result.extend([f for f in other.files])
                for grp in other.groups:
                    if grp in self.groups:
                        result.groups[grp]+=other.groups[grp] # recursively merge groups
                    else:
                        result.groups[grp]=copy(other.groups[grp])
            else:
                raise RuntimeError("Incompatible types ({} must be a subclass of {}) in the two folders.".format(other.type,result.type))
        elif isinstance(other,result.type):
            result.append(self.type(other))
        else:
            result=NotImplemented
        return result
        
    def __div_core__(self,result,other):
        """Implements the divide operator as a grouping function."""
        if isinstance(other,string_types+(list,tuple)):
            result.group(other)
            return result
        elif isinstance(other,int_types): #Simple decimate
            for i in range(other):
                self.add_group("Group {}".format(i))
            for ix,f in enumerate(self):
                group=ix%other
                self.groups["Group {}".format(group)]+=d
            self.__clear__()

    def __sub_core__(self,result,other):
        """Implemenets the core logic of the subtraction operator.
        
        Note:
            We're in the base class here, so we don't call super() if we can't handle this, then we're stuffed!
        
        """
        if isinstance(other,int_types):
            delname=result.__names__()[other]
            result.__deleter__(delname)
        elif isinstance(other,string_types):
            if other in result.__names__():
                result.__deleter__(other)
            else:
                raise RuntimeError("{} is not in the folder.".format(other))
        elif isinstance(other,metadataObject) and (hasattr(other,"filename") or hasattr(other,"title")):
            othername=getattr(other,"filename",getattr(other,"title"))
            if othername in result.__names__():
                result.__deleter__(othername)
            else:
                raise RuntimeError("{} is not in the folder.".format(othername))
        elif isinstance(other,baseFolder):
            if issubclass(other.type,self.type):
                for othername in other.ls:
                    if othername in result:
                        result.__deleter__(othername)
                for othergroup in other.groups:
                    if othergroup in result.groups:
                        result.groups[othergroup].__sub_core__(result.groups[othergroup],other.groups[othergroup])
            else:
                raise RuntimeError("Incompatible types ({} must be a subclass of {}) in the two folders.".format(other.type,result.type))
        elif isinstance(other,Iterable):
            for c in sorted(other):
                result.__sub_core__(result,c)
        else:
            result=NotImplemented
        return result

        
    ###########################################################################
    ###################### Standard Special Methods ###########################

    

    def __add__(self,other):
        """Implement the addition operator for baseFolder and metadataObjects."""
        result=deepcopy(self)
        result=self.__add_core__(result,other)
        return result

    def __iadd__(self,other):
        """Implement the addition operator for baseFolder and metadataObjects."""
        result=self
        result=self.__add_core__(result,other)
        return result

    if python_v3:
        def __truediv__(self,other):
            """The divide operator is a grouping function for a :py:class:`baseFolder`."""
            result=deepcopy(self)
            return self.__div_core__(result,other)

        def __itruediv__(self,other):
            """The divide operator is a grouping function for a :py:class:`baseFolder`."""
            result=self
            return self.__div_core__(result,other)
    else:            
        def __div__(self,other):
            """The divide operator is a grouping function for a :py:class:`baseFolder`."""
            result=deepcopy(self)
            return self.__div_core__(result,other)

        def __idiv__(self,other):
            """The divide operator is a grouping function for a :py:class:`baseFolder`."""
            result=self
            return self.__div_core__(result,other)
        
    def __invert__(self):
        """For a :py:class:`naseFolder`, inverting means either flattening or unflattening the folder.
        
        If we have no sub-groups then we assume we are unflattening the Folder and that the object names have embedded path separators.
        If we have sub-groups then we assume that we need to flatten the data.."""
        result=deepcopy(self)
        if len(result.groups)==0:
            result.unflatten()
        else:
            result.flatten()
        return result
        
    def __iter__(self):
        """Iterate over objects."""
        return self.next()
        
    def __next__(self):
        """Python 3.x style iterator function."""
        for n in self.__names__():
            yield self.__getter__(n,instantiate=True)
 
    def next(self):
        """Python 2.7 style iterator function."""
        for n in self.__names__():
            yield self.__getter__(n,instantiate=True)
    
        
    def __sub__(self,other):
        """Implement the addition operator for baseFolder and metadataObjects."""
        result=deepcopy(self)
        result=self.__sub_core__(result,other)
        return result

    def __isub__(self,other):
        """Implement the addition operator for baseFolder and metadataObjects."""
        result=self
        result=self.__sub_core__(result,other)
        return result

        
        
    def __getattr__(self, item):
        """Handles some special case attributes that provide alternative views of the objectFolder

        Args:
            item (string): The attribute name being requested

        Returns:
            Depends on the attribute

        """
        try:
            ret=super(baseFolder,self).__getattribute__(item)
        except AttributeError:
            if item.startswith("_"):
                raise AttributeError("{} is not an Attribute of {}".format(item,self.__class__))
                
            try:
                instance=super(baseFolder,self).__getattribute__("instance")
                if callable(getattr(instance,item,None)): # It's a method
                    ret=self.__getattr_proxy(item)
                else: # It's a static attribute
                    if item in self._object_attrs:
                        ret=self._object_attrs[item]
                    elif len(self)>0:
                        ret=getattr(instance,item,None)
                    else:
                        ret=None
                    if ret==None:
                        raise AttributeError
            except AttributeError: # Ok, pass back
                raise AttributeError("{} is not an Attribute of {} or {}".format(item,type(self),type(instance)))
        return ret

    def __getattr_proxy(self,item):
        """Make a prpoxy call to access a method of the metadataObject like types.

        Args:
            item (string): Name of method of metadataObject class to be called

        Returns:
            Either a modifed copy of this objectFolder or a list of return values
            from evaluating the method for each file in the Folder.
        """
        meth=getattr(self.instance,item,None)
        def _wrapper_(*args,**kargs):
            """Wraps a call to the metadataObject type for magic method calling.
            Note:
                This relies on being defined inside the enclosure of the objectFolder method
                so we have access to self and item"""
            retvals=[]
            for ix,f in enumerate(self):
                meth=getattr(f,item,None)
                ret=meth(*args,**kargs)
                if ret is not f: # method did not returned a modified version of the metadataObject
                    retvals.append(ret)
                if isinstance(ret,self._type):
                    self[ix]=ret
            if len(retvals)==0: # If we haven't got anything to retun, return a copy of our objectFolder
                retvals=self
            return retvals
        #Ok that's the wrapper function, now return  it for the user to mess around with.
        _wrapper_.__doc__=meth.__doc__
        _wrapper_.__name__=meth.__name__
        return _wrapper_

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            try:
                setattr(result, k, deepcopy(v, memo))
            except:
                setattr(result, k, copy(v))                
        return result

        
    def __repr__(self):
        """Prints a summary of the objectFolder structure

        Returns:
            A string representation of the current objectFolder object"""
        cls=self.__class__.__name__
        pth=getattr(self,"key")
        if pth is None:
            pth=self.directory
        s="{}({}) with pattern {} has {} files and {} groups\n".format(cls,pth,self.pattern,len(self),len(self.groups))
        for g in self.groups: # iterate over groups
            r=self.groups[g].__repr__()
            for l in r.split("\n"): # indent each line by one tab
                s+="\t"+l+"\n"
        return s.strip()
        
    def __reversed__(self):
        """Create an iterator function that runs backwards through the stored objects."""
        def reverse_iterator(self):
            for n in reversed(self.__names__()):
                yield self.__getter__(n,instantiate=True)
        return reverse_iterator

    def __setattr__(self,name,value):
        """Pass through to set the sample attributes."""
        if name.startswith("_") or name in ["debug","groups","args","kargs","objects","key"]: # pass ddirectly through for private attributes
            super(baseFolder,self).__setattr__(name,value)
        elif hasattr(self,name) and not callable(getattr(self,name,None)): #If we recognise this our own attribute, then just set it
            super(baseFolder,self).__setattr__(name,value)
        elif hasattr(self,"_object_attrs") and hasattr(self,"_type") and name in dir(self._type() and not callable(getaatr(self._type,name))):
            #If we're tracking the object attributes and have a type set, then we can store this for adding to all loaded objects on read.
            self._object_attrs[name]=value
        else:
            super(baseFolder,self).__setattr__(name,value)



    ###########################################################################
    ###################### Private Methods ####################################
    
    def _update_from_object_attrs(self,object):
        """Updates an object from object_attrs store."""
        if hasattr(self,"_object_attrs") and isinstance(self._object_attrs,dict):
            for k in self._object_attrs:
                setattr(object,k,self._object_attrs[k])
        return object


    def _pruner_(self,grp,breadcrumb):
        """Removes any empty groups fromthe objectFolder tree."""
        if len(grp)==0:
            self._pruneable.append(breadcrumb)
            ret=True
        else:
            ret=False
        return ret

    def __walk_groups(self,walker,group=False,replace_terminal=False,only_terminal=True,walker_args={},breadcrumb=[]):
        """"Actually implements the walk_groups method,m but adds the breadcrumb list of groups that we've already visited.

        Args:
            walker (callable): a callable object that takes either a metadataObject instance or a objectFolder instance.

        Keyword Arguments:
            group (bool): (default False) determines whether the wealker function will expect to be given the objectFolder
                representing the lowest level group or individual metadataObject objects from the lowest level group
            replace_terminal (bool): if group is True and the walker function returns an instance of metadataObject then the return value is appended
                to the files and the group is removed from the current objectFolder. This will unwind the group heirarchy by one level.
            only_terminal (bool): Only iterate over the files in the group if the group has no sub-groups.
            walker_args (dict): a dictionary of static arguments for the walker function.
            bbreadcrumb (list of strings): a list of the group names or key values that we've walked through

        Notes:
            The walker function should have a prototype of the form:
                walker(f,list_of_group_names,**walker_args)
                where f is either a objectFolder or metadataObject."""
        if (len(self.groups)>0):
            ret=[]
            removeGroups=[]
            if replace_terminal:
                self.__clear__()
            for g in self.groups:
                bcumb=copy(breadcrumb)
                bcumb.append(g)
                tmp=self.groups[g].__walk_groups(walker,group=group,replace_terminal=replace_terminal,walker_args=walker_args,breadcrumb=bcumb)
                if group and  replace_terminal and isinstance (tmp, metadataObject):
                    removeGroups.append(g)
                    tmp.filename="{}-{}".format(g,tmp.filename)
                    self.append(tmp)
                    ret.append(tmp)
            for g in removeGroups:
                del(self.groups[g])
        elif len(self.groups)==0 or not only_terminal:
            if group:
                ret=walker(self,breadcrumb,**walker_args)
            else:
                ret=[walker(f,breadcrumb,**walker_args) for f in self]
        return ret


    ###########################################################################
    ############# Normal Methods ##############################################

    def add_group(self,key):
        """Add a new group to the current baseFolder with the given key.

        Args:
            key(string): A hashable value to be used as the dictionary key in the groups dictionary
        Returns:
            A copy of the objectFolder

        Note:
            If key already exists in the groups dictionary then no action is taken.

        Todo:
            Propagate any extra attributes into the groups.
        """
        if self.groups.has_key(key): # do nothing here
            pass
        else:
            new_group=self.__clone__()
            self.groups[key]=new_group
            self.groups[key].key=key
        return self

    def clear(self):
        """Clear the subgroups."""
        self.groups.clear()
        self.__clear__()

    def count(self,name):
        """Provide a count() method like a sequence.
        
        Args:
            name(str, regexp, or :py:class:`Stoner.Core.metadataObject`): The thing to count matches for.
            
        Returns:
            (int): The number of matching metadataObject instances.
            
        If *name* is a string, then matching is based on either exact matches of the name, or if it includes a * or ? then the basis of a globbing match.
        *name* may also be a regular expressiuon, in which case matches are made on the basis of  the match with the name of the metadataObject. Finally,
        if *name* is a metadataObject, then it matches for an equyality test."""
        if isinstance(name,string_types):
            if "*" in name or "?" in name: # globbing pattern
                return len(fnmatch.filter(self.__names__(),name))
            else:
                return self.__names__().count(self.__lookup__(name))
        if isinstance(name,re._pattern_type):
            match=[1 for n in self.__names__() if name.match(n)]
            return len(match)
        if isinstance(name,metadataObject):
            match=[1 for d in self if d==name ]
            return len(match)
            
    def filter(self, filter=None,  invert=False,copy=False):
        """Filter the current set of files by some criterion

        Args:
            filter (string or callable): Either a string flename pattern or a callable function which takes a single parameter x which is an instance of a metadataObject and evaluates True or False
            
        Keyword Arguments:
            invert (bool): Invert the sense of the filter (done by doing an XOR whith the filter condition
            copy (bool): If True, then a new copy of the current baseFolder is made before filtering.
            
        Returns:
            The current objectFolder object"""

        names=[]
        if copy:
            result=deepcopy(self)
        else:
            result=self
        if isinstance(filter, string_types):
            for f in result.__names__():
                if fnmatch.fnmatch(f, filter)  ^ invert:
                    names.append(result.__getter__(f))
        elif isinstance(filter, re._pattern_type):
            for f in result.__names__():
                if filter.search(f) is not None:
                    names.append(result.__getter__(f))
        elif filter is None:
            raise ValueError("A filter must be defined !")
        else:
            for i,x in enumerate(result):
                if filter(x)  ^ invert:
                    names.append(x)
        result.__clear__()
        result.extend(names)
        return result

    def filterout(self, filter):
        """Synonym for self.filter(filter,invert=True)

        Args:
        filter (string or callable): Either a string flename pattern or a callable function which takes a single parameter x which is an instance of a metadataObject and evaluates True or False

        Returns:
            The current objectFolder object with the files in the file list filtered."""
        return self.filter(filter, invert=True)

    def flatten(self, depth=None):
        """Compresses all the groups and sub-groups iunto a single flat file list.

        Keyword Arguments:
            depth )(int or None): Only flatten ub-=groups that are within (*depth* of the deepest level.

        Returns:
            A copy of the now flattened DatFolder"""
        if isinstance(depth,int):
            if self.depth<=depth:
                self.flatten()
            else:
                for g in self.groups:
                    self.groups[g].flatten(depth)
        else:
            for g in self.groups:
                self.groups[g].flatten()
                self.extend([
                    self.groups[g].__getter__(self.groups[g].__lookup__(n),instantiate=False)
                    for n in self.groups[g].__names__()])
            self.groups={}
        return self

    def get(self,name,default=None):
        """Return either a sub-group or named object from this folder."""
        try:
            ret=self[name]
        except (KeyError,IndexError):
            ret=default
        return ret

    def group(self, key):
        """Take the files and sort them into a series of separate objectFolder objects according to the value of the key

        Args:
            key (string or callable or list): Either a simple string or callable function or a list. If a string then it is interpreted as an item of metadata in each file. If a callable function then
                takes a single argument x which should be an instance of a metadataObject and returns some vale. If key is a list then the grouping is done recursively for each element
                in key.
        Returns:
            A copy of the current objectFolder object in which the groups attribute is a dictionary of objectFolder objects with sub lists of files

        If ne of the grouping metadata keys does not exist in one file then no exception is raised - rather the fiiles will be returned into the group with key None. Metadata keys that
        are generated from the filename are supported."""
        if isinstance(key, list):
            next_keys=key[1:]
            key=key[0]
        else:
            next_keys=[]
        if isinstance(key, string_types):
            k=key
            key=lambda x:x.get(k,"None")
        for x in self:
            v=key(x)
            if not self.groups.has_key(v):
                self.add_group(v)
            self.groups[v].append(x)
        self.__clear__()
        if len(next_keys)>0:
            for g in self.groups:
                self.groups[g].group(next_keys)
        return self
        
    def index(self,name):
        """Provide an index() method like a sequence.
        
        Args:
            name(str, regexp, or :py:class:`Stoner.Core.metadataObject`): The thing to search for.
            
        Returns:
            (int): The index of the first matching metadataObject instances.
            
        If *name* is a string, then matching is based on either exact matches of the name, or if it includes a * or ? then the basis of a globbing match.
        *name* may also be a regular expressiuon, in which case matches are made on the basis of  the match with the name of the metadataObject. Finally,
        if *name* is a metadataObject, then it matches for an equyality test."""
        if isinstance(name,string_types):
            if "*" in name or "?" in name: # globbing pattern
                m=fnmatch.filter(self.__names__(),name)
                if len(m)>0:
                    return self.__names__().index(m[0])
                else:
                    raise ValueError("{} is not a name of a metadataObject in this baseFolder.".format(name))
            else:
                return self.__names__().index(self.__lookup__(name))
        if isinstance(name,re._pattern_type):
            for i,n in enumerate(self.__names__()):
                if name.match(n): return i
            else:
                    raise ValueError("No match for any name of a metadataObject in this baseFolder.")
        if isinstance(name,metadataObject):
            for i,n in enumerate(self.__names__()):
                if name==n: return i
            else:
                    raise ValueError("No match for any name of a metadataObject in this baseFolder.")

    def insert(self,ix,value):
        """Implements the insert method with the option to append as well."""
        if -len(self)<ix<len(self):
            name=self.__names__()[ix]
            self.__setter__(self.__lookup__(name),value)
        elif ix>=len(self):
            name= self.make_name(value)
            i=1
            names=self.__names__()
            while name in names: # Since we're adding a new entry, make sure we have a unique name !
                name,ext=os.path.splitext(name)
                name="{}({}).{}".format(name,i,ext)
                i+=1
            self.__setter__(name,value)

    def items(self):
        """Return the key,value pairs for the subbroups of this folder."""
        return self.groups.items()

    def keys(self):
        """Return the keys used to access the sub-=groups of this folder."""
        return self.groups.keys()

    def make_name(self,value=None):
        """Construct a name from the value object if possible."""
        if isinstance(value,self.type):
            return value.filename
        elif isinstance(value,string_types):
            return value
        else:
            name="Untitled-{}".format(self._last_name)
            while name in self:
                self._last_name+=1
                name="Untitled-{}".format(self._last_name)
            return name
            
            
    def pop(self,name=-1,default=None):
        """Return and remove either a subgroup or named object from this folder."""
        try:
            ret=self[name]
            del self[name]
        except (KeyError,IndexError):
            ret=default
        return ret

    def popitem(self):
        """Return the most recent subgroup from this folder."""
        return self.groups.popitem()

    def prune(self):
        """Remove any groups from the objectFolder (and subgroups).

        Returns:
            A copy of thte pruned objectFolder."""

        self._pruneable=[] # slightly ugly to avoid modifying whilst iterating
        self.walk_groups(self._pruner_,group=True)
        while len(self._pruneable)!=0:
            for p in self._pruneable:
                pth=tuple(p[:-1])
                item=p[-1]
                if len(pth)==0:
                    del self[item]
                else:
                    grp=self[pth]
                    del grp[item]
            self._pruneable=[]
            self.walk_groups(self._pruner_,group=True)
        del self._pruneable
        return self

    def select(self,*args, **kargs):
        """A generator that can be used to select particular data files from the objectFolder

        Args:
            args (various): A single positional argument if present is interpreted as follows:

            * If a callable function is given, the entire metadataObject is presented to it.
                If it evaluates True then that metadataObject is selected. This allows arbitary select operations
            * If a dict is given, then it and the kargs dictionary are merged and used to select the metadataObjects

        Keyword Arguments:
            recurse (bool): Also recursively slect through the sub groups
            kargs (varuous): Arbitary keyword arguments are interpreted as requestion matches against the corresponding
                metadata values. The keyword argument may have an additional *__operator** appended to it which is interpreted
                as follows:

                - *eq* metadata value equals argument value (this is the default test for scalar argument)
                - *ne* metadata value doe not equal argument value
                - *gt* metadata value doe greater than argument value
                - *lt* metadata value doe less than argument value
                - *ge* metadata value doe greater than or equal to argument value
                - *le* metadata value doe less than or equal to argument value
                - *contains* metadata value contains argument value (this is the default test for non-tuple iterable arguments)
                - *startswith* metadata value startswith argument value
                - *endswith* metadata value endwith argument value
                - *icontains*,*istartswith*,*iendswith* as above but case insensitive
                - *between* metadata value lies beween the minimum and maximum values of the arguement (the default test for 2-length tuple arguments)
                - *ibetween*,*ilbetween*,*iubetween* as above but include both,lower or upper values

            The syntax is inspired by the Django project for selecting, but is not quite as rich.

        Returns:
            (baseFGolder): a new baseFolder instance that contains just the matching metadataObjects.

        Note:
            If any of the tests is True, then the metadataObject will be selected, so the effect is a logical OR. To
            achieve a logical AND, you can chain two selects together::

                d.select(temp__le=4.2,vti_temp__lt=4.2).select(field_gt=3.0)

            will select metadata objects that have either temp or vti_temp metadata values below 4.2 AND field metadata values greater than 3.

            If you need to select on a aparameter called *recurse*, pass a dictionary of {"recurse":value} as the sole
            positional argument. If you need to select on a metadata value that ends in an operator word, then append
            *__eq* in the keyword name to force the equality test. If the metadata keys to select on are not valid python identifiers,
            then pass them via the first positional dictionary value.
        """
        recurse=kargs.pop("recurse",False)
        if len(args)==1:
            if callable(args[0]):
                kargs["__"]=args[0]
            elif isinstance(args[0],dict):
                kargs.update(args[0])
        operator={
            "eq":lambda k,v:k==v,
            "ne":lambda k,v:k!=v,
            "contains":lambda k,v: k in v,
            "icontains":lambda k,v: k.upper() in str(v).upper(),
            "lt":lambda k,v:k<v,
            "le":lambda k,v:k<=v,
            "gt":lambda k,v:k>v,
            "ge":lambda k,v:k>=v,
            "between":lambda k,v: min(v)<k<max(v),
            "ibetween":lambda k,v: min(v)<=k<=max(v),
            "ilbetween":lambda k,v: min(v)<=k<max(v),
            "iubetween":lambda k,v: min(v)<k<=max(v),
            "startswith":lambda k,v:str(v).startswith(k),
            "istartswith":lambda k,v:str(v).upper().startswith(k.upper()),
            "endsswith":lambda k,v:str(v).endswith(k),
            "iendsswith":lambda k,v:str(v).upper().endswith(k.upper()),
        }
        result=self.__clone__
        if recurse:
            gkargs={}
            gkargs.update(kargs)
            gkargs["recurse"]=True
            for g in self.groups:
                result.groups[g]=self.groups[g].select(*args,**gkargs)
        for f in self:
            for arg in kargs:
                if callable(kargs[arg]) and kargs[arg](f):
                    break
                elif isinstance(arg,string_types):
                    parts=arg.split("__")
                    if parts[-1] in operator and len(parts)>1:
                        arg="__".join(parts[:-1])
                        op=parts[-1]
                    else:
                        if isinstance(kargs[arg],tuple) and len(kargs[arg]==2):
                            op="between" #Assume two length tuples are testing for range
                        elif not isinstance(kargs[arg],string_types) and isinstance(kargs[arg],Iterable):
                            op="contains" # Assume other iterables are testing for memebership
                        else: #Everything else is exact matches
                            op="eq"
                    func=operator[op]
                    if arg in f and func(kargs[arg],f[arg]):
                        break
            else: # No tests matched - contineu to next line
                continue
            #Something matched, so append to result
            result.append(f)
        return result

    def setdefault(self,k,d=None):
        """Return or set a subgroup or named object."""
        self[k]=self.get(k,d)
        return self[k]

    def sort(self, key=None, reverse=False):
        """Sort the files by some key

        Keyword Arguments:
            key (string, callable or None): Either a string or a callable function. If a string then this is interpreted as a
                metadata key, if callable then it is assumed that this is a a function of one paramater x
                that is a :py:class:`Stoner.Core.metadataObject` object and that returns a key value.
                If key is not specified (default), then a sort is performed on the filename

        reverse (bool): Optionally sort in reverse order

        Returns:
            A copy of the current objectFolder object"""
        if isinstance(key, string_types):
            k=[(x.get(key),i) for x,i in enumerate(self)]
            k=sorted(k,reverse=reverse)
            new_order=[self[i] for x,i in k]
        elif key is None:
            fnames=self.__names__()
            fnames.sort(reverse=reverse)
            new_order=[self.__getter__(name,instantiate=False) for name in fnames]
        elif isinstance(key,re._pattern_type):
            new_order=sorted(self,cmp=lambda x, y:cmp(key.match(x).groups(),key.match(y).groups()), reverse=reverse)
        else:
            order=range(len(self))
            if python_v3:
                new_order=sorted(order,key=lambda x:key(self[x]), reverse=reverse)
            else:
                new_order=sorted(order,cmp=lambda x, y:cmp(key(self[x]), key(self[y])), reverse=reverse)
            new_order=[self.__names__()[i] for i in new_order]
        self.__clear__()
        self.extend(new_order)
        return self

    def unflatten(self):
        """Takes a file list an unflattens them according to the file paths.

        Returns:
            A copy of the objectFolder
        """
        self.directory=path.commonprefix(self.__names__())
        if self.directory[-1]!=path.sep:
            self.directory=path.dirname(self.directory)
        relpaths=[path.relpath(f,self.directory) for f in self.__names__()]
        dels=list()
        for i,f in enumerate(relpaths):
            grp=path.split(f)[0]
            if grp!=f and grp!="":
                self.add_group(grp)
                self.groups[grp].append([i])
                dels.append(i)
        for i in sorted(dels,reverse=True):
            del self[i]
        for g in self.groups:
            self.groups[g].unflatten()
        return self
        
    def update(self,other):
        """Update this folder with a dictionary or another folder."""
        if isinstance(other,dict):
            for k in other:
                self[k]=other[k]
        elif isinstance(other,baseFolder):
            for k in other.groups:
                self.groups[k]=other.groups[k]
            for k in self.__names__():
                self.__setter__(self.__lookup__(k),other.__getter__(other.__lookup__(k)))

    def values(self):
        """Return the sub-groups of this folder."""
        return self.groups.values()

    def walk_groups(self, walker, group=False, replace_terminal=False,only_terminal=True,walker_args={}):
        """Walks through a heirarchy of groups and calls walker for each file.

        Args:
            walker (callable): a callable object that takes either a metadataObject instance or a objectFolder instance.

        Keyword Arguments:
            group (bool): (default False) determines whether the walker function will expect to be given the objectFolder
                representing the lowest level group or individual metadataObject objects from the lowest level group
            replace_terminal (bool): if group is True and the walker function returns an instance of metadataObject then the return value is appended
                to the files and the group is removed from the current objectFolder. This will unwind the group heirarchy by one level.
            obly_terminal(bool): Only execute the walker function on groups that have no sub-groups inside them (i.e. are terminal groups)
            walker_args (dict): a dictionary of static arguments for the walker function.

        Notes:
            The walker function should have a prototype of the form:
                walker(f,list_of_group_names,**walker_args)
                where f is either a objectFolder or metadataObject."""

        return self.__walk_groups(walker,group=group,replace_terminal=replace_terminal,only_terminal=only_terminal,walker_args=walker_args,breadcrumb=[])

    def zip_groups(self, groups):
        """Return a list of tuples of metadataObjects drawn from the specified groups

        Args:
            groups(list of strings): A list of keys of groups in the Lpy:class:`objectFolder`

        ReturnsL
            A list of tuples of groups of files: [(grp_1_file_1,grp_2_file_1....grp_n_files_1),(grp_1_file_2,grp_2_file_2....grp_n_file_2)....(grp_1_file_m,grp_2_file_m...grp_n_file_m)]
        """
        if not isinstance(groups, list):
            raise SyntaxError("groups must be a list of groups")
        grps=[[y for y in self.groups[x]] for x in groups]
        return zip(*grps)

class DiskBssedFolder(object):
    """A Mixin class that implmenets reading metadataObjects from disc.
    
    Attributes:
        type (:py:class:`Stoner.Core.metadataObject`) the type ob object to sotre in the folder (defaults to :py:class:`Stoner.Util.Data`)

        extra_args (dict): Extra arguments to use when instantiatoing the contents of the folder from a file on disk.

        pattern (str or regexp): A filename globbing pattern that matches the contents of the folder. If a regular expression is provided then
            any named groups are used to construct additional metadata entryies from the filename. Default is *.* to match all files with an extension.

        read_means (bool): IF true, additional metatdata keys are added that return the mean value of each column of the data. This can hep in
            grouping files where one column of data contains a constant value for the experimental state. Default is False

        recursive (bool): Specifies whether to search recurisvely in a whole directory tree. Default is True.

        flatten (bool): Specify where to present subdirectories as spearate groups in the folder (False) or as a single group (True). Default is False.
            The :py:meth:`DiskBasedFolder.flatten` method has the equivalent effect and :py:meth:`DiskBasedFolder.unflatten` reverses it.

        directory (str): The root directory on disc for the folder - by default this is the current working directory.

        multifile (boo): Whether to select individual files manually that are not (necessarily) in  a common directory structure.
        
        readlist (bool): Whether to read the directory immediately on creation. Default is True
        
        """
        
    _defaults={"type":None,
              "extra_args":dict(),
              "pattern":["*.*"],
              "read_means":False,
              "recursive":True,
              "flat":False,
              "directory":None,
              "multifile":False,
              "readlist":True,
              }


    def __init__(self,*args,**kargs):
        from Stoner import Data
        defaults=copy(self._defaults)
        if "directory" in defaults and defaults["directory"] is None:
            defaults["directory"]=os.getcwd()
        if "type" in defaults and defaults["type"] is None:
            defaults["type"]=Data
        for k in defaults:
            setattr(self,k,kargs.pop(k,defaults[k]))
        super(DiskBssedFolder,self).__init__(*args,**kargs) #initialise before __clone__ is called in getlist
        if self.readlist:
            self.getlist(directory=args[0])
        
        
    def __clone__(self,other=None):
        """Add something to stop clones from autolisting again."""
        if other is None:
            other=self.__class__(readlist=False)
        return super(DiskBssedFolder,self).__clone__(other=other)

    def _dialog(self, message="Select Folder",  new_directory=True):
        """Creates a directory dialog box for working with

        Keyword Arguments:
            message (string): Message to display in dialog
            new_directory (bool): True if allowed to create new directory

        Returns:
            A directory to be used for the file operation."""
        # Wildcard pattern to be used in file dialogs.
        if isinstance(self.directory, string_types):
            dirname = self.directory
        else:
            dirname = os.getcwd()
        if not self.multifile:
            mode="directory"
        else:
            mode="files"
        dlg = get_filedialog(what=mode)
        if len(dlg)!=0:
            if not self.multifile:
                self.directory = dlg
                ret=self.directory
            else:
                ret=None
        else:
            self.pattern=[path.basename(name) for name in dlg]
            self.directory = path.commonprefix(dlg)
            ret = self.directory
        return ret

    def _removeDisallowedFilenameChars(filename):
        """Utility method to clean characters in filenames

        Args:
            filename (string): filename to cleanse

        Returns:
            A filename with non ASCII characters stripped out
        """
        validFilenameChars = "-_.() %s%s" % (string.ascii_letters, string.digits)
        cleanedFilename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore')
        return ''.join(c for c in cleanedFilename if c in validFilenameChars)

    def _save(self,grp,trail,root=None):
        """Save a group of files to disc by calling the save() method on each file. This internal method is called by walk_groups in turn
        called from the public save() method. The trail of group keys is used to create a directory tree.

        Args:
            grp (:py:class:`objectFolder` or :py:calss:`Stoner.metadataObject`): A group or file to save
            trail (list of strings): the trail of paths used to get here
            root (string or None): a replacement root directory

        Returns:
            Saved Path
        """

        trail=[self._removeDisallowedFilenameChars(t) for t in trail]
        grp.filename=self._removeDisallowedFilenameChars(grp.filename)
        if root is None:
            root=self.directory

        pth=path.join(root,*trail)
        os.makesdirs(pth)
        grp.save(path.join(pth,grp.filename))
        return grp.filename
        
    def __add_core__(self,result,other):
        if isinstance(other,string_types):
            othername=path.join(self.directory,other)
            if path.exists(othername) and othername not in result:
                result.append(othername)
            else:
                raise RuntimeError("{} either does not exist of is already in the folder.".format(othername))
        else:
            return super(DiskBssedFolder,self).__add_core__(result,other)
        return result

    def __sub_core__(self,result,other):
        """Additional logic to check for match to basenames,"""
        if isinstance(other,string_types):
            if other in result.basenames and path.join(result.directory,other) in result.ls:
                other=path.join(result.directory,other)
                result.__deleter__(other)
                return result
        return super(DiskBssedFolder,self).__sub_core__(result,other)

        
    def __lookup__(self,name):
        if isinstance(name,string_types):
            if self.basenames.count(name)==1:
                return self.__names__()[self.basenames.index(name)]
            
        return super(DiskBssedFolder,self).__lookup__(name)
        
    def __getter__(self,name,instantiate=True):
        """Loads the specified name from a file on disk.

        Parameters:
            name (key type): The canonical mapping key to get the dataObject. By default
                the baseFolder class uses a :py:class:`regexpDict` to store objects in.

        Keyword Arguments:
            instatiate (bool): IF True (default) then always return a :py:class:`Stoner.Util.Data` object. If False,
                the __getter__ method may return a key that can be used by it later to actually get the
                :py:class:`Stoner.Util.Data` object.

        Returns:
            (metadataObject): The metadataObject
        """
        try:
            return super(DiskBssedFolder,self).__getter__(name,instantiate=instantiate)
        except (AttributeError,IndexError,KeyError):
            pass
        if not path.exists(name):
            name=path.join(self.directory,name)
        tmp= self.type(name,**self.extra_args)
        if not hasattr(tmp,"filename") or not isinstance(tmp.filename,string_types):
            tmp.filename=path.basename(name)
        for p in self.pattern:
            if isinstance(p,re._pattern_type) and (p.search(tmp.filename) is not None):
                m=p.search(tmp.filename)
                for k in m.groupdict():
                    tmp.metadata[k]=tmp.metadata.string_to_type(m.group(k))
        if self.read_means:
            if len(tmp)==0:
                pass
            elif len(tmp)==1:
                for h in tmp.column_headers:
                    tmp[h]=tmp.column(h)[0]
            else:
                for h in tmp.column_headers:
                    tmp[h]=_np_.mean(tmp.column(h))
        tmp['Loaded from']=tmp.filename
        tmp=self._update_from_object_attrs(tmp)
        self.__setter__(name,tmp)
        return tmp

    @property
    def basenames(self):
        """Returns a list of just the filename parts of the objectFolder."""
        ret=[]
        for x in self.__names__():
            ret.append(path.basename(x))
        return ret

    @property
    def pattern(self):
        return self._pattern

    @pattern.setter
    def pattern(self,value):
        """Sets the filename searching pattern(s) for the :py:class:`Stoner.Core.metadataObject`s."""
        if isinstance(value,string_types):
            self._pattern=(value,)
        elif isinstance(value,re._pattern_type):
            self._pattern=(value,)
        elif isinstance(value,Iterable):
            self._pattern=[x for x in value]
        else:
            raise ValueError("pattern should be a string, regular expression or iterable object not a {}".format(type(value)))


    def getlist(self, recursive=None, directory=None,flatten=None):
        """Scans the current directory, optionally recursively to build a list of filenames

        Keyword Arguments:
            recursive (bool): Do a walk through all the directories for files
            directory (string or False): Either a string path to a new directory or False to open a dialog box or not set in which case existing directory is used.
            flatten (bool): After scanning the directory tree, flaten all the subgroupos to make a flat file list. (this is the previous behaviour of
            :py:meth:`objectFolder.getlist()`)

        Returns:
            A copy of the current DataFoder directory with the files stored in the files attribute

        getlist() scans a directory tree finding files that match the pattern. By default it will recurse through the entire
        directory tree finding sub directories and creating groups in the data folder for each sub directory.
        """
        self.__clear__()
        if recursive is None:
            recursive=self.recursive
        if flatten is None:
            flatten=getattr(self,"flat",False) #ImageFolders don't have flat because it clashes with a numpy attribute
        if isinstance(directory,  bool) and not directory:
            self._dialog()
        elif isinstance(directory, string_types):
            self.directory=directory
            if self.multifile:
                self._dialog()
        if isinstance(self.directory, bool) and not self.directory:
            self._dialog()
        elif self.directory is None:
            self.directory=os.getcwd()
        root=self.directory
        dirs=[]
        files=[]
        for f in os.listdir(root):
            if path.isdir(path.join(root, f)):
                dirs.append(f)
            elif path.isfile(path.join(root, f)):
                files.append(f)
        for p in self.pattern: # pattern is a list of strings and regeps
            if isinstance(p,string_types):
                for f in fnmatch.filter(files, p):
                    self.append(path.join(root, f))
                    # Now delete the matched file from the list of candidates
                    #This stops us double adding fles that match multiple patterns
                    del(files[files.index(f)])
            if isinstance(p,re._pattern_type):
                matched=[]
                # For reg expts we iterate over all files, but we can't delete matched
                # files as we go as we're iterating over them - so we store the
                # indices and delete them later.
                for f in files:
                    if p.search(f):
                        self.__setter__(path.join(root,f),path.join(root,f))
                        matched.append(files.index(f))
                matched.sort(reverse=True)
                for i in matched: # reverse sort the matching indices to safely delete
                    del(files[i])
        if recursive:
            for d in dirs:
                if self.debug: print("Entering directory {}".format(d))
                self.add_group(d)
                self.groups[d].directory=path.join(root,d)
                self.groups[d].getlist(recursive=recursive,flatten=flatten)
        if flatten:
            self.flatten()
            #Now collapse out the common path in the names
            self.directory=path.commonprefix(self.__names__())
            if self.directory[-1]!=path.sep:
                self.directory=path.dirname(self.directory)
            relpaths=[path.relpath(f,self.directory) for f in self.__names__()]
            for n,o in zip(relpaths,self.__names__()):
                self.__setter__(n,self.__getter__(o))
                self.__deleter__(o)
        return self

    def save(self,root=None):
        """Save the entire data folder out to disc using the groups as a directory tree,
        calling the save method for each file in turn.

        Args:
            root (string): The root directory to start creating files and subdirectories under. If set to None or not specified, the current folder's
                diretory attribute will be used.
        Returns:
            A list of the saved files
        """
        return self.walk_groups(self._save,walker_args={"root",root})




class DataFolder(DiskBssedFolder,baseFolder):


    def __init__(self,*args,**kargs):
        from Stoner import Data
        self.type=kargs.pop("type",Data)
        super(DataFolder,self).__init__(*args,**kargs)

    def __read__(self,f):
        """Reads a single filename in and creates an instance of metadataObject.

        Args:
            f(string or :py:class:`Stoner.Core.metadataObject`): A filename or metadataObject object

        Returns:
            A metadataObject object

        Note:
             If self.pattern is a regular expression then use any named groups in it to create matadata from the
            filename. If self.read_means is true then create metadata from the mean of the data columns.
        """
        if isinstance(f,DataFile):
            return f
        tmp= self.type(f,**self.extra_args)
        if not isinstance(tmp.filename,string_types):
            tmp.filename=path.basename(f)
        for p in self.pattern:
            if isinstance(p,re._pattern_type) and (p.search(tmp.filename) is not None):
                m=p.search(tmp.filename)
                for k in m.groupdict():
                    tmp.metadata[k]=tmp.metadata.string_to_type(m.group(k))
        if self.read_means:
            if len(tmp)==0:
                pass
            elif len(tmp)==1:
                for h in tmp.column_headers:
                    tmp[h]=tmp.column(h)[0]
            else:
                for h in tmp.column_headers:
                    tmp[h]=_np_.mean(tmp.column(h))
        tmp['Loaded from']=tmp.filename
        for k in self._file_attrs:
            tmp.__setattr__(k,self._file_attrs[k])
        return tmp


    def concatentate(self,sort=None,reverse=False):
        """Concatentates all the files in a objectFolder into a single metadataObject like object.

        Keyword Arguments:
            sort (column index, None or bool, or clallable function): Sort the resultant metadataObject by this column (if a column index),
                or by the *x* column if None or True, or not at all if False. *sort* is passed directly to the eponymous method as the
                *order* paramter.
            reverse (bool): Reverse the order of the sort (defaults to False)

        Returns:
            The current objectFolder with only one metadataObject item containing all the data.
        """
        for d in self[1:]:
            self[0]+=d
        del self[1:]

        if not isinstance(sort,bool) or sort:
            if isinstance(sort, bool) or sort is None:
                sort=self[0].setas["x"]
            self[0].sort(order=sort,reverse=True)

        return self

    def extract(self,metadata):
        """Walks through the terminal group and gets the listed metadata from each file and constructsa replacement metadataObject.

        Args:
            metadata (list): List of metadata indices that should be used to construct the new data file.

        Returns:
            An instance of a metadataObject like object.
        """

        def _extractor(group,trail,metadata):

            results=group.type()
            results.metadata=group[0].metadata

            ok_data=list
            for m in metadata: # Sanity check the metadata to include
                try:
                    test=_np_.array(results[m])
                except:
                    continue
                else:
                    ok_data.append(m)
                    results.column_headers.extend([m]*len(test))

            row=_np_.array([])
            for d in group:
                for m in ok_data:
                    row=_np_.append(row,_np_array(d[m]))
                results+=row

            return results

        return self.walk_groups(_extractor,group=True,replace_terminal=True,walker_args={"metadata":metadata})

    def gather(self,xcol=None,ycol=None):
        """Collects xy and y columns from the subfiles in the final group in the tree and builds iunto a :py:class:`Stoner.Core.metadataObject`

        Keyword Arguments:
            xcol (index or None): Column in each file that has x data. if None, then the setas settings are used
            ycol (index or None): Column(s) in each filwe that contain the y data. If none, then the setas settings are used.

        Notes:
            This is a wrapper around walk_groups that assembles the data into a single file for further analysis/plotting.

        """
        def _gatherer(group,trail,xcol=None,ycol=None):
            yerr=None
            xerr=None
            if xcol is None and ycol is None:
                lookup=True
                cols=group[0]._get_cols()
                xcol=cols["xcol"]
                ycol=cols["ycol"]
                if  cols["has_xerr"]:
                    xerr=cols["xerr"]
                if cols["has_yerr"]:
                    yerr=cols["yerr"]
            else:
                lookup=False

            xcol=group[0].find_col(xcol)
            ycol=group[0].find_col(ycol)

            results=group.type()
            results.metadata=group[0].metadata
            xbase=group[0].column(xcol)
            xtitle=group[0].column_headers[xcol]
            results&=xbase
            results.column_headers[0]=xtitle
            setas=["x"]
            if cols["has_xerr"]:
                xerrdata=group[0].column(xerr)
                results&=xerrdata
                results.column_headers[-1]="Error in {}".format(xtitle)
                setas.append("d")
            for f in group:
                if lookup:
                    cols=f._get_cols()
                    xcol=cols["xcol"]
                    ycol=cols["ycol"]
                    zcol=cols["zcol"]
                xdata=f.column(xcol)
                ydata=f.column(ycol)
                if _np_.any(xdata!=xbase):
                    results&=xdata
                    results.column_headers[-1]="{}:{}".format(path.basename(f.filename),f.column_headers[xcol])
                    xbase=xdata
                    setas.append("x")
                    if cols["has_xerr"]:
                        xerr=cols["xerr"]
                        if _np_.any(f.column(xerr)!=xerrdata):
                            xerrdata=f.column(xerr)
                            results&=xerrdata
                            results.column_headers[-1]="{}:{}".format(path.basename(f.filename),f.column_headers[xerr])
                            setas.append("d")
                for i in range(len(ycol)):
                    results&=ydata[:,i]
                    setas.append("y")
                    results.column_headers[-1]="{}:{}".format(path.basename(f.filename),f.column_headers[ycol[i]])
                    if cols["has_yerr"]:
                        yerr=cols["yerr"][i]
                        results&=f.column(yerr)
                        results.column_headers[-1]="{}:{}".format(path.basename(f.filename),f.column_headers[yerr])
                        setas.append("e")
                if len(zcol)>0:
                    zdata=f.column(zcol)
                    for i in range(len(zcol)):
                        results&=zdata[:,i]
                        setas.append("z")
                        results.column_headers[-1]="{}:{}".format(path.basename(f.filename),f.column_headers[zcol[i]])
                        if cols["has_zerr"]:
                            zerr=cols["zerr"][i]
                            results&=f.column(zerr)
                            results.column_headers[-1]="{}:{}".format(path.basename(f.filename),f.column_headers[zerr])
                            setas.append("f")
            results.setas=setas
            return results

        return self.walk_groups(_gatherer,group=True,replace_terminal=True,walker_args={"xcol":xcol,"ycol":ycol})

objectFolder=DataFolder # Just a backwards compatibility shim

class PlotFolder(DataFolder):
    """A subclass of :py:class:`objectFolder` with extra methods for plotting lots of files."""

    def plot(self,*args,**kargs):
        """Call the plot method for each metadataObject, but switching to a subplot each time.

        Args:
            args: Positional arguments to pass through to the :py:meth:`Stoner.plot.PlotMixin.plot` call.
            kargs: Keyword arguments to pass through to the :py:meth:`Stoner.plot.PlotMixin.plot` call.

        Returns:
            A list of :py:class:`matplotlib.pyplot.Axes` instances.

        Notes:
            If the underlying type of the :py:class:`Stoner.Core.metadataObject` instances in the :py:class:`PlotFolder`
            lacks a **plot** method, then the instances are converted to :py:class:`Stoner.Util.Data`.

            Each plot is generated as sub-plot on a page. The number of rows and columns of subplots is computed
            from the aspect ratio of the figure and the number of files in the :py:class:`PlotFolder`.
        """
        plts=len(self)

        if not hasattr(self.type,"plot"): # switch the objects to being Stoner.Data instances
            from Stoner import Data
            for i,d in enumerate(self):
                self[i]=Data(d)

        fig_num=kargs.pop("figure",None)
        fig_args={}
        for arg in ("figsize", "dpi", "facecolor", "edgecolor", "frameon", "FigureClass"):
            if arg in kargs:
                fig_args[arg]=kargs.pop(arg)
        if fig_num is None:
            fig=plt.figure(**fig_args)
        else:
            fig=plt.figure(fig_num,**fig_args)
        w,h=fig.get_size_inches()
        plt_x=_np_.floor(_np_.sqrt(plts*w/h))
        plt_y=_np_.ceil(plts/plt_x)

        kargs["figure"]=fig
        ret=[]
        for i,d in enumerate(self):
            ax=plt.subplot(plt_y,plt_x,i+1)
            ret.append(d.plot(*args,**kargs))
        plt.tight_layout()
        return ret