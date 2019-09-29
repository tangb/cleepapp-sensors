#!/usr/bin/env python
# -*- coding: utf-8 -*-
    
import logging
from raspiot.utils import MissingParameter, InvalidParameter, CommandError
from raspiot.raspiot import RaspIotModule
from raspiot.libs.internals.task import Task
from .sensormotiongeneric import SensorMotionGeneric
from .sensordht22 import SensorDht22
from .sensoronewire import SensorOnewire

__all__ = [u'Sensors']

class Sensors(RaspIotModule):
    """
    Sensors module handles different kind of sensors:
     - temperature (DS18B20)
     - motion
     - DHT22
     - ...
    """
    MODULE_AUTHOR = u'Cleep'
    MODULE_VERSION = u'1.0.0'
    MODULE_CATEGORY = u'APPLICATION'
    MODULE_PRICE = 0
    MODULE_DEPS = [u'gpios']
    MODULE_DESCRIPTION = u'Implements easily and quickly sensors like temperature, motion, light...'
    MODULE_LONGDESCRIPTION = u'With this module you will be able to follow environment temperature, detect some motion around your device, detect when light level is dim... and trigger some action according to those stimuli.'
    MODULE_TAGS = [u'sensors', u'temperature', u'motion' u'onewire', u'1wire']
    MODULE_COUNTRY = None
    MODULE_URLINFO = u'https://github.com/tangb/cleepmod-sensors'
    MODULE_URLHELP = None
    MODULE_URLBUGS = u'https://github.com/tangb/cleepmod-sensors/issues'
    MODULE_URLSITE = None

    MODULE_CONFIG_FILE = u'sensors.conf'
    DEFAULT_CONFIG = {}

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
        self._tasks_by_device_uuid = {}
        self.raspi_gpios = {}
        self.addons_by_name = {}
        self.addons_by_type = {}
        self.sensors_types = {}
      
        #addons
        self._register_addon(SensorMotionGeneric(self))
        self._register_addon(SensorOnewire(self))
        self._register_addon(SensorDht22(self))
                
    def _register_addon(self, addon):
        """
        Register addon (internal use only).
        It will save addon link for further use and inject in sensors addon public methods.
        
        Args:
            addon (instance): addon instance
        """
        #save addon by type
        for type in addon.TYPES:
            if type not in self.addons_by_type:
                self.addons_by_type[type] = {}
            if addon.SUBTYPE in self.addons_by_type[type]:
                raise Exception(u'Subtype "%s" already registered in type "%s"' % (addon.SUBTYPE, type))
            self.addons_by_type[type][addon.SUBTYPE] = addon

        #save sensors types (by addons)
        self.sensors_types[addon.__class__.__name__] = {
            u'types': addon.TYPES,
            u'subtype': addon.SUBTYPE,
        }

        #save addon by name
        self.addons_by_name[addon.__class__.__name__] = addon

        #inject in sensors public addon methods
        blacklist = [
            u'add_gpio',
            u'update_gpio',
            u'get_reserved_gpio',
            u'update_value',
            u'update',
            u'add',
            u'delete',
            u'get_task',
            u'process_event',
            u'has_drivers',
            u'send_command',
        ]
        methods = [method_name for method_name in dir(addon) if method_name not in blacklist and not method_name.startswith('_') and callable(getattr(addon, method_name))]
        self.logger.debug('Addon "%s" public methods: %s' % (addon.__class__.__name__, methods))
        for method_name in methods:
            if hasattr(self, method_name):
                self.logger.error(u'Public method "%s" from addon "%s" is already referenced. Please rename it' % (method_name, addon.__class__.__name__))
                continue
            setattr(self, method_name, getattr(addon, method_name))

    def _configure(self):
        """
        Configure module
        """
        #raspi gpios
        self.raspi_gpios = self._get_raspi_gpios()

        #update addons
        for _, addon in self.addons_by_name.items():
            addon.raspi_gpios = self.raspi_gpios
        
        #launch tasks
        sensors = self.get_module_devices()
        for _, sensor in sensors.items():
            addon = self._get_addon(sensor[u'type'], sensor[u'subtype'])
            if addon is None:
                continue
            self._start_sensor_task(addon.get_task(sensor), [sensor])

    def _stop(self):
        """
        Stop module
        """
        #stop tasks
        for _, task in self._tasks_by_device_uuid.items():
            task.stop()

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
            
        #driver event
        if event[u'event'] in (u'system.driver.install', u'system.driver.uninstall'):
            for _, addon in self.addons_by_name.items():
                if addon.has_drivers():
                    addon.process_event(event, None)

        #gpio event
        if event[u'event'] in (u'gpios.gpio.on', u'gpios.gpio.off'):
            #drop gpio init
            if event[u'params'][u'init']:
                self.logger.debug(u'Drop gpio init event')
                return

            #get uuid event
            gpio_uuid = event[u'device_id']

            #search sensor
            sensor = self._search_by_gpio(gpio_uuid)
            self.logger.debug(u'Found sensor: %s' % sensor)
            if not sensor:
                return
            
            #process event on addon
            addon = self._get_addon(sensor[u'type'], sensor[u'subtype'])
            self.logger.debug(u'Found addon: %s' % addon)
            if addon:
                addon.process_event(event, sensor)

    def _search_by_gpio(self, gpio_uuid):
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
                if gpio[u'uuid']==gpio_uuid:
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
        config = {
            u'drivers': {},
            u'sensorstypes': self.sensors_types
        }

        #add drivers
        for _, addon in self.addons_by_name.items():
            for driver_name, driver in addon.drivers.items():
                config[u'drivers'][driver_name] = driver.is_installed()
                
        return config

    def _get_gpio_uses(self, gpio):
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
            list: assigned gpios
        """
        resp = self.send_command(u'get_assigned_gpios', 'gpios')
        if resp[u'error']:
            self.logger.error(resp[u'message'])
            return []
        else:
            return resp[u'data']
            
    def _get_addon(self, type, subtype):
        """
        Return addon
        
        Args:
            type (string): sensor type
            subtype (string): sensor subtype
            
        Returns:
            Sensor: sensor instance or None if not found
        """
        if type in self.addons_by_type and subtype in self.addons_by_type[type]:
            return self.addons_by_type[type][subtype]

        return None
        
    def _fill_sensor_gpios(self, sensor, gpios):
        """
        Fill sensor gpios field content.
        It will store only some useful fields from gpio like uuid, pin number and gpio name

        Args:
            sensor (dict): sensor data to fill
            gpios (list): list of gpios
        """
        if u'gpios' not in sensor:
            sensor[u'gpios'] = []
            
        for gpio in gpios:
            sensor[u'gpios'].append({
                u'uuid': gpio[u'uuid'],
                u'pin': gpio[u'pin'],
                u'gpio': gpio['gpio'],
            })
            
    def add_sensor(self, type, subtype, data):
        """
        Add sensor
        
        Args:
            type (string): sensor type
            subtype (string): sensor subtype
            data (dict): sensor data

        Returns:
            list: list of created sensors
        """
        addon = self._get_addon(type, subtype)
        if addon is None:
            raise CommandError(u'Sensor subtype "%s" doesn\'t exist' % subtype)
            
        sensor_devices = []
        gpio_devices = []
        try:
            self.logger.debug(u'Addon add with data: %s' % data)
            (gpios, sensors) = addon.add(**data).values()
            if not isinstance(gpios, list):
                raise Exception(u'Invalid gpios type. Must be a list')
            if not isinstance(sensors, list):
                raise Exception(u'Invalid sensors type. Must be a list')

            #add gpios
            self.logger.debug('gpios=%s' % gpios)
            for gpio in gpios:
                self.logger.debug(u'add_gpio with: %s' % gpio)
                resp_gpio = self.send_command(u'add_gpio', u'gpios', gpio)
                if resp_gpio[u'error']:
                    raise CommandError(resp_gpio[u'message'])
                gpio_devices.append(resp_gpio[u'data'])
                
            #fill sensors gpios
            for sensor_device in sensors:
                self._fill_sensor_gpios(sensor_device, gpio_devices)

            #add sensors
            for sensor in sensors:
                self.logger.debug(u'add_device with: %s' % sensor)
                sensor_device = self._add_device(sensor)
                if sensor_device is None:
                    raise CommandError(u'Unable to save new sensor')
                sensor_devices.append(sensor_device)
                
            #start task
            self._start_sensor_task(addon.get_task(sensor_devices[0]), sensor_devices)

            return sensor_devices

        except:
            self.logger.exception(u'Error occured adding sensor "%s-%s": %s' % (type, subtype, data))
            
            #undo saved gpios
            for gpio in gpio_devices:
                self.send_command(u'delete_gpio', u'gpios', {u'uuid': gpio[u'uuid']})
                
            #undo saved sensors
            for sensor in sensor_devices:
               self._delete_device(sensor[u'uuid']) 

            raise CommandError(u'Error occured adding sensor')
        
    def delete_sensor(self, uuid):
        """
        Delete specified sensor

        Args:
            uuid (string): sensor identifier

        Returns:
            bool: True if deletion succeed
        """
        sensor = self._get_device(uuid)
        if not uuid:
            raise MissingParameter(u'Uuid parameter is missing')
        elif sensor is None:
            raise InvalidParameter(u'Sensor with uuid "%s" doesn\'t exist' % uuid)

        #search addon
        addon = self._get_addon(sensor[u'type'], sensor[u'subtype'])
        if addon is None:
            raise CommandError(u'Unhandled sensor type "%s-%s"' % (sensor[u'type'], sensor[u'subtype']))
            
        try:
            #stop task
            self._stop_sensor_task(sensor)
            
            (gpios, sensors) = addon.delete(sensor).values()
            if not isinstance(gpios, list):
                raise Exception(u'Invalid gpios type. Must be a list')
            if not isinstance(sensors, list):
                raise Exception(u'Invalid sensors type. Must be a list')
                                   
            #unconfigure gpios
            self.logger.debug('Gpios=%s' % gpios)
            for gpio in gpios:
                #is a reserved gpio
                self.logger.debug('is_reserved_gpio for gpio "%s"' % gpio)
                resp = self.send_command(u'is_reserved_gpio', u'gpios', {u'gpio': gpio[u'uuid']})
                self.logger.debug(u'is_reserved_gpio: %s' % resp)
                if resp[u'error']:
                    raise CommandError(resp[u'message'])
                reserved_gpio = resp[u'data']
               
                #check if we can delete gpio
                delete_gpio = True
                if reserved_gpio:
                    #reserved gpio, don't delete it
                    delete_gpio = False
                elif self._get_gpio_uses(gpio[u'gpio'])>1:
                    #another device is using gpio, do not delete it in gpio module
                    self.logger.info(u'More than one sensor is using gpio, disable gpio deletion')
                    delete_gpio = False

                #delete device in gpio module
                if delete_gpio:
                    self.logger.debug(u'Delete gpio "%s" from gpios module' % gpio[u'uuid'])
                    resp = self.send_command(u'delete_gpio', u'gpios', {u'uuid':gpio[u'uuid']})
                    if resp[u'error']:
                        raise CommandError(resp[u'message'])
                else:
                    self.logger.debug(u'Gpio device not deleted because other sensor is using it')

            #delete sensors
            for sensor in sensors:
                self._delete_device(sensor[u'uuid'])
                self.logger.debug(u'Sensor "%s" deleted successfully' % sensor[u'uuid'])
            
            return True
        
        except:
            self.logger.exception(u'Error occured deleting sensor "%s":' % (uuid))
            raise CommandError(u'Error deleting sensor')
        
    def update_sensor(self, uuid, data):
        """
        Update sensor
        
        Args:
            uuid (string): sensor uuid
            data (dict): sensor data
            
        Returns:
            list: list of updated sensors
        """
        sensor = self._get_device(uuid)
        self.logger.debug('update_sensor found device: %s' % sensor)
        if not uuid:
            raise MissingParameter(u'Uuid parameter is missing')
        elif sensor is None:
            raise InvalidParameter(u'Sensor with uuid "%s" doesn\'t exist' % uuid)

        #search addon
        addon = self._get_addon(sensor[u'type'], sensor[u'subtype'])
        if addon is None:
            raise CommandError(u'Unhandled sensor type "%s-%s"' % (sensor[u'type'], sensor[u'subtype']))

        sensor_devices = []
        gpio_devices = []
        try:
            #prepare data mixing all params from all sensors
            #sensors = self._search_device(u'name', sensor[u'name'])
            #for sensor in sensors:
            #    data.update(sensor)
            data[u'sensor'] = sensor
            (gpios, sensors) = addon.update(**data).values()
            if not isinstance(gpios, list):
                raise Exception(u'Invalid gpios type. Must be a list')
            if not isinstance(sensors, list):
                raise Exception(u'Invalid sensors type. Must be a list')

            #update gpios
            for gpio in gpios:
                resp_gpio = self.send_command(u'update_gpio', u'gpios', gpio)
                if resp_gpio[u'error']:
                    raise CommandError(resp_gpio[u'message'])
                gpio_devices.append(resp_gpio[u'data'])
                
            #update sensors
            for sensor in sensors:
                if not self._update_device(sensor[u'uuid'], sensor):
                    raise CommandError(u'Unable to save sensor update')
                sensor_devices.append(sensor)
                
            #restart sensor task
            task = addon.get_task(sensor)
            if task:
                self._stop_sensor_task(sensor)
                self._start_sensor_task(task, [sensor])
                
            return sensor_devices
        
        except:
            self.logger.exception(u'Error occured updating sensor "%s": %s' % (uuid, data))
            raise CommandError(u'Error updating sensor')

    def _start_sensor_task(self, task, sensors):
        """
        Start specified sensor task
        
        Args:
            task (Task): task to start. If None nothing will be done
            sensor (dict): sensor data
        """
        #for some sensors there is no task because sensor value is updated by another way (gpio event...)
        if not task:
            self.logger.debug('No task for sensors %s' % sensors)
            return

        #save and start task
        for sensor in sensors:
            self._tasks_by_device_uuid[sensor[u'uuid']] = task
        self.logger.debug(u'Start task for sensor "%s" [%s]' % (sensor[u'name'], id(task)))
        task.start()

    def _stop_sensor_task(self, sensor):
        """
        Stop sensor task
        sensor name is specified in specific parameter because sensor can contain different name after sensor update

        Args:
            sensor (dict): sensor data
        """
        #search for task
        task = None
        for uuid, _task in self._tasks_by_device_uuid.items():
            if uuid==sensor[u'uuid']:
                task = _task
        if task is None:
            self.logger.warning(u'Sensor "%s" has no task running' % sensor[u'name'])
            return

        #stop task
        self.logger.debug(u'Stop task for sensor "%s" [%s]' % (sensor[u'name'], id(task)))
        task.stop()
        
        #purge not running task
        for uuid, _task in self._tasks_by_device_uuid.items():
            if not task.is_running():
                del self._tasks_by_device_uuid[uuid]

