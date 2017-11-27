import random, math
from .config import Config
from . import genome
import numpy as np
from keras.models import Model
from keras.layers import Input, Activation, Dense, Dropout, Flatten
from keras.layers.convolutional import Convolution2D, MaxPooling2D
from keras.layers.normalization import BatchNormalization
from keras import backend

class Chromosome(object):
    """ A chromosome data type for co-evolving deep neural networks """
    _id = 0
    def __init__(self, parent1_id, parent2_id, gene_type):

        self._id = self.__get_new_id()

        # the type of ModuleGene or LayerGene the chromosome carries
        self._gene_type = gene_type
        # how many genes of the previous type the chromosome has
        self._genes = []

        self.fitness = None
        self.num_use = None
        self.species_id = None

        # my parents id: helps in tracking chromosome's genealogy
        self.parent1_id = parent1_id
        self.parent2_id = parent2_id

    genes      = property(lambda self: self._genes)
    id         = property(lambda self: self._id)

    @classmethod
    def __get_new_id(cls):
        cls._id += 1
        return cls._id

    def mutate(self):
        """ Mutates this chromosome """
        raise NotImplementedError

    def crossover(self, other):
        """ Crosses over parents' chromosomes and returns a child. """

        # This can't happen! Parents must belong to the same species.
        assert self.species_id == other.species_id, 'Different parents species ID: %d vs %d' \
                                                         % (self.species_id, other.species_id)

        if self.fitness > other.fitness:
            parent1 = self
            parent2 = other
        elif self.fitness == other.fitness:
            if len(self._genes) > len(other._genes):
                parent1 = other
                parent2 = self
            else:
                parent1 = self
                parent2 = other
        else:
            parent1 = other
            parent2 = self

        # creates a new child
        child = self.__class__(self.id, other.id, self._gene_type)

        child._inherit_genes(parent1, parent2)

        child.species_id = parent1.species_id

        return child

    def _inherit_genes(child, parent1, parent2):
        """ Applies the crossover operator. """
        raise NotImplementedError

    # compatibility function
    def distance(self, other):
        """ Returns the distance between this chromosome and the other. """
        if len(self._genes) > len(other._genes):
            chromo1 = self
            chromo2 = other
        else:
            chromo1 = other
            chromo2 = self

        return chomo1._genes-chromo2._genes

    def size(self):
        """ Defines chromosome 'complexity': number of hidden nodes plus
            number of enabled connections (bias is not considered)
        """
        return len(self._genes)

    def __cmp__(self, other):
        return cmp(self.fitness, other.fitness)

    def __lt__(self, other):
        return self.fitness <  other.fitness

    def __gt__(self, other):
        return self.fitness > other.fitness

    def __str__(self):
        s = "ID: "+str(self._id)+" Species: "+str(self.species_id)+"\nGenes:"
        for ng in self._genes:
            s += "\n\t" + str(ng)
        return s

class BlueprintChromo(Chromosome):
    """
    A chromosome for deep neural network blueprints.
    """
    def __init__(self, parent1_id, parent2_id, module_pop, active_params={}, gene_type='MODULE'):
        super(BlueprintChromo, self).__init__(parent1_id, parent2_id, gene_type)
        self._species_indiv = {}
        self._all_params = {
                "learning_rate": [.0001, .1],
                "momentum": [.68,.99],
                "hue_shift": [0, 45],
                "sv_shift": [0, .5],
                "sv_scale": [0, .5],
                "cropped_image_size": [26,32],
                "spatial_scaling": [0,0.3],
                "horizontal_flips": [True, False],
                "variance_norm": [True, False],
                "nesterov_acc": [True, False],
                }
        self._active_params = active_params
        self._module_pop = module_pop

    def crossover(self, other):
        """ Crosses over parents' chromosomes and returns a child. """

        # This can't happen! Parents must belong to the same species.
        assert self.species_id == other.species_id, 'Different parents species ID: %d vs %d' \
                                                         % (self.species_id, other.species_id)

        if self.fitness > other.fitness:
            parent1 = self
            parent2 = other
        elif self.fitness == other.fitness:
            if len(self._genes) > len(other._genes):
                parent1 = other
                parent2 = self
            else:
                parent1 = self
                parent2 = other
        else:
            parent1 = other
            parent2 = self

        # creates a new child
        child = self.__class__(self.id, other.id, self._module_pop, self._active_params)

        child._inherit_genes(parent1, parent2)

        child.species_id = parent1.species_id

        return child


    def __get_species_indiv(self):
        valid_species = False
        #TODO if species is working correctly, shouldn't need while loop
        while not valid_species:
          valid_species = True
          for g in self._genes:
              if not (self._module_pop.has_species(g.module)):
                g.set_module(self._module_pop.get_species())
                valid_species = False
        for g in self._genes:
            try:
                self._species_indiv[g.module.id] = random.choice(g.module.members)
            except KeyError:
                pass

    def decode(self, inputs):
        self.__get_species_indiv()
        next = inputs
        for g in self._genes:
            mod = self._species_indiv[g.module.id].decode(next)
            next = mod(next)
        return next

    def distance(self, other):
        dist = 0
        if len(self._genes) > len(other._genes):
            chromo1 = self
            chromo2 = other
        else:
            chromo1 = other
            chromo2 = self
        dist += (len(chromo1._genes)-len(chromo2._genes))*Config.excess_coefficient
        chromo1_species = []
        chromo2_species = []
        for g in chromo1._genes:
            chromo1_species.append(g.module.id)
        for g in chromo2._genes:
            chromo2_species.append(g.module.id)
        for id in chromo1_species:
            if id in chromo2_species:
                chromo2_species.remove(id)
            else:
                dist += Config.disjoint_coefficient
        return dist

    def _inherit_genes(child, parent1, parent2):
        """ Applies the crossover operator. """
        assert(parent1.fitness >= parent2.fitness)

        # Crossover layer genes
        for i, g1 in enumerate(parent1._genes):
            try:
                # matching node genes: randomly selects the neuron's bias and response
                child._genes.append(g1.get_child(parent2._genes[i]))
            except IndexError:
                # copies extra genes from the fittest parent
                child._genes.append(g1.copy())
            except TypeError:
                # copies disjoint genes from the fittest parent
                child._genes.append(g1.copy())

    def mutate(self):
        """ Mutates this chromosome """

        r = random.random
        if r() < Config.prob_addmodule:
            self._mutate_add_module()
        elif len(self._active_params) > 0:
            for param in list(self._active_params.keys):
                if r() < 0.5:
                    self._active_params[param] = random.choice(self._all_params[param])
        ind = random.randrange(len(self._genes))
        self._genes[ind].set_module = self._module_pop.get_species()
        return self

    def _mutate_add_module(self):
        """ Adds a module to the BluePrintChromo"""
        ind = random.randint(0,len(self._genes))
        module = self._module_pop.get_species()
        self._genes.insert(ind, genome.ModuleGene(None, module))

    @classmethod
    def create_initial(cls, module_pop):
        c = cls(None, None, module_pop)
        n = random.randrange(2,5)
        for i in range(n):
            c._genes.append(genome.ModuleGene(None, module_pop.get_species()))
        return c


class ModuleChromo(Chromosome):
    # TODO: remove most of the connection sorts
    """
    A chromosome for deep neural network "modules" which consist of a small
    number of layers and their associated hyperparameters.
    """
    def __init__(self, parent1_id, parent2_id, gene_type='DENSE'):
        super(ModuleChromo, self).__init__(parent1_id, parent2_id, gene_type)
        self._connections = []

    def decode(self, inputs):
        """
        Produces Keras Model of this module
        """
        inputdim = backend.int_shape(inputs)[1:]
        inputlayer = Input(shape=inputdim)
        mod_inputs = {0: inputlayer}
        self.__connection_sort()
        for conn in self._connections:
            conn.decode(mod_inputs)
        mod = Model(inputs=inputlayer, outputs=mod_inputs[-1])
        return mod

    def distance(self, other):
        dist = 0
        if len(self._genes) > len(other._genes):
            chromo1 = self
            chromo2 = other
        else:
            chromo1 = other
            chromo2 = self
        dist += (len(chromo1._connections)-len(chromo2._connections))*Config.excess_coefficient
        if (chromo1._gene_type != chromo2._gene_type):
            return (dist+1000)
        else:
            for i, conn in enumerate(chromo2._connections):
                for j in range(len(chromo1._connections[i]._in)):
                    if chromo1._connections[i]._in[j] not in list(conn._in):
                        dist += Config.connection_coefficient
            size_diff = 0
            for j, layer in enumerate(chromo2._genes):
               size_diff += math.log2(chromo1._genes[j]._size) - math.log2(layer._size)
            dist += abs(size_diff)*Config.size_coefficient
        return dist

    def _inherit_genes(child, parent1, parent2):
        """ Applies the crossover operator. """
        assert(parent1.fitness >= parent2.fitness)

        # Crossover layer genes
        for i, g1 in enumerate(parent1._genes):
            try:
                # matching node genes: randomly selects parameters
                child._genes.append(g1.get_child(parent2._genes[i]))
            except IndexError:
                # copies extra genes from the fittest parent
                child._genes.append(g1.copy())
            except TypeError:
                # copies disjoint genes from the fittest parent
                child._genes.append(g1.copy())
        parent1.__connection_sort()
        child._connections = parent1._connections.copy()
        child.__connection_sort()
        for i, conn in enumerate(parent1._connections):
            for j, inlayer in enumerate(conn.input):
                if inlayer.type != 'IN':
                    try:
                        if len(parent1._genes) == 1:
                            child._connections[i]._in[j] = child._genes[0]
                        else:
                            ind = parent1._genes.index(inlayer)
                            child._connections[i]._in[j] = child._genes[ind]
                    except ValueError:
                        # below code used for debugging, this exception isn't actually handled
                        print(inlayer.type)
                        print(conn.input[j].type)
                        print(str(conn))
                        for g in parent1._genes:
                            print(str(g))
            for k, outlayer in enumerate(conn.output):
                if outlayer.type != 'OUT':
                    try:
                        if len(parent1._genes) == 1:
                            child._connections[i]._out[k] = child._genes[0]
                        else:
                            ind = parent1._genes.index(outlayer)
                            child._connections[i]._out[k] = child._genes[ind]
                    except ValueError:
                        # below code used for debugging, this exception isn't actually handled
                        print(outlayer.type)
                        print(conn)
                        for g in parent1._genes:
                            print(str(g))
        child.__connection_sort()


    def mutate(self):
        """ Mutates this chromosome """

        r = random.random
        if r() < Config.prob_addlayer:
            self._mutate_add_layer()

        else:
            for g in self._genes:
                g.mutate() # mutate layer params

        return self

    def _mutate_add_layer(self):
        r = random.random
        self.__connection_sort()
        # create new either conv or dense gene
        if self._gene_type == 'CONV' and r() < Config.prob_addconv:
            ng = genome.ConvGene(None, random.choice(genome.ConvGene.layer_params['_size']))
            self._genes.append(ng)
        else:
            ng = genome.DenseGene(None, random.choice(genome.DenseGene.layer_params['_size']))
            self._genes.append(ng)
        # add the possibility of inserting new layer in front of existing layers linearly
        n = genome.LayerGene(0, 'IN', 0)
        x = genome.LayerGene(-1, 'OUT', 0)
        conns = self._connections.copy()
        conns.insert(0, genome.Connection([n], []))
        # randomly pick location for new layer
        inind = random.randrange(len(conns))
        inconn = conns[inind]
        inconn._out.append(ng)
        # if in front was chosen, add a new connection to the connection list
        if inind == 0:
            self._connections[0]._in.pop(0)
            self._connections[0]._in.insert(0,ng)
            self._connections.insert(0,inconn)
            self.__connection_sort()
            return
        # otherwise add the new layer to the output of the chosen input connections
        else:
            self._connections[inind-1]._out.append(ng)
        # add possibility of inserting layer at end linearly
        conns.append(genome.Connection([], [x]))
        # choose random out location
        outind = random.randrange(conns.index(inconn),len(conns))
        output = conns[outind]
        # if the output location is the same as the input location
        if ng in output._out:
            # if this layer is the only layer that takes output, choose a new out location
            if len(output._in) == 1 or outind == 0:
                outind = random.randrange(conns.index(inconn)+1,len(conns))
                output = conns[outind]
            else:
            # otherwise, insert a new connection
                inlayers = output._in.copy()
                self._connections[inind-1]._out.remove(ng)
                self._connections[inind-1]._in.append(ng)
                self._connections.insert(inind-1, genome.Connection(inlayers, [ng]))
                self.__connection_sort()
                return
        output._in.append(ng)
        if len(output._in) == 1 and output._out[0].type == 'OUT':
            self._connections[-1]._out.pop(0)
            self._connections[-1]._out.insert(0,ng)
            self._connections.append(output)
            self.__connection_sort
            return
        else:
            self._connections[outind-1]._in.append(ng)
        self.__connection_sort()

    def __connection_sort(self):
        assert self._connections[0]._in[0].id == 0, str(self._connections[0])
        assert self._connections[-1]._out[0].id == -1, str(self._connections[-1])
        new_conns = []
        new_conns.append(self._connections.pop(0))
        avail_layers = new_conns[0]._out.copy()
        ind = 0
        pos_correct = False
        while len(self._connections) > 1:
            need_layers = self._connections[ind]._in
            for layer in need_layers:
                if layer not in avail_layers:
                    ind += 1
                    pos_correct = False
                    break
                else:
                    pos_correct = True
            if(pos_correct):
                next_conn = self._connections.pop(ind)
                avail_layers.extend(next_conn._out.copy())
                new_conns.append(next_conn)
                ind = 0
        assert self._connections[0]._out[0].id == -1
        new_conns.append(self._connections.pop(0))
        self._connections = new_conns


    @classmethod
    def create_initial(cls):
        c = cls(None,None)
        n = genome.LayerGene(0, 'IN', 0)
        x = genome.LayerGene(-1, 'OUT', 0)
        if Config.conv and random.random() < Config.prob_addconv:
            c._gene_type = 'CONV'
            g = genome.ConvGene(None, random.choice(genome.ConvGene.layer_params['_size']))
            c._genes.append(g)
            c._connections.append(genome.Connection([n],[g]))
            c._connections.append(genome.Connection([g],[x]))
        else:
            g = genome.DenseGene(None, random.choice(genome.DenseGene.layer_params['_size']))
            c._genes.append(g)
            c._connections.append(genome.Connection([n],[g]))
            c._connections.append(genome.Connection([g],[x]))
        return c
