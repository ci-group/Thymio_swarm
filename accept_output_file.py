import os, threading, socket, select, struct, pickle, errno, shutil, time
from color_tracking import *

N_THYMIOS = 2
TRACKING_SISTEM = False
OUTPUT_FILE_RECEIVER_PORT = 29456
CURRENT_FILE_PATH = os.path.abspath(os.path.dirname(__file__))
RECEIVED_OUTPUTS_PATH = os.path.join(CURRENT_FILE_PATH, 'received_outputs')
ALGORITHM_PATH = os.path.join(CURRENT_FILE_PATH, 'algorithm')
TEMP_COORD_PATH = os.path.join(CURRENT_FILE_PATH, 'temp_store_coord')
EOF_REACHED = 'EOF_REACHED'
LOG_FORMAT = "%(asctime)-15s:%(levelname)-8s:%(threadName)s:%(filename)s:%(funcName)s: %(message)s"
LOG_LEVEL = logging.INFO

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

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
    if not lengthbuf: return None
    length, = struct.unpack('!I', lengthbuf)
    recvD = recvall(socket, length)
    data = pickle.loads(recvD)
    return data

def sendOneMessage(conn, data):
    packed_data = pickle.dumps(data)
    length = len(packed_data)
    conn.sendall(struct.pack('!I', length))
    conn.sendall(packed_data)

class RecvFileThread(threading.Thread):
    def __init__(self, conn, addr):
        threading.Thread.__init__(self)
        self.__conn = conn
        self.__addr = addr
        self.savingDir = None

    def run(self):
        logging.info(str(self.__addr) + " Receiving experimentName...")
        experimentName = recvOneMessage(self.__conn)
        NAME_EXPERIMENT = experimentName
        self.savingDir = os.path.join(RECEIVED_OUTPUTS_PATH, experimentName)
        mkdir_p(self.savingDir)
        
        # Receive output file
        logging.info(str(self.__addr) + " Receiving output...")
        fO = open(self.savingDir + '/' + experimentName + '_' + str(self.__addr) + '_out.txt', 'wb')
        l = recvOneMessage(self.__conn)
        while l:
            fO.write(l)
            l = recvOneMessage(self.__conn)
            if l == EOF_REACHED:
                break
        fO.close()

        logging.info(str(self.__addr) + " Receiving log...")
        fL = open(self.savingDir + '/' + experimentName + '_' + str(self.__addr) + '_sim_debug.log', 'wb')
        l = recvOneMessage(self.__conn)
        while l:
            fL.write(l)
            l = recvOneMessage(self.__conn)
            if l == EOF_REACHED:
                break
        fL.close()

        logging.info(str(self.__addr) + " Receiving temperatue...")
        fT = open(self.savingDir + '/' + experimentName + '_' + str(self.__addr) + '_temp.txt', 'wb')
        l = recvOneMessage(self.__conn)
        while l:
            fT.write(l)
            l = recvOneMessage(self.__conn)
            if l == EOF_REACHED:
                break
        fT.close()

        logging.info(str(self.__addr) + " Receiving weight...")
        fW = open(self.savingDir + '/' + experimentName + '_' + str(self.__addr) + '_weight_out.txt', 'wb')
        l = recvOneMessage(self.__conn)
        while l:
            fW.write(l)
            l = recvOneMessage(self.__conn)
        fW.close()

if __name__ == '__main__':
    logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
    logging.info("START: " + time.strftime("%Y-%m-%d_%H-%M-%S"))

    if TRACKING_SISTEM:
        # Start tracking system
        tracker = Tracker(False, False)
        tracker.start()

    # Start socket
    s = socket.socket()         # Create a socket object
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', OUTPUT_FILE_RECEIVER_PORT))        # Bind to the port
    s.listen(N_THYMIOS)                 # Now wait for client connection.
    recvThreads = list()
    savingDir = None

    for i in range(0, N_THYMIOS):
        c, (addr, port) = s.accept()     # Establish connection with client.
        t = RecvFileThread(c, addr)
        recvThreads.append(t)
        t.start()
    for rT in recvThreads:
        rT.join()
        savingDir = rT.savingDir

    s.close()
    shutil.copyfile(ALGORITHM_PATH + "/Simulation.py", savingDir + "/Simulation.py")
    shutil.copyfile(ALGORITHM_PATH + "/classes.py", savingDir + "/classes.py")
    shutil.copyfile(ALGORITHM_PATH + "/parameters.py", savingDir + "/parameters.py")

    if TRACKING_SISTEM:
        # Stop tracking system
        tracker.stop()
        tracker.join()
        # Copy file from temp folder to right folder
        shutil.copyfile(TEMP_COORD_PATH + '/temp_name_red.txt', savingDir + "/red.txt")
        shutil.copyfile(TEMP_COORD_PATH + '/temp_name_yellow.txt', savingDir + "/yellow.txt")
        shutil.copyfile(TEMP_COORD_PATH + '/temp_name_green.txt', savingDir + "/green.txt")
        # Delete file
        os.remove(TEMP_COORD_PATH + '/temp_name_red.txt')
        os.remove(TEMP_COORD_PATH + '/temp_name_yellow.txt')
        os.remove(TEMP_COORD_PATH + '/temp_name_green.txt')

    logging.info("END: " + time.strftime("%Y-%m-%d_%H-%M-%S"))
