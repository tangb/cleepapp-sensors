#!/usr/bin/env python
# -*- coding: utf-8 -*-
    
import os
import logging
from raspiot.utils import MissingParameter, InvalidParameter, CommandError
from raspiot.raspiot import RaspIotModule
from raspiot.libs.internals.task import Task
from raspiot.libs.configs.configtxt import ConfigTxt
from raspiot.libs.configs.etcmodules import EtcModules
from raspiot.libs.commands.lsmod import Lsmod
import time
import glob

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
    TEMPERATURE_READING = 600 #in seconds

    TYPE_TEMPERATURE = u'temperature'
    TYPE_MOTION = u'motion'

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
        self.__tasks = {}
        self.raspi_gpios = {}
        self.driver_onewire = False

        #events
        self.sensorsMotionOn = self._get_event(u'sensors.motion.on')
        self.sensorsMotionOff = self._get_event(u'sensors.motion.off')
        self.sensorsTemperatureUpdate = self._get_event(u'sensors.temperature.update')

    def _configure(self):
        """
        Configure module
        """
        #raspi gpios
        self.raspi_gpios = self.get_raspi_gpios()
        
        #onewire driver
        self.is_onewire_installed()

        #launch temperature reading tasks
        devices = self.get_module_devices()
        for uuid in devices:
            if devices[uuid][u'type']==self.TYPE_TEMPERATURE:
                self.__start_temperature_task(devices[uuid])

    def _stop(self):
        """
        Stop module
        """
        #stop tasks
        for t in self.__tasks:
            self.__tasks[t].stop()

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

    def __process_motion_sensor(self, event, sensor):
        """
        Process motion event

        Params:
            event (MessageRequest): gpio event
            sensor (dict): sensor data
        """
        #get current time
        now = int(time.time())

        if event[u'event']==u'gpios.gpio.on':
            #check if task already running
            if not sensor['on']:
                #sensor not yet triggered, trigger it
                self.logger.debug(u' +++ Motion sensor "%s" turned on' % sensor[u'name'])

                #motion sensor triggered
                sensor[u'lastupdate'] = now
                sensor[u'on'] = True
                self._update_device(sensor[u'uuid'], sensor)

                #new motion event
                self.sensorsMotionOn.send(params={u'sensor':sensor[u'name'], u'lastupdate':now}, device_id=sensor[u'uuid'])

        elif event[u'event']==u'gpios.gpio.off':
            if sensor[u'on']:
                #sensor is triggered, need to stop it
                self.logger.debug(u' --- Motion sensor "%s" turned off' % sensor[u'name'])

                #motion sensor triggered
                sensor[u'lastupdate'] = now
                sensor[u'on'] = False
                sensor[u'lastduration'] = event[u'params'][u'duration']
                self._update_device(sensor[u'uuid'], sensor)

                #new motion event
                self.sensorsMotionOff.send(params={u'sensor': sensor[u'name'], u'duration':sensor[u'lastduration'], u'lastupdate':now}, device_id=sensor[u'uuid'])

    def event_received(self, event):
        """
        Event received

        Params:
            event (MessageRequest): event data
        """
        #self.logger.debug('*** event received: %s' % unicode(event))
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

    def is_onewire_installed(self):
        """
        Return True if onewire drivers are installed

        Returns:
            bool: True if onewire drivers installed
        """
        configtxt = ConfigTxt(self.cleep_filesystem)
        etcmodules = EtcModules(self.cleep_filesystem)
        lsmod = Lsmod()

        installed_configtxt = configtxt.is_onewire_enabled()
        installed_etcmodules = etcmodules.is_onewire_enabled()
        loaded_module = lsmod.is_module_loaded(etcmodules.MODULE_ONEWIREGPIO)

        self.driver_onewire = installed_configtxt and installed_etcmodules and loaded_module

        return self.driver_onewire

    def install_onewire(self):
        """
        Install onewire drivers

        Returns:
            bool: True if onewire drivers installed successfully
        """
        configtxt = ConfigTxt(self.cleep_filesystem)
        etcmodules = EtcModules(self.cleep_filesystem)
        result = etcmodules.enable_onewire() and configtxt.enable_onewire()
        self.driver_onewire = result

        #reboot right now
        if result:
            self.send_command(u'reboot_system', to=u'system', params={'delay':1.0})

        return result

    def uninstall_onewire(self):
        """
        Uninstall onewire drivers

        Returns:
            bool: True if onewire drivers uninstalled successfully
        """
        configtxt = ConfigTxt(self.cleep_filesystem)
        etcmodules = EtcModules(self.cleep_filesystem)
        result = etcmodules.disable_onewire() and configtxt.disable_onewire()
        self.driver_onewire = result

        #reboot right now
        if result:
            self.send_command(u'reboot_system', to=u'system', params={'delay':1.0})

        return result

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

        devices = glob.glob(os.path.join(Sensors.ONEWIRE_PATH, u'28*'))
        for device in devices:
            try:
                onewires.append({
                    u'device': os.path.basename(device),
                    u'path': os.path.join(device, Sensors.ONEWIRE_SLAVE)
                })
            except:
                self.logger.exception(u'Error during 1wire bus scan:')
                raise CommandError(u'Unable to scan onewire bus')

        return onewires

    def __read_onewire_temperature(self, sensor):
        """
        Read temperature from 1wire device
        
        Params:
            sensor (string): path to 1wire device

        Returns:
            tuple: temperature infos::
                (<celsius>, <fahrenheit>) or (None, None) if error occured
        """
        tempC = None
        tempF = None

        self.logger.debug(u'sensor: %s' % sensor)

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
                    tempF = tempC * 9.0 / 5.0 + 32.0

                    #apply offsets
                    tempC += sensor[u'offsetcelsius']
                    tempF += sensor[u'offsetfahrenheit']

                else:
                    #no temperature found in file
                    raise Exception(u'No temperature found for onewire %s' % sensor[u'path'])

            else:
                #onewire device doesn't exist
                raise Exception(u'Onewire device %s doesn\'t exist anymore' % sensor[u'path'])

        except:
            self.logger.exception(u'Unable to read 1wire device file "%s":' % sensor[u'path'])

        return (tempC, tempF)

    def __read_temperature(self, sensor):
        """
        Read temperature

        Params:
            sensor (dict): sensor data
        """
        if sensor[u'subtype']==u'onewire':
            (tempC, tempF) = self.__read_onewire_temperature(sensor)
            self.logger.debug(u'Read temperature: %s°C - %s°F' % (tempC, tempF))
            if tempC is not None and tempF is not None:
                #temperature values are valid, update sensor values
                sensor[u'celsius'] = tempC
                sensor[u'fahrenheit'] = tempF
                sensor[u'lastupdate'] = int(time.time())
                if not self._update_device(sensor[u'uuid'], sensor):
                    self.logger.error(u'Unable to update device %s' % sensor['uuid'])

                #and send event
                now = int(time.time())
                self.sensorsTemperatureUpdate.send(params={u'sensor':sensor[u'name'], u'celsius':tempC, u'fahrenheit':tempF, u'lastupdate':now}, device_id=sensor[u'uuid'])

        else:
            self.logger.warning(u'Unknown temperature subtype "%s"' % sensor[u'subtype'])

    def __start_temperature_task(self, sensor):
        """
        start temperature reading task

        Params:
            sensor (dict): sensor data
        """
        if self.__tasks.has_key(sensor[u'uuid']):
            #sensor has already task
            self.logger.warning(u'Temperature sensor "%s" has already task running' % sensor[u'uuid'])
            return

        #start task
        self.logger.debug(u'Start temperature task (refresh every %s seconds) for sensor %s ' % (unicode(sensor[u'interval']), sensor[u'uuid']))
        self.__tasks[sensor[u'uuid']] = Task(float(sensor[u'interval']), self.__read_temperature, self.logger, [sensor])
        self.__tasks[sensor[u'uuid']].start()

    def __stop_temperature_task(self, sensor):
        """
        Stop temperature reading task

        Params:
            sensor (dict): sensor data
        """
        if not self.__tasks.has_key(sensor[u'uuid']):
            #sensor hasn't already task
            self.logger.warning(u'Temperature sensor "%s" has no task to stop' % sensor[u'uuid'])
            return

        #stop task
        self.logger.debug(u'Stop temperature task for sensor %s' % sensor[u'uuid'])
        self.__tasks[sensor[u'uuid']].stop()
        del self.__tasks[sensor[u'uuid']]

    def __compute_temperature_offset(self, offset, offset_unit):
        """
        Compute temperature offset

        Params:
            offset (int): offset value
            offset_unit (celsius|fahrenheit): determine if specific offset is in celsius or fahrenheit

        Returns:
            tuple: temperature offset::
                (<offset celsius>, <offset fahrenheit>)
        """
        if offset==0:
            #no offset
            return (0, 0)
        elif offset_unit==u'celsius':
            #compute fahrenheit offset
            return (offset, offset*1.8+32)
        else:
            #compute celsius offset
            return ((offset-32)/1.8, offset)

    def __get_gpio_uses(self, gpio):
        """
        Return number of gpio uses

        Params:
            uuid (string): device uuid

        Returns:
            list: list of gpios or empty list if nothing found
        """
        devices = self._get_devices()
        uses = 0
        for uuid in devices:
            for gpio_ in devices[uuid][u'gpios']:
                if gpio==gpio_[u'gpio']:
                    uses += 1

        return uses

    def get_module_config(self):
        """
        Get full module configuration

        Returns:
            dict: module configuration
        """
        config = {}
        config[u'raspi_gpios'] = self.get_raspi_gpios()
        config[u'drivers'] = {
            u'onewire': self.driver_onewire
        }

        return config

    def get_raspi_gpios(self):
        """
        Get raspi gpios

        Returns:
            dict: raspi gpios
        """
        resp = self.send_command(u'get_raspi_gpios', u'gpios')
        if not resp:
            self.logger.error(u'No response')
            return {}
        elif resp[u'error']:
            self.logger.error(resp[u'message'])
            return {}
        else:
            return resp[u'data']

    def get_assigned_gpios(self):
        """
        Return assigned gpios

        Returns:
            dict: assigned gpios
        """
        resp = self.send_command(u'get_assigned_gpios', 'gpios')
        if not resp:
            self.logger.error(u'No response')
            return {}
        elif resp[u'error']:
            self.logger.error(resp[u'message'])
            return {}
        else:
            return resp[u'data']

    def add_temperature_onewire(self, name, device, path, interval, offset, offset_unit, gpio=u'GPIO4'):
        """
        Add new onewire temperature sensor (DS18B20)

        Params:
            name (string): sensor name
            device (string): onewire device as returned by get_onewire_devices function
            path (string): onewire path as returned by get_onewire_devices function
            interval (int): interval between temperature reading (seconds)
            offset (int): temperature offset
            offset_unit (string): temperature offset unit (string 'celsius' or 'fahrenheit')
            gpio (string): onewire gpio (for now this parameter is useless because forced to default onewire gpio GPIO4)

        Returns:
            bool: True if sensor added
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
        elif interval<=0:
            raise InvalidParameter(u'Interval must be greater than 60')
        elif offset is None:
            raise MissingParameter(u'Offset parameter is missing')
        elif offset<0:
            raise InvalidParameter(u'Offset must be positive')
        elif offset_unit is None or len(offset_unit)==0:
            raise MissingParameter(u'Offset_unit paramter is missing')
        elif offset_unit not in (u'celsius', u'fahrenheit'):
            raise InvalidParameter(u'Offset_unit must be equal to "celsius" or "fahrenheit"')
        elif gpio is None or len(gpio)==0:
            raise MissingParameter(u'Gpio parameter is missing')
        else:
            #compute offsets
            (offsetC, offsetF) = self.__compute_temperature_offset(offset, offset_unit)

            #configure gpio
            params = {
                u'name': name + u'_onewire',
                u'gpio': gpio,
                u'usage': u'onewire'
            }
            resp_gpio = self.send_command(u'reserve_gpio', u'gpios', params)
            if resp_gpio[u'error']:
                raise CommandError(resp_gpio[u'message'])
            resp_gpio = resp_gpio[u'data']

            #sensor is valid, save new entry
            sensor = {
                u'name': name,
                u'gpios': [{'gpio':gpio, 'gpio_uuid':resp_gpio['uuid']}],
                u'device': device,
                u'path': path,
                u'type': self.TYPE_TEMPERATURE,
                u'subtype': u'onewire',
                u'interval': interval,
                u'offsetcelsius': offsetC,
                u'offsetfahrenheit': offsetF,
                u'offset': offset,
                u'offsetunit': offset_unit,
                u'lastupdate': int(time.time()),
                u'celsius': None,
                u'fahrenheit': None
            }

            #read temperature
            (tempC, tempF) = self.__read_onewire_temperature(sensor)
            sensor[u'celsius'] = tempC
            sensor[u'fahrenheit'] = tempF

            #save sensor
            sensor = self._add_device(sensor)

            #launch temperature reading task
            self.__start_temperature_task(sensor)

        return True

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
            bool: True if device update is successful
        """
        device = self._get_device(uuid)
        if not uuid:
            raise MissingParameter(u'Uuid parameter is missing')
        elif device is None:
            raise InvalidParameter(u'Sensor "%s" doesn\'t exist' % name)
        elif name is None or len(name)==0:
            raise MissingParameter(u'Name parameter is missing')
        elif name!=device[u'name'] and self._search_device(u'name', name) is not None:
            raise InvalidParameter(u'Name "%s" is already used' % name)
        elif interval is None:
            raise MissingParameter(u'Interval parameter is missing')
        elif interval<=0:
            raise InvalidParameter(u'Interval must be greater than 60')
        elif offset is None:
            raise MissingParameter(u'Offset parameter is missing')
        elif offset<0:
            raise InvalidParameter(u'Offset must be positive')
        elif offset_unit is None or len(offset_unit)==0:
            raise MissingParameter(u'Offset_unit paramter is missing')
        elif offset_unit not in (u'celsius', u'fahrenheit'):
            raise InvalidParameter(u'Offset_unit must be equal to "celsius" or "fahrenheit"')
        else:
            #compute offsets
            (offsetC, offsetF) = self.__compute_temperature_offset(offset, offset_unit)

            #update sensor
            device[u'name'] = name
            device[u'interval'] = interval
            device[u'offset'] = offset
            device[u'offsetunit'] = offset_unit
            device[u'offsetcelsius'] = offsetC
            device[u'offsetfahrenheit'] = offsetF
            if not self._update_device(uuid, device):
                raise commanderror(u'Unable to update sensor')

            #stop and launch temperature reading task
            self.__stop_temperature_task(device)
            self.__start_temperature_task(device)

        return True

    def add_motion_generic(self, name, gpio, inverted):
        """
        Add new generic motion sensor

        Params:
            name (string): sensor name
            gpio (string): sensor gpio
            inverted (bool): set if gpio is inverted or not (bool)

        Returns:
            bool: True if sensor added successfully
        """
        #get assigned gpios
        assigned_gpios = self.get_assigned_gpios()

        #check values
        if not name:
            raise MissingParameter(u'Name parameter is missing')
        elif not gpio:
            raise MissingParameter(u'Gpio parameter is missing')
        elif inverted is None:
            raise MissingParameter(u'Inverted parameter is missing')
        elif gpio in assigned_gpios:
            raise InvalidParameter(u'Gpio is already used')
        elif self._search_device(u'name', name) is not None:
            raise InvalidParameter(u'Name "%s" is already used' % name)
        elif gpio not in self.raspi_gpios:
            raise InvalidParameter(u'Gpio does not exist for this raspberry pi')
        else:
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
            resp_gpio = resp_gpio[u'data']
                
            #gpio was added and sensor is valid, add new sensor
            data = {
                u'name': name,
                u'gpios': [{u'gpio':gpio, u'gpio_uuid':resp_gpio[u'uuid']}],
                u'type': self.TYPE_MOTION,
                u'subtype': u'generic',
                u'on': False,
                u'inverted': inverted,
                u'lastupdate': 0,
                u'lastduration': 0,
            }
            if self._add_device(data) is None:
                raise CommandError(u'Unable to add sensor')

        return True

    def update_motion_generic(self, uuid, name, inverted):
        """
        Update generic motion sensor

        Params:
            uuid (string): sensor identifier
            name (string): sensor name
            inverted (bool): set if gpio is inverted or not

        Returns:
            bool: True if device update is successful
        """
        device = self._get_device(uuid)
        if not uuid:
            raise MissingParameter(u'Uuid parameter is missing')
        elif device is None:
            raise InvalidParameter(u'Sensor "%s" doesn\'t exist' % name)
        elif name!=device[u'name'] and self._search_device(u'name', name) is not None:
            raise InvalidParameter(u'Name "%s" is already used' % name)
        elif not name:
            raise MissingParameter(u'Name parameter is missing')
        elif inverted is None:
            raise MissingParameter(u'Inverted parameter is missing')
        elif self._search_device(u'name', name) is not None:
            raise InvalidParameter(u'Name is already used')
        else:
            #update sensor
            device[u'name'] = name
            device[u'inverted'] = inverted
            if not self._update_device(uuid, device):
                raise commanderror(u'Unable to update sensor')

        return True

    def delete_sensor(self, uuid):
        """
        Delete specified sensor

        Params:
            uuid (string): sensor identifier

        Returns:
            bool: True if deletion succeed
        """
        device = self._get_device(uuid)
        if not uuid:
            raise MissingParameter(u'Uuid parameter is missing')
        elif device is None:
            raise InvalidParameter(u'Sensor "%s" doesn\'t exist' % name)
        else:
            #stop task if necessary
            if device[u'type']==self.TYPE_TEMPERATURE:
                self.__stop_temperature_task(device)

            #unconfigure gpios
            for gpio in device[u'gpios']:
                #is a reserved gpio (onewire?)
                resp = self.send_command(u'is_reserved_gpio', u'gpios', {u'uuid': gpio[u'gpio_uuid']})
                self.logger.debug(u'is_reserved_gpio: %s' % resp)
                if not resp:
                    raise CommandError(u'No reponse')
                elif resp[u'error']:
                    raise CommandError(resp[u'message'])
                
                #if gpio is reserved, check if no other sensor is using it
                delete = True
                if resp[u'data']==True:
                    if self.__get_gpio_uses(gpio[u'gpio'])>1:
                        #more than one devices are using this gpio, disable gpio unconfiguration
                        self.logger.debug(u'More than one device is using gpio, disable gpio deletion')
                        delete = False

                #unconfigure gpio
                if delete:
                    self.logger.debug(u'Unconfigure gpio %s' % gpio[u'gpio_uuid'])
                    resp = self.send_command(u'delete_gpio', u'gpios', {u'uuid':gpio[u'gpio_uuid']})
                    if not resp:
                        raise CommandError(u'No response')
                    elif resp[u'error']:
                        raise CommandError(resp[u'message'])

            #sensor is valid, remove it
            if not self._delete_device(device[u'uuid']):
                raise CommandError(u'Unable to delete sensor')
            self.logger.debug(u'Device %s deleted sucessfully' % uuid)

        return True

