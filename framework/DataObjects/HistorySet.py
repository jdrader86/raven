
# Copyright 2017 Battelle Energy Alliance, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Created on Feb 16, 2013

@author: alfoa
"""
#for future compatibility with Python 3--------------------------------------------------------------
from __future__ import division, print_function, unicode_literals, absolute_import
import warnings
warnings.simplefilter('default',DeprecationWarning)
if not 'xrange' in dir(__builtins__):
  xrange = range
#End compatibility block for Python 3----------------------------------------------------------------

#External Modules------------------------------------------------------------------------------------
import copy
import itertools
import numpy as np
import os
from scipy import spatial
#External Modules End--------------------------------------------------------------------------------

#Internal Modules------------------------------------------------------------------------------------
from utils.cached_ndarray import c1darray
from .Data import Data, NotConsistentData, ConstructError
from utils import utils,mathUtils
import Files
#Internal Modules End--------------------------------------------------------------------------------

class HistorySet(Data):
  """
    HistorySet is an object that stores multiple sets of inputs and associated history for output parameters.
  """
  def __init__(self):
    """
      Constructor
      @ In, None
      @ Out, None
    """
    Data.__init__(self)

  def _specializedInputCheckParam(self,paramInput):
    """
      Here we check if the parameters read by the global reader are compatible with this type of Data
      @ In, paramInput, ParameterInput, the input
      @ Out, None
    """
    if set(self._dataParameters.keys()).issubset(['operator','outputRow']):
      self.raiseAnError(IOError,"Inputted operator or outputRow attributes are available for Point and PointSet only!")

  def addSpecializedReadingSettings(self):
    """
      This function adds in the _dataParameters dictionary the options needed for reading and constructing this class
      @ In,  None
      @ Out, None
    """
    if self._dataParameters['hierarchical']:
      self._dataParameters['type'] = 'History'
    else:
      self._dataParameters['type'] = self.type # store the type into the _dataParameters dictionary
    if hasattr(self._toLoadFromList[-1],'type'):
      sourceType = self._toLoadFromList[-1].type
    else:
      sourceType = None
    if('HDF5' == sourceType):
      self._dataParameters['type']      =  self.type
      self._dataParameters['filter'   ] = 'whole'

  def checkConsistency(self):
    """
      This method performs the consistency check for the structured data HistorySet
      @ In,  None
      @ Out, None
    """
    sourceType = self._toLoadFromList[-1].type
    lenMustHave = self.numAdditionalLoadPoints
    # here we assume that the outputs are all read....so we need to compute the total number of time point sets
    if self._dataParameters['hierarchical']:
      for key in self._dataContainer['inputs'].keys():
        if (self._dataContainer['inputs'][key].size) != 1:
          self.raiseAnError(NotConsistentData,'The input parameter value, for key ' + key + ' has not a consistent shape for History in HistorySet ' + self.name + '!! It should be a single value since we are in hierarchical mode.' + '.Actual size is ' + str(len(self._dataContainer['inputs'][key])))
      for key in self._dataContainer['outputs'].keys():
        if (self._dataContainer['outputs'][key].ndim) != 1:
          self.raiseAnError(NotConsistentData,'The output parameter value, for key ' + key + ' has not a consistent shape for History in HistorySet ' + self.name + '!! It should be an 1D array since we are in hierarchical mode.' + '.Actual dimension is ' + str(self._dataContainer['outputs'][key].ndim))
    else:
      if(lenMustHave != len(self._dataContainer['inputs'].keys())):
        self.raiseAnError(NotConsistentData,'Number of HistorySet contained in HistorySet data ' + self.name + ' != number of loading sources!!! ' + str(lenMustHave) + ' !=' + str(len(self._dataContainer['inputs'].keys())))
      for key in self._dataContainer['inputs'].keys():
        for key2 in self._dataContainer['inputs'][key].keys():
          if (self._dataContainer['inputs'][key][key2].size) != 1:
            self.raiseAnError(NotConsistentData,'The input parameter value, for key ' + key2 + ' has not a consistent shape for History ' + key + ' contained in HistorySet ' +self.name+ '!! It should be a single value.' + '.Actual size is ' + str(len(self._dataContainer['inputs'][key][key2])))
      for key in self._dataContainer['outputs'].keys():
        for key2 in self._dataContainer['outputs'][key].keys():
          if (self._dataContainer['outputs'][key][key2].ndim) != 1:
            self.raiseAnError(NotConsistentData,'The output parameter value, for key ' + key2 + ' has not a consistent shape for History ' + key + ' contained in HistorySet ' +self.name+ '!! It should be an 1D array.' + '.Actual dimension is ' + str(self._dataContainer['outputs'][key][key2].ndim))

  def _updateSpecializedInputValue(self,name,value,options=None):
    """
      This function performs the updating of the values (input space) into this Data
      @ In,  name, either 1) list (size = 2), name[0] == history number(ex. 1 or 2 etc) - name[1], parameter name (ex. cladTemperature)
                       or 2) string, parameter name (ex. cladTemperature) -> in this second case,the parameter is added in the last history (if not present),
                                                                             otherwise a new history is created and the new value is inserted in it
      @ In, value, newer value
      @ Out, None
    """

    ## Check if we need to reduce the dataset
    value = np.atleast_1d(value).flatten()
    rows = None
    if self._dataParameters is not None:
      rows = self._dataParameters.get('inputRow', None)
    if rows is None:
      rows = range(len(value))
    else:
      if rows > len(value):
        rows = range(len(value))
        self.raiseAWarning("inputRow > len of history! Taking last row!")

    value = value[rows]

    # if this flag is true, we accept realizations in the input space that are not only scalar but can be 1-D arrays!
    #acceptArrayRealizations = False if options == None else options.get('acceptArrayRealizations',False)
    unstructuredInput = False
    if isinstance(value,np.ndarray):
      if value.shape == (): #can't cast single-entry ND array into a c1darray, so make it into a single entry
        value = value.dtype.type(value)
      else:
        value = c1darray(values=value)
    if not isinstance(value,(float,int,bool,c1darray)):
      self.raiseAnError(NotConsistentData,'HistorySet Data accepts only a numpy array  or a single value for method <_updateSpecializedInputValue>. Got type ' + str(type(value)))
    if isinstance(value,c1darray):
      if np.asarray(value).ndim > 1 and max(value.values.shape) != np.asarray(value).size:
        self.raiseAnError(NotConsistentData,'HistorySet Data accepts only a 1 Dimensional numpy array or a single value for method <_updateSpecializedInputValue>. Array shape is ' + str(value.shape))
      #if value.size != 1 and not acceptArrayRealizations: self.raiseAnError(NotConsistentData,'HistorySet Data accepts only a numpy array of dim 1 or a single value for method <_updateSpecializedInputValue>. Size is ' + str(value.size))
      unstructuredInput = True if value.size > 1 else False
    containerType = 'inputs' if not unstructuredInput else 'unstructuredInputs'
    if options and self._dataParameters['hierarchical']:
      # we retrieve the node in which the specialized 'History' has been stored
      parentID = None
      if type(name) == list:
        namep = name[1]
        if type(name[0]) == str:
          nodeId = name[0]
        else:
          if 'metadata' in options.keys():
            nodeId = options['metadata']['prefix']
            if 'parentID' in options['metadata'].keys():
              parentID = options['metadata']['parentID']
          else:
            nodeId = options['prefix']
            if 'parentID' in options.keys():
              parentID = options['parentID']
      else:
        if 'metadata' in options.keys():
          nodeId = options['metadata']['prefix']
          if 'parentID' in options['metadata'].keys():
            parentID = options['metadata']['parentID']
        else:
          nodeId = options['prefix']
          if 'parentID' in options.keys():
            parentID = options['parentID']
        namep = name
      if parentID:
        tsnode = self.retrieveNodeInTreeMode(nodeId, parentID)
      else:
        tsnode = self.retrieveNodeInTreeMode(nodeId)
      self._dataContainer = tsnode.get('dataContainer')
      if not self._dataContainer:
        tsnode.add('dataContainer',{'inputs':{},'unstructuredInputs':{},'outputs':{}})
        self._dataContainer = tsnode.get('dataContainer')
      if namep in self._dataContainer[containerType].keys():
        self._dataContainer[containerType].pop(name)
      if namep not in self._dataParameters['inParam']:
        self._dataParameters['inParam'].append(namep)
      self._dataContainer[containerType][namep] = c1darray(values=np.ravel(value)) # np.atleast_1d(np.array(value))
      self.addNodeInTreeMode(tsnode,options)
    else:
      if type(name) == list:
        # there are info regarding the history number
        if name[0] in self._dataContainer[containerType].keys():
          gethistory = self._dataContainer[containerType].pop(name[0])
          gethistory[name[1]] = c1darray(values=np.ravel(np.array(value,dtype=float)))
          self._dataContainer[containerType][name[0]] = gethistory
        else:
          self._dataContainer[containerType][name[0]] = {name[1]:c1darray(values=np.ravel(np.array(value,dtype=float)))}
      else:
        # no info regarding the history number => use internal counter
        if len(self._dataContainer[containerType].keys()) == 0:
          self._dataContainer[containerType][1] = {name:c1darray(values=np.ravel(np.array(value,dtype=float)))}
        else:
          hisn = max(self._dataContainer[containerType].keys())
          if name in list(self._dataContainer[containerType].values())[-1]:
            hisn += 1
            self._dataContainer[containerType][hisn] = {}
          self._dataContainer[containerType][hisn][name] = c1darray(values=np.ravel(np.array(value,dtype=float))) # np.atleast_1d(np.array(value))

  def _updateSpecializedMetadata(self,name,value,valueType,options=None):
    """
      This function performs the updating of the values (metadata) into this Data
      @ In, name, string, parameter name (ex. probability)
      @ In, value, object, newer value
      @ In, valueType, dtype, the value type
      @ Out, None
      NB. This method, if the metadata name is already present, replaces it with the new value. No appending here, since the metadata are dishomogenius and a common updating strategy is not feasable.
    """
    if options and self._dataParameters['hierarchical']:
      # we retrieve the node in which the specialized 'Point' has been stored
      parentID = None
      if type(name) == list:
        if type(name[0]) == str:
          nodeId = name[0]
        else:
          if 'metadata' in options.keys():
            nodeId = options['metadata']['prefix']
            if 'parentID' in options['metadata'].keys():
              parentID = options['metadata']['parentID']
          else:
            nodeId = options['prefix']
            if 'parentID' in options.keys():
              parentID = options['parentID']
      else:
        if 'metadata' in options.keys():
          nodeId = options['metadata']['prefix']
          if 'parentID' in options['metadata'].keys():
            parentID = options['metadata']['parentID']
        else:
          nodeId = options['prefix']
          if 'parentID' in options.keys():
            parentID = options['parentID']
      if parentID:
        tsnode = self.retrieveNodeInTreeMode(nodeId, parentID)
      self._dataContainer = tsnode.get('dataContainer')
      if not self._dataContainer:
        tsnode.add('dataContainer',{'metadata':{}})
        self._dataContainer = tsnode.get('dataContainer')
      else:
        if 'metadata' not in self._dataContainer.keys():
          self._dataContainer['metadata'] ={}
      if name in self._dataContainer['metadata'].keys():
        self._dataContainer['metadata'][name].append(np.atleast_1d(np.array(value)))
      else:
        valueToAdd = np.array(value,dtype=valueType) if valueType is not None else np.array(value)
        self._dataContainer['metadata'][name] = copy.copy(c1darray(values=np.atleast_1d(valueToAdd)))
      self.addNodeInTreeMode(tsnode,options)
    else:
      if name in self._dataContainer['metadata'].keys():
        self._dataContainer['metadata'][name].append(np.atleast_1d(value))
      else:
        valueToAdd = np.array(value,dtype=valueType) if valueType is not None else np.array(value)
        self._dataContainer['metadata'][name] = copy.copy(c1darray(values=np.atleast_1d(valueToAdd)))

  def _updateSpecializedOutputValue(self,name,value,options=None):
    """
      This function performs the updating of the values (output space) into this Data
      @ In,  name, either 1) list (size = 2), name[0] == history number(ex. 1 or 2 etc) - name[1], parameter name (ex. cladTemperature)
                       or 2) string, parameter name (ex. cladTemperature) -> in this second case,the parameter is added in the last history (if not present),
                                                                             otherwise a new history is created and the new value is inserted in it
      @ In, value, ?, ?
      @ Out, None
    """

    ## Check if we need to reduce the dataset
    value = np.atleast_1d(value).flatten()
    rows = None
    if self._dataParameters is not None:
      rows = self._dataParameters.get('outputRow', None)
    if rows is None:
      rows = range(len(value))
    else:
      if rows > len(value):
        rows = range(len(value))
        self.raiseAWarning("inputRow > len of history! Taking last row!")
    value = np.atleast_1d(value[rows])

    if isinstance(value,np.ndarray):
      value = c1darray(values=value)
    if not isinstance(value,c1darray):
      self.raiseAnError(NotConsistentData,'HistorySet Data accepts only cached_ndarray as type for method <_updateSpecializedOutputValue>. Got ' + str(type(value)))

    if options and self._dataParameters['hierarchical']:
      parentID = None
      if type(name) == list:
        namep = name[1]
        if type(name[0]) == str:
          nodeId = name[0]
        else:
          if 'metadata' in options.keys():
            nodeId = options['metadata']['prefix']
            if 'parentID' in options['metadata'].keys():
              parentID = options['metadata']['parentID']
          else:
            nodeId = options['prefix']
            if 'parentID' in options.keys():
              parentID = options['parentID']
      else:
        if 'metadata' in options.keys():
          nodeId = options['metadata']['prefix']
          if 'parentID' in options['metadata'].keys():
            parentID = options['metadata']['parentID']
        else:
          nodeId = options['prefix']
          if 'parentID' in options.keys():
            parentID = options['parentID']
        namep = name
      if parentID:
        tsnode = self.retrieveNodeInTreeMode(nodeId, parentID)

      # we store the pointer to the container in the self._dataContainer because checkConsistency acts on this
      self._dataContainer = tsnode.get('dataContainer')
      if not self._dataContainer:
        tsnode.add('dataContainer',{'inputs':{},'outputs':{}})
        self._dataContainer = tsnode.get('dataContainer')
      if namep in self._dataContainer['outputs'].keys():
        self._dataContainer['outputs'].pop(namep)
      if namep not in self._dataParameters['outParam']:
        self._dataParameters['outParam'].append(namep)
      self._dataContainer['outputs'][namep] = c1darray(values=np.atleast_1d(np.array(value,dtype=float)))
      self.addNodeInTreeMode(tsnode,options)
    else:
      resultsArray = c1darray(values=np.atleast_1d(np.array(value,dtype=float)))
      if type(name) == list:
        # there are info regarding the history number
        try:
          self._dataContainer['outputs'][name[0]][name[1]] = resultsArray
        except KeyError:
          self._dataContainer['outputs'][name[0]] = {name[1]:resultsArray}
      else:
        # no info regarding the history number => use internal counter
        if len(self._dataContainer['outputs']) == 0:
          self._dataContainer['outputs'][1] = {name:resultsArray}
        else:
          hisn = max(self._dataContainer['outputs'].keys())
          if name in list(self._dataContainer['outputs'].values())[-1]:
            hisn += 1
            self._dataContainer['outputs'][hisn] = {}
          self._dataContainer['outputs'][hisn][name] = copy.copy(resultsArray) #FIXME why deepcopy here but not elsewhere?

  def specializedPrintCSV(self,filenameLocal,options):
    """
      This function prints a CSV file with the content of this class (Input and Output space)
      @ In,  filenameLocal, string, filename root (for example, 'homo_homini_lupus' -> the final file name is going to be called 'homo_homini_lupus.csv')
      @ In,  options, dictionary, dictionary of printing options
      @ Out, None (a csv is gonna be printed)
    """

    if self._dataParameters['hierarchical']:
      outKeys   = []
      inpKeys   = []
      inpValues = []
      outValues = []
      # retrieve a serialized of DataObjects from the tree
      O_o = self.getHierParam('inout','*',serialize=True)
      for key in O_o.keys():
        inpKeys.append([])
        inpValues.append([])
        outKeys.append([])
        outValues.append([])
        if 'what' in options.keys():
          for var in options['what']:
            splitted = var.split('|')
            variableName = "|".join(splitted[1:])
            varType = splitted[0]
            if varType == 'input':
              if variableName not in self.getParaKeys('input'):
                self.raiseAnError(Exception,"variable named "+variableName+" is not among the "+varType+"s!")
              inpKeys[-1].append(variableName)
              axa = np.zeros(len(O_o[key]))
              for index in range(len(O_o[key])):
                axa[index] = O_o[key][index]['inputs'][variableName][0]
              inpValues[-1].append(axa)
            if varType == 'output':
              if variableName not in self.getParaKeys('output'):
                self.raiseAnError(Exception,"variable named "+variableName+" is not among the "+varType+"s!")
              outKeys[-1].append(variableName)
              axa = O_o[key][0]['outputs'][variableName]
              for index in range(len(O_o[key])-1):
                axa = np.concatenate((axa,O_o[key][index+1]['outputs'][variableName]))
              outValues[-1].append(axa)
        else:
          inpKeys[-1] = O_o[key][0]['inputs'].keys()
          outKeys[-1] = O_o[key][0]['outputs'].keys()
          for var in O_o[key][0]['inputs'].keys():
            axa = np.zeros(len(O_o[key]))
            for index in range(len(O_o[key])):
              axa[index] = O_o[key][index]['inputs'][var][0]
            inpValues[-1].append(axa)
          for var in O_o[key][0]['outputs'].keys():
            axa = O_o[key][0]['outputs'][var]
            for index in range(len(O_o[key])-1):
              axa = np.concatenate((axa,O_o[key][index+1]['outputs'][var]))
            outValues[-1].append(axa)

        if len(inpKeys) > 0 or len(outKeys) > 0:
          myFile = open(filenameLocal + '_' + key + '.csv', 'w')
        else:
          return
        myFile.write('Ending branch,'+key+'\n')
        myFile.write('branch #')
        for item in inpKeys[-1]:
          myFile.write(',' + item)
        myFile.write('\n')
        # write the input paramters' values for each branch
        for i in range(inpValues[-1][0].size):
          myFile.write(str(i+1))
          for index in range(len(inpValues[-1])):
            myFile.write(',' + str(inpValues[-1][index][i]))
          myFile.write('\n')
        # write out keys
        myFile.write('\n')
        myFile.write('TimeStep #')
        for item in outKeys[-1]:
          myFile.write(',' + item)
        myFile.write('\n')
        for i in range(outValues[-1][0].size):
          myFile.write(str(i+1))
          for index in range(len(outValues[-1])):
            myFile.write(',' + str(outValues[-1][index][i]))
          myFile.write('\n')
        myFile.close()
    else:
      #if not hierarchical
      #For HistorySet, create an XML file, and multiple CSV
      #files.  The first CSV file has a header with the input names,
      #and a column for the filenames.  There is one CSV file for each
      #data line in the first CSV and they are named with the
      #filename.  They have the output names for a header, a column
      #for time, and the rest of the file is data for different times.
      inpValues = list(self._dataContainer['inputs'].values())
      outKeys   = self._dataContainer['outputs'].keys()
      outValues = list(self._dataContainer['outputs'].values())
      unstructuredInpKeys   = self._dataContainer['unstructuredInputs'].keys()
      unstructuredInpValues = list(self._dataContainer['unstructuredInputs'].values())
      #Create Input file
      myFile = open(filenameLocal + '.csv','w')
      if len(unstructuredInpValues) > 0 and len(unstructuredInpValues[0].keys())>0:
        unstructuredInpKeysFiltered, unstructuredInpValuesFiltered = [], []
      else:
        unstructuredInpKeysFiltered, unstructuredInpValuesFiltered = None, None
      for n in range(len(outKeys)):
        inpKeys_h   = []
        inpValues_h = []
        outKeys_h   = []
        outValues_h = []
        if unstructuredInpKeysFiltered is not None:
          unstructuredInpKeysFiltered.append([])
          unstructuredInpValuesFiltered.append([])

        if 'what' in options.keys():
          for var in options['what']:
            splitted = var.split('|')
            variableName = "|".join(splitted[1:])
            varType = splitted[0]
            if varType == 'input':
              if variableName not in self.getParaKeys('input'):
                self.raiseAnError(Exception,"variable named "+variableName+" is not among the "+varType+"s!")
              if variableName in inpValues[n].keys():
                inpKeys_h.append(variableName)
                inpValues_h.append(inpValues[n][variableName])
              else:
                if unstructuredInpKeysFiltered is not None:
                  unstructuredInpKeysFiltered[n].append(variableName)
                  unstructuredInpValuesFiltered[n].append(unstructuredInpValues[n][variableName])
                else:
                  self.raiseAnError(Exception,"variable named "+variableName+" is not among the "+varType+"s!")
            if varType == 'output':
              if variableName not in self.getParaKeys('output'):
                self.raiseAnError(Exception,"variable named "+variableName+" is not among the "+varType+"s!")
              outKeys_h.append(variableName)
              outValues_h.append(outValues[n][variableName])
        else:
          inpKeys_h   = list(inpValues[n].keys())
          inpValues_h = list(inpValues[n].values())
          if unstructuredInpKeysFiltered is not None:
            unstructuredInpKeysFiltered[n] = list(unstructuredInpValues[n].keys())
            unstructuredInpValuesFiltered[n] =  list(unstructuredInpValues[n].values())
          outKeys_h   = list(outValues[n].keys())
          outValues_h = list(outValues[n].values())

        dataFilename = filenameLocal + '_'+ str(n) + '.csv'
        if len(inpKeys_h) > 0 or len(outKeys_h) > 0:
          myDataFile = open(dataFilename, 'w')
        else:
          return #XXX should this just skip this iteration?

        #Write header for main file
        if n == 0:
          myFile.write(','.join([item for item in itertools.chain(inpKeys_h,['filename'])]))
          myFile.write('\n')
          self._createXMLFile(filenameLocal,'HistorySet',inpKeys_h,outKeys_h)
        myFile.write(','.join([str(item[0]) for item in
                                itertools.chain(inpValues_h,[[dataFilename]])]))
        myFile.write('\n')
        #Data file
        #Print time + output values
        myDataFile.write(','.join([item for item in outKeys_h]))
        if len(outKeys_h) > 0:
          myDataFile.write('\n')
          for j in range(outValues_h[0].size):
            myDataFile.write(','.join([str(item[j]) for item in
                                    outValues_h]))
            myDataFile.write('\n')
        myDataFile.close()
      myFile.close()
      if unstructuredInpKeysFiltered is not None and len(unstructuredInpKeysFiltered) > 0:
        # write unstructuredData
        self._writeUnstructuredInputInXML(filenameLocal +'_unstructured_inputs',unstructuredInpKeysFiltered,unstructuredInpValuesFiltered)

  def _specializedLoadXMLandCSV(self, filenameRoot, options):
    """
      Function to load the xml additional file of the csv for data
      (it contains metadata, etc). It must be implemented by the specialized classes
      @ In, filenameRoot, string, file name root
      @ In, options, dict, dictionary -> options for loading
      @ Out, None
    """
    #For HistorySet, create an XML file, and multiple CSV
    #files.  The first CSV file has a header with the input names,
    #and a column for the filenames.  There is one CSV file for each
    #data line in the first CSV and they are named with the
    #filename.  They have the output names for a header, a column
    #for time, and the rest of the file is data for different times.
    if options is not None and 'fileToLoad' in options.keys():
      name = os.path.join(options['fileToLoad'].getPath(),options['fileToLoad'].getBase())
    else:
      name = self.name

    filenameLocal = os.path.join(filenameRoot,name)

    if os.path.isfile(filenameLocal+'.xml'):
      xmlData = self._loadXMLFile(filenameLocal)
      assert(xmlData["fileType"] == "HistorySet")
      if "metadata" in xmlData:
        self._dataContainer['metadata'] = xmlData["metadata"]
      mainCSV = os.path.join(filenameRoot,xmlData["filenameCSV"])
    else:
      mainCSV = os.path.join(filenameRoot,name+'.csv')

    myFile = open(mainCSV,"rU")
    header = myFile.readline().rstrip()
    inpKeys = header.split(",")[:-1]
    inpValues = []
    outKeys   = []
    outValues = []
    allLines  = myFile.readlines()
    for mainLine in allLines:
      mainLineList = mainLine.rstrip().split(",")
      inpValues_h = [utils.partialEval(a) for a in mainLineList[:-1]]
      inpValues.append(inpValues_h)
      dataFilename = mainLineList[-1]
      subCSVFilename = os.path.join(filenameRoot,dataFilename)
      subCSVFile = Files.returnInstance("CSV", self)
      subCSVFile.setFilename(subCSVFilename)
      self._toLoadFromList.append(subCSVFile)
      with open(subCSVFilename, "rU") as myDataFile:
        header = myDataFile.readline().rstrip()
        outKeys_h = header.split(",")
        outValues_h = [[] for a in range(len(outKeys_h))]
        for lineNumber,line in enumerate(myDataFile.readlines(),2):
          lineList = line.rstrip().split(",")
          for i in range(len(outKeys_h)):
            datum = utils.partialEval(lineList[i])
            if datum == '':
              self.raiseAnError(IOError, 'Invalid data in input file: {} at line {}: "{}"'.format(subCSVFilename,lineNumber,line.rstrip()))
            outValues_h[i].append(datum)
        myDataFile.close()
      outKeys.append(outKeys_h)
      outValues.append(outValues_h)


    ## Do not reset these containers because it will wipe whatever information
    ## already exists in this HistorySet. This is not one of the use cases for
    ## our data objects. We claim in the manual to construct or update
    ## information. These should be non-destructive operations. -- DPM 6/26/17
    # self._dataContainer['inputs'] = {} #XXX these are indexed by 1,2,...
    # self._dataContainer['outputs'] = {} #XXX these are indexed by 1,2,...
    startKey = len(self._dataContainer['inputs'].keys())
    for i in range(len(inpValues)):
      mainKey = startKey + i + 1
      subInput = {}
      subOutput = {}
      for key,value in zip(inpKeys,inpValues[i]):
        #subInput[key] = c1darray(values=np.array([value]*len(outValues[0][0])))
        if key in self.getParaKeys('inputs'):
          subInput[key] = c1darray(values=np.array([value]))
      for key,value in zip(outKeys[i],outValues[i]):
        if key in self.getParaKeys('outputs'):
          subOutput[key] = c1darray(values=np.array(value))

      self._dataContainer['inputs'][mainKey] = subInput
      self._dataContainer['outputs'][mainKey] = subOutput

    #extend the expected size of this point set
    self.numAdditionalLoadPoints += len(allLines) #used in checkConsistency

    self.checkConsistency()

  def _constructKDTree(self,requested):
    """
      Constructs a KD tree consisting of the variable values in "requested"
      @ In, requested, list, requested variable names
      @ Out, None
    """
    # get by-sample data
    samples = self.getParametersValues('inputs')
    # this preserves the order of "requested" variables, which is critical to the KDTree
    ## the non-float variables will be handled outside the KD tree.
    floatVars = list(r for r in requested if r in samples.values()[0].keys())
    inpVals = {}
    #set up data scaling, so that relative distances are used
    # scaling is so that scaled = (actual - mean)/scale
    for v in floatVars:
      inpVals[v] = np.array(list(samples[i][v][0] for i in samples))
      mean,scale = mathUtils.normalizationFactors(inpVals[v])
      self.treeScalingFactors[v] = (mean,scale)
    # create normalized tree
    data = np.dstack(tuple((inpVals[v]-self.treeScalingFactors[v][0])/self.treeScalingFactors[v][1] for v in floatVars))[0]
    self.inputKDTree = spatial.KDTree(data)
