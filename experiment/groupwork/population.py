import gzip, random, math, time
from .config import Config
from . import species
from . import chromosome
import pickle as pickle
from . import visualize
"""
Updated by Gabriel Meyer-Lee for DeepNEAT-like use.

Updated by Lisa Meeden in Fall 2018 for CS81

Updated the code to run in python3 vs the original python2.

Added self.first so that the species id could be reset whenever a
new population is formed.

Updated by Lisa Meeden in Spring 2009 for CS81

Modified self.__best_fitness. It is now a list of the best fitness
scores rather than the best individuals.  This was done so that the
graph of best and average fitness scores throughout evolution are
based on the scores received rather than updated scores.
"""

class Population(object):
    """ Manages all the species  """
    evaluate = None # Evaluates the entire population. You need to override
                    # this method in your experiments

    def __init__(self, size=Config.pop_size, chromo_type=None, co_pop=None, \
            checkpoint_file=None, debug=None):
        self.first = True
        self.__debug = debug

        self.__co_population = co_pop
        self.__chromo_type = chromo_type
        if checkpoint_file:
            # start from a previous point: creates an 'empty'
            # population and point its __dict__ to the previous one
            self.__resume_checkpoint(checkpoint_file)
        else:
            # total population size
            self.__popsize = size
            # currently living species
            self.__species = []

            # species history
            self.__species_log = []

            # Statistics
            self.__avg_fitness = []
            self.__best_fitness = []

            self.__create_population()
            self.__speciate(False)
            self.__generation = -1
            self.best = None

    stats = property(lambda self: (self.__best_fitness, self.__avg_fitness))
    species_log = property(lambda self: self.__species_log)

    def __resume_checkpoint(self, checkpoint):
        """ Resumes the simulation from a previous saved point. """
        try:
            #file = open(checkpoint)
            file = gzip.open(checkpoint)
        except IOError:
            raise
        print('Resuming from a previous point: %s' %checkpoint)
        # when unpickling __init__ is not called again
        previous_pop = pickle.load(file)
        self.__dict__ = previous_pop.__dict__

        print('Loading random state')
        rstate = pickle.load(file)
        random.setstate(rstate)
        #random.jumpahead(1)
        file.close()

    def __create_checkpoint(self, report):
        """ Saves the current simulation state. """
        #from time import strftime
        # get current time
        #date = strftime("%Y_%m_%d_%Hh%Mm%Ss")
        if report:
            print('Creating checkpoint file at generation: %d' % \
                  self.__generation)

        # dumps 'self'
        #file = open('checkpoint_'+str(self.__generation), 'w')
        file = gzip.open(self.name+'checkpoint_'+ \
                         str(self.__generation), 'w', compresslevel = 5)
        # dumps the population
        pickle.dump(self, file, protocol=2)
        # dumps the current random state
        pickle.dump(random.getstate(), file, protocol=2)
        file.close()

    def __create_population(self):
        self.__population = []
        for i in range(self.__popsize):
            self.__population.append(self.create_individual())

    def create_individual(self):
        if self.__chromo_type != None:
            genotypes = self.__chromo_type
        else:
            genotypes = chromosome.Chromosome
        if self.__co_population == None:
            g = genotypes.create_initial()
        else:
            g = genotypes.create_initial(self.__co_population)
        return g

    def __repr__(self):
        s = "Population size: %d" %self.__popsize
        s += "\nTotal species: %d" %len(self.__species)
        return s

    def __len__(self):
        return len(self.__population)

    def __iter__(self):
        return iter(self.__population)

    def __getitem__(self, key):
        return self.__population[key]

    #def remove(self, chromo):
    #    ''' Removes a chromosome from the population '''
    #    self.__population.remove(chromo)
    def __speciate(self, report):
        """ Group chromosomes into species by similarity """
        # Speciate the population
        for individual in self:
            found = False
            for s in self.__species:
                if individual.distance(s.representant) < \
                       Config.compatibility_threshold:
                    s.add(individual)
                    found = True
                    break
            if not found: # create a new species for this lone chromosome
                """
                When creating the very first species, reset the id to 0.
                """
                if self.first:
                    self.__species.append(species.Species(individual, 0))
                    self.first = False
                else:
                    self.__species.append(species.Species(individual))
        # python technical note:
        # we need a "working copy" list when removing elements while looping
        # otherwise we might end up having sync issues
        for s in self.__species[:]:
            # this happens when no chromosomes are compatible with the species
            if len(s) == 0:
                #if report:
                #    print "Removing species %d for being empty" % s.id
                # remove empty species
                self.__species.remove(s)
        if self.__debug is not None:
            self.__debug.write('Speciating ' + self.__chromo_type.__name__ + '\n')
            string = ''
            for s in self.__species:
                string += str(s) + '\n'
            self.__debug.write(string)
        self.__set_compatibility_threshold()
    def __set_compatibility_threshold(self):
        ''' Controls compatibility threshold '''
        if len(self.__species) > Config.species_size:
            Config.compatibility_threshold += Config.compatibility_change
        elif len(self.__species) < Config.species_size:
            if Config.compatibility_threshold > Config.compatibility_change:
                Config.compatibility_threshold -= Config.compatibility_change
            else:
                print('Compatibility threshold cannot be changed')
                print('(minimum value has been reached)')

    def average_fitness(self):
        """ Returns the average raw fitness of population """
        sum = 0.0
        for c in self:
            sum += c.fitness
        return sum/len(self)

    def get_species(self):
        """ Used for getting a pointer to a random species."""
        indiv = random.choice(self.__population)
        for s in self.__species:
            if s.id == indiv.species_id:
                return s

    def has_species(self, species):
        """ Checks if a species is in the population."""
        try:
          ind = self.__species.index(species)
          #this should be redundant
          if len(self.__species[ind]) == 0:
              self._species.pop(ind)
              return False
          else:
              return True
        except ValueError:
            return False

    def stdeviation(self):
        """ Returns the population standard deviation """
        # first compute the average
        u = self.average_fitness()
        error = 0.0

        try:
            # now compute the distance from average
            for c in self:
                error += (u - c.fitness)**2
        except OverflowError:
            #TODO: catch OverflowError: (34, 'Numerical result out of range')
            print("Overflow - printing population status")
            print("error = %f \t average = %f" %(error, u))
            print("Population fitness:")
            print([c.fitness for c in self])

        return math.sqrt(error/len(self))

    def __compute_spawn_levels(self):
        """ Compute each species' spawn amount (Stanley, p. 40) """

        # 1. Boost if young and penalize if old
        # TODO: does it really increase the overall performance?
        species_stats = []
        for s in self.__species:
            if s.age < Config.youth_threshold:
                species_stats.append(s.average_fitness()*Config.youth_boost)
            elif s.age > Config.old_threshold:
                species_stats.append(s.average_fitness()*Config.old_penalty)
            else:
                species_stats.append(s.average_fitness())

        # 2. Share fitness (only useful for computing spawn amounts)       
        # More info: http://tech.groups.yahoo.com/group/neat/message/2203
        # Sharing the fitness is only meaningful here  
        # we don't really have to change each individual's raw fitness 
        total_average = 0.0
        for s in species_stats:
                total_average += s

        # 3. Compute spawn
        for i, s in enumerate(self.__species):
            s.spawn_amount = int(round((species_stats[i]*\
                                        self.__popsize/total_average)))

    def __tournament_selection(self, k=2):
        """ Tournament selection with size k (default k=2). 
            Make sure the population has at least k individuals """
        random.shuffle(self.__population)   

        return max(self.__population[:k])     

    def __log_species(self):
        """ Logging species data for visualizing speciation """
        higher = max([s.id for s in self.__species])
        temp = []
        for i in range(1, higher+1):
            found_specie = False
            for s in self.__species:
                if i == s.id:
                    temp.append(len(s))
                    found_specie = True
                    break
            if not found_specie:
                temp.append(0)
        self.__species_log.append(temp)
    def __population_diversity(self):
        """ Calculates the diversity of population: total average weights, 
            number of connections, nodes """

        num_nodes = 0

        for c in self:
            num_nodes += len(c._genes)

        total = len(self)
        return (num_nodes/total, num_nodes/total, avg_nodes/total)

    def getGen(self):
        return self.__generation

    def epoch(self, g, report=True, save_best=False, checkpoint_interval = 10.0,
        checkpoint_generation = None, name = ""):
        
        t0 = time.time() # for saving checkpoints
        self.name = name
        """ Runs NEAT's genetic algorithm for n epochs.

            Keyword arguments:
            report -- show stats at each epoch (default True)
            save_best -- save the best chromosome from each epoch
            (default False)
            checkpoint_interval -- time in minutes between saving checkpoints
            (default 10 minutes)
            checkpoint_generation -- time in generations between
            saving checkpoints (default 0 -- option disabled)
        """

        self.__generation += 1

        if report: print('\n ****** Generation %d ****** \n' % \
               self.__generation)

        # Compute spawn levels for each remaining species
        self.__compute_spawn_levels()

        # Current generation's best chromosome
        self.best = max(self.__population)
        self.__best_fitness.append(self.best.fitness)
        # Current population's average fitness
        self.__avg_fitness.append(self.average_fitness())

        # Print some statistics
        # Which species has the best chromosome?
        for s in self.__species:
            s.hasBest = False
            if self.best.species_id == s.id:
                s.hasBest = True

        # saves the best chromo from the current generation
        if save_best:
            filename = "best_chromo_" + str(self.__generation)
            if self.name != "":
                filename = self.name + "_" + filename
            file = open(filename,'wb')
            pickle.dump(self.best, file)
            file.close()

        #-----------------------------------------
        #Prints chromosome's parents id:  {dad_id, mon_id} -> child_id
        #for chromosome in self.__population:
        #    print '{%3d; %3d} -> %3d' % \
        #    (chromosome.parent1_id, chromosome.parent2_id, chromosome.id)
        #-----------------------------------------
        if report:
            #print 'Poluation size: %d \t Divirsity: %s' %\
            #      (len(self), self.__population_diversity())
            print('Population\'s average fitness: %3.5f stdev: %3.5f' %\
                  (self.__avg_fitness[-1], self.stdeviation()))
            print('Best fitness: %2.12s - size: %s - species %s - id %s'%\
                  (self.best.fitness, self.best.size(), self.best.species_id, self.best.id))

            # print some "debugging" information
            print('Species length: %d totalizing %d individuals' \
                    %(len(self.__species), \
                      sum([len(s) for s in self.__species])))
            print('Species ID       : %s' % \
                  [s.id for s in self.__species])
            print('Each species size: %s' % \
                  [len(s) for s in self.__species])
            print('Amount to spawn  : %s' % \
                  [s.spawn_amount for s in self.__species])
            print('Species age      : %s' % \
                  [s.age for s in self.__species])
            print('Species no improv: %s' % \
                  [s.no_improvement_age for s in self.__species])

        # Stops the simulation
        if self.best.fitness > Config.max_fitness_threshold:
            print('\nBest individual found in epoch %s - complexity: %s'%\
                  (self.__generation, self.best.size()))
            return -1

        # Removing species with spawn amount = 0
        for s in self.__species[:]:
            # This rarely happens
            if s.spawn_amount == 0:
                for c in self.__population[:]:
                    if c.species_id == s.id:
                        self.__population.remove(c)
                            #self.remove(c)
                self.__species.remove(s)

        # Logging speciation stats
        self.__log_species()

        # --------- Producing new offspring ------------ #
        new_population = [] # next generation's population

        # Spawning new population
        for s in self.__species:
            new_population.extend(s.reproduce())

        # Remove stagnated species and its members
        # (except if it has the best chromosome)
        for s in self.__species[:]:
            if s.no_improvement_age > Config.max_stagnation:
                if s.hasBest == False:
                    if report:
                        print("\n   Species %2d is stagnated: removing it" % s.id)
                    # removing species
                    self.__species.remove(s)
                    # removing all the species' members
                    #TODO: can be optimized!
                    for c in new_population[:]:
                        if c.species_id == s.id:
                            new_population.remove(c)

        # Remove "super-stagnated" species
        # (even if it has the best chromosome)
        # It is not clear if it really avoids local minima
        for s in self.__species[:]:
            if s.no_improvement_age > 2*Config.max_stagnation:
                if report:
                    print("\n   Species %2d is super-stagnated: removing it" % s.id)
                # removing species
                self.__species.remove(s)
                # removing all the species' members
                #TODO: can be optimized!
                for c in new_population[:]:
                    if c.species_id == s.id:
                        new_population.remove(c)

        # ----------------------------#
        # Controls under or overflow  #
        # ----------------------------#
        fill = (self.__popsize) - len(new_population)
        if fill < 0: # overflow
            if report:
                print('Removing %d excess indiv(s) from the new population' %-fill)
            # TODO: This is dangerous!
            # I can't remove a species' representative!
            # Removing the last added members
            new_population = new_population[:fill]
            for s in self.__species:
                if s.representant not in new_population:
                    self.__species.remove(s)
            if self.__debug is not None:
                self.__debug.write('Spawn Overflow ' + self.__chromo_type.__name__ + '\n')

        if fill > 0: # underflow
            if report:
                print('Selecting %d more indiv(s) to fill up the new population' %fill)
            while fill > 0:
                # Selects a random chromosome from population
                parent1 = random.choice(self.__population)
                # Search for a mate within the same species
                found = False
                for c in self:
                    # what if c is parent1 itself?
                    if c.species_id == parent1.species_id:
                        child = parent1.crossover(c)
                        new_population.append(child.mutate())
                        found = True
                        break
                if not found:
                    # If no mate was found, just mutate it
                    new_population.append(parent1.mutate())
                fill -= 1

        assert self.__popsize == len(new_population), \
               'Different population sizes!'
        # Updates current population
        self.__population = new_population[:]
        # Speciates the population
        self.__speciate(report)

        # how often a checkpoint will be created?
        #if self.__generation % 10 is 0:
        #    self.__create_checkpoint(report)
        if checkpoint_interval is not None and \
               time.time() > t0 + 60*checkpoint_interval:
            self.__create_checkpoint(report)
            t0 = time.time() # updates the counter
        elif checkpoint_generation is not None and \
                 self.__generation % checkpoint_generation == 0:
            self.__create_checkpoint(report)

        return 1



if __name__ ==  '__main__' :

    # sample fitness function
    def eval_fitness(population):
        for individual in population:
            individual.fitness = 1.0

    # set fitness function 
    Population.evaluate = eval_fitness
    
    # creates the population
    pop = Population()
    # runs the simulation for 250 epochs
    pop.epoch(250)       

# Things left to check:
# b) boost and penalize is done inside Species.shareFitness() method
#    (as in Buckland's code)
# d) ELE (Extinct Life Events) - something to be implemented as described
#    in the NEAT4J version 
