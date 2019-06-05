#!/usr/bin/env python
# -*- coding: utf-8 -*-
    
import os
import logging
from raspiot.utils import MissingParameter, InvalidParameter, CommandError
from raspiot.raspiot import RaspIotModule
from raspiot.libs.internals.task import Task
from raspiot.libs.internals.console import Console
from .onewiredriver import OnewireDriver
import time
import glob
import json

__all__ = [u'Sensors']

class Sensors(RaspIotModule):
    """
    Sensors module handles different kind of sensors:
     - temperature (DS18B20)
     - motion
     - more to come...
    """
    MODULE_AUTHOR = u'Cleep'
    MODULE_VERSION = u'1.0.0'
    MODULE_CATEGORY = 'APPLICATION'
    MODULE_PRICE = 0
    MODULE_DEPS = [u'gpios']
    MODULE_DESCRIPTION = u'Implements easily and quickly sensors like temperature, motion, light...'
    MODULE_LONGDESCRIPTION = u'With this module you will be able to follow environment temperature, detect some motion around your device, detect when light level is dim... and trigger some action according to those stimuli.'
    MODULE_TAGS = [u'sensors', u'temperature', u'motion' u'onewire', u'1wire']
    MODULE_COUNTRY = None
    MODULE_URLINFO = None
    MODULE_URLHELP = None
    MODULE_URLBUGS = None
    MODULE_URLSITE = None

    MODULE_CONFIG_FILE = u'sensors.conf'
    DEFAULT_CONFIG = {}

    ONEWIRE_PATH = u'/sys/bus/w1/devices/'
    ONEWIRE_SLAVE = u'w1_slave'
    DHT22_CMD = u'/usr/local/bin/dht22 %s'

    TYPE_TEMPERATURE = u'temperature'
    TYPE_MOTION = u'motion'
    TYPE_HUMIDITY = u'humidity'
    SUBTYPE_DHT22 = u'dht22'
    SUBTYPE_ONEWIRE = u'onewire'

    TEMP_CELSIUS = 'celsius'
    TEMP_FAHRENHEIT = 'fahrenheit'

    USAGE_ONEWIRE = u'onewire'
    ONEWIRE_RESERVED_GPIO = u'GPIO4'

    def __init__(self, bootstrap, debug_enabled):
        """
        Constructor

        Params:
            bootstrap (dict): bootstrap objects
            debug_enabled (bool): debug status
        """
        #init
        RaspIotModule.__init__(self, bootstrap, debug_enabled)

        #members
        self._tasks = {}
        self.raspi_gpios = {}

        #events
        self.sensors_motion_on = self._get_event(u'sensors.motion.on')
        self.sensors_motion_off = self._get_event(u'sensors.motion.off')
        self.sensors_temperature_update = self._get_event(u'sensors.temperature.update')
        self.sensors_humidity_update = self._get_event(u'sensors.humidity.update')

        #drivers
        self.onewire_driver = OnewireDriver(self.cleep_filesystem)
        self._register_driver(self.onewire_driver)

    def _configure(self):
        """
        Configure module
        """
        #raspi gpios
        self.raspi_gpios = self._get_raspi_gpios()
        
        #launch sensors monitoring tasks
        devices = self.get_module_devices()
        for uuid in devices:
            self.__start_sensor_task(devices[uuid])

    def _stop(self):
        """
        Stop module
        """
        #stop tasks
        for t in self._tasks:
            self._tasks[t].stop()

    def event_received(self, event):
        """
        Event received

        Params:
            event (MessageRequest): event data
        """
        #drop startup events
        if event[u'startup']:
            self.logger.debug(u'Drop startup event')
            return

        if event[u'event'] in (u'gpios.gpio.on', u'gpios.gpio.off'):
            #drop gpio init
            if event[u'params'][u'init']:
                self.logger.debug(u'Drop gpio init event')
                return

            #get uuid event
            gpio_uuid = event[u'device_id']

            #search sensor
            sensor = self.__search_by_gpio(gpio_uuid)
            self.logger.debug(u'Found sensor: %s' % sensor)

            #process event
            if sensor:
                if sensor[u'type']==self.TYPE_MOTION:
                    #motion sensor
                    self.__process_motion_sensor(event, sensor)

        if event[u'event']==u'system.driver.install' and event[u'params'][u'drivername']=='onewire':
            #reserve onewire gpio
            params = {
                u'name': u'reserved_onewire',
                u'gpio': self.ONEWIRE_RESERVED_GPIO,
                u'usage': self.USAGE_ONEWIRE
            }
            resp = self.send_command(u'reserve_gpio', u'gpios', params)
            self.logger.debug(u'Reserve gpio result: %s' % resp)
        elif event[u'event']==u'system.driver.uninstall' and event[u'params'][u'drivername']=='onewire':
            #free onewire gpio
            sensor = self.__search_by_gpio(self.ONEWIRE_RESERVED_GPIO)
            if sensor:
                resp = self.send_command('delete_gpio', u'gpios', {u'uuid': sensor[u'gpios'][0][u'gpio_uuid']})
                self.logger.debug(u'Delete gpio result: %s' % resp)

    def __search_by_gpio(self, gpio_uuid):
        """
        Search sensor connected to specified gpio_uuid

        Params:
            gpio_uuid (string): gpio uuid to search

        Returns:
            dict: sensor data or None if nothing found
        """
        devices = self.get_module_devices()
        for uuid in devices:
            for gpio in devices[uuid][u'gpios']:
                if gpio[u'gpio_uuid']==gpio_uuid:
                    #sensor found
                    return devices[uuid]

        #nothing found
        return None

    def get_module_config(self):
        """
        Get full module configuration

        Returns:
            dict: module configuration
        """
        config = {}
        config[u'drivers'] = {
            u'onewire': self.onewire_driver.is_installed()
        }

        return config

    def __get_gpio_uses(self, gpio):
        """
        Return number of device that are using specified gpio (multi sensors)

        Params:
            uuid (string): device uuid

        Returns:
            number of devices that are using the gpio
        """
        devices = self._get_devices()
        uses = 0
        for uuid in devices:
            for gpio_ in devices[uuid][u'gpios']:
                if gpio==gpio_[u'gpio']:
                    uses += 1
        return uses

    def _get_raspi_gpios(self):
        """
        Get raspi gpios

        Returns:
            dict: raspi gpios
        """
        resp = self.send_command(u'get_raspi_gpios', u'gpios')
        if resp[u'error']:
            self.logger.error(resp[u'message'])
            return {}
        else:
            return resp[u'data']

    def _get_assigned_gpios(self):
        """
        Return assigned gpios

        Returns:
            dict: assigned gpios
        """
        resp = self.send_command(u'get_assigned_gpios', 'gpios')
        if resp[u'error']:
            self.logger.error(resp[u'message'])
            return {}
        else:
            return resp[u'data']

    def delete_sensor(self, uuid):
        """
        Delete specified sensor

        Params:
            uuid (string): sensor identifier

        Returns:
            bool: True if deletion succeed
        """
        sensor = self._get_device(uuid)
        if not uuid:
            raise MissingParameter(u'Uuid parameter is missing')
        elif sensor is None:
            raise InvalidParameter(u'Sensor with uuid "%s" doesn\'t exist' % uuid)
        else:
            #unconfigure gpios
            for gpio in sensor[u'gpios']:
                #is a reserved gpio (onewire?)
                resp = self.send_command(u'is_reserved_gpio', u'gpios', {u'uuid': gpio[u'gpio_uuid']})
                self.logger.debug(u'is_reserved_gpio: %s' % resp)
                if resp[u'error']:
                    raise CommandError(resp[u'message'])
                reserved_gpio = resp[u'data']
               
                #check if we can delete gpio
                delete_gpio = True
                if reserved_gpio:
                    #reserved gpio, don't delete it
                    delete_gpio = False
                elif self.__get_gpio_uses(gpio[u'gpio'])>1:
                    #another device is using gpio, do not delete it in gpio module
                    self.logger.debug(u'More than one sensor is using gpio, disable gpio deletion')
                    delete_gpio = False

                #delete device in gpio module
                if delete_gpio:
                    self.logger.debug(u'Delete gpio "%s" from gpios module' % gpio[u'gpio_uuid'])
                    resp = self.send_command(u'delete_gpio', u'gpios', {u'uuid':gpio[u'gpio_uuid']})
                    if resp[u'error']:
                        raise CommandError(resp[u'message'])
                else:
                    self.logger.debug(u'Gpio device not deleted because other sensor is using it')

            #remove sensor
            if not self._delete_device(sensor[u'uuid']):
                raise CommandError(u'Unable to delete sensor')
            self.logger.debug(u'Sensor "%s" deleted successfully' % uuid)

            #finally stop task if necessary
            self.__stop_sensor_task(sensor[u'name'], sensor)

        return True

    def __start_sensor_task(self, sensor):
        """
        Start sensor task if necessary according to its type/subtype
        """
        if sensor[u'name'] in self._tasks:
            #sensor has already task running
            self.logger.info(u'Sensor "%s" has already task running (can occured for multisensor)' % sensor[u'name'])
            return

        #prepare task
        if sensor[u'type']==self.TYPE_MOTION:
            #no task to start for motion sensor, it is already handled by gpio module
            return

        elif sensor[u'type']==self.TYPE_TEMPERATURE:
            if sensor[u'subtype']==self.SUBTYPE_DHT22:
                self.__launch_dht_task(sensor)
            else:
                self._tasks[sensor[u'name']] = Task(float(sensor[u'interval']), self._read_temperature, self.logger, [sensor])

        elif sensor[u'type']==self.TYPE_HUMIDITY:
            if sensor[u'subtype']==self.SUBTYPE_DHT22:
                self.__launch_dht_task(sensor)

        #start task
        self.logger.debug(u'Start task (refresh every %s seconds) for sensor %s ' % (unicode(sensor[u'interval']), sensor[u'name']))
        self._tasks[sensor[u'name']].start()

    def __launch_dht_task(self, sensor):
        """
        Prepare task for DHT sensor only. It should have 2 devices with the same name.

        Args:
            sensor (dict): DHT sensor data
        """
        #DHT should have 2 sensors, find both of them
        devices = self._search_devices('name', sensor[u'name'])
        if len(devices)==2:
            #the 2 devices exist
            if devices[0][u'type']==self.TYPE_TEMPERATURE:
                self._tasks[sensor[u'name']] = Task(float(sensor[u'interval']), self._read_dht, self.logger, [devices[0], devices[1]])
            else:
                self._tasks[sensor[u'name']] = Task(float(sensor[u'interval']), self._read_dht, self.logger, [devices[1], devices[0]])

        elif len(devices)==1:
            #only 1 sensor exists
            if sensor[u'type']==self.TYPE_TEMPERATURE:
                self._tasks[sensor[u'name']] = Task(float(sensor[u'interval']), self._read_dht, self.logger, [sensor, None])
            else:
                self._tasks[sensor[u'name']] = Task(float(sensor[u'interval']), self._read_dht, self.logger, [None, sensor])

    def __stop_sensor_task(self, sensor_name, sensor):
        """
        Stop sensor task if necessary according to its type/subtype
        Task unicity is based on sensor name to properly handle multi device (usually they use the same task)

        Args:
            sensor_name (string): sensor name. Can be different from sensor data
            sensor (dict): sensor data
        """
        #check if task is running
        if sensor_name not in  self._tasks:
            self.logger.warning(u'Sensor "%s" has no task running' % sensor_name)
            return

        #check if task can be stopped
        stop_task = False
        if sensor[u'subtype']==self.SUBTYPE_DHT22:
            #DHT is multisensor, so stop task only if both of sensors are deleted
            count = self.__get_gpio_uses(sensor[u'gpios'][0][u'gpio'])
            self.logger.debug(u'%d sensors are using gpio "%s"' % (count, sensor[u'gpios'][0][u'gpio']))
            if count==0:
                stop_task = True
            else:
                self.logger.debug(u'Thread for sensor "%s" not stopped because at least one of associated sensor is running' % sensor_name)
            
        elif sensor[u'type']==self.TYPE_TEMPERATURE:
            stop_task = True

        elif sensor[u'type']==self.TYPE_MOTION:
            #no task to stop, task is running in gpio module and will be stopped when device will be deleted
            stop_task = False

        #stop task
        if stop_task:
            self.logger.debug(u'Stop task for sensor %s' % sensor_name)
            self._tasks[sensor_name].stop()
            del self._tasks[sensor_name]

    """
    ONEWIRE DRIVER
    """

    #def is_onewire_driver_installed(self):
    #    """
    #    Return True if onewire drivers are installed
    #
    #    Returns:
    #        bool: True if onewire drivers installed
    #    """
    #    configtxt = ConfigTxt(self.cleep_filesystem)
    #    etcmodules = EtcModules(self.cleep_filesystem)
    #    lsmod = Lsmod()
    #
    #    installed_configtxt = configtxt.is_onewire_enabled()
    #    installed_etcmodules = etcmodules.is_onewire_enabled()
    #    loaded_module = lsmod.is_module_loaded(etcmodules.MODULE_ONEWIREGPIO)
    #
    #    self.__onewire_driver_installed = installed_configtxt and installed_etcmodules and loaded_module
    #
    #    return self.__onewire_driver_installed

    #def install_onewire_driver(self):
    #    """
    #    Install onewire drivers
    #
    #    Returns:
    #        bool: True if onewire drivers installed successfully
    #
    #    Raises:
    #        CommandError if error occured
    #    """
    #    configtxt = ConfigTxt(self.cleep_filesystem)
    #    etcmodules = EtcModules(self.cleep_filesystem)
    #    if not etcmodules.enable_onewire() or not configtxt.enable_onewire():
    #        self.logger.error(u'Unable to install onewire driver')
    #        raise CommandError(u'Unable to install onewire driver')
    #    self.__onewire_driver_installed = True
    #
    #    #reserve gpio dedicated to onewire
    #    params = {
    #        u'name': u'reserved_onewire',
    #        u'gpio': self.ONEWIRE_RESERVED_GPIO,
    #        u'usage': self.USAGE_ONEWIRE
    #    }
    #    resp_gpio = self.send_command(u'reserve_gpio', u'gpios', params)
    #    if resp_gpio[u'error']:
    #        raise CommandError(resp_gpio[u'message'])
    #
    #    #reboot right now
    #    self.send_command(u'reboot_system', to=u'system', params={'delay':1.0})
    #
    #    return True

    #def uninstall_onewire_driver(self):
    #    """
    #    Uninstall onewire drivers
    #
    #    Returns:
    #        bool: True if onewire drivers uninstalled successfully
    #
    #    Raises:
    #        CommandError if error occured
    #    """
    #    configtxt = ConfigTxt(self.cleep_filesystem)
    #    etcmodules = EtcModules(self.cleep_filesystem)
    #    if not etcmodules.disable_onewire() or not configtxt.disable_onewire():
    #        self.logger.error(u'Unable to uninstall onewire driver')
    #        raise CommandError(u'Unable to uninstall onewire driver')
    #    self.__onewire_driver_installed = False
    #
    #    #reboot right now
    #    self.send_command(u'reboot_system', to=u'system', params={'delay':1.0})
    #
    #    return True

    def get_onewire_devices(self):
        """
        Scan for devices connected on 1wire bus

        Returns:
            dict: list of onewire devices::
                {
                    <onewire device>, <onewire path>,
                    ...
                }
        """
        onewires = []

        if not self.onewire_driver.is_installed():
            raise CommandError(u'Onewire driver is not installed')

        devices = glob.glob(os.path.join(self.ONEWIRE_PATH, u'28*'))
        for device in devices:
            onewires.append({
                u'device': os.path.basename(device),
                u'path': os.path.join(device, self.ONEWIRE_SLAVE)
            })

        return onewires

    def _read_onewire_temperature(self, sensor):
        """
        Read temperature from 1wire device
        
        Params:
            sensor (string): Sensors sensor which contains onewire device path

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
                    (tempC, tempF) = self.__convert_temperatures_from_celsius(tempC, sensor[u'offset'], sensor[u'offsetunit'])

                else:
                    #no temperature found in file
                    raise Exception(u'No temperature found for onewire %s' % sensor[u'path'])

            else:
                #onewire device doesn't exist
                raise Exception(u'Onewire device %s doesn\'t exist' % sensor[u'path'])

        except:
            self.logger.exception(u'Unable to read 1wire device file "%s":' % sensor[u'path'])

        return (tempC, tempF)

    """
    TEMPERATURE SENSOR
    """

    def _read_temperature(self, sensor):
        """
        Read temperature

        Params:
            sensor (dict): sensor data
        """
        if sensor[u'subtype']==self.SUBTYPE_ONEWIRE:
            (tempC, tempF) = self._read_onewire_temperature(sensor)
            self.logger.info(u'Read temperature: %s°C - %s°F' % (tempC, tempF))
            if tempC is not None and tempF is not None:
                #temperature values are valid, update sensor values
                sensor[u'celsius'] = tempC
                sensor[u'fahrenheit'] = tempF
                sensor[u'lastupdate'] = int(time.time())
                if not self._update_device(sensor[u'uuid'], sensor):
                    self.logger.error(u'Unable to update device %s' % sensor['uuid'])

                #and send event
                now = int(time.time())
                self.sensors_temperature_update.send(params={u'sensor':sensor[u'name'], u'celsius':tempC, u'fahrenheit':tempF, u'lastupdate':now}, device_id=sensor[u'uuid'])

        else:
            self.logger.warning(u'Unknown temperature subtype "%s"' % sensor[u'subtype'])

    def __convert_temperatures_from_celsius(self, celsius, offset, offset_unit):
        """
        Convert temperatures from celsius

        Args:
            celsius (float): celsius temperature (without offset)
            offset (float): temperature offset
            offset_unit (string): temperature offset unit

        Returns:
            tuple: celsius and fahrenheit temperatures::
                (float: celsius, float: fahrenheit)
        """
        tempC = None
        tempF = None
        if offset is not None and offset!=0:
            if offset_unit==self.TEMP_CELSIUS:
                #apply offset on celsius value
                tempC = celsius + offset
                tempF = (tempC * 9/5) + 32
            else:
                #apply offset on computed fahrenheit value
                tempF = (celsius * 9/5) + 32 + offset
                tempC = (tempF - 32) * 5/9
        else:
            #no offset
            tempC = celsius
            tempF = (celsius * 9/5) + 32

        return (round(tempC,2), round(tempF,2))

    def _convert_temperatures_from_fahrenheit(self, fahrenheit, offset, offset_unit):
        """
        Convert temperatures from fahrenheit

        Note:
            This function is protected because it is not use yet and we want to execute unit test on it
            It won't stay protected as soon as function is used.

        Args:
            fahrenheit (float): fahrenheit temperature (without offset)
            offset (float): temperature offset
            offset_unit (string): temperature offset unit

        Returns:
            float: celsius temperature
        """
        tempC = None
        tempF = None
        if offset is not None and offset!=0:
            if offset_unit==self.TEMP_CELSIUS:
                #apply offset on celsius value
                tempC = (fahrenheit - 32) * 5/9 + offset
                tempF = (tempC * 9/5) + 32
            else:
                #apply offset on computed fahrenheit value
                tempF = fahrenheit + offset
                tempC = (tempF - 32) * 5/9
        else:
            #no offset
            tempF = fahrenheit
            tempC = (tempF - 32) * 5/9

        return (round(tempC,2), round(tempF,2))

    def add_temperature_onewire(self, name, device, path, interval, offset, offset_unit):
        """
        Add new onewire temperature sensor (DS18B20)

        Params:
            name (string): sensor name
            device (string): onewire device as returned by get_onewire_devices function
            path (string): onewire path as returned by get_onewire_devices function
            interval (int): interval between temperature reading (seconds)
            offset (int): temperature offset
            offset_unit (string): temperature offset unit (string 'celsius' or 'fahrenheit')

        Returns:
            dict: created sensor data
        """
        #check values
        if name is None or len(name)==0:
            raise MissingParameter(u'Name parameter is missing')
        elif self._search_device(u'name', name) is not None:
            raise InvalidParameter(u'Name "%s" is already used' % name)
        elif device is None or len(device)==0:
            raise MissingParameter(u'Device parameter is missing')
        elif path is None or len(path)==0:
            raise MissingParameter(u'Path parameter is missing')
        elif interval is None:
            raise MissingParameter(u'Interval parameter is missing')
        elif interval<60:
            raise InvalidParameter(u'Interval must be greater than 60')
        elif offset is None:
            raise MissingParameter(u'Offset parameter is missing')
        elif offset_unit is None or len(offset_unit)==0:
            raise MissingParameter(u'Offset_unit paramter is missing')
        elif offset_unit not in (self.TEMP_CELSIUS, self.TEMP_FAHRENHEIT):
            raise InvalidParameter(u'Offset_unit must be equal to "celsius" or "fahrenheit"')

        gpio_device = None
        sensor_device = None
        try:
            #configure gpio
            resp_gpio = self.send_command(u'get_reserved_gpio', u'gpios', {u'usage': self.USAGE_ONEWIRE})
            if resp_gpio[u'error']:
                raise CommandError(resp_gpio[u'message'])
            gpio_device = resp_gpio[u'data']

            #sensor is valid, save new entry
            sensor = {
                u'name': name,
                u'gpios': [{'gpio':gpio_device[u'gpio'], 'gpio_uuid':gpio_device['uuid'], u'pin':gpio_device[u'pin']}],
                u'device': device,
                u'path': path,
                u'type': self.TYPE_TEMPERATURE,
                u'subtype': self.SUBTYPE_ONEWIRE,
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

            #save sensor
            sensor_device = self._add_device(sensor)
            if not sensor_device:
                raise CommandError(u'Unable to add onewire temperature sensor')

            #launch temperature reading task
            self.__start_sensor_task(sensor)

        except Exception as e:
            if gpio_device:
                self.send_command(u'delete_gpio', u'gpios', {u'uuid': gpio_device[u'uuid']})
            if sensor_device:
                self._delete_sensor(sensor_device[u'uuid'])

            self.logger.error(unicode(e))
            raise CommandError(unicode(e))

        return sensor_device

    def update_temperature_onewire(self, uuid, name, interval, offset, offset_unit):
        """
        Update onewire temperature sensor

        Params:
            uuid (string): sensor identifier
            name (string): sensor name
            interval (int): interval between reading (seconds)
            offset (int): temperature offset
            offset_unit (string): temperature offset unit (string 'celsius' or 'fahrenheit')

        Returns:
            dict: updated sensor data
        """
        sensor = self._get_device(uuid)
        if not uuid:
            raise MissingParameter(u'Uuid parameter is missing')
        elif sensor is None:
            raise InvalidParameter(u'Sensor "%s" doesn\'t exist' % uuid)
        elif name is None or len(name)==0:
            raise MissingParameter(u'Name parameter is missing')
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
        elif offset_unit not in (self.TEMP_CELSIUS, self.TEMP_FAHRENHEIT):
            raise InvalidParameter(u'Offset_unit value must be either "celsius" or "fahrenheit"')

        #update sensor
        old_name = sensor[u'name']
        sensor[u'name'] = name
        sensor[u'interval'] = interval
        sensor[u'offset'] = offset
        sensor[u'offsetunit'] = offset_unit
        if not self._update_device(uuid, sensor):
            raise CommandError(u'Unable to update sensor')

        #stop and launch temperature reading task
        self.__stop_sensor_task(old_name, sensor)
        self.__start_sensor_task(sensor)

        return sensor

    """
    MOTION SENSOR
    """

    def add_motion_generic(self, name, gpio, inverted):
        """
        Add new generic motion sensor

        Params:
            name (string): sensor name
            gpio (string): sensor gpio
            inverted (bool): set if gpio is inverted or not (bool)

        Returns:
            dict: created sensor data
        """
        #get assigned gpios
        assigned_gpios = self._get_assigned_gpios()

        #check values
        if name is None or len(name)==0:
            raise MissingParameter(u'Name parameter is missing')
        elif self._search_device(u'name', name) is not None:
            raise InvalidParameter(u'Name "%s" is already used' % name)
        elif not gpio:
            raise MissingParameter(u'Gpio parameter is missing')
        elif inverted is None:
            raise MissingParameter(u'Inverted parameter is missing')
        elif gpio in assigned_gpios:
            raise InvalidParameter(u'Gpio is already used')
        elif self._search_device(u'name', name) is not None:
            raise InvalidParameter(u'Name "%s" is already used' % name)
        elif gpio not in self.raspi_gpios:
            raise InvalidParameter(u'Gpio "%s" does not exist for this raspberry pi' % gpio)
        elif self._search_device(u'name', name) is not None:
            raise InvalidParameter(u'Name "%s" is already used' % name)

        gpio_device = None
        sensor_device = None
        try:
            #configure gpio
            params = {
                u'name': name + u'_motion',
                u'gpio': gpio,
                u'mode': u'input',
                u'keep': False,
                u'inverted':inverted
            }
            resp_gpio = self.send_command(u'add_gpio', u'gpios', params)
            if resp_gpio[u'error']:
                raise CommandError(resp_gpio[u'message'])
            gpio_device = resp_gpio[u'data']
                
            #gpio was added and sensor is valid, add new sensor
            data = {
                u'name': name,
                u'gpios': [{u'gpio':gpio, u'gpio_uuid':gpio_device[u'uuid'], u'pin':gpio_device[u'pin']}],
                u'type': self.TYPE_MOTION,
                u'subtype': u'generic',
                u'on': inverted,
                u'inverted': inverted,
                u'lastupdate': 0,
                u'lastduration': 0,
            }
            sensor_device = self._add_device(data)
            if sensor_device is None:
                raise CommandError(u'Unable to add motion sensor')

        except Exception as e:
            if gpio_device:
                self.send_command(u'delete_gpio', u'gpios', {u'uuid': gpio_device[u'uuid']})
            if sensor_device:
               self._delete_device(sensor_device[u'uuid']) 

            self.logger.error(unicode(e))
            raise CommandError(unicode(e))

        return sensor_device

    def update_motion_generic(self, uuid, name, inverted):
        """
        Update generic motion sensor

        Params:
            uuid (string): sensor identifier
            name (string): sensor name
            inverted (bool): set if gpio is inverted or not

        Returns:
            dict: updated sensor data
        """
        sensor = self._get_device(uuid)
        if not uuid:
            raise MissingParameter(u'Uuid parameter is missing')
        elif sensor is None:
            raise InvalidParameter(u'Sensor "%s" doesn\'t exist' % name)
        elif name is None or len(name)==0:
            raise MissingParameter(u'Name parameter is missing')
        elif name!=sensor[u'name'] and self._search_device(u'name', name) is not None:
            raise InvalidParameter(u'Name "%s" is already used' % name)
        elif not name:
            raise MissingParameter(u'Name parameter is missing')
        elif inverted is None:
            raise MissingParameter(u'Inverted parameter is missing')
           
        #update gpio
        params = {
            u'uuid': sensor[u'gpios'][0][u'gpio_uuid'],
            u'name': name + u'_motion',
            u'keep': False,
            u'inverted':inverted
        }
        resp_gpio = self.send_command(u'update_gpio', u'gpios', params)
        if resp_gpio[u'error']:
            raise CommandError(resp_gpio[u'message'])
        gpio_device = resp_gpio[u'data']

        #update sensor
        sensor[u'name'] = name
        sensor[u'inverted'] = inverted
        if not self._update_device(uuid, sensor):
            raise CommandError(u'Unable to update sensor')

        return sensor

    def __process_motion_sensor(self, event, sensor):
        """
        Process motion event

        Params:
            event (MessageRequest): gpio event
            sensor (dict): sensor data
        """
        #get current time
        now = int(time.time())

        if event[u'event']==u'gpios.gpio.on' and not sensor['on']:
            #sensor not yet triggered, trigger it
            self.logger.debug(u' +++ Motion sensor "%s" turned on' % sensor[u'name'])

            #motion sensor triggered
            sensor[u'lastupdate'] = now
            sensor[u'on'] = True
            self._update_device(sensor[u'uuid'], sensor)

            #new motion event
            self.sensors_motion_on.send(params={u'sensor':sensor[u'name'], u'lastupdate':now}, device_id=sensor[u'uuid'])

        elif event[u'event']==u'gpios.gpio.off' and sensor[u'on']:
            #sensor is triggered, need to stop it
            self.logger.debug(u' --- Motion sensor "%s" turned off' % sensor[u'name'])

            #motion sensor triggered
            sensor[u'lastupdate'] = now
            sensor[u'on'] = False
            sensor[u'lastduration'] = event[u'params'][u'duration']
            self._update_device(sensor[u'uuid'], sensor)

            #new motion event
            self.sensors_motion_off.send(params={u'sensor': sensor[u'name'], u'duration':sensor[u'lastduration'], u'lastupdate':now}, device_id=sensor[u'uuid'])

    """
    DHT SENSOR
    """

    def add_dht22(self, name, gpio, interval, offset, offset_unit):
        """
        Add new DHT22 sensor

        Params:
            name (string): sensor name
            gpio (string): sensor gpio
            interval (int): interval between sensor reading (seconds)
            offset (int): temperature offset
            offset_unit (string): temperature offset unit (string 'celsius' or 'fahrenheit')

        Returns:
            tuple: created temperature and humidity sensors
        """
        #get assigned gpios
        assigned_gpios = self._get_assigned_gpios()

        #check values
        if name is None or len(name)==0:
            raise MissingParameter(u'Name parameter is missing')
        elif self._search_device(u'name', name) is not None:
            raise InvalidParameter(u'Name "%s" is already used' % name)
        elif interval is None:
            raise MissingParameter(u'Interval parameter is missing')
        elif interval<60:
            raise InvalidParameter(u'Interval must be greater than 60')
        elif offset is None:
            raise MissingParameter(u'Offset parameter is missing')
        elif offset_unit is None or len(offset_unit)==0:
            raise MissingParameter(u'Offset_unit paramter is missing')
        elif offset_unit not in (self.TEMP_CELSIUS, self.TEMP_FAHRENHEIT):
            raise InvalidParameter(u'Offset_unit must be equal to "celsius" or "fahrenheit"')
        elif gpio is None or len(gpio)==0:
            raise MissingParameter(u'Gpio parameter is missing')
        
        gpio_device = None
        temperature_device = None
        humidity_device = None
        try:
            #configure gpio
            params = {
                u'name': name + '_dht22',
                u'gpio': gpio,
                u'mode': u'input',
                u'keep': False,
                u'inverted': False
            }
            resp_gpio = self.send_command(u'add_gpio', u'gpios', params)
            if resp_gpio[u'error']:
                raise CommandError(resp_gpio[u'message'])
            gpio_device = resp_gpio[u'data']

            #add new temperature sensor
            data = {
                u'name': name,
                u'gpios': [{u'gpio':gpio, u'gpio_uuid':gpio_device[u'uuid'], u'pin':gpio_device[u'pin']}],
                u'type': self.TYPE_TEMPERATURE,
                u'subtype': self.SUBTYPE_DHT22,
                u'interval': interval,
                u'offset': offset,
                u'offsetunit': offset_unit,
                u'lastupdate': int(time.time()),
                u'celsius': None,
                u'fahrenheit': None
            }
            temperature_device = self._add_device(data)
            if temperature_device is None:
                raise CommandError(u'Unable to add DHT22 temperature sensor')

            #add new humidity sensor
            data = {
                u'name': name,
                u'gpios': [{u'gpio':gpio, u'gpio_uuid':gpio_device[u'uuid'], u'pin':gpio_device[u'pin']}],
                u'type': self.TYPE_HUMIDITY,
                u'subtype': self.SUBTYPE_DHT22,
                u'interval': interval,
                u'lastupdate': int(time.time()),
                u'humidity': None
            }
            humidity_device = self._add_device(data)
            if humidity_device is None:
                raise CommandError(u'Unable to add DHT22 humidity sensor')
    
            #launch DHT monitoring task (doesn't matter using one or the other device)
            self.__start_sensor_task(temperature_device)

        except Exception as e:
            #remove devices if necessary
            if gpio_device:
                self.send_command(u'delete_gpio', u'gpios', {u'uuid': gpio_device[u'uuid']})
            if temperature_device:
                self._delete_device(temperature_device[u'uuid'])
            if humidity_device:
                self._delete_device(humidity_device[u'uuid'])

            self.logger.error(u'Error while adding DHT22 sensor: %s' % unicode(e))
            raise CommandError(unicode(e))

        return temperature_device, humidity_device

    def update_dht22(self, old_name, new_name, interval, offset, offset_unit):
        """
        Update DHT22 sensor

        Params:
            old_name (string): old sensor name
            new_name (string): new sensor name
            interval (int): interval between sensor reading (seconds)
            offset (int): temperature offset
            offset_unit (string): temperature offset unit (string 'celsius' or 'fahrenheit')

        Returns:
            dict: updated sensor data
        """
        #get assigned gpios
        assigned_gpios = self._get_assigned_gpios()

        #check values
        devices = self._search_devices('name', old_name)
        if len(devices)==0:
            raise InvalidParameter(u'DHT22 sensor with name "%s" doesn\'t exist' % old_name)
        elif new_name is None or len(new_name)==0:
            raise MissingParameter(u'Parameter "new_name" is missing')
        elif old_name!=new_name and self._search_device(u'name', new_name) is not None:
            raise InvalidParameter(u'Name "%s" is already used' % new_name)
        elif interval is None:
            raise MissingParameter(u'Parameter "interval" is missing')
        elif interval<60:
            raise InvalidParameter(u'Interval must be greater or equal than 60')
        elif offset is None:
            raise MissingParameter(u'Parameter "offset" is missing')
        elif offset_unit is None or len(offset_unit)==0:
            raise MissingParameter(u'Parameter "offset_unit" is missing')
        elif offset_unit not in (self.TEMP_CELSIUS, self.TEMP_FAHRENHEIT):
            raise InvalidParameter(u'Offset_unit value must be either "celsius" or "fahrenheit"')
        
        temperature_device = None
        humidity_device = None
        if len(devices)==1:
            if devices[0][u'type']==self.TYPE_HUMIDITY:
                humidity_device = devices[0]
            else:
                temperature_device = devices[0]
        else:
            if devices[0][u'type']==self.TYPE_HUMIDITY:
                humidity_device = devices[0]
                temperature_device = devices[1]
            else:
                temperature_device = devices[0]
                humidity_device = devices[1]

        #reconfigure gpio
        if old_name!=new_name:
            params = {
                u'uuid': (temperature_device or humidity_device)[u'gpios'][0][u'gpio_uuid'],
                u'name': new_name + '_dht22',
                u'mode': u'input',
                u'keep': False,
                u'inverted': False
            }
            resp_gpio = self.send_command(u'update_gpio', u'gpios', params)
            if resp_gpio[u'error']:
                raise CommandError(resp_gpio[u'message'])
            gpio_device = resp_gpio[u'data']

        #update new temperature sensor
        if temperature_device:
            temperature_device[u'name'] = new_name
            temperature_device[u'interval'] = interval
            temperature_device[u'offset'] = offset
            temperature_device[u'offsetunit'] = offset_unit
            if not self._update_device(temperature_device[u'uuid'], temperature_device):
                raise CommandError(u'Unable to update DHT22 temperature sensor')

        #update new humidity sensor
        if humidity_device:
            humidity_device[u'name'] = new_name
            humidity_device[u'interval'] = interval
            if not self._update_device(humidity_device[u'uuid'], humidity_device):
                raise CommandError(u'Unable to update DHT22 humidity sensor')

        #relaunch DHT monitoring task
        self.__stop_sensor_task(old_name, temperature_device or humidity_device)
        self.__start_sensor_task(temperature_device or humidity_device)

        return temperature_device, humidity_device
    
    def _read_dht(self, temperature, humidity):
        """
        Read temperature and humidity from dht sensor

        Params:
            temperature (dict): temperature device
            humidity (dict): humidity device
        """
        if (temperature and temperature[u'subtype']==self.SUBTYPE_DHT22) or (humidity and humidity[u'subtype']==self.SUBTYPE_DHT22):
            #send only one of sensor because both of them contains same gpio id
            (tempC, tempF, humP) = self._read_dht22(temperature or humidity)
            self.logger.info(u'Read values from DHT22: %s°C, %s°F, %s%%' % (tempC, tempF, humP))
            now = int(time.time())
            if temperature and tempC is not None and tempF is not None:
                #temperature values are valid, update sensor values
                temperature[u'celsius'] = tempC
                temperature[u'fahrenheit'] = tempF
                temperature[u'lastupdate'] = now

                #and send event if update succeed (if not device may has been removed)
                if self._update_device(temperature[u'uuid'], temperature):
                    self.sensors_temperature_update.send(params={u'sensor':temperature[u'name'], u'celsius':tempC, u'fahrenheit':tempF, u'lastupdate':now}, device_id=temperature[u'uuid'])

            if humidity and humP is not None:
                #humidity value is valid, update sensor value
                humidity[u'humidity'] = humP
                humidity[u'lastupdate'] = now

                #and send event if update succeed (if not device may has been removed)
                if self._update_device(humidity[u'uuid'], humidity):
                    self.sensors_humidity_update.send(params={u'sensor':humidity[u'name'], u'humidity':humP, u'lastupdate':now}, device_id=humidity[u'uuid'])

            if tempC is None and tempF is None and humP is None:
                self.logger.warning(u'No value returned by DHT sensor!')

        else:
            self.logger.warning(u'Unknown temperature subtype "%s"' % sensor[u'subtype'])

    def _read_dht22(self, sensor):
        """
        Read temperature from dht22 sensor
        
        Params:
            sensor (string): path to re device

        Returns:
            tuple: temperature infos::
                (float: celsius, float: fahrenheit, float: humidity) or (None, None, None) if error occured
        """
        tempC = None
        tempF = None
        humidity= None

        if u'gpios' not in sensor or len(sensor[u'gpios'])!=1:
            self.logger.error('Unable to read DHT22 sensor values because gpios field is misconfigured [%s]' % sensor[u'gpios'])
        else:
            try:
                #get values from external binary (binary hardcoded timeout set to 10 seconds)
                console = Console()
                cmd = self.DHT22_CMD % sensor[u'gpios'][0][u'pin']
                self.logger.debug(u'Read DHT22 sensor values from command "%s"' % cmd)
                resp = console.command(cmd, timeout=11)
                self.logger.debug(u'Read DHT command response: %s' % resp)
                if not resp[u'error'] and not resp[u'killed']:
                    #parse json output
                    data = json.loads(resp[u'stdout'][0])

                    #check read errors
                    if len(data[u'error'])>0:
                        raise Exception(data[u'error'])
                    
                    #store values
                    (tempC, tempF) = self.__convert_temperatures_from_celsius(data[u'celsius'], sensor[u'offset'], sensor[u'offsetunit'])
                    humidity = data[u'humidity']

            except Exception as e:
                self.logger.error(unicode(e))

        return (tempC, tempF, humidity)

