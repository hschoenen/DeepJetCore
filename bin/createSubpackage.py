#!/usr/bin/env python
# encoding: utf-8


import sys
import os
from argparse import ArgumentParser

parser = ArgumentParser('script to create a DeepJetCore subpackage')

parser.add_argument("subpackage_directory", help="Directory to place the subpackage in (will be created). Last part will be the name of the subpackage")
parser.add_argument("--data", help="create example data", default=False, action="store_true")

args=parser.parse_args()

deepjetcore = os.getenv('DEEPJETCORE')

subpackage_dir=args.subpackage_directory
subpackage_name = os.path.basename(os.path.normpath(subpackage_dir))

if len(subpackage_dir)<1:
    raise Exception("The subpackage name is too short")

### templates ####


environment_file='''
#! /bin/bash

export {subpackage}=$( cd "$( dirname "${BASH_SOURCE}" )" && pwd -P)
export DEEPJETCORE_SUBPACKAGE=${subpackage}

cd ${subpackage}
export PYTHONPATH=${subpackage}/modules:$PYTHONPATH
export PYTHONPATH=${subpackage}/modules/datastructures:$PYTHONPATH
export PATH=${subpackage}/scripts:$PATH

export LD_LIBRARY_PATH=${subpackage}/modules/compiled:$LD_LIBRARY_PATH
export PYTHONPATH=${subpackage}/modules/compiled:$PYTHONPATH

'''.format(deepjetcore=deepjetcore, 
           subpackage=subpackage_name.upper(),
           subpackage_dir=os.path.abspath(subpackage_dir),
           BASH_SOURCE="{BASH_SOURCE[0]}")

create_dir_structure_script='''
#! /bin/bash
mkdir -p {subpackage_dir}
mkdir -p {subpackage_dir}/modules
mkdir -p {subpackage_dir}/modules/datastructures
mkdir -p {subpackage_dir}/scripts
mkdir -p {subpackage_dir}/Train
mkdir -p {subpackage_dir}/example_data
mkdir -p {subpackage_dir}/cpp_analysis/src
mkdir -p {subpackage_dir}/cpp_analysis/interface
mkdir -p {subpackage_dir}/cpp_analysis/bin
mkdir -p {subpackage_dir}/modules/compiled/src
mkdir -p {subpackage_dir}/modules/compiled/interface
'''.format(subpackage_dir=subpackage_dir)

datastructure_template='''

from DeepJetCore.TrainData import TrainData, fileTimeOut
import numpy as np

class TrainData_example(TrainData):
    def __init__(self):
        TrainData.__init__(self)
        # no class member is mandatory
        self.description = "This is a TrainData example file. Having a description string is not a bad idea (but not mandatory), e.g. for describing the array structure."
        #define any other (configuration) members that seem useful
        self.someusefulemember = "something you might need later"

        
    #def createWeighterObjects(self, allsourcefiles):
        # 
        # This function can be used to derive weights (or whatever quantity)
        # based on the entire data sample. It should return a dictionary that will then
        # be passed to either of the following functions. The weighter objects
        # should be pickleable.
        # In its default implementation, the dict is empty
        # return {}
    
    
    def convertFromSourceFile(self, filename, weighterobjects, istraining):
        # This is the only really mandatory function (unless writeFromSourceFile is defined).
        # It defines the conversion rule from an input source file to the lists of training 
        # arrays self.x, self.y, self.w
        #  self.x is a list of input feature arrays
        #  self.y is a list of truth arrays
        #  self.w is optional and can contain a weight array 
        #         (needs to have same number of entries as truth array)
        #         If no weights are needed, this can be left completely empty
        #
        # The conversion should convert finally to numpy arrays. In the future, 
        # also tensorflow tensors will be supported.
        #
        # In this example, differnt ways of reading files are deliberatly mixed
        # 
        
        
        print('reading '+filename)
        
        import ROOT
        fileTimeOut(filename,120) #give eos a minute to recover
        rfile = ROOT.TFile(filename)
        tree = rfile.Get("tree")
        nsamples = tree.GetEntries()
        
        # user code, example works with the example 2D images in root format generated by make_example_data
        from DeepJetCore.preprocessing import read2DArray

        feature_array = read2DArray(filename,"tree","image2d",nsamples,32,32)
        
        print('feature_array',feature_array.shape)
        

        import uproot

        urfile = uproot.open(filename)["tree"]
        truth = np.concatenate([np.expand_dims(urfile.array("isA"), axis=1) , 
                                np.expand_dims(urfile.array("isB"), axis=1), 
                                np.expand_dims(urfile.array("isC"), axis=1)],axis=1)
        
        truth = truth.astype(dtype='float32', order='C') #important, float32 and C-type!
        
        self.nsamples=len(feature_array)
        
        #returns a list of feature arrays, a list of truth arrays and a list of weight arrays
        return [feature_array], [truth], []
    
    ## defines how to write out the prediction
    def writeOutPrediction(self, predicted, features, truth, weights, outfilename, inputfile):
        # predicted will be a list
        
        from root_numpy import array2root
        out = np.core.records.fromarrays(predicted[0].transpose(), 
                                             names='prob_isA, prob_isB, prob_isC')
        
        array2root(out, outfilename, 'tree')
        
'''


training_template='''

from DeepJetCore.training.training_base import training_base
import keras
from keras.models import Model
from keras.layers import Dense, Conv2D, Flatten, BatchNormalization #etc

def my_model(Inputs,otheroption):
    
    x = Inputs[0] #this is the self.x list from the TrainData data structure
    x = BatchNormalization(momentum=0.9)(x)
    x = Conv2D(8,(4,4),activation='relu', padding='same')(x)
    x = Conv2D(8,(4,4),activation='relu', padding='same')(x)
    x = Conv2D(8,(4,4),activation='relu', padding='same')(x)
    x = BatchNormalization(momentum=0.9)(x)
    x = Conv2D(8,(4,4),strides=(2,2),activation='relu', padding='valid')(x)
    x = Conv2D(4,(4,4),strides=(2,2),activation='relu', padding='valid')(x)
    x = Flatten()(x)
    x = Dense(32, activation='relu')(x)
    
    # 3 prediction classes
    x = Dense(3, activation='softmax')(x)
    
    predictions = [x]
    return Model(inputs=Inputs, outputs=predictions)


train=training_base(testrun=False,resumeSilently=False,renewtokens=False)

if not train.modelSet(): # allows to resume a stopped/killed training. Only sets the model if it cannot be loaded from previous snapshot

    train.setModel(my_model,otheroption=1)
    
    train.compileModel(learningrate=0.003,
                   loss='categorical_crossentropy') 
                   
print(train.keras_model.summary())


model,history = train.trainModel(nepochs=10, 
                                 batchsize=500,
                                 checkperiod=1, # saves a checkpoint model every N epochs
                                 verbose=1)
                                 
print('Since the training is done, use the predict.py script to predict the model output on you test sample, e.g.:\n predict.py <training output>/KERAS_model.h5 <training output>/trainsamples.djcdc <path to data>/test.txt <output dir>')
'''
        
datastructures_init = '''
#Make it look like a package
from glob import glob
from os import environ
from os.path import basename, dirname
from pdb import set_trace

#gather all the files here
modules = [basename(i.replace('.py','')) for i in glob('%s/[A-Za-z]*.py' % dirname(__file__))]
__all__ = []
structure_list=[]
for module_name in modules:
    module = __import__(module_name, globals(), locals(), [module_name])
    for model_name in [i for i in dir(module) if 'TrainData' in i]:
        
        
        model = getattr(module, model_name)
        globals()[model_name] = model
        locals( )[model_name] = model
        __all__.append(model_name)
        structure_list.append(model_name)

'''
        
layers_template='''
# Define custom layers here and add them to the global_layers_list dict (important!)
global_layers_list = {}
'''
losses_template='''
# Define custom losses here and add them to the global_loss_list dict (important!)
global_loss_list = {}
'''

metrics_template='''
# Define custom metrics here and add them to the global_metrics_list dict (important!)
global_metrics_list = {}
'''

makefile_template='''

#
# This file might need some adjustments but should serve as a good basis
#

PYTHON_INCLUDE = `python-config --includes`
PYTHON_LIB=`python-config --libs`

ROOTSTUFF=`root-config --libs --glibs --ldflags`
ROOTCFLAGS=`root-config  --cflags`

CPP_FILES := $(wildcard src/*.cpp)
OBJ_FILES := $(addprefix obj/,$(notdir $(CPP_FILES:.cpp=.o)))
LD_FLAGS := `root-config --cflags --glibs`  -lMathMore -L${DEEPJETCORE}/compiled -ldeepjetcorehelpers -lquicklz
CC_FLAGS := -fPIC -g -Wall `root-config --cflags`
CC_FLAGS += -I./interface -I${DEEPJETCORE}/compiled/interface
#CC_FLAGS += -MMD


all: $(patsubst bin/%.cpp, %, $(wildcard bin/*.cpp))


%: bin/%.cpp  $(OBJ_FILES) 
	g++ $(CC_FLAGS) $(LD_FLAGS) $(OBJ_FILES) $< -o $@ 


obj/%.o: src/%.cpp
	g++ $(CC_FLAGS) -c -o $@ $<


clean: 
	rm -f obj/*.o obj/*.d
	rm -f %
'''

bin_template='''
#include "TString.h"
#include "friendTreeInjector.h"
#include <iostream>

int main(int argc, char* argv[]){
    if(argc<2) return -1;

    TString infile = argv[1];

    friendTreeInjector intree;
    intree.addFromFile(infile);
    intree.setSourceTreeName("tree");

    intree.createChain();

    auto c = intree.getChain();

    std::cout << c->GetEntries() <<std::endl;
    
    /*
    * For more information please refer to how to analse a TTree of the root documentation
    */
}
'''

compiled_module_template='''

#include <boost/python.hpp>
#include "boost/python/numpy.hpp"
#include "boost/python/list.hpp"
#include "boost/python/str.hpp"
#include <boost/python/exception_translator.hpp>
#include <exception>

//includes from deepjetcore
#include "helper.h"
#include "simpleArray.h"

namespace p = boost::python;
namespace np = boost::python::numpy;

/*
 * Example of a python module that will be compiled.
 * It can be used, e.g. to convert from fully custom input data
 */

np::ndarray readFirstFeatures(std::string infile){

    auto arr = djc::simpleArray<float>({10,3,4});
    arr.at(0,2,1) = 5. ;//filling some data

    return simpleArrayToNumpy(arr);
}

BOOST_PYTHON_MODULE(c_convert) {
    Py_Initialize();
    np::initialize();
    def("readFirstFeatures", &readFirstFeatures);
}

'''

module_makefile='''


#
# This file might need some adjustments but should serve as a good basis
#

PYTHON_INCLUDE = `python-config --includes`
PYTHON_LIB=`python-config --libs`

ROOTSTUFF=`root-config --libs --glibs --ldflags`
ROOTCFLAGS=`root-config  --cflags`

CPP_FILES := $(wildcard src/*.cpp)
OBJ_FILES := $(addprefix obj/,$(notdir $(CPP_FILES:.cpp=.o)))
LD_FLAGS := `root-config --cflags --glibs`  -lMathMore -L${DEEPJETCORE}/compiled -ldeepjetcorehelpers -lquicklz
CC_FLAGS := -fPIC -g -Wall `root-config --cflags`
CC_FLAGS += -I./interface -I${DEEPJETCORE}/compiled/interface
DJC_LIB = -L${DEEPJETCORE}/compiled -ldeepjetcorehelpers 


MODULES := $(wildcard src/*.C)
MODULES_OBJ_FILES := $(addprefix ./,$(notdir $(MODULES:.C=.o)))
MODULES_SHARED_LIBS := $(addprefix ./,$(notdir $(MODULES:.C=.so)))


all: $(MODULES_SHARED_LIBS) $(patsubst bin/%.cpp, %, $(wildcard bin/*.cpp))

#compile the module helpers if necessary
#../modules/libsubpackagehelpers.so:
#        cd ../modules; make; cd -

%: bin/%.cpp  $(OBJ_FILES) 
	g++ $(CC_FLAGS) $(LD_FLAGS) $(OBJ_FILES) $< -o $@ 


obj/%.o: src/%.cpp
	g++ $(CC_FLAGS) -c -o $@ $<


#python modules

%.so: %.o 
	g++  -o $(@) -shared -fPIC  $(LINUXADD) $<   $(ROOTSTUFF)  $(PYTHON_LIB) -lboost_python -lboost_numpy $(DJC_LIB)

%.o: src/%.C 
	g++   $(ROOTCFLAGS) -O2 $(CC_FLAGS) -I./interface $(PYTHON_INCLUDE) -fPIC -c -o $(@) $<


clean: 
	rm -f obj/*.o obj/*.d *.so
	rm -f %

'''

######## create the structure ########


os.system(create_dir_structure_script)
with  open(subpackage_dir+'/env.sh','w') as envfile:
    envfile.write(environment_file)
    
with  open(subpackage_dir+'/modules/datastructures/TrainData_example.py','w') as lfile:
    lfile.write(datastructure_template)
    
with  open(subpackage_dir+'/modules/datastructures/__init__.py','w') as lfile:
    lfile.write(datastructures_init)
    
with  open(subpackage_dir+'/Train/training_example.py','w') as lfile:
    lfile.write(training_template)
    
with  open(subpackage_dir+'/modules/Layers.py','w') as lfile:
    lfile.write(layers_template)
with  open(subpackage_dir+'/modules/Losses.py','w') as lfile:
    lfile.write(losses_template)
with  open(subpackage_dir+'/modules/Metrics.py','w') as lfile:
    lfile.write(metrics_template)
    
with  open(subpackage_dir+'/cpp_analysis/Makefile','w') as lfile:
    lfile.write(makefile_template)
    
with  open(subpackage_dir+'/cpp_analysis/bin/example.cpp','w') as lfile:
    lfile.write(bin_template)
    
with  open(subpackage_dir+'/modules/compiled/Makefile','w') as lfile:
    lfile.write(module_makefile)
    
with  open(subpackage_dir+'/modules/compiled/src/c_convert.C','w') as lfile:
    lfile.write(compiled_module_template)


print('subpackage '+ subpackage_name + " created in "+subpackage_dir)    
if args.data:
    print('creating example data... (10 training files, 1 test file, 1000 events each)')
    os.system('cd '+subpackage_dir+'/example_data;  make_example_data  1000 10 1')
    print('example data can be found in '+subpackage_dir+'/example_data.')
    
print('Before using the subpackage, source the "env.sh" file in the subpackage directory (not in DeepJetCore).')
print('to convert to example TrainData format use:')
print('convertFromSource.py -i '+subpackage_dir+'/example_data/train_files.txt -o <train output dir> -c TrainData_example')

print('\nAn example to run the training can be found in '+subpackage_dir+'/Train/training_example.py')
print('It can be run with: \npython '+subpackage_dir+'/Train/training_example.py <train output dir>/dataCollection.djcdc <train output dir>')







