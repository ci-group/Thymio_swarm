__author__ = 'alessandrozonta'

import threading
import socket
import sys
import traceback

import classes as cl

# Listens to incoming connections from other agents and delivers them to the corresponding thread
class ConnectionsListener(threading.Thread):
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
                if addr == cl.LOCALHOST:
                    iterator.next().setStopSocket(conn)
                    nStopSockets += 1

            while not self.__stopped():
                self.__simLogger.debug('ConnectionsListener - Waiting for accept')
                conn, (addr, port) = self.__socket.accept()
                if not self.__stopped():
                    try:
                        self.__simLogger.debug(
                            'ConnectionsListener - Received request from ' + addr + ' - FORWARDING to Receiver')
                        self.__msgReceivers[addr].setConnectionSocket(conn)
                    except:
                        # Received connection from unknown IP
                        self.__simLogger.warning(
                            "Exception: " + str(sys.exc_info()[0]) + ' - ' + traceback.format_exc())

            self.__socket.close()
            self.__simLogger.debug('ConnectionsListener STOPPED -> EXITING...')
        except:
            self.__simLogger.critical(
                'Error in ConnectionsListener: ' + str(sys.exc_info()[0]) + ' - ' + traceback.format_exc())

    def stop(self):
        self.__isStopped.set()
        # If blocked on accept() wakes it up with a fake connection
        fake = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        fake.connect((cl.LOCALHOST, self.__port))
        self.__simLogger.debug('ConnectionsListener - Fake connection')
        fake.close()

    def __stopped(self):
        return self.__isStopped.isSet()
