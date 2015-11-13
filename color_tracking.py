#!/usr/bin/env python
import json
import logging
import os
#import classes
import pickle
import socket
import struct
import threading
import traceback
import cv2
import math
import numpy as np
import pipes
import sys
import time
import datetime

__author__ = 'vcgorka'
# modified by Alessandro Zonta
# improvement:
# - change hsv color value
# - add four color
# - add size image/resize custom size
# - add show map parameters

LOG_FORMAT = "%(asctime)-15s:%(levelname)-8s:%(threadName)s:%(filename)s:%(funcName)s: %(message)s"
LOG_LEVEL = logging.CRITICAL


class Tracker(threading.Thread):
    def __init__(self, show_map, log_file):
        threading.Thread.__init__(self)
        logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
        logging.info("Starting tracking system..")
        self.show_map = show_map
        self.log_file = log_file
        if self.show_map:
            cv2.namedWindow("Colour Tracker", cv2.CV_WINDOW_AUTOSIZE)
        self.capture = cv2.VideoCapture(0)
        # I need 16:9 to see the goal
        self.capture.set(3, 1280)
        self.capture.set(4, 720)
        self.scale_down = 1
        self.red = []
        self.x_yellow = 0
        self.y_yellow = 0
        self.x_green = 0
        self.y_green = 0
        self.x_blue = 0
        self.y_blue = 0
        # Precedent value vector
        self.precedent_position = [0, 0, 0, 0]
        # radius of circle in track map (BGR)
        self.circle = 5
        # Color of object track object_tracking_box
        self.color_yellow = (0, 255, 255)  # yellow
        self.color_red = (0, 0, 255)  # red
        self.color_green = (0, 255, 0)  # green
        self.color_blue = (255, 0, 0)  # blue
        # threshold area color tracked
        self.threshold_area = 500
        # save log
        current_file_path = os.path.abspath(os.path.dirname(__file__))
        output_path = os.path.join(current_file_path, 'temp_store_coord')
        try:
            os.makedirs(output_path)
        except OSError as exc:  # Python >2.5
                pass
        self.__redOutput = os.path.join(output_path, 'temp_name_red.txt')
        self.__yellowOutput = os.path.join(output_path, 'temp_name_yellow.txt')
        self.__greenOutput = os.path.join(output_path, 'temp_name_green.txt')

        self.__isCameraAlive = threading.Condition()
        self.__isStopped = threading.Event()

    def run(self):
        # Counter for frame number
        counter = 0

        # create image_frame for track map, set to input resolution
        image_frame2 = np.zeros((720, 800, 3), np.uint8)

        while not self.__stopped():
            counter += 1
            # Import video frame from capture
            f, video_frame = self.capture.read()

            # preprocess the video frame # resize image cutting useless border
            video_frame = video_frame[0:720, 300:1100]
            image_frame = cv2.GaussianBlur(video_frame, (5, 5), 0)
            image_frame = cv2.cvtColor(image_frame, cv2.COLOR_BGR2HSV)
            image_frame = cv2.resize(image_frame,
                                     (len(video_frame[0]) / self.scale_down, len(video_frame) / self.scale_down))

            # define the colors, need to be set before experiment
            # red tracking -> box
            self.red_tracking(image_frame, video_frame, image_frame2, counter)

            # yellow tracking -> robot
            self.yellow_tracking(image_frame, video_frame, image_frame2, counter)

            # green tracking
            self.green_tracking(image_frame, video_frame, image_frame2, counter)

            if cv2.waitKey(20) == 27:
                cv2.destroyWindow("Colour Tracker")
                self.capture.release()

            # Print and save
            yellow = [self.x_yellow, self.y_yellow]
            green = [self.x_green, self.y_green]
            if self.log_file:
                logging.info("Yellow --> {}".format(yellow))
                logging.info("Green --> {}".format(green))
                logging.info("Red --> {}".format(self.red))

            # Write yellow output
            with open(self.__yellowOutput, 'a') as outputFile:
                outputFile.write(datetime.datetime.now().isoformat() + " \t " + str(self.x_yellow) + " \t " + str(self.y_yellow))
                outputFile.write("\n")

            # Write green output
            with open(self.__greenOutput, 'a') as outputFile:
                outputFile.write(datetime.datetime.now().isoformat() + " \t " + str(self.x_green) + " \t " + str(self.y_green))
                outputFile.write("\n")

            # Write red output
            with open(self.__redOutput, 'a') as outputFile:
                for i in range(0, len(self.red)):
                    outputFile.write(datetime.datetime.now().isoformat() + " \t " + str(i) + " \t " + str(self.red[i][0]) + " \t " + str(self.red[i][1]))
                    outputFile.write("\n")

            # Delete red vector
            del self.red[:]

            if self.show_map:
                cv2.imshow("Colour Tracker", video_frame)
            sys.stdout.flush()

    def stop(self):
        logging.info("Stopping tracking system..")
        self.__isStopped.set()
        logging.info("Stopping tracking system..")
        with self.__isCameraAlive:
            self.__isCameraAlive.notify()

    def __stopped(self):
        return self.__isStopped.isSet()

    # red -> box tracking
    def red_tracking(self, image_frame, video_frame, image_frame2, counter):
        # define the colors, need to be set before experiment
        # red_lower = np.array([0, 150, 100], np.uint8)
        # red_upper = np.array([5, 255, 255], np.uint8)
        red_lower = np.array([120, 80, 150], np.uint8)
        red_upper = np.array([180, 255, 255], np.uint8)
        red_binary = cv2.inRange(image_frame, red_lower, red_upper)
        red_binary = cv2.dilate(red_binary, np.ones((15, 15), "uint8"))
        contours_red_objects, hierarchy_red = cv2.findContours(red_binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        # I am tracking all the red points
        for idx, contour in enumerate(contours_red_objects):
            moment = cv2.moments(contour)
            if moment["m00"] > self.threshold_area / self.scale_down:
                object_tracking_rect = cv2.minAreaRect(contour)
                object_tracking_box = np.int0(cv2.cv.BoxPoints(((object_tracking_rect[0][0] * self.scale_down,
                                                                 object_tracking_rect[0][1] * self.scale_down), (
                                                                    object_tracking_rect[1][0] * self.scale_down,
                                                                    object_tracking_rect[1][1] * self.scale_down),
                                                                object_tracking_rect[2])))
                cv2.drawContours(video_frame, [object_tracking_box], 0, self.color_red, 2)

                # calculate Coordinates
                x_red = ((object_tracking_box[0][0] + object_tracking_box[1][0] + object_tracking_box[2][0] +
                               object_tracking_box[3][0]) / 4)
                y_red = ((object_tracking_box[0][1] + object_tracking_box[1][1] + object_tracking_box[2][1] +
                               object_tracking_box[3][1]) / 4)
                self.red.append((x_red,y_red))

                # display coordinates in map
                if self.show_map:
                    cv2.circle(image_frame2, (x_red, y_red), self.circle, self.color_red, thickness=-1,
                               lineType=8, shift=0)
                    cv2.imshow("map", image_frame2)

                # print objectnr + frame number + x coordinate + y coordinate
                logging.debug("1." + str(counter) + ", " + str(x_red) + ", " + str(y_red) + ";")

                # chek the mask color -> only for debug
                # mask = cv2.inRange(image_frame, red_lower, red_upper)
                # cv2.imshow('maskRed', mask)

    # yellow -> robot tracking
    def yellow_tracking(self, image_frame, video_frame, image_frame2, counter):
        # yellow object tracking - search for biggest yellow object in frame
        # define the colors, need to be set before experiment
        yellow_lower = np.array([20, 50, 50], np.uint8)
        yellow_upper = np.array([40, 255, 255], np.uint8)
        yellow_binary = cv2.inRange(image_frame, yellow_lower, yellow_upper)
        yellow_binary = cv2.dilate(yellow_binary, np.ones((15, 15), "uint8"))
        contours_yellow_objects, hierarchy_blue = cv2.findContours(yellow_binary, cv2.RETR_LIST,
                                                                   cv2.CHAIN_APPROX_SIMPLE)

        max_yellow_area_object = 0
        largest_contour_yellow = None

        for idx, contour in enumerate(contours_yellow_objects):
            yellow_area_object = cv2.contourArea(contour)
            if yellow_area_object > max_yellow_area_object:
                max_yellow_area_object = yellow_area_object
                largest_contour_yellow = contour

        if not largest_contour_yellow is None:
            moment = cv2.moments(largest_contour_yellow)
            if moment["m00"] > self.threshold_area / self.scale_down:
                object_tracking_rect = cv2.minAreaRect(largest_contour_yellow)
                object_tracking_box = np.int0(cv2.cv.BoxPoints(((object_tracking_rect[0][0] * self.scale_down,
                                                                 object_tracking_rect[0][1] * self.scale_down), (
                                                                    object_tracking_rect[1][0] * self.scale_down,
                                                                    object_tracking_rect[1][1] * self.scale_down),
                                                                object_tracking_rect[2])))
                cv2.drawContours(video_frame, [object_tracking_box], 0, self.color_yellow, 2)

                # calculate Coordinates
                self.x_yellow = (
                    (object_tracking_box[0][0] + object_tracking_box[1][0] + object_tracking_box[2][0] +
                     object_tracking_box[3][0]) / 4)
                self.y_yellow = (
                    (object_tracking_box[0][1] + object_tracking_box[1][1] + object_tracking_box[2][1] +
                     object_tracking_box[3][1]) / 4)

                # display coordinates in map
                if self.show_map:
                    cv2.circle(image_frame2, (self.x_yellow, self.y_yellow), self.circle, self.color_yellow,
                               thickness=-1,
                               lineType=8,
                               shift=0)
                    cv2.imshow("map", image_frame2)

                # print objectnr + frame number + x coordinate + y coordinate
                logging.debug("2." + str(counter) + ", " + str(self.x_yellow) + ", " + str(self.y_yellow) + ";")

                # chek the mask color -> only for debug
                # mask = cv2.inRange(image_frame, yellow_lower, yellow_upper)
                # cv2.imshow('maskYellow', mask)

    # green
    def green_tracking(self, image_frame, video_frame, image_frame2, counter):
        # green object tracking - search for biggest green object in frame

        # define the colors, need to be set before experiment
        # [40,100,100]
        # [80, 150, 150]
        # these value fit with green box, but not the other green
        green_lower = np.array([45, 40, 110], np.uint8)
        green_upper = np.array([90, 90, 160], np.uint8)
        green_binary = cv2.inRange(image_frame, green_lower, green_upper)
        green_binary = cv2.dilate(green_binary, np.ones((15, 15), "uint8"))
        contours_green_objects, hierarchy_blue = cv2.findContours(green_binary, cv2.RETR_LIST,
                                                                  cv2.CHAIN_APPROX_SIMPLE)

        max_green_area_object = 0
        largest_contour_green = None

        for idx, contour in enumerate(contours_green_objects):
            green_area_object = cv2.contourArea(contour)
            if green_area_object > max_green_area_object:
                max_green_area_object = green_area_object
                largest_contour_green = contour

        if largest_contour_green is not None:
            moment = cv2.moments(largest_contour_green)
            if moment["m00"] > self.threshold_area / self.scale_down:
                object_tracking_rect = cv2.minAreaRect(largest_contour_green)
                object_tracking_box = np.int0(cv2.cv.BoxPoints(((object_tracking_rect[0][0] * self.scale_down,
                                                                 object_tracking_rect[0][1] * self.scale_down), (
                                                                    object_tracking_rect[1][0] * self.scale_down,
                                                                    object_tracking_rect[1][1] * self.scale_down),
                                                                object_tracking_rect[2])))
                cv2.drawContours(video_frame, [object_tracking_box], 0, self.color_green, 2)

                # calculate Coordinates
                self.x_green = (
                    (object_tracking_box[0][0] + object_tracking_box[1][0] + object_tracking_box[2][0] +
                     object_tracking_box[3][0]) / 4)
                self.y_green = (
                    (object_tracking_box[0][1] + object_tracking_box[1][1] + object_tracking_box[2][1] +
                     object_tracking_box[3][1]) / 4)

                # display coordinates in map
                if self.show_map:
                    cv2.circle(image_frame2, (self.x_green, self.y_green), self.circle, self.color_green, thickness=-1,
                               lineType=8,
                               shift=0)
                    cv2.imshow("map", image_frame2)

                # print objectnr + frame number + x coordinate + y coordinate
                logging.debug("3." + str(counter) + ", " + str(self.x_green) + ", " + str(self.y_green) + ";")

                # chek the mask color -> only for debug
                # mask = cv2.inRange(image_frame, green_lower, green_upper)
                # cv2.imshow('maskGreen', mask)

    # blue
    def blue_tracking(self, image_frame, video_frame, image_frame2, counter):
        # blue object tracking - search for biggest blue object in frame

        # define the colors, need to be set before experiment
        blue_lower = np.array([80, 20, 30], np.uint8)
        blue_upper = np.array([120, 255, 255], np.uint8)
        blue_binary = cv2.inRange(image_frame, blue_lower, blue_upper)
        blue_binary = cv2.dilate(blue_binary, np.ones((15, 15), "uint8"))
        contours_blue_objects, hierarchy_blue = cv2.findContours(blue_binary, cv2.RETR_LIST,
                                                                 cv2.CHAIN_APPROX_SIMPLE)

        max_blue_area_object = 0
        largest_contour_blue = None

        for idx, contour in enumerate(contours_blue_objects):
            blue_area_object = cv2.contourArea(contour)
            if blue_area_object > max_blue_area_object:
                max_blue_area_object = blue_area_object
                largest_contour_blue = contour

        if not largest_contour_blue is None:
            moment = cv2.moments(largest_contour_blue)
            if moment["m00"] > self.threshold_area / self.scale_down:
                object_tracking_rect = cv2.minAreaRect(largest_contour_blue)
                object_tracking_box = np.int0(cv2.cv.BoxPoints(((object_tracking_rect[0][0] * self.scale_down,
                                                                 object_tracking_rect[0][1] * self.scale_down), (
                                                                    object_tracking_rect[1][0] * self.scale_down,
                                                                    object_tracking_rect[1][1] * self.scale_down),
                                                                object_tracking_rect[2])))
                cv2.drawContours(video_frame, [object_tracking_box], 0, self.color_blue, 2)

                # calculate Coordinates
                self.x_blue = (
                    (object_tracking_box[0][0] + object_tracking_box[1][0] + object_tracking_box[2][0] +
                     object_tracking_box[3][0]) / 4)
                self.y_blue = (
                    (object_tracking_box[0][1] + object_tracking_box[1][1] + object_tracking_box[2][1] +
                     object_tracking_box[3][1]) / 4)

                # display coordinates in map
                if self.show_map:
                    cv2.circle(image_frame2, (self.x_blue, self.y_blue), self.circle, self.color_blue, thickness=-1,
                               lineType=8,
                               shift=0)
                    cv2.imshow("map", image_frame2)

                # print objectnr + frame number + x coordinate + y coordinate
                logging.debug("4." + str(counter) + ", " + str(self.x_blue) + ", " + str(self.y_blue) + ";")

                # chek the mask color -> only for debug
                # mask = cv2.inRange(image_frame, blue_lower, blue_upper)
                # cv2.imshow('maskBlue', mask)

    # black
    def black_tracking(self, image_frame, video_frame, image_frame2, counter):
        # black object tracking - search for biggest black object in frame

        # define the colors, need to be set before experiment
        blue_lower = np.array([0, 0, 0], np.uint8)
        blue_upper = np.array([180, 255, 50], np.uint8)
        blue_binary = cv2.inRange(image_frame, blue_lower, blue_upper)
        blue_binary = cv2.dilate(blue_binary, np.ones((15, 15), "uint8"))
        contours_blue_objects, hierarchy_blue = cv2.findContours(blue_binary, cv2.RETR_LIST,
                                                                 cv2.CHAIN_APPROX_SIMPLE)

        max_blue_area_object = 0
        largest_contour_blue = None

        for idx, contour in enumerate(contours_blue_objects):
            blue_area_object = cv2.contourArea(contour)
            if blue_area_object > max_blue_area_object:
                max_blue_area_object = blue_area_object
                largest_contour_blue = contour

        if not largest_contour_blue is None:
            moment = cv2.moments(largest_contour_blue)
            if moment["m00"] > self.threshold_area / self.scale_down:
                object_tracking_rect = cv2.minAreaRect(largest_contour_blue)
                object_tracking_box = np.int0(cv2.cv.BoxPoints(((object_tracking_rect[0][0] * self.scale_down,
                                                                 object_tracking_rect[0][1] * self.scale_down), (
                                                                    object_tracking_rect[1][0] * self.scale_down,
                                                                    object_tracking_rect[1][1] * self.scale_down),
                                                                object_tracking_rect[2])))
                cv2.drawContours(video_frame, [object_tracking_box], 0, self.color_red, 2)

                # calculate Coordinates
                self.x_blue = (
                    (object_tracking_box[0][0] + object_tracking_box[1][0] + object_tracking_box[2][0] +
                     object_tracking_box[3][0]) / 4)
                self.y_blue = (
                    (object_tracking_box[0][1] + object_tracking_box[1][1] + object_tracking_box[2][1] +
                     object_tracking_box[3][1]) / 4)

                # print objectnr + frame number + x coordinate + y coordinate
                logging.debug("BLACK" + str(counter) + ", " + str(self.x_blue) + ", " + str(self.y_blue) + ";")

                if cv2.waitKey(20) == 27:
                    cv2.destroyWindow("Colour Tracker")
                    self.capture.release()
                    return False

        # chek the mask color -> only for debug
        # mask = cv2.inRange(image_frame, blue_lower, blue_upper)
        # cv2.imshow('maskBlue', mask)
        return True



if __name__ == "__main__":
    tracker = Tracker(False, True)
    tracker.start()

    # tracker.stop()
    # tracker.join()
