#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
from raspiot.utils import MissingParameter, InvalidParameter, CommandError
from .sensor import Sensor
from .sensorsutils import SensorsUtils
from raspiot.libs.internals.console import Console
from raspiot.libs.internals.task import Task
import json
import time

class SensorDht22(Sensor):
    """
    Sensor DHT22 addon
    """
    
    TYPE_HUMIDITY = u'humidity'
    TYPE_TEMPERATURE = u'temperature'
    TYPES = [TYPE_TEMPERATURE, TYPE_HUMIDITY]
    SUBTYPE = u'dht22'
    
    DHT22_CMD = u'/usr/local/bin/dht22 %s'
    
    def __init__(self, sensors):
        """
        Constructor
        
        Args:
            sensors (Sensors): Sensors instance
        """
        Sensor.__init__(self, sensors)
        
        #events
        self.sensors_temperature_update = self._get_event(u'sensors.temperature.update')
        self.sensors_humidity_update = self._get_event(u'sensors.humidity.update')
        
    def _get_dht22_devices(self, name):
        """
        Search for DHT22 devices using specified name
        
        Args:
            name (string): device name
            
        Returns:
            tuple: temperature and humidity sensors
        """
        humidity_device = None
        temperature_device = None
        
        for device in self._search_devices('name', name):
            if device[u'subtype']==self.SUBTYPE:
                if device[u'type']==self.TYPE_TEMPERATURE:
                    temperature_device = device
                elif device[u'type']==self.TYPE_HUMIDITY:
                    humidity_device = device

        return (temperature_device, humidity_device)
    
    def add(self, name, gpio, interval, offset, offset_unit):
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
        elif interval is None:
            raise MissingParameter(u'Parameter "interval" is missing')
        elif interval<60:
            raise InvalidParameter(u'Interval must be greater than 60')
        elif offset is None:
            raise MissingParameter(u'Parameter "offset" is missing')
        elif offset_unit is None or len(offset_unit)==0:
            raise MissingParameter(u'Parameter "offset_unit" is missing')
        elif offset_unit not in (SensorsUtils.TEMP_CELSIUS, SensorsUtils.TEMP_FAHRENHEIT):
            raise InvalidParameter(u'Offset_unit must be equal to "celsius" or "fahrenheit"')
        elif gpio is None or len(gpio)==0:
            raise MissingParameter(u'Parameter "gpio" is missing')
        elif gpio in assigned_gpios:
            raise InvalidParameter(u'Gpio "%s" is already used' % gpio)
        elif gpio not in self.raspi_gpios:
            raise InvalidParameter(u'Gpio "%s" does not exist for this raspberry pi' % gpio)

        gpio_data = [
            {
                u'name': name + '_dht22',
                u'gpio': gpio,
                u'mode': u'input',
                u'keep': False,
                u'inverted': False
            }
        ]
        
        temperature_data = {
            u'name': name,
            u'gpios': [],
            u'type': self.TYPE_TEMPERATURE,
            u'subtype': self.SUBTYPE,
            u'interval': interval,
            u'offset': offset,
            u'offsetunit': offset_unit,
            u'lastupdate': int(time.time()),
            u'celsius': None,
            u'fahrenheit': None
        }
 
        humidity_data = {
            u'name': name,
            u'gpios': [],
            u'type': self.TYPE_HUMIDITY,
            u'subtype': self.SUBTYPE,
            u'interval': interval,
            u'lastupdate': int(time.time()),
            u'humidity': None
        }
        
        #update sensor values
        #(tempC, tempF, humP) = self._read_dht22(temperature_device, humidity_device)
        #temperature_device[u'celsius'] = tempC
        #temperature_device[u'fahrenheit'] = tempF
        #humidity_device[u'humidity'] = humP
        
        return {
            u'gpios': [gpio_data,],
            u'sensors': [temperature_data, humidity_data,],
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
        #check params
        if sensor is None:
            raise MissingParameter(u'Parameter "sensor" is missing')
        elif name is None or len(name)==0:
            raise MissingParameter(u'Parameter "name" is missing')
        elif sensor[u'name']!=name and self._search_device(u'name', name) is not None:
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
            
        #search all sensors with same name
        old_name = sensor[u'name']
        (temperature_device, humidity_device) = self._get_dht22_devices(sensor[u'name'])
                    
        #reconfigure gpio
        gpios = []
        if old_name!=name:
            gpios.append({
                u'uuid': (temperature_device or humidity_device)[u'gpios'][0][u'uuid'],
                u'name': name + '_dht22',
                u'mode': u'input',
                u'keep': False,
                u'inverted': False
            })

        #temperature sensor
        sensors = []
        if temperature_device:
            temperature_device[u'name'] = name
            temperature_device[u'interval'] = interval
            temperature_device[u'offset'] = offset
            temperature_device[u'offsetunit'] = offset_unit
            sensors.append(temperature_device)

        #humidity sensor
        if humidity_device:
            humidity_device[u'name'] = name
            humidity_device[u'interval'] = interval
            sensors.append(humidity_device)

        return {
            u'gpios': gpios,
            u'sensors': sensors,
        }
        
    def delete(self, sensor):
        """
        Returns sensor data to delete
        Can perform specific stuff
        
        Returns:
            dict: sensor data to delete::
            
                {
                    gpios (list): list of gpios data to add
                    sensors (list): list sensors data to add
                }

        """
        #check params
        if sensor is None:
            raise MissingParameter(u'Parameter "sensor" is missing')

        #search all sensors with same name
        (temperature_device, humidity_device) = self._get_dht22_devices(sensor[u'name'])
            
        #gpios
        gpios = [(temperature_device or humidity_device)[u'gpios'][0][u'gpio'], ]
        
        #sensors
        sensors = []
        if temperature_device:
            sensors.append(temperature_device)
        if humidity_device:
            sensors.append(humidity_device)
            
        return {
            u'gpios': gpios,
            u'sensors': sensors,
        }

    def _execute_command(self, sensor): # pragma: no cover
        """
        Execute dht22 binary command
        Useful for unit testing
        """
        console = Console()
        cmd = self.DHT22_CMD % sensor[u'gpios'][0][u'pin']
        self.logger.debug(u'Read DHT22 sensor values from command "%s"' % cmd)
        resp = console.command(cmd, timeout=11)
        self.logger.debug(u'Read DHT command response: %s' % resp)
        if resp[u'error'] or resp[u'killed']:
            self.logger.error(u'DHT22 command failed: %s' % resp)

        return json.loads(resp[u'stdout'][0])

    def _read_dht22(self, sensor):
        """
        Read temperature from dht22 sensor
        
        Params:
            sensor (dict): sensor data
            
        Returns:
            tuple: (temp celsius, temp fahrenheit, humidity)
        """
        tempC = None
        tempF = None
        humP = None
        
        try:
            #get values from external binary (binary hardcoded timeout set to 10 seconds)
            data = self._execute_command(sensor)
            
            #check read errors
            if len(data[u'error'])>0:
                self.logger.error(u'Error occured during DHT22 command execution: %s' % data[u'error'])
                raise Exception(u'DHT22 command failed')
                
            #get DHT22 values
            (tempC, tempF) = SensorsUtils.convert_temperatures_from_celsius(data[u'celsius'], sensor[u'offset'], sensor[u'offsetunit'])
            humP = data[u'humidity']
            self.logger.info(u'Read values from DHT22: %s°C, %s°F, %s%%' % (tempC, tempF, humP))

        except Exception as e:
            self.logger.exception('Error executing DHT22 command:')
            
        return (tempC, tempF, humP)
            
    def _task(self, temperature_device, humidity_device):
        """
        DHT22 task
        
        Args:
            temperature_device (dict): temperature sensor
            humidity_device (dict): humidity sensor
        """
        #read values
        (tempC, tempF, humP) = self._read_dht22((temperature_device or humidity_device))
        
        now = int(time.time())
        if temperature_device and tempC is not None and tempF is not None:
            #temperature values are valid, update sensor values
            temperature_device[u'celsius'] = tempC
            temperature_device[u'fahrenheit'] = tempF
            temperature_device[u'lastupdate'] = now

            #and send event if update succeed (if not device may has been removed)
            if self.update_value(temperature_device):
                params = {
                    u'sensor': temperature_device[u'name'],
                    u'celsius': tempC,
                    u'fahrenheit': tempF,
                    u'lastupdate': now
                }
                self.sensors_temperature_update.send(params=params, device_id=temperature_device[u'uuid'])

        if humidity_device and humP is not None:
            #humidity value is valid, update sensor value
            humidity_device[u'humidity'] = humP
            humidity_device[u'lastupdate'] = now

            #and send event if update succeed (if not device may has been removed)
            if self.update_value(humidity_device):
                params = {
                    u'sensor': humidity_device[u'name'],
                    u'humidity': humP,
                    u'lastupdate': now
                }
                self.sensors_humidity_update.send(params=params, device_id=humidity_device[u'uuid'])

        if tempC is None and tempF is None and humP is None:
            self.logger.warning(u'No value returned by DHT22 sensor!')
        
    def get_task(self, sensor):
        """
        Prepare task for DHT sensor only. It should have 2 devices with the same name.

        Args:
            sensor (dict): DHT sensor data

        Returns:
            Task: sensor task
        """
        #search all sensors with same name
        (temperature_device, humidity_device) = self._get_dht22_devices(sensor[u'name'])
        
        return Task(float(sensor[u'interval']), self._task, self.logger, [temperature_device, humidity_device])
