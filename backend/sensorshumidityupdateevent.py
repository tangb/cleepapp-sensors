#!/usr/bin/env python
# -*- coding: utf-8 -*-

from cleep.libs.internals.event import Event


class SensorsHumidityUpdateEvent(Event):
    """
    Sensors.humidity.update event
    """

    EVENT_NAME = "sensors.humidity.update"
    EVENT_PARAMS = ["sensor", "lastupdate", "humidity"]

    def __init__(self, params):
        """
        Constructor

        Args:
            params (dict): event parameters
        """
        Event.__init__(self, params)

