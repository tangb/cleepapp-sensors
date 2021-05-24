#!/usr/bin/env python
# -*- coding: utf-8 -*-

from cleep.libs.internals.event import Event


class SensorsTemperatureUpdateEvent(Event):
    """
    Sensors.temperature.update event
    """

    EVENT_NAME = "sensors.temperature.update"
    EVENT_PARAMS = ["sensor", "lastupdate", "celsius", "fahrenheit"]

    def __init__(self, params):
        """
        Constructor

        Args:
            params (dict): event parameters
        """
        Event.__init__(self, params)
