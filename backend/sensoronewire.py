#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import logging
from raspiot.utils import MissingParameter, InvalidParameter, CommandError
from .sensor import Sensor
from .sensorsutils import SensorsUtils
from raspiot.libs.internals.task import Task
from .onewiredriver import OnewireDriver
import glob
import time

class SensorOnewire(Sensor):
    """
    Sensor onewire addon
    """
    TYPE_TEMPERATURE = u'temperature'
    TYPES = [TYPE_TEMPERATURE]
    SUBTYPE = u'onewire'
    
    #members for driver
    USAGE_ONEWIRE = u'onewire'
    ONEWIRE_RESERVED_GPIO = u'GPIO4'
    
    ONEWIRE_PATH = u'/sys/bus/w1/devices/'
    ONEWIRE_SLAVE = u'w1_slave'
    
    def __init__(self, sensors):
        """
        Constructor
        
        Args:
            sensors (Sensors): Sensors instance
        """
        Sensor.__init__(self, sensors)
        
        #events
        self.sensors_temperature_update = self._get_event(u'sensors.temperature.update')
        
        #drivers
        self.onewire_driver = OnewireDriver(self.cleep_filesystem)
        self._register_driver(self.onewire_driver)
        
    def add(self, name, device, path, interval, offset, offset_unit):
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
        #check values
        if name is None or len(name)==0:
            raise MissingParameter(u'Parameter "name" is missing')
        elif self._search_device(u'name', name) is not None:
            raise InvalidParameter(u'Name "%s" is already used' % name)
        elif device is None or len(device)==0:
            raise MissingParameter(u'Parameter "device" is missing')
        elif path is None or len(path)==0:
            raise MissingParameter(u'Parameter "path" is missing')
        elif interval is None:
            raise MissingParameter(u'Parameter "interval" is missing')
        elif interval<60:
            raise InvalidParameter(u'Interval must be greater or equal than 60')
        elif offset is None:
            raise MissingParameter(u'Parameter "offset" is missing')
        elif offset_unit is None or len(offset_unit)==0:
            raise MissingParameter(u'Parameter "offset_unit" is missing')
        elif not isinstance(offset_unit, str) or offset_unit not in (SensorsUtils.TEMP_CELSIUS, SensorsUtils.TEMP_FAHRENHEIT):
            raise InvalidParameter(u'Offset_unit must be equal to "celsius" or "fahrenheit"')
            
        #get 1wire gpio
        gpio_device = self.sensors.send_command(u'get_reserved_gpio', u'gpios', {u'usage': self.USAGE_ONEWIRE})
        self.logger.debug(u'gpio_device=%s' % gpio_device)

        #prepare sensor
        sensor = {
            u'name': name,
            u'gpios': [{'gpio':gpio_device[u'gpio'], 'uuid':gpio_device['uuid'], u'pin':gpio_device[u'pin']}],
            u'device': device,
            u'path': path,
            u'type': self.TYPE_TEMPERATURE,
            u'subtype': self.SUBTYPE,
            u'interval': interval,
            u'offset': offset,
            u'offsetunit': offset_unit,
            u'lastupdate': int(time.time()),
            u'celsius': None,
            u'fahrenheit': None
        }

        #read temperature
        (tempC, tempF) = self._read_onewire_temperature(sensor)
        sensor[u'celsius'] = tempC
        sensor[u'fahrenheit'] = tempF
            
        return {
            u'gpios': [],
            u'sensors': [sensor,]
        }

    def update(self, sensor, name, interval, offset, offset_unit):
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
            raise InvalidParameter(u'Sensor wasn\'t specified')
        elif u'uuid' not in sensor or self._search_device(u'uuid', sensor[u'uuid']) is None:
            raise InvalidParameter(u'Sensor "%s" does not exist' % sensor[u'uuid'])
        elif name is None or len(name)==0:
            raise MissingParameter(u'Parameter "name" is missing')
        elif name!=sensor[u'name'] and self._search_device(u'name', name) is not None:
            raise InvalidParameter(u'Name "%s" is already used' % name)
        elif interval is None:
            raise MissingParameter(u'Parameter "interval" is missing')
        elif interval<60:
            raise InvalidParameter(u'Interval must be greater or equal than 60')
        elif offset is None:
            raise MissingParameter(u'Parameter "offset" is missing')
        elif offset_unit is None or len(offset_unit)==0:
            raise MissingParameter(u'Parameter "offset_unit" is missing')
        elif offset_unit not in (SensorsUtils.TEMP_CELSIUS, SensorsUtils.TEMP_FAHRENHEIT):
            raise InvalidParameter(u'Offset_unit value must be either "celsius" or "fahrenheit"')

        #update sensor
        sensor[u'name'] = name
        sensor[u'interval'] = interval
        sensor[u'offset'] = offset
        sensor[u'offsetunit'] = offset_unit
        
        return {
            u'gpios': [],
            u'sensors': [sensor,]
        }
    
    def get_onewire_devices(self):
        """
        Scan for devices connected on 1wire bus

        Returns:
            dict: list of onewire devices::
            
                {
                    device (dict): onewire device
                    path (string): device onewire path
                }
                
        """
        onewires = []

        if not self.onewire_driver.is_installed():
            raise CommandError(u'Onewire driver is not installed')

        devices = glob.glob(os.path.join(self.ONEWIRE_PATH, u'28*'))
        self.logger.debug('Onewire devices: %s' % devices)
        for device in devices:
            onewires.append({
                u'device': os.path.basename(device),
                u'path': os.path.join(device, self.ONEWIRE_SLAVE)
            })

        return onewires
     
    def process_event(self, event, sensor):
        """
        Event received specific process for onewire
        
        Args:
            event (MessageRequest): gpio event
            sensor (dict): sensor data
        """
        if event[u'event']==u'system.driver.install' and event[u'params'][u'drivername']=='onewire':
            #reserve onewire gpio
            params = {
                u'name': u'reserved_onewire',
                u'gpio': self.ONEWIRE_RESERVED_GPIO,
                u'usage': self.USAGE_ONEWIRE
            }
            resp = self.sensors.send_command(u'reserve_gpio', u'gpios', params)
            self.logger.debug(u'Reserve gpio result: %s' % resp)

        elif event[u'event']==u'system.driver.uninstall' and event[u'params'][u'drivername']=='onewire':
            #free onewire gpio
            sensor = self._search_by_gpio(self.ONEWIRE_RESERVED_GPIO)
            if sensor:
                resp = self.sensors.send_command('delete_gpio', u'gpios', {u'uuid': sensor[u'gpios'][0][u'uuid']})
                self.logger.debug(u'Delete gpio result: %s' % resp)
                
    def _read_onewire_temperature(self, sensor):
        """
        Read temperature from 1wire device
        
        Params:
            sensor (dict): sensor data

        Returns:
            tuple: temperature infos::
            
                (<celsius>, <fahrenheit>) or (None, None) if error occured
                
        """
        tempC = None
        tempF = None

        try:
            if os.path.exists(sensor[u'path']):
                f = open(sensor[u'path'], u'r')
                raw = f.readlines()
                f.close()
                equals_pos = raw[1].find(u't=')

                if equals_pos!=-1:
                    tempString = raw[1][equals_pos+2:].strip()

                    #check value
                    if tempString==u'85000' or tempString==u'-62':
                        #invalid value
                        raise Exception(u'Invalid temperature "%s"' % tempString)

                    #convert temperatures
                    tempC = float(tempString) / 1000.0
                    (tempC, tempF) = SensorsUtils.convert_temperatures_from_celsius(tempC, sensor[u'offset'], sensor[u'offsetunit'])

                else:
                    #no temperature found in file
                    raise Exception(u'No temperature found for onewire "%s"' % sensor[u'path'])

            else:
                #onewire device doesn't exist
                raise Exception(u'Onewire device "%s" doesn\'t exist' % sensor[u'path'])

        except:
            self.logger.exception(u'Unable to read 1wire device file "%s":' % sensor[u'path'])

        return (tempC, tempF)
        
    def _task(self, sensor):
        """
        Onewire sensor task
        
        Args:
            sensor (dict): sensor data
        """
        #read values
        (tempC, tempF) = self._read_onewire_temperature(sensor)
        
        #update sensor
        sensor[u'celsius'] = tempC
        sensor[u'fahrenheit'] = tempF
        sensor[u'lastupdate'] = int(time.time())
        if not self.update_value(sensor):
            self.logger.error(u'Unable to update onewire device %s' % sensor['uuid'])

        #and send event
        params = {
            u'sensor': sensor[u'name'],
            u'celsius': tempC,
            u'fahrenheit': tempF,
            u'lastupdate': int(time.time())
        }
        self.sensors_temperature_update.send(params=params, device_id=sensor[u'uuid'])
                
    def get_task(self, sensor):
        """
        Return sensor task
        
        Args:
            sensor (dict): sensor data
        """
        return Task(float(sensor[u'interval']), self._task, self.logger, [sensor])

