# parameters.py created on March 12, 2015. Jacqueline Heinerman & Massimiliano Rango
import classes

EXPERIMENT_NAME = "ESYT30_exp1"

motorspeed = [0,0]
ps_value = [0.0 for x in range(classes.NB_DIST_SENS)]

# system parameters
evolution = 1               # evolution
sociallearning = 1          # social learning
lifetimelearning = 1        # lifetime learning
threshold = 0.3             # fitness/maximum fitness value to exceed
total_evals = 800           # one eval is lifetime/social or reevaluation
max_robot_lifetime = 100    # either 200 or 100
seed = 0                    # experiment seed
real_speed_percentage = 0.6 # percentage of maximum speed used

# genome memory parameters
disable_sensor = 0.3          # change that sensor is enabled for every sensor
collected_genomes_total = 0 # number collected genomes
collected_genomes_max = 7   # maximum number genomes space
genome_tournament_size = 2  # tournament size picked from collected genomes during life.
mutate_sensor = 0.05        # bitflip probability after uniform crossover with tournament winner

# memome parameters
range_weights = 4.0           # weights between [-range_weights, range_weights]
collected_memomes_total = 0   # number collected memomes
collected_memomes_max = 20    # max memome memory
sigmainitial = 1.0            # initital sigma
sigma_max = 4.0               # maximum sigma value
sigma_min = 0.01              # min sigma value
sigma_increase = 2.0          # sigma increase after not better solution

# reevaluate parameters
tau = 30                   # Recovery  period tau, in steps
evaltime = 175             # Evaluation time, in steps
re_weight = 0.8            # part or reevaluation fitness that stays the same

real_maxspeed = classes.MAXSPEED * real_speed_percentage
max_fitness = (2*real_maxspeed)*evaltime  # max fitness = 105000.0
