#!/usr/bin/env python
# -*- coding: utf-8 -*-

from raspiot.libs.internals.event import Event

class SensorsTemperatureUpdateEvent(Event):
    """
    Sensors.temperature.update event
    """

    EVENT_NAME = u'sensors.temperature.update'
    EVENT_SYSTEM = False
    EVENT_PARAMS = [u'sensor', u'lastupdate', u'celsius', u'fahrenheit']

    def __init__(self, bus, formatters_broker, events_broker):
        """ 
        Constructor

        Args:
            bus (MessageBus): message bus instance
            formatters_broker (FormattersBroker): formatters broker instance
            events_broker (EventsBroker): events broker instance
        """
        Event.__init__(self, bus, formatters_broker, events_broker)

