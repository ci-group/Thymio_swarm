# parameters.py created on March 12, 2015. Jacqueline Heinerman & Massimiliano Rango
# modified by Alessandro Zonta on June 25, 2015

import classes as cl

EXPERIMENT_NAME = "MsT_FIXED_EVOLVED_CONTROLLER"
starter_number = 0
# final name will be  "EXPERIMENT_NAME_starter_number"

motorspeed = [0, 0]
ps_value = [0.0 for x in range(cl.NB_DIST_SENS)]

# system parameters
evolution = 0                # evolution
sociallearning = 0          # social learning
lifetimelearning = 1         # lifetime learning
threshold = 0.50             # fitness/maximum fitness value to exceed
total_evals = 1000            # one eval is lifetime/social or reevaluation
max_robot_lifetime = 1000     # either 200 or 100
seed = 0                     # experiment seed
real_speed_percentage = 0.3  # percentage of maximum speed used

# memome parameters
range_weights = 4.0           # weights between [-range_weights, range_weights]
collected_memomes_total = 0   # number collected memomes
collected_memomes_max = 20    # max memome memory
sigmainitial = 1.0            # initital sigma
sigma_max = 4.0               # maximum sigma value
sigma_min = 0.01              # min sigma value
sigma_increase = 2.0          # sigma increase after not better solution

# reevaluate parameters
eval_time = 1000                    # Evaluation time, in steps
tau = 0                             # Recovery  period tau, in steps -> 5% of evaltime
tau_goal = 0                        # Recovery after goal -> must be longer than normal tau -> 25% of evaltime
re_weight = 0.8                     # part or reevaluation fitness that stays the same

real_max_speed = cl.MAXSPEED * real_speed_percentage
max_fitness = eval_time * 6
obs_max_fitness = eval_time
push_max_fitness = eval_time * 4

# Am I using hidden layer?
hidden_layer = 1

# Random controller (0), Expert Controller (1), Evolving Controller (2), Fixed Controller (3) [set social learning = 0]
controller = 3
fixed_weight = [0.3632327950982409, 2.362145805521601, 2.971690008741785, -0.3969151928216546, 3.2063623149521807, -1.254319672191445, 4.0, 2.429032596260466, -4.0, -4.0, -4.0, 2.4727744741570277, -3.9817630250725364, 0.240898343050197, -3.992256723696965, -4.0, -1.471214797957708, -3.9965766670823646, -0.15260463220670067, 0.8078117948505793, 0.49189926822244623, 4.0, 3.9895963353024033, -3.9966216965389636, 3.6737536142369747, -3.541559875967271, 3.1820060909609507, -3.898949320356433, 0.7082371390005677, 3.9997563995943692, 3.9897920323214415, -3.329887598617244, 3.9847059865663668, -2.3449433139300475, -4.0, 3.9967263458923323, 3.989937430590648, 3.9980678399591296, -4.0, 3.2095199671221786, 0.8911166371888513, 0.6720838278926793, 1.6793643970934853, -3.982389788872813, 2.3310320411933345, -0.38340680877789396, -1.2570541806610522, -2.754108034092217, -3.9228395332204755, -1.1054146917974628, 0.31478173887702154, 4.0, 0.509531009479891, 2.623362501754587, -3.6220870929373943, -3.9993489509302593, 1.3629100506121234, 0.30988845296947737, 4.0, 4.0, -2.43687113739277, 1.8898963323655467]

# Obstacle Avoidance Behaviour (0), Pushing Behaviour (1), Foraging Behaviour (2) [only if controller == 2]
behaviour = 2
