# Usage: python get_genome.py ESYT00/ESYT00_exp1/ESYT00_exp1
# where ESYT00 is the folder containing all the experiments, 
# ESYT00_exp1 is the folder containing the specific experiment
# and ESYT00_exp1 is the prefix of the file names in that folder

import sys
import datetime

ip_addresses = ["192.168.1.103", "192.168.1.52", "192.168.1.62", "192.168.1.72", "192.168.1.82", "192.168.1.92"]

class Robot(object):
    def __init__(self, ip, output):
        self.list_evaluation = list()
        self.list_coordinate = list()
        self.ip_address = ip
        self.outputPath = output
        self.diff_date = None

    def print_eval(self):
        toWrite = "#evaluation" + "\t" + "#fitness_obstacle" + "\t" + "#fitness_looking_red" + "\t" + "#fitness_pushing" + "\t" + "#fitness_looking_blue" + "\t" + "#fitness_bonus" + "\t" + "#fitness_total" + "\t" + "#pushing" + "\t" + "#learning_type" + "\n"
        for i in range(0, len(self.list_evaluation)):
            el = self.list_evaluation[i]
            toWrite += str(el.eval) + "\t" + str(round(float(el.fitness_obstacle))) + "\t" + str(el.fitness_looking_red) + "\t" + str(el.fitness_pushing) + "\t"
            toWrite += str(el.fitness_looking_blue) + "\t" + str(el.fitness_bonus) + "\t" + str(round(float(el.fitness_total))) + "\t"
            toWrite += str(el.pushing) + "\t" + str(el.learning_type) + "\n"
        outputFile = self.outputPath + "_thymio_" + str(self.ip_address) + "_single_fitness.txt"
        with open(outputFile, 'w') as oF:
            oF.write(toWrite)

    def print_pos(self):
        toWrite = "#evaluation" + "\t" + "#number" + "\t" + "#x" + "\t" + "#y" + "\n"
        for i in range(0, len(self.list_coordinate)):
            el = self.list_coordinate[i]
            toWrite += str(el.eval) + "\t" + str(el.pos) + "\t" + str(el.x) + "\t" + str(el.y) + "\n"
        if self.ip_address == "192.168.1.103":
            outputFile = self.outputPath + "_green_coordinate.txt"
        elif self.ip_address == "192.168.1.52":
            outputFile = self.outputPath + "_yellow_coordinate.txt"
        else:
            outputFile = self.outputPath + "_pucks_coordinate.txt"
        with open(outputFile, 'w') as oF:
            oF.write(toWrite)

    def change_robot_time(self):
        self.diff_date = self.list_coordinate[0].time - self.list_evaluation[0].time

    def set_evaluation_for_robot(self):
        pos = 0
        for i in range(0, len(self.list_evaluation)):
            self.list_evaluation[i].time += self.diff_date

        for i in range(1, len(self.list_evaluation)):
            while pos < len(self.list_coordinate) and self.list_coordinate[pos].time < self.list_evaluation[i].time:
                self.list_coordinate[pos].eval = i - 1
                pos += 1
            if i == 999:
                while pos < len(self.list_coordinate):
                    self.list_coordinate[pos].eval = 999
                    pos += 1


class Evaluation(object):
    def __init__(self, eval, time, obstacle, looking_red, push, looking_blue, bonus, total, learning_type):
        self.eval = eval
        self.time = time
        self.fitness_obstacle = obstacle
        self.fitness_pushing = push
        self.fitness_looking_red = looking_red
        self.fitness_looking_blue = looking_blue
        self.fitness_bonus = bonus
        self.fitness_total = total
        if int(push) > 0:
            self.pushing = 1
        else:
            self.pushing = 0
        self.learning_type = learning_type

class Coordinate(object):
    def __init__(self, time, pos, x, y):
        self.time = time
        self.eval = 0
        self.pos = pos
        self.x = x
        self.y = y


if __name__ == '__main__':
     for numb in range(0, 9):
        last = None
        name = "MsT_FORAGING_50%_" + str(numb)
        half_path = "received_outputs/" + name + "/"
        path = "received_outputs/" + name + "/" + name
        list_robot = list()
        # read debug file and write 6 fitness files:
        for i in range(0, len(ip_addresses)):
            rob = Robot(ip_addresses[i], path)
            toWrite = ""
            eof = False
            count = -2
            elem_split = None
            total = None
            time = None
            learning_type = " --- "
            check = [0, 0, 0, 0]
            first_check_fitness = False
            first_check_total_fitness = False
            with open(path + "_" + ip_addresses[i] + "_sim_debug.log", 'r') as inputFile:
                while not eof:
                    line = inputFile.readline()
                    if not line:
                        eof = True
                        break
                    if "Single fitness" in line:
                        count += 1
                        # print(count)
                        fitness_line = line[51:len(line)-2]
                        elem_split = fitness_line.split(",")
                        # print("slip {}".format(elem_split))
                        # toWrite += str(count) + "\t"
                        # for j in range(len(elem_split)):
                        #     toWrite += str(elem_split[j]) + "\t"
                        if first_check_fitness:
                            check[0] = 1
                        first_check_fitness = True
                    if "INFO: Fitness ->" in line:
                        total = line[42:]
                        # print("fit_line {}".format(fit_line))
                        # toWrite += str(fit_line) + "\t"
                        if first_check_total_fitness:
                            check[1] = 1
                        first_check_total_fitness = True
                    if "INFO: @@@@@ EVALUATION" in line:
                        time = datetime.datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S,%f")
                        check[2] = 1
                    if "INFO: ----- " in line:
                        learning_type = line[38:-6]
                        check[3] = 1
                    if sum(check) == 4:
                        check = [0, 0, 0, 0]
                        evaluation = Evaluation(count, time, elem_split[0], elem_split[1], elem_split[2], elem_split[3], elem_split[4], total, learning_type)
                        # print("evaluation {}".format(evaluation))
                        rob.list_evaluation.append(evaluation)

            rob.print_eval()
            eof = False
            # green robot
            if ip_addresses[i] == "192.168.1.103":
                with open(half_path + "green.txt", 'r') as inputFileTwo:
                    while not eof:
                        line = inputFileTwo.readline()
                        if not line:
                            eof = True
                            break
                        elem_split = line.split(" ")
                        coord = Coordinate(datetime.datetime.strptime(elem_split[0], "%Y-%m-%dT%H:%M:%S.%f"), 0, elem_split[2], elem_split[4][:-1])
                        rob.list_coordinate.append(coord)
                rob.change_robot_time()
                rob.set_evaluation_for_robot()
                rob.print_pos()

            # yellow  robot
            if ip_addresses[i] == "192.168.1.52":
                with open(half_path + "yellow.txt", 'r') as inputFileTwo:
                    while not eof:
                        line = inputFileTwo.readline()
                        if not line:
                            eof = True
                            break
                        elem_split = line.split(" ")
                        coord = Coordinate(datetime.datetime.strptime(elem_split[0], "%Y-%m-%dT%H:%M:%S.%f"), 0, elem_split[2], elem_split[4][:-1])
                        rob.list_coordinate.append(coord)
                rob.change_robot_time()
                rob.set_evaluation_for_robot()
                rob.print_pos()

            # pucks
            if ip_addresses[i] == "192.168.1.62":
                with open(half_path + "red.txt", 'r') as inputFileTwo:
                    while not eof:
                        line = inputFileTwo.readline()
                        if not line:
                            eof = True
                            break
                        elem_split = line.split(" ")
                        coord = Coordinate(datetime.datetime.strptime(elem_split[0], "%Y-%m-%dT%H:%M:%S.%f"), elem_split[2], elem_split[4], elem_split[6][:-1])
                        rob.list_coordinate.append(coord)
                rob.change_robot_time()
                rob.set_evaluation_for_robot()
                rob.print_pos()

            list_robot.append(rob)
    # time = datetime.datetime.strptime("2015-06-18 05:00:01,000", "%Y-%m-%d %H:%M:%S,%f")  # 192.168.1.103
    # time1 = datetime.datetime.strptime("2015-10-07 16:17:25,000", "%Y-%m-%d %H:%M:%S,%f")  # pc
    # diff_time_103 = time1-time
    # print(diff)
    # print(time + diff)
    # time2 = datetime.datetime.strptime("2015-06-18 02:00:59,000", "%Y-%m-%d %H:%M:%S,%f")  # 192.168.1.103
    # print(time2 + diff)

    #                 while True:
    #                     line = inputFile.readline()
    #                     if not line:
    #                         eof = True
    #                         break
    #                     if "New champion:" in line:
    #                         genomeDec = int(inputFile.readline()[8:])
    #                         genome = "{0:07b}".format(genomeDec)
    #                         toWrite += str(generation) + "\t"
    #                         for c in genome:
    #                             toWrite += c + "\t"
    #                         toWrite += "\n"
    #                         break
    #     with open(outputFile, 'w') as oF:
    #         oF.write(toWrite)
    #
    # # merge genome files in one:
    # outputFileFinal = path + "_genome.txt"
    # toWrite = ""
    # for i in range(1, 9):
    #     for j in range(1, 7):
    #         inputFile = path + "_thymio-" + str(j) + "_genome.txt"
    #         with open(inputFile, "r") as iF:
    #             line = ""
    #             for k in range(0, i):
    #                 line = iF.readline()
    #             (before, sep, after) = line.partition("\t")
    #             toWrite += before + "\tthymio-" + str(j) + "\t" + after
    #
    # with open(outputFileFinal, 'w') as oF:
    #     oF.write(toWrite)
