#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
from raspiot.utils import MissingParameter, InvalidParameter, CommandError
from .sensor import Sensor
import time

class SensorMotionGeneric(Sensor):
    """
    Sensor motion addon
    """
    
    TYPE_MOTION = u'motion'
    TYPES = [TYPE_MOTION]
    SUBTYPE = u'generic'
    
    def __init__(self, sensors):
        """
        Constructor
        
        Args:
            sensors (Sensors): Sensors instance
        """
        Sensor.__init__(self, sensors)

        #events
        self.sensors_motion_on = self._get_event(u'sensors.motion.on')
        self.sensors_motion_off = self._get_event(u'sensors.motion.off')
    
    def add(self, name, gpio, inverted):
        """
        Return sensor data to add.
        Can perform specific stuff
        
        Returns:
            dict: sensor data to add::
            
                {
                    gpios (list): list of gpios data to add
                    sensors (list): list sensors data to add
                }
                
        """
        #get assigned gpios
        assigned_gpios = self._get_assigned_gpios()

        #check values
        if name is None or len(name)==0:
            raise MissingParameter(u'Parameter "name" is missing')
        elif self._search_device(u'name', name) is not None:
            raise InvalidParameter(u'Name "%s" is already used' % name)
        elif not gpio:
            raise MissingParameter(u'Parameter "gpio" is missing')
        elif inverted is None:
            raise MissingParameter(u'Parameter "inverted" is missing')
        elif gpio in assigned_gpios:
            raise InvalidParameter(u'Gpio "%s" is already used' % gpio)
        elif gpio not in self.raspi_gpios:
            raise InvalidParameter(u'Gpio "%s" does not exist for this raspberry pi' % gpio)

        #configure gpio
        gpio = {
            u'name': name + u'_motion',
            u'gpio': gpio,
            u'mode': u'input',
            u'keep': False,
            u'inverted':inverted
        }
           
        sensor = {
            u'name': name,
            u'gpios': [],
            u'type': self.TYPE_MOTION,
            u'subtype': self.SUBTYPE,
            u'on': False,
            u'inverted': inverted,
            u'lastupdate': 0,
            u'lastduration': 0,
        }
        
        #read current gpio value
        resp = self.send_command(u'is_gpio_on', u'gpios', {u'gpio': gpio})
        if not resp[u'error']:
            sensor[u'on'] = resp[u'data']
        
        return {
            u'gpios': [gpio,],
            u'sensors': [sensor,]
        }

    def update(self, sensor, name, inverted):
        """
        Returns sensor data to update
        Can perform specific stuff
        
        Returns:
            dict: sensor data to update::
            
                {
                    gpios (list): list of gpios data to add
                    sensors (list): list sensors data to add
                }
                
        """
        if sensor is None:
            raise MissingParameter(u'Parameter "sensor" is missing')
        elif name is None or len(name)==0:
            raise MissingParameter(u'Parameter "name" is missing')
        elif name!=sensor[u'name'] and self._search_device(u'name', name) is not None:
            raise InvalidParameter(u'Name "%s" is already used' % name)
        elif inverted is None:
            raise MissingParameter(u'Parameter "inverted" is missing')
        elif self._search_device(u'uuid', sensor[u'uuid']) is None:
            raise InvalidParameter(u'Sensor "%s" does not exist' % sensor[u'uuid'])
           
        gpio = {
            u'uuid': sensor[u'gpios'][0][u'uuid'],
            u'name': name + u'_motion',
            u'keep': False,
            u'inverted':inverted
        }

        #update sensor
        sensor[u'name'] = name
        sensor[u'inverted'] = inverted
        
        return {
            u'gpios': [gpio,],
            u'sensors': [sensor,]
        }
    
    def process_event(self, event, sensor):
        """
        Process received event
        
        Args:
            event (MessageRequest): gpio event
            sensor (dict): sensor data
        """
        #get current time
        now = int(time.time())

        if event[u'event']==u'gpios.gpio.on' and not sensor['on']:
            #sensor not yet triggered, trigger it
            self.logger.debug(u'Motion sensor "%s" turned on' % sensor[u'name'])

            #motion sensor triggered
            sensor[u'lastupdate'] = now
            sensor[u'on'] = True
            self.update_value(sensor)

            #new motion event
            self.sensors_motion_on.send(params={
                u'sensor': sensor[u'name'],
                u'lastupdate':now
            }, device_id=sensor[u'uuid'])

        elif event[u'event']==u'gpios.gpio.off' and sensor[u'on']:
            #sensor is triggered, need to stop it
            self.logger.debug(u'Motion sensor "%s" turned off' % sensor[u'name'])

            #motion sensor triggered
            sensor[u'lastupdate'] = now
            sensor[u'on'] = False
            sensor[u'lastduration'] = event[u'params'][u'duration']
            self.update_value(sensor)

            #new motion event
            self.sensors_motion_off.send(params={
                u'sensor': sensor[u'name'],
                u'duration': sensor[u'lastduration'],
                u'lastupdate':now
            }, device_id=sensor[u'uuid'])

    def get_task(self, sensor):
        """
        Return sensor task
        """
        return None
