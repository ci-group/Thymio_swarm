# algorithm.py created on March 12, 2015. Jacqueline Heinerman & Massimiliano Rango
# modified by Alessandro Zonta on June 25, 2015

import dbus
import dbus.mainloop.glib
import gobject
from ThymioController import *

import classes as cl


def getNextIDPath(path):
    nextID = 0
    filelist = sorted(os.listdir(path))
    if filelist and filelist[-1][0].isdigit():
        nextID = int(filelist[-1][0]) + 1
    return str(nextID)


if __name__ == '__main__':
    # Main logger for ThymioController and CommandsListener
    mainLogger = logging.getLogger('mainLogger')
    mainLogger.setLevel(logging.DEBUG)
    mainLogFilename = getNextIDPath(cl.MAIN_LOG_PATH) + '_' + time.strftime("%Y-%m-%d_%H-%M-%S") + '_main_debug.log'
    mainHandler = logging.FileHandler(os.path.join(cl.MAIN_LOG_PATH, mainLogFilename))
    mainHandler.setFormatter(cl.FORMATTER)
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
        # mainLogger.critical('Error in main: ' + str(sys.exc_info()[0]) + ' - ' + traceback.forma_exc())
        mainLogger.critical('Error in main')
