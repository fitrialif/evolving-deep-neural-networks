import random, math
from .config import Config
from . import genome
import numpy as np
from keras.models import Model
from keras.layers import Input, Activation, Dense, Dropout, Flatten
from keras.layers.convolutional import Convolution2D, MaxPooling2D
from keras.layers.normalization import BatchNormalization


# Temporary workaround - default settings
#node_gene_type = genome.NodeGene
conn_gene_type = genome.ConnectionGene

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

        r = random.random
        if r() < Config.prob_addnode:
            self._mutate_add_node()

        elif r() < Config.prob_addconn:
            self._mutate_add_connection()

        else:
            for cg in list(self._connection_genes.values()):
                cg.mutate() # mutate weights
            for ng in self._node_genes[self._input_nodes:]:
                ng.mutate() # mutate bias, response, and etc...

        return self


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
        child = self.__class__(self._input, self.id, other.id, self._gene_type)

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
        s = "Genes:"
        for ng in self._genes:
            s += "\n\t" + str(ng)
        return s

def BlueprintChromo(Chromosome):
    """
    A chromosome for deep neural network blueprints.
    """
    def __init__(self, parent1_id, parent2_id, module_pop, activ_params={}, gene_type='MODULE'):
        super(BluePrintChromo, self).__init__(parent1_id, parent2_id, gene_type)
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

    def __get_species_indiv(self):
        for i in range(len(self._genes)):
            if not (self._module_pop.has_species(module(self._genes[i]))):
                self._genes[i].set_module(self._module_pop.get_species())
        for g in self._genes:
            try:
                self._species_indiv[module(g)._species_id] = species.get_indiv()
            except KeyError:
                pass

    def decode(self, input):
        self.__get_species_indiv()
        inputs = Input(shape=input)
        next = inputs
        for species in self._genes:
            mod, x = self._species_indiv[species._species_id].decode(next)
            next = x
        network = Model(inputs=inputs, outputs=next)
        return network

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
            chromo1_species.append(module(g)._species_id)
        for g in chromo2._genes:
            chromo2_species.append(module(g)._species_id)
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
        else:
            for param in list(self._active_params.keys):
                if r() < 0.5:
                    self._active_params[param] = random.choice(self._all_params[param])
        return self

    def _mutate_add_module(self):
        """ Adds a module to the BluePrintChromo"""
        ind = random.randint(0,len(self._genes))
        module = self._module_pop.get_species()
        self._genes.insert(ind, genome.ModuleGene(None, module))

    def create_initial(newchromo, module_pop):
        newchromo.__init__(None, None, module_pop)
        newchromo._genes.append(genome.ModuleGene(None, module_pop.get_species()))
        newchromo._genes.append(genome.ModuleGene(None, module_pop.get_species()))
        return newchromo


def ModuleChromo(Chromosome):
    """
    A chromosome for deep neural network "modules" which consist of a small number of layers and
    their associated hyperparameters.
    """
    def __init__(self, parent1_id, parent2_id, gene_type='DENSE'):
        super(ModuleChromo, self).__init__(parent1_id, parent2_id, gene_type)
        self._connections = []

    def decode(self, input):
        """
        Produces Keras Model of this module
        """
        inputs = Input(shape=input)
        next = inputs
        for conn in self._connections:
            x = conn.decode(next)
            next = x
        mod = Model(inputs=inputs, outputs=x)
        return mod, next

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
                for input in chromo1._connections[i]._in:
                    if input not in conn._in:
                        dist += Config.connection_coefficient
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
        child._connections = parent1._connections.copy()
        for conn in child._connections:
            for input in conn._in:
                ind = parent1._genes.index(input)
                input = child._genes(ind)

    def mutate(self):
        """ Mutates this chromosome """

        r = random.random
        if r() < Config.prob_addlayer:
            self._mutate_add_layer()

        # elif r() < Config.prob_addconn:
        #    self._mutate_add_connection()

        else:
            for g in self._genes:
                g.mutate() # mutate layer params

        return self

    def _mutate_add_layer(self):
        r = random.random
        input = random.choice(self._connections[:len(self._connections)/2])
        output = random.choice(self._connections[len(self._connections)/2])
        if self._gene_type == 'CONV':
            if r() < .4:
                ng = genome.ConvGene(None,32)
                input._out.append(ng)
                output._in.append(ng)
                self._genes.append(ng)
        else:
            ng = genome.DenseGene(None,128)
            input._out.append(ng)
            output._in.append(ng)
            self._genes.append(ng)

    def create_initial(newchromo):
        newchromo.__init__(None,None)
        if Config.conv and random.random() > .5:
            newchromo._gene_type = 'CONV'
            g = genome.ConvGene(None, 32)
            newchromo._genes.append(g)
            newchromo._connections.append(genome.Connection([],g))
            newchromo._connections.append(genome.Connection(g,[]))
        else:
            g = genome.DenseGene(None, 128)
            newchromo._genes.append(g)
            newchromo._connections.append(genome.Connection([],g))
            newchromo._connections.append(genome.Connection(g,[]))

if __name__ == '__main__':
    # Example
    from . import visualize
    # define some attributes
    node_gene_type = genome.NodeGene         # standard neuron model
    conn_gene_type = genome.ConnectionGene   # and connection link
    Config.nn_activation = 'exp'             # activation function
    Config.weight_stdev = 0.9                # weights distribution

    Config.input_nodes = 2                   # number of inputs
    Config.output_nodes = 1                  # number of outputs

    # creates a chromosome for recurrent networks
    #c1 = Chromosome.create_fully_connected()

    # creates a chromosome for feedforward networks
    c2 = FFChromosome.create_fully_connected()
    # add two hidden nodes
    c2.add_hidden_nodes(2)
    # apply some mutations
    #c2._mutate_add_node()
    #c2._mutate_add_connection()

    # check the result
    #visualize.draw_net(c1) # for recurrent nets
    visualize.draw_ff(c2)   # for feedforward nets
    # print the chromosome
    print(c2)
