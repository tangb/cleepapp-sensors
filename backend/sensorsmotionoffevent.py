#!/usr/bin/env python
# -*- coding: utf-8 -*-

from cleep.libs.internals.event import Event


class SensorsMotionOffEvent(Event):
    """
    Sensors.motion.off event
    """

    EVENT_NAME = "sensors.motion.off"
    EVENT_PARAMS = ["sensor", "lastupdate", "duration"]

    def __init__(self, params):
        """
        Constructor

        Args:
            params (dict): event parameters
        """
        Event.__init__(self, params)
