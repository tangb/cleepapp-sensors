#!/usr/bin/env python
# -*- coding: utf-8 -*-

from raspiot.events.event import Event

class SensorsTemperatureUpdateEvent(Event):
    """
    Sensors.temperature.update event
    """

    EVENT_NAME = u'sensors.temperature.update'
    EVENT_SYSTEM = False

    def __init__(self, bus, formatters_broker, events_broker):
        """ 
        Constructor

        Args:
            bus (MessageBus): message bus instance
            formatters_broker (FormattersBroker): formatters broker instance
            events_broker (EventsBroker): events broker instance
        """
        Event.__init__(self, bus, formatters_broker, events_broker)

    def _check_params(self, params):
        """
        Check event parameters

        Args:
            params (dict): event parameters

        Return:
            bool: True if params are valid, False otherwise
        """
        return all(key in [u'sensor', u'lastupdate', u'celsius', u'fahrenheit'] for key in params.keys())

