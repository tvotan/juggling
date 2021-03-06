"""
Module provides service to monitor circles.
"""

import logging
import numpy

from juggling.circle import Circle
from juggling.matcher import Matcher
from juggling.motion_tracker import UpDownMotionTracker


class Tracker:
    """
    Provides service to monitor circles: store them, match with changes and update circle states.
    """
    __ignore_threshold = 0

    def __init__(self, height, width):
        """
        Creates tracker to track circles on an image with specified sizes.

        :param height: Height of the image.
        :param width: Width of the image.
        """
        self.__circles = None
        self.__region = None
        self.__ignore = None
        self.__skip = 0

        self.__height = height
        self.__width = width

    def __len__(self):
        """
        :return: Return amount of tracked circles.
        """
        if self.__circles is None:
            return 0
        return len(self.__circles)

    def get_circles(self):
        """
        :return: Return circles that are tracked.
        :type: array_like
        """
        return self.__circles

    def get_complete_motions(self, index):
        """
        :param Index of circles that is tracked.

        :return: Return amount of complete motions for specified circle.
        :type: numeric
        """
        return self.__region[index].get_count()

    def predict(self, rectangles):
        """
        Predict position of each circle and use it as a fact.

        """
        if self.__circles is None or len(rectangles) == 0:
            return

        centers = []
        for (x, y, w, h) in rectangles:
            center = [int(x + w / 2), int(y + h / 2)]
            centers.append(center)

        predicted_positions = []
        segment_assigned_map = [False] * len(centers)
        centers = numpy.array(centers)
        for circle in self.__circles:
            x = circle.get_x_telemetry().predict_position()
            y = circle.get_y_telemetry().predict_position()
            r = circle.get_radius()
            # predicted_positions.append([x, y, r])   # old way - just predict using telemetry

            # new way - predict and find real object that is moved
            point = numpy.array([x, y])
            distances = numpy.sum((centers - point)**2, axis=1)
            closest_indexes = distances.argsort()
            for index in closest_indexes:
                if segment_assigned_map[index] is False:
                    segment_assigned_map[index] = True
                    predicted_positions.append([centers[index][0], centers[index][1], r])
                    break

        self.update(predicted_positions)

    def update(self, next_positions):
        """
        Calculates changes, analyse reliability and update circle states if it required.

        :param next_positions: New positions for each circles.
        """
        if self.__circles is None:
            self.__circles = [Circle(next_positions[i], None) for i in range(len(next_positions))]
            self.__region = [UpDownMotionTracker() for _ in next_positions]
            self.__ignore = [0] * len(next_positions)

        else:
            self.__match_circles(next_positions)

        self.__skip = 0

    def __update_state(self, index_circle, position):
        """
        Updates state of specified circle and marks circle as visible.

        :param index_circle: Index that defines circle.
        :param position: New position and radius for specified circle.
        """

        self.__circles[index_circle].update(position)
        self.__region[index_circle].track(position)
        self.__ignore[index_circle] = 0

    def __mark_circles_invisible(self):
        """
        Marks each circle as an invisible - not updated.
        """
        for circle in self.__circles:
            circle.invisible()

    def __match_circles(self, next_positions):
        """
        Match circles with new positions by calculating similarity and comparing with prediction in line with telemetry.
        :param next_positions: New positions for each circle.
        """
        self.__mark_circles_invisible()
        results = Matcher(self.__height, self.__width, self.__circles).match(next_positions)

        for result in results:
            index_circle = result.index_circle
            if result.relible is True or self.__ignore[index_circle] > self.__ignore_threshold:
                self.__update_state(index_circle, result.next_position)
            else:
                self.__ignore[index_circle] += 1
