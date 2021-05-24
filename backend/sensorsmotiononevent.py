#!/usr/bin/env python
# -*- coding: utf-8 -*-

from cleep.libs.internals.event import Event


class SensorsMotionOnEvent(Event):
    """
    Sensors.motion.on event
    """

    EVENT_NAME = "sensors.motion.on"
    EVENT_PARAMS = ["sensor", "lastupdate"]

    def __init__(self, params):
        """
        Constructor

        Args:
            params (dict): event parameters
        """
        Event.__init__(self, params)
