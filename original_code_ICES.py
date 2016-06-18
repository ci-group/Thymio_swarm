f# algorithm.py created on March 12, 2015. Jacqueline Heinerman & Massimiliano Rango
import parameters as pr
import classes
import dbus, dbus.mainloop.glib
import copy
import glib, gobject
import sys, os, errno
import random, math, time
import logging, traceback, json
import threading, socket, select, struct, pickle

RAND_MAX = sys.maxint 
LEFT = 0
RIGHT = 1

CURRENT_FILE_PATH = os.path.abspath(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(CURRENT_FILE_PATH, 'config.json')
AESL_PATH = os.path.join(CURRENT_FILE_PATH, 'asebaCommands.aesl')
MAIN_LOG_PATH = os.path.join(CURRENT_FILE_PATH, 'log_main')
# SIM_LOG_PATH = os.path.join(CURRENT_FILE_PATH, 'log', 'sim_log')
OUTPUT_PATH = os.path.join(CURRENT_FILE_PATH, 'output')
FORMATTER = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')

LOCALHOST = '127.0.0.1'
PC_FIXED_IP = '192.168.1.100'
TRUSTED_CLIENTS = [LOCALHOST, PC_FIXED_IP]
COMMANDS_LISTENER_HOST = ''
COMMANDS_LISTENER_PORT = 54321
OUTPUT_FILE_RECEIVER_PORT = 23456
EOF_REACHED = 'EOF_REACHED'

# Uniform distribution (0..1]
def drand():
	return random.randint(0, RAND_MAX) / float(RAND_MAX + 1)

# Normal distribution, centered on 0, std dev 1
def random_normal():
	return -2 * math.log(drand())

# Used because else webots gives a strange segfault during cross compilation
def sqrt_rand_normal():
	return math.sqrt(random_normal())

def gaussrand():
	return sqrt_rand_normal() * math.cos(2 * math.pi * drand())

def recvall(conn, count):
	buf = b''
	while count:
		newbuf = conn.recv(count)
		if not newbuf: return None
		buf += newbuf
		count -= len(newbuf)
	return buf

def recvOneMessage(socket):
	lengthbuf = recvall(socket, 4)
	length, = struct.unpack('!I', lengthbuf)
	data = pickle.loads(recvall(socket, length))
	return data

def sendOneMessage(conn, data):
	packed_data = pickle.dumps(data)
	length = len(packed_data)
	conn.sendall(struct.pack('!I', length))
	conn.sendall(packed_data)

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

def getNextIDPath(path):
	nextID = 0
	filelist = sorted(os.listdir(path))
	if filelist and filelist[-1][0].isdigit():
		nextID = int(filelist[-1][0]) + 1
	return str(nextID)

# Reads the values contained in the passed configuration file and stores them in this object
class ConfigParser(object):
	def __init__(self, filename):
		json_data = open(filename)
		data = json.load(json_data)
		json_data.close()
		self.__address = data["address"]
		self.__port = data["port"]
		self.__bots = data["bots"]

	@property
	def address(self):
		return self.__address

	@property
	def port(self):
		return self.__port
	
	@property
	def bots(self):
		return self.__bots

# Represents a shared inbox object
class Inbox (object):
	def __init__(self, simulationLogger):
		self.__inbox = list()
		self.__inboxLock = threading.Lock()
		self.__simLogger = simulationLogger

	def append(self, data):
		with self.__inboxLock:
			self.__inbox.append(data)

	def popAll(self):
		itemsList = list()
		with self.__inboxLock:
			for i in self.__inbox:
				item = self.__inbox.pop(0)
				# self.__simLogger.debug("popAll - message fitness = " + str(item.fitness))
				itemsList.append(item)
		# self.__simLogger.debug("popAll - Popped " + str(itemsList))
		return itemsList

# Listens to incoming connections from other agents and delivers them to the corresponding thread
class ConnectionsListener (threading.Thread):
	def __init__(self, address, port, msgReceivers, simulationLogger):
		threading.Thread.__init__(self)
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		sock.bind((address, port))
		sock.listen(5)
		self.__address = address
		self.__port = port
		self.__socket = sock
		self.__msgReceivers = msgReceivers
		self.__simLogger = simulationLogger
		self.__isStopped = threading.Event()

	def run(self):
		try:
			self.__simLogger.debug('ConnectionsListener - RUNNING')

			nStopSockets = 0
			iterator = self.__msgReceivers.itervalues()
			while nStopSockets < len(self.__msgReceivers):
				conn, (addr, port) = self.__socket.accept()
				if addr == LOCALHOST:
					iterator.next().setStopSocket(conn)
					nStopSockets += 1

			while not self.__stopped():
				self.__simLogger.debug('ConnectionsListener - Waiting for accept')
				conn, (addr, port) = self.__socket.accept()
				if not self.__stopped():
					try:
						self.__simLogger.debug('ConnectionsListener - Received request from ' + addr + ' - FORWARDING to Receiver')
						self.__msgReceivers[addr].setConnectionSocket(conn)
					except:
						# Received connection from unknown IP
						self.__simLogger.warning("Exception: " + str(sys.exc_info()[0]) + ' - ' + traceback.format_exc())

			self.__socket.close()
			self.__simLogger.debug('ConnectionsListener STOPPED -> EXITING...')
		except:
			self.__simLogger.critical('Error in ConnectionsListener: ' + str(sys.exc_info()[0]) + ' - ' + traceback.format_exc())

	def stop(self):
		self.__isStopped.set()
		# If blocked on accept() wakes it up with a fake connection
		fake = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		fake.connect((LOCALHOST, self.__port))
		self.__simLogger.debug('ConnectionsListener - Fake connection')
		fake.close()

	def __stopped(self):
		return self.__isStopped.isSet()	

# Waits for incoming messages on one socket and stores them in the shared inbox
class MessageReceiver (threading.Thread):
	def __init__(self, ipAddress, inbox, simulationLogger):
		threading.Thread.__init__(self)
		self.__ipAddress = ipAddress
		self.__inbox = inbox
		self.__connectionSocket = None
		self.__stopSocket = None
		self.__isSocketAlive = threading.Condition()
		self.__isStopped = threading.Event()
		self.__simLogger = simulationLogger

	@property
	def ipAddress(self):
		return self.__ipAddress

	def setConnectionSocket(self, newSock):
		with self.__isSocketAlive:
			if not self.__connectionSocket and newSock:
				self.__connectionSocket = newSock
				self.__simLogger.debug('Receiver - ' + self.__ipAddress + ' - CONNECTED!!!')
				self.__isSocketAlive.notify()

	def setStopSocket(self, stopSock):
		self.__stopSocket = stopSock

	def run(self):
		try:
			self.__simLogger.debug('Receiver - ' + self.__ipAddress + ' - RUNNING')

			while not self.__stopped():
				
				# Waits while the connection is not set
				with self.__isSocketAlive:
					if not self.__connectionSocket and not self.__stopped():
						self.__simLogger.debug('Receiver - ' + self.__ipAddress + ' - Not connected: WAIT')
						self.__isSocketAlive.wait()

				if not self.__stopped():
					self.__simLogger.debug('Receiver - ' + self.__ipAddress + ' - Waiting on select')
					readable, _, _ = select.select([self.__connectionSocket, self.__stopSocket], [], [])
					if self.__stopSocket in readable:
						# 	Received a message (stop) from localhost
						self.__simLogger.debug('Receiver - ' + self.__ipAddress + ' - StopSocket is in readable')
						data = recvOneMessage(self.__stopSocket)
						self.__simLogger.debug('Received ' + data)
					elif self.__connectionSocket in readable:
						self.__simLogger.debug('Receiver - ' + self.__ipAddress + ' - ConnectionSocket is in readable')
						# 	Received a message from remote host
						try:
							data = recvOneMessage(self.__connectionSocket)
							self.__simLogger.debug('Receiver - ' + self.__ipAddress + ' - Received ' + str(data))
							if data and not self.__stopped():
								# self.__simLogger.debug('Receiver - ' + self.__ipAddress + ' - Appending ' + str(data))
								self.__inbox.append(data)
								self.__simLogger.debug('Receiver - ' + self.__ipAddress + ' - Appended ' + str(data) + ' to inbox.')
						except:
							# Error while receiving: current socket is corrupted -> closing it
							self.__simLogger.warning('Receiver - ' + self.__ipAddress + ' - Error while receiving - CLOSING socket!')
							self.__connectionSocket.close()
							self.__connectionSocket = None
		except:
			self.__simLogger.critical('Error in Receiver ' + self.__ipAddress + ': ' + str(sys.exc_info()[0]) + ' - ' + traceback.format_exc())

		self.__simLogger.debug('Receiver - ' + self.__ipAddress + ' - STOPPED -> EXITING...')

	def stop(self):
		self.__isStopped.set()
		with self.__isSocketAlive:
			self.__isSocketAlive.notify()

	def __stopped(self):
		return self.__isStopped.isSet()

# Sends outgoing messages to the remote host
class MessageSender (threading.Thread):
	def __init__(self, ipAddress, port, simulationLogger):
		threading.Thread.__init__(self)
		self.__ipAddress = ipAddress
		self.__port = port
		self.__outbox = list()
		self.__outboxNotEmpty = threading.Condition()
		self.__connectionSocket = None
		self.__isStopped = threading.Event()
		self.__simLogger = simulationLogger

	@property
	def ipAddress(self):
		return self.__ipAddress

	def __estabilishConnection(self):
		nAttempt = 0
		if self.__connectionSocket:
			self.__simLogger.debug('Sender - ' + self.__ipAddress + ' - ALREADY CONNECTED')
			return True
		# Otherwise retry to connect unless stop signal is sent
		while not self.__stopped():
			try:
				sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				sock.connect((self.__ipAddress, self.__port))
				self.__connectionSocket = sock
				self.__simLogger.debug('Sender - ' + self.__ipAddress + ' - CONNECTED @ attempt' + str(nAttempt))
				return True
			except:
				# Error during connect, new attempt if not stopped
				nAttempt += 1
		return False

	def outboxAppend(self, item):
		with self.__outboxNotEmpty:
			self.__outbox.append(item)
			self.__outboxNotEmpty.notify()

	def __outboxPop(self):
		item = None
		with self.__outboxNotEmpty:
			if not self.__outbox:
				self.__simLogger.debug('Sender - ' + self.__ipAddress + ' - EMPTY OUTBOX: WAIT')
				self.__outboxNotEmpty.wait()
			if not self.__stopped():
				self.__simLogger.debug('Sender - ' + self.__ipAddress + ' - OUTBOX is' + str(self.__outbox) + ' - taking ' + str(self.__outbox[0]))
				item = self.__outbox.pop(0)
		return item

	def run(self):
		try:
			self.__simLogger.debug('Sender - ' + self.__ipAddress + ' - RUNNING')
			while not self.__stopped():
				item = self.__outboxPop()
				self.__simLogger.debug('Sender - ' + self.__ipAddress + ' - OUTBOX popped ' + str(item))
				if item and self.__estabilishConnection():
					# Not stopped and has an item to send and an estabilished connection
					try:
						sendOneMessage(self.__connectionSocket, item)
						self.__simLogger.debug('Sender - ' + self.__ipAddress + ' - SENT' + str(item))
					except:
						# Error while sending: put back item in the outbox
						with self.__outboxNotEmpty:
							self.__outbox.insert(0, item)
						# Current socket is corrupted: closing it
						self.__connectionSocket.close()
						self.__connectionSocket = None
						self.__simLogger.warning('Sender - ' + self.__ipAddress + ' - Error while sending - CLOSED socket and restored OUTBOX:' + str(self.__outbox))
			self.__simLogger.debug('Sender - ' + self.__ipAddress + ' - STOPPED -> EXITING...')
		except:
			self.__simLogger.critical('Error in Sender ' + self.__ipAddress + ': ' + str(sys.exc_info()[0]) + ' - ' + traceback.format_exc())

	def stop(self):
		self.__isStopped.set()
		with self.__outboxNotEmpty:
			self.__outboxNotEmpty.notify()

	def __stopped(self):
		return self.__isStopped.isSet()

class Simulation(threading.Thread):
	def __init__(self, thymioController, debug):
		threading.Thread.__init__(self)
		config = ConfigParser(CONFIG_PATH)
		self.__address = config.address
		self.__port = config.port
		self.__thymioController = thymioController
		self.__tcPerformedAction = threading.Condition()
		self.__tcPA = False
		self.__msgSenders = dict()
		self.__msgReceivers = dict()
		self.__stopSockets = list()
		self.__stopped = False
		# simulation logging file
		self.__simLogger = logging.getLogger('simulationLogger')
		logLevel = logging.INFO
		if debug:
			logLevel = logging.DEBUG
		self.__simLogger.setLevel(logLevel)
		outputDir = os.path.join(OUTPUT_PATH, pr.EXPERIMENT_NAME)
		mkdir_p(outputDir)
		# self.__nextSimFilename = getNextIDPath(SIM_LOG_PATH) + '_' + time.strftime("%Y-%m-%d_%H-%M-%S")
		# simHandler = logging.FileHandler(os.path.join(SIM_LOG_PATH, self.__nextSimFilename + '_sim_debug.log'))
		self.__simulationLogFile = os.path.join(outputDir, pr.EXPERIMENT_NAME + '_sim_debug.log')
		self.__simulationOutputFile = os.path.join(outputDir, pr.EXPERIMENT_NAME + '_out.txt')
		simHandler = logging.FileHandler(self.__simulationLogFile)
		simHandler.setFormatter(FORMATTER)
		self.__simLogger.addHandler(simHandler)

		self.__inbox = Inbox(self.__simLogger)
		for bot in config.bots:
			address = bot["address"]
			self.__msgSenders[address] = MessageSender(address, bot["port"], self.__simLogger)
			self.__msgReceivers[address] = MessageReceiver(address, self.__inbox, self.__simLogger)
		self.__connListener = ConnectionsListener(self.__address, self.__port, self.__msgReceivers, self.__simLogger)

	def getLogger(self):
		return self.__simLogger
		
	def thymioControllerPerformedAction(self):
		with self.__tcPerformedAction:
			self.__tcPA = True
			self.__tcPerformedAction.notify()

	def __waitForControllerResponse(self):
		# Wait for ThymioController response
		with self.__tcPerformedAction:
			while not self.__tcPA:
				self.__tcPerformedAction.wait()
			self.__tcPA = False

	def __sendFiles(self, filepathOut, filepathLog):
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.connect((PC_FIXED_IP, OUTPUT_FILE_RECEIVER_PORT))
			
			# Send output file
			self.__simLogger.debug("Sending file " + str(filepathOut))
			sendOneMessage(s, pr.EXPERIMENT_NAME)
			fO = open(filepathOut, 'rb')
			l = fO.read(1024)
			while (l):
			    sendOneMessage(s, l)
			    l = fO.read(1024)
			self.__simLogger.debug("End of output file")
			sendOneMessage(s, EOF_REACHED)
			fO.close()
			
			# Send log file
			self.__simLogger.debug("Sending file " + str(filepathLog))
			fL = open(filepathLog, 'rb')
			l = fL.read(1024)
			while (l):
			    sendOneMessage(s, l)
			    l = fL.read(1024)
			fL.close()

			s.shutdown(socket.SHUT_WR)
			s.close()
		except:
			self.__simLogger.critical('Error while sending file: ' + str(sys.exc_info()[0]) + ' - ' + traceback.format_exc())

	# def CreateRandomGenome(self):
	# 	weights = list()
	# 	for i in range(0, classes.NMBRWEIGHTS):
	# 		rndGene = pr.range_weights * ((2 * random.randint(0, RAND_MAX)) / float(RAND_MAX)) - pr.range_weights
	# 		weights.append(rndGene)
	# 	return weights

	def __mutateMemome(self, solution):
		for i in range(0, classes.NMBRWEIGHTS):
			if solution.memome[i] != 100:
				# If sensor is enabled -> mutate weight adding gaussrand() * sigma
				solution.memome[i] = solution.memome[i] + gaussrand() * solution.sigma
				if solution.memome[i] > pr.range_weights:
					solution.memome[i] = pr.range_weights
				elif solution.memome[i] < -pr.range_weights:
					solution.memome[i] = -pr.range_weights

	def __runAndEvaluate(self, evaluee):
		# Recovery period (tau timesteps)
		self.__simLogger.info("Recovery period")
		for i in range(0, pr.tau):
			self.__runAndEvaluateForOneTimeStep(evaluee)
			# self.__simLogger.info("Timestep " + str(i) + " done")

		# Evaluate (evaltime timesteps)
		self.__simLogger.info("Evaluation")
		fitness = 0
		for i in range(0, pr.evaltime):
			fitness += self.__runAndEvaluateForOneTimeStep(evaluee)
		return fitness # fitness IN [-175000, 175000]

	def __runAndEvaluateForOneTimeStep(self, evaluee):
		# Read sensors: request to ThymioController
		self.__thymioController.readSensorsRequest()
		self.__waitForControllerResponse()
		psValues = self.__thymioController.getPSValues()

		# Calculate neural net
		left = 0
		right = 0
		for i in range(0, classes.NB_DIST_SENS):
			if evaluee.memome[i] != 100:
				# Only evaluate when sensor i is enabled: normalizedSensor in [-1,1]
				normalizedSensor = min((psValues[i] - (classes.SENSOR_MAX/2)) / (classes.SENSOR_MAX/2), 1.0)
				left  += normalizedSensor * evaluee.memome[i]
				right += normalizedSensor * evaluee.memome[i + (classes.NMBRWEIGHTS/2)]
		# Add bias weights
		left += evaluee.memome[(classes.NMBRWEIGHTS/2) - 1]
		right +=  evaluee.memome[(classes.NMBRWEIGHTS) - 1]
		# Apply hyberbolic tangent activation function -> left and right in [-1, 1]
		left = math.tanh(left)
		right = math.tanh(right)
		if left > 1 or left < -1 or right > 1 or right < -1:
			self.__simLogger.warning("WUT? left = " + str(left) + ", right = " + str(right))

		motorspeed = [0, 0]
		motorspeed[LEFT] = int(left * pr.real_maxspeed)
		motorspeed[RIGHT] = int(right * pr.real_maxspeed)
		# Set motor speed: request to ThymioController
		self.__thymioController.writeMotorspeedRequest(motorspeed)
		self.__waitForControllerResponse()
		# self.__simLogger.info("Simulation - Set motorspeed " + str(motorspeed)[1:-1])

		# Calculate penalty for rotating
		speedpenalty = 0
		if motorspeed[LEFT] > motorspeed[RIGHT]:
			speedpenalty = float((motorspeed[LEFT] - motorspeed[RIGHT])) / float(pr.real_maxspeed)
		else:
			speedpenalty = float((motorspeed[RIGHT] - motorspeed[LEFT])) / float(pr.real_maxspeed)
		if speedpenalty > 1:
			speedpenalty = 1

		# Calculate normalized distance to the nearest object
		sensorpenalty = 0
		for i in range(0, classes.NB_DIST_SENS):
			if evaluee.memome[classes.NB_DIST_SENS] != 100:
				# Only if sensor i is activated
				if sensorpenalty < (psValues[i] / float(classes.SENSOR_MAX)):
					sensorpenalty = (psValues[i] / float(classes.SENSOR_MAX))
		if sensorpenalty > 1:
			sensorpenalty = 1

		# fitness for 1 timestep in [-1000, 1000]
		return float(motorspeed[LEFT] + motorspeed[RIGHT]) * (1 - speedpenalty) * (1 - sensorpenalty)

	def run(self):
		# Start ConnectionsListener
		self.__connListener.start()

		# Set connections for stopping the receivers
		for i in range (0, len(self.__msgReceivers)):
			stopSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			stopSocket.connect((LOCALHOST, self.__port))
			self.__stopSockets.append(stopSocket)

		# Start message receivers
		for addr in self.__msgReceivers:
			self.__msgReceivers[addr].start()

		# Start message senders
		for addr in self.__msgSenders:
			self.__msgSenders[addr].start()

		# Wait for the simulation to be set on the controller
		self.__waitForControllerResponse()
		
		# Set color: request to ThymioController
		self.__thymioController.writeColorRequest([0,0,0]) # TODO: set different colors
		self.__waitForControllerResponse()

		# Set parameters
		seed = random.seed() # when no arguments, time of system is used
		lifetime = pr.max_robot_lifetime if pr.evolution == 1 else pr.total_evals # when no evolution, robot life is whole experiment length
		collected_genomes = [classes.RobotGenomeDataMessage(0,0.0,0) for i in range(pr.collected_genomes_max)]
		collected_memomes = [classes.RobotMemomeDataMessage(0,0.0,[0.0 for i in range(classes.NMBRWEIGHTS)]) for i in range(pr.collected_memomes_max)]
		evals = 0       # current evaluation
		generation = 0  # current generation
		champion = classes.Candidate([0.0 for i in range(classes.NMBRWEIGHTS)], 0.0, 0.0, 0)

		# start main loop
		while (evals < pr.total_evals):
			generation += 1
			self.__simLogger.info("########## GENERATION " + str(generation) + " ##########")
			self.__simLogger.info("Current champion: \nGenome: " + str(champion.genome) + "\nMemome: " + str(champion.memome) + "\nSigma: " + str(champion.sigma) + "\nFitness: " + str(champion.fitness))
		
			# INIT GENOME
			self.__simLogger.info("Collected genomes total = " + str(pr.collected_genomes_total))
			if pr.collected_genomes_total == 0: 
				# First generation or no genotypes collected -> random genome
				champion.genome = 0
				for i in range(classes.NB_DIST_SENS):
					# If random() <= probability -> sensor stays disabled, else -> activate it (OR)
					if random.random() > pr.disable_sensor: 
						champion.genome = champion.genome | 2**i
			else:
				# Pick mate by tournament from collected genotypes
				self.__simLogger.info("Pick mate by tournament")
				tournamentChampion = classes.RobotGenomeDataMessage(0, 0.0, 0)
				largestFitness = -1
				for i in range(pr.genome_tournament_size):
					tournamentChallenger = random.randint(0, pr.collected_genomes_total - 1)
					if (collected_genomes[tournamentChallenger].fitness > largestFitness or i == 0):
						tournamentChampion = collected_genomes[tournamentChallenger]
						largestFitness = collected_genomes[tournamentChallenger].fitness
				self.__simLogger.info("Tournament champion's genome: " + str(tournamentChampion.genome) + ", in binary is: " + str(bin(tournamentChampion.genome)))
			   
			   	# Create child with tournamentChampion
				for i in range(classes.NB_DIST_SENS):
					# Genome Crossover
					if random.random() < 0.5:
						self.__simLogger.info("Sensor " + str(i) + " crossover")
						currentBit = 2**i # Bit representing sensor i
						curBitTrue = ((champion.genome & currentBit) == (tournamentChampion.genome & currentBit))
						# If current layout and tournament champion layout disagree on value of sensor i: 
						if curBitTrue == 0:
							# Bit flip currentBit (XOR) on champion = take the value from tournamentChampion
							champion.genome = champion.genome ^ (2**i)
					# Mutation of Champion
					if random.random() < pr.mutate_sensor:
						self.__simLogger.info("Sensor " + str(i) + " bit flip mutation")
						# Bit flip currentBit (XOR) on champion
						champion.genome = champion.genome ^ 2**i
			pr.collected_genomes_total = 0
			pr.collected_memomes_total = 0
			
			# INIT NEW MEMOME
			tmp_weight = [random.uniform(-1*pr.range_weights, pr.range_weights) for x in range(classes.NMBRWEIGHTS)]
			for i in range(classes.NB_DIST_SENS):
				if ((champion.genome & 2**i) != 2**i): 
					# If sensor i is not enabled in the genome -> set neural network weights (left and right) to 100
					champion.memome[i] = 100.0
					champion.memome[i + (classes.NMBRWEIGHTS/2)] = 100.0
				else:
					# Else -> set random neural network weights for sensor i (left and right)
					champion.memome[i] = tmp_weight[i]
					champion.memome[i + (classes.NMBRWEIGHTS/2)] = tmp_weight[i + (classes.NMBRWEIGHTS/2)]
			# Set always random weights for bias node:
			champion.memome[(classes.NMBRWEIGHTS/2)-1] = tmp_weight[(classes.NMBRWEIGHTS/2)-1]
			champion.memome[(classes.NMBRWEIGHTS)-1] = tmp_weight[(classes.NMBRWEIGHTS)-1]
			
			champion.sigma = pr.sigmainitial
			try:
				# Evaluate the new individual
				champion.fitness = self.__runAndEvaluate(copy.deepcopy(champion))
				self.__simLogger.info("New champion: \nGenome: " + str(champion.genome) + "\nMemome: " + str(champion.memome) + "\nSigma: " + str(champion.sigma) + "\nFitness: " + str(champion.fitness))
				
				# DURING INDIVIDUAL LIFE
				for l in range(lifetime):
					self.__simLogger.info("@@@@@ EVALUATION  " + str(evals) + " @@@@@")
					evals += 1
			
					# Choose one between: Reevaluation | Social learning | Individual learning
					if (random.random() <= 0.2):
						# Reevaluation
						self.__simLogger.info("----- REEVALUATION -----")
						self.__simLogger.info("Old fitness = " + str(champion.fitness))
						re_fitness = self.__runAndEvaluate(copy.deepcopy(champion)) # XXX: why deepcopy??? Challenger is not changed during evaluation
						self.__simLogger.info("Reevaluated fitness = " + str(re_fitness))
						champion.fitness = champion.fitness * pr.re_weight + re_fitness * (1 - pr.re_weight)
						self.__simLogger.info("New fitness = " + str(champion.fitness))

					else:
						if (pr.collected_memomes_total > 0 and pr.sociallearning == 1 and random.random() <= 0.3):
							# Social learning
							self.__simLogger.info("----- SOCIAL LEARNING -----")
							socialChallenger = copy.deepcopy(champion) # Deep copy: we don't want to change the champion
							
							# Memome Crossover with last memotype in collected_memomes (LIFO order)
							lastCollectedMemome = collected_memomes[pr.collected_memomes_total-1].memome
							for i in range(classes.NMBRWEIGHTS):
								if (socialChallenger.memome[i] != 100.0 and lastCollectedMemome[i] != 100.0):
									# If sensor is enabled on both champion and lastCollectedMemome genomes -> overwrite corresponding meme on champion
									socialChallenger.memome[i] = lastCollectedMemome[i]
							pr.collected_memomes_total -= 1

							socialChallenger.fitness = self.__runAndEvaluate(copy.deepcopy(socialChallenger)) # XXX: why deepcopy??? Challenger is not changed during evaluation
							self.__simLogger.info("Social challenger memome = " + str(socialChallenger.memome))
							self.__simLogger.info("Social challenger fitness = " + str(socialChallenger.fitness))

							if socialChallenger.fitness > champion.fitness:
								self.__simLogger.info("Social challenger IS better -> Becomes champion")
								champion = copy.deepcopy(socialChallenger) # XXX: why deepcopy??? Champion is deepcopied into challenger during next iteration 
								champion.sigma = pr.sigma_min
							else:
								self.__simLogger.info("Social challenger NOT better -> Sigma is doubled")
								champion.sigma = champion.sigma * pr.sigma_increase
								if champion.sigma > pr.sigma_max:
									champion.sigma = pr.sigma_max
							self.__simLogger.info("New sigma = " + str(champion.sigma))
						else:
							# Individual learning
							self.__simLogger.info("----- INDIVIDUAL LEARNING -----")
							if pr.lifetimelearning == 1:
								challenger = copy.deepcopy(champion) # Deep copy: we don't want to mutate the champion
								self.__simLogger.info("Sigma = " + str(champion.sigma))
								self.__simLogger.info("Challenger memome before mutation = " + str(challenger.memome))
								self.__mutateMemome(copy.copy(challenger)) # XXX: why copy.copy??? challenger memome is changed also without copying
								self.__simLogger.info("Mutated challenger memome = " + str(challenger.memome))
								challenger.fitness = self.__runAndEvaluate(copy.deepcopy(challenger)) # XXX: why deepcopy??? Challenger is not changed during evaluation
								self.__simLogger.info("Mutated challenger fitness = " + str(challenger.fitness) + " VS Champion fitness = " + str(champion.fitness))

								if challenger.fitness > champion.fitness:
									self.__simLogger.info("Challenger IS better -> Becomes champion")
									champion = copy.deepcopy(challenger) # XXX: why deepcopy??? Champion is deepcopied into challenger during next iteration 
									champion.sigma = pr.sigma_min
								else:
									self.__simLogger.info("Challenger NOT better -> Sigma is doubled")
									champion.sigma = champion.sigma * pr.sigma_increase
									if champion.sigma > pr.sigma_max: # boundary rule
										champion.sigma = pr.sigma_max
								self.__simLogger.info("New sigma = " + str(champion.sigma))

					self.__simLogger.info("Current champion: \nGenome: " + str(champion.genome) + "\nMemome: " + str(champion.memome) + "\nSigma: " + str(champion.sigma) + "\nFitness: " + str(champion.fitness))

					# Write output: open file to append the values
					with open(self.__simulationOutputFile, 'a') as outputFile:
						outputFile.write(str(evals) + " \t " + str(generation) + " \t " + str(l) + " \t " + str(champion.fitness) + "\n")

					# Send messages: tell MessageSenders to do that
					self.__simLogger.info("Sending messages...")
					for addr in self.__msgSenders: # TODO: create just one message
						messageGen = classes.RobotGenomeDataMessage(addr, champion.fitness, champion.genome)
						self.__simLogger.info("Broadcast message genome = " + str(messageGen.genome))
						self.__msgSenders[addr].outboxAppend(messageGen)
						if pr.sociallearning == 1 and (champion.fitness / pr.max_fitness) > pr.threshold:
							messageMem = classes.RobotMemomeDataMessage(addr, champion.fitness, champion.memome)
							self.__simLogger.info("Broadcast message memome = " + str(messageMem.memome))
							self.__msgSenders[addr].outboxAppend(messageMem)

					# Read received messages from Inbox
					receivedMsgs = self.__inbox.popAll()
					self.__simLogger.info("Reading " + str(len(receivedMsgs)) + " received messages")
					for rmsg in receivedMsgs:
						if type(rmsg) is classes.RobotGenomeDataMessage:
							if pr.collected_genomes_total < pr.collected_genomes_max:
								self.__simLogger.info("Received genome = " + str(rmsg.genome))
								found = False
								for i in range(0, len(collected_genomes)):
									if collected_genomes[i].genome == rmsg.genome:
										collected_genomes[i].fitness = rmsg.fitness
										found = True
										break
								if not found:
									collected_genomes[pr.collected_genomes_total] = rmsg
									pr.collected_genomes_total += 1
						elif type(rmsg) is classes.RobotMemomeDataMessage:
							if pr.collected_memomes_total < pr.collected_memomes_max:
								self.__simLogger.info("Received memome = " + str(rmsg.memome))
								collected_memomes[pr.collected_memomes_total] = rmsg
								pr.collected_memomes_total += 1
						else:
							self.__simLogger.warning("WUT? Received stuff = " + str(rmsg))
			except Exception as e:
				self.__simLogger.critical("Ground sensors exception: " + str(e))
				self.__thymioController.stopThymioRequest()
				break

		self.__simLogger.info("End of while loop: "+ str(evals) + " >= "+ str(pr.total_evals))
		
		self.stop()
		self.__sendFiles(self.__simulationOutputFile, self.__simulationLogFile)

		self.__simLogger.info("_____END OF SIMULATION_____\n")

	def isStopped(self):
		return self.__stopped

	def stop(self):
		if self.__stopped:
			self.__simLogger.info('Simulation already stopped.')
			return
		self.__stopped = True

		# Stop Thymio from moving
		self.__thymioController.stopThymioRequest()

		# Stopping all the message senders: no more outgoing messages
		for addr in self.__msgSenders:
			self.__simLogger.info('Killing Sender ' + addr)
			self.__msgSenders[addr].stop()
			self.__msgSenders[addr].join()
		self.__simLogger.info('All MessageSenders: KILLED')

		# Stopping connections listener: no more incoming connections
		self.__connListener.stop()
		self.__connListener.join()
		self.__simLogger.info('ConnectionsListener: KILLED')

		# Stopping all the message receivers: no more incoming messages
		i = 0
		for addr in self.__msgReceivers:
			self.__simLogger.info('Killing Receiver ' + addr)
			self.__msgReceivers[addr].stop()
			sendOneMessage(self.__stopSockets[i], 'STOP') # Send stop messages
			self.__msgReceivers[addr].join()
			self.__stopSockets[i].close()
			i += 1
		self.__simLogger.info('All MessageReceivers: KILLED')

class ThymioController(object):
	def __init__(self, mainLogger):
		self.__mainLogger = mainLogger
		self.__psValue = [0,0,0,0,0,0,0]
		self.__psGroundAmbiantSensors = [0,0]
		self.__psGroundReflectedSensors = [0,0]
		self.__psGroundDeltaSensors = [0,0]
		self.__motorspeed = [0,0]
		self.__color = [0,0,0]
		
		self.__performActionReq = threading.Condition()
		self.__rSensorsReq = False
		self.__rGroundSensorsReq = False
		self.__wMotorspeedReq = False
		self.__wColorReq = False
		self.__stopThymioReq = False
		self.__killReq = False

		self.__commandsListener = None
		self.__simulationStarted = threading.Event()
		self.__simulation = None
		self.__simLogger = None

		# Init the main loop
		dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
		# Get stub of the Aseba network
		bus = dbus.SessionBus()
		# Create Aseba network 
		asebaNetworkObject = bus.get_object('ch.epfl.mobots.Aseba', '/')
		self.__asebaNetwork = dbus.Interface(asebaNetworkObject, dbus_interface='ch.epfl.mobots.AsebaNetwork')
		# self.__mainLogger.debug('Aseba nodes: ' + str(self.__asebaNetwork.GetNodesList()))
		# Load the aesl file
		self.__asebaNetwork.LoadScripts(AESL_PATH, reply_handler=self.__dbusEventReply, error_handler=self.__dbusError)
		# Schedules first run of the controller
		glib.idle_add(self.__execute)

	def setSimulation(self, simulation):
		if not self.__simulation:
			self.__simulation = simulation
			self.__simLogger = simulation.getLogger()
			self.__simulationStarted.set()

	def __dbusError(self, e):
		# there was an error on D-Bus, stop loop
		self.__simLogger.critical('dbus error: %s' % str(e) + "\nNow sleeping for 1 second and retrying...")
		time.sleep(1)
		raise Exception("dbus error")
		# self.__loop.quit()

	def __dbusEventReply(self):
		# correct replay on D-Bus, ignore
		pass

	def __dbusSendEventName(self, eventName, params):
		ok = False
		while not ok:
			try:
				self.__asebaNetwork.SendEventName(eventName, params, reply_handler=self.__dbusEventReply, error_handler=self.__dbusError)
				ok = True
			except:
				self.__simLogger.critical("Error during SEND EVENT NAME: " + eventName + " - " + str(params))
				ok = False

	def __dbusGetVariable(self, varName, replyHandler):
		ok = False
		while not ok:
			try:
				self.__asebaNetwork.GetVariable("thymio-II", varName, reply_handler=replyHandler, error_handler=self.__dbusError) 
				ok = True
			except:
				self.__simLogger.critical("Error during GET VARIABLE: " + varName)
				ok = False
	
	def __dbusSetMotorspeed(self):
		self.__dbusSendEventName("SetSpeed", self.__motorspeed)

	def __dbusSetColor(self):
		self.__dbusSendEventName("SetColor", self.__color)
	
	def __dbusGetProxSensorsReply(self, r):
		self.__psValue = r

	def __dbusGetProxSensors(self):
		self.__dbusGetVariable("prox.horizontal", self.__dbusGetProxSensorsReply)

	def __dbusGetGroundAmbiantReply(self, r):
		self.__psGroundAmbiantSensors = r

	def __dbusGetGroundReflectedReply(self, r):
		self.__psGroundReflectedSensors = r

	def __dbusGetGroundDeltaReply(self, r):
		self.__psGroundDeltaSensors = r	

	def __dbusGetGroundSensors(self):
		self.__dbusGetVariable("prox.ground.ambiant", self.__dbusGetGroundAmbiantReply)
		self.__dbusGetVariable("prox.ground.reflected", self.__dbusGetGroundReflectedReply)
		self.__dbusGetVariable("prox.ground.delta", self.__dbusGetGroundDeltaReply)

	def __stopThymio(self):
		# Red LEDs: Thymio stops moving
		self.__color = [32,16,0]
		self.__dbusSetColor()
		self.__motorspeed = [0,0]
		self.__dbusSetMotorspeed()
		self.__simulation = None
		self.__simulationStarted.clear()

	def __execute(self):
		# Wait for the simulation to be set
		while not self.__simulationStarted.isSet():
			self.__simulationStarted.wait()
		# Notifying that simulation has been set
		self.__simulation.thymioControllerPerformedAction()

		with self.__performActionReq:
			# Wait for requests:
			while not (self.__rSensorsReq or self.__rGroundSensorsReq or self.__wMotorspeedReq or self.__wColorReq or self.__stopThymioReq or self.__killReq):
				self.__performActionReq.wait()
			if self.__rSensorsReq:
				# Read sensor values
				self.__dbusGetProxSensors()
				self.__rSensorsReq = False
			elif self.__rGroundSensorsReq:
				# Read ground sensor values
				self.__dbusGetGroundSensors()
				self.__rGroundSensorsReq = False
			elif self.__wMotorspeedReq:
				# Write motorspeed
				self.__dbusSetMotorspeed() # IF COMMENTED: wheels don't move
				# Make sure that Thymio moved for 1 timestep
				time.sleep(classes.TIME_STEP) # TODO: more precise -> thymio should notify controller when it moved for 50 ms
				self.__wMotorspeedReq = False
			elif self.__wColorReq:
				self.__dbusSetColor()
				self.__wColorReq = False
			elif self.__stopThymioReq:
				# Stop Thymio
				self.__stopThymio()
				self.__stopThymioReq = False
			elif self.__killReq:
				# Kill everything
				self.__stopThymio()
				self.__color = [32,0,0]
				self.__dbusSetColor()
				self.__loop.quit()
				return False
		return True

	def readSensorsRequest(self):
		with self.__performActionReq:
			self.__rSensorsReq = True
			self.__performActionReq.notify()

	def readGroundSensorsRequest(self):
		with self.__performActionReq:
			self.__rGroundSensorsReq = True
			self.__performActionReq.notify()

	def writeMotorspeedRequest(self, motorspeed):
		with self.__performActionReq:
			self.__motorspeed = motorspeed
			self.__wMotorspeedReq = True
			self.__performActionReq.notify()

	def writeColorRequest(self, color):
		with self.__performActionReq:
			self.__color = color
			self.__wColorReq = True
			self.__performActionReq.notify()

	def stopThymioRequest(self):
		with self.__performActionReq:
			self.__stopThymioReq = True
			self.__performActionReq.notify()

	def killRequest(self):
		with self.__performActionReq:
			self.__killReq = True
			self.__performActionReq.notify()

	def getMotorSpeed(self):
		return self.__motorspeed

	def getPSValues(self):
		return self.__psValue

	def getGroundSensorsValues(self):
		return (self.__psGroundAmbiantSensors, self.__psGroundReflectedSensors, self.__psGroundDeltaSensors)

	def run(self):
		self.__mainLogger.debug('Controller - RUNNING')
		# Starts commands listener
		self.__cmdListener = CommandsListener(self, self.__mainLogger)
		self.__cmdListener.start()
		# Run gobject loop
		self.__loop = gobject.MainLoop()
		self.__loop.run()

class CommandsListener(threading.Thread):
	def __init__(self, thymioController, mainLogger):
		threading.Thread.__init__(self)
		# Create socket for listening to simulation commands
		self.__sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.__sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.__sock.bind((COMMANDS_LISTENER_HOST, COMMANDS_LISTENER_PORT))
		self.__sock.listen(5)
		self.__thymioController = thymioController
		self.__mainLogger = mainLogger
		self.__simulation = None

	def run(self):
		while 1:
			try:
				# Waiting for client...
				self.__mainLogger.debug("CommandListener - Waiting on accept...")
				conn, (addr, port) = self.__sock.accept()
				self.__mainLogger.debug('CommandListener - Received command from (' + addr + ', ' + str(port) + ')')
				if addr not in TRUSTED_CLIENTS:
					self.__mainLogger.error('CommandListener - Received connection request from untrusted client (' + addr + ', ' + str(port) + ')')
					continue
				
				# Receive one message
				self.__mainLogger.debug('CommandListener - Receiving command...')
				recvOptions = recvOneMessage(conn)
				self.__mainLogger.debug('CommandListener - Received ' + str(recvOptions))

				if recvOptions.kill:
					# Received killing command -> Stop everything
					self.__thymioController.killRequest()
					if self.__simulation:
						self.__simulation.stop()
					break
				elif recvOptions.start and (not self.__simulation or self.__simulation.isStopped()):
					# Received start request AND simulation is not running -> Start a new simulation
					self.__mainLogger.debug("CommandListener - Starting simulation...")
					self.__simulation = Simulation(self.__thymioController, recvOptions.debug)
					self.__thymioController.setSimulation(self.__simulation)
					self.__simulation.start()
				elif recvOptions.stop and self.__simulation and not self.__simulation.isStopped(): # TODO: Stop properly
					# Received stop request AND simulation is up and running -> Stop the simulation
					self.__mainLogger.debug("CommandListener - Stopping simulation...")
					self.__simulation.stop()
					self.__simulation = None
				elif recvOptions.stopthymio:
					self.__mainLogger.debug("CommandListener - Stopping Thymio...")
					self.__thymioController.stopThymio()

			except:
				self.__mainLogger.critical('Error in CommandsListener: ' + str(sys.exc_info()[0]) + ' - ' + traceback.format_exc())

		self.__mainLogger.debug('CommandListener - KILLED -> Exiting...')

if __name__ == '__main__':
	# Main logger for ThymioController and CommandsListener
	mainLogger = logging.getLogger('mainLogger')
	mainLogger.setLevel(logging.DEBUG)
	mainLogFilename = getNextIDPath(MAIN_LOG_PATH) + '_' + time.strftime("%Y-%m-%d_%H-%M-%S") + '_main_debug.log'
	mainHandler = logging.FileHandler(os.path.join(MAIN_LOG_PATH, mainLogFilename))
	mainHandler.setFormatter(FORMATTER)
	mainLogger.addHandler(mainHandler)
	try:
		# To avoid conflicts between gobject and python threads
		gobject.threads_init()
		dbus.mainloop.glib.threads_init()

		tC = ThymioController(mainLogger)
		tC.run()
		# ThymioController is the main loop now (needed for communication with the Thymio).
		mainLogger.debug("ThymioController stopped -> main stops.")
	except:
		mainLogger.critical('Error in main: ' + str(sys.exc_info()[0]) + ' - ' + traceback.format_exc())
