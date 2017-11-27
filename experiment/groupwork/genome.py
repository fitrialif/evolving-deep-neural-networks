# -*- coding: UTF-8 -*-
import random
from .config import Config
import keras
import math

class LayerGene(object):
    _id = 0
    def __init__(self, id, layertype, outputdim):
        """
        A layer gene is a node which represents a single Keras layer.
        """
        if (id == None):
            self._id = self.__get_new_id()
        else:
            self._id = id
        self._type = layertype
        self._size = outputdim

    id = property(lambda self: self._id)
    type = property(lambda self: self._type)
    size = property(lambda self: self._size)

    @classmethod
    def __get_new_id(cls):
        cls._id += 1
        return cls._id


    def __str__(self):
        return "Layer %2d %6s %6s" \
                %(self._id, self._type, self._size)

    def get_child(self, other):
        """
        Creates a new LayerGene randonly inheriting its attributes from
        parents.
        """
        assert(self._type == other._type)

        g = LayerGene(self.__get_new_id, self._type, random.choice(self._size, other._size))
        return g

    def __cmp__(self, other):
        return cmp(self._id, other._id)

    def __lt__(self, other):
        return self._id <  other._id

    def __gt__(self, other):
        return self._id > other._id


    def copy(self):
        return LayerGene(self.__get_new_id(), self._type, self._size)

    def mutate(self):
        raise NotImplementedError

    def decode(self, x):
        raise NotImplementedError

class DenseGene(LayerGene):
    def __init__(self, id, numnodes, activation='relu', dropout=0.0, batch_norm=False, layertype='DENSE'):
        super(DenseGene, self).__init__(id, layertype, numnodes)
        self._activation = activation
        self._dropout = dropout
        self._batch_norm = batch_norm
        self.layer_params = {
            "_size": [2**i for i in range(4, int(math.log(256, 2)) + 1)],
            "_activation": ['sigmoid', 'tanh', 'relu'],
            "_dropout": [0.0, 0.7],
            "_batch_norm": [True, False],
        }

    def get_child(self, other):
        if(self._type != other._type):
            raise TypeError
        child_param = []
        for key in self.layer_params:
           child_param.append(random.choice(self.key, other.key))
        return DenseGene(self.__get_new_id(), child_param[0], child_param[1], child_param[2], \
                child_param[3])

    def copy(self):
        return DenseGene(self._id, self._size, self._activation, \
                self._dropout, self._batch_norm)

    def mutate(self):
        pass

    def decode(self, x):
        inputdim = len(keras.backend.int_shape(x)[1:])
        if inputdim > 1:
            x = keras.layers.Flatten()(x)
        x = keras.layers.Dense(self._size, activation=self._activation)(x)
        if self._dropout:
            x = keras.layers.Dropout(self._dropout)(x)
        return x

class ConvGene(LayerGene):
    def __init__(self, id, numfilter, kernel_size=1, activation='relu', dropout=0.0, \
            padding='same', strides=(1,1), max_pooling=0, batch_norm=False, layertype='CONV'):
        super(ConvGene, self).__init__(id, layertype, numfilter)
        self._kernel_size = kernel_size
        self._activation = activation
        self._dropout = dropout
        self._padding = padding
        self._strides = strides
        self._max_pooling = max_pooling
        self._batch_norm = batch_norm
        self.layer_params = {
            "_size": [2**i for i in range(5, 9)],
            "_kernel_size": [1,3,5],
            "_activation": ['sigmoid','tanh','relu'],
            "_dropout": [(i if dropout else 0) for i in range(11)],
            "_padding": ['same','valid'],
            "_strides": [(1,1), (2,1), (1,2), (2,2)],
            "_max_pooling": list(range(3)),
            "_batch_norm": [True, False],
        }
    def get_child(self, other):
        if(self._type != other._type):
            raise TypeError
        child_param = []
        for key in self.layer_params:
           child_param.append(random.choice(self.key, other.key))
        return ConvGene(self.__get_new_id(), child_param[0], child_param[1], child_param[2], \
                child_param[3], child_param[4], child_param[5], child_param[6], child_param[7])


    def copy(self):
        return ConvGene(self._id, self._size, self._activation, self._dropout, \
                self._padding, self._strides, self._max_pooling, self._batch_norm)

    def mutate(self):
        pass

    def decode(self, x):
        inputdim = len(keras.backend.int_shape(x)[1:])
        if inputdim == 1:
            xval = keras.backend.int_shape(x)[1]
            dim1 = math.floor(math.sqrt(xval))
            while (xval%dim1 != 0):
                dim1 -= 1
            dim2 = xval/dim1
            x = keras.layers.Reshape((int(dim1),int(dim2),1))(x)
        x = keras.layers.Conv2D(self._size, self._kernel_size, strides=self._strides, \
                padding=self._padding, activation=self._activation)(x)
        if self._dropout:
            x = keras.layers.Dropout(self._dropout)(x)
        if self._max_pooling:
            x = keras.layers.MaxPool2D()(x)
        return x



class ModuleGene(object):
    _id = 0
    def __init__(self, id, modspecies):
        """
        A module gene is a node which represents a multilayer component of
        a deep neural network.
        """
        if id == None:
            self._id = self.__get_new_id
        else:
            self._id = id
        self._type = 'MODULE'
        self._module = modspecies

    @classmethod
    def __get_new_id(cls):
        cls._id += 1
        return cls._id

    id = property(lambda self: self._id)
    type = property(lambda self: self._type)
    module = property(lambda self: self._module)

    def __str__(self):
        return "Module %2d %6s " \
                %(self._id, self._type, self._module._species_id)

    def get_child(self, other):
        """
        Creates a new NodeGene randonly inheriting its attributes from
        parents.
        """
        assert(self._type == other._type)

        g = ModuleGene(self._id, self._type, random.choice(self._module, other._module))
        return g

    def copy(self):
        return ModuleGene(self._id, self._type, self._module)

    def set_module(self, modspecies):
        self._module = modspecies

    def mutate(self):
        pass


class Connection(object):
    def __init__(self, innodes=[], outnodes=[]):
        self._in = innodes
        self._out = outnodes

    input  = property(lambda self: self._in)
    output = property(lambda self: self._out)

    def __str__(self):
        s = "In %10s, Out %10s " % \
            (self._in, self._out)
        return s

    def decode(self, mod_inputs):
        if len(self._in) > 1:
            conn_inputs = []
            for mod in self._in:
                conn_inputs.append(mod_inputs[mod._id])
            x = keras.layers.Add()(conn_inputs)
        else:
            x = mod_inputs[self._in[0]._id]
        for layer in self._out:
            if layer._type == 'OUT':
                mod_inputs[-1] = x
            else:
                mod_inputs[layer._id] = layer.decode(x)

        ###############################################