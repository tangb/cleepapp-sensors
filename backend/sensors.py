#!/usr/bin/env python
# -*- coding: utf-8 -*-

import copy
from cleep.exception import MissingParameter, InvalidParameter, CommandError
from cleep.core import CleepModule
from .sensormotiongeneric import SensorMotionGeneric
from .sensordht22 import SensorDht22
from .sensoronewire import SensorOnewire

__all__ = ["Sensors"]


class Sensors(CleepModule):
    """
    Sensors module handles different kind of sensors:
     - temperature (DS18B20)
     - motion
     - DHT22
     - ...
    """

    MODULE_AUTHOR = "Cleep"
    MODULE_VERSION = "1.2.0"
    MODULE_CATEGORY = "APPLICATION"
    MODULE_DEPS = ["gpios"]
    MODULE_DESCRIPTION = (
        "Implements easily and quickly sensors like temperature, motion, light..."
    )
    MODULE_LONGDESCRIPTION = (
        "With this module you will be able to follow environment temperature, "
        "detect some motion around your device, detect when light level is dim... "
        "and trigger some action according to those stimuli."
    )
    MODULE_TAGS = ["sensors", "temperature", "motion", "onewire", "1wire"]
    MODULE_URLINFO = "https://github.com/tangb/cleepmod-sensors"
    MODULE_URLHELP = None
    MODULE_URLBUGS = "https://github.com/tangb/cleepmod-sensors/issues"
    MODULE_URLSITE = None

    MODULE_CONFIG_FILE = "sensors.conf"
    DEFAULT_CONFIG = {}

    def __init__(self, bootstrap, debug_enabled):
        """
        Constructor

        Params:
            bootstrap (dict): bootstrap objects
            debug_enabled (bool): debug status
        """
        # init
        CleepModule.__init__(self, bootstrap, debug_enabled)

        # members
        self._tasks_by_device_uuid = {}
        self.raspi_gpios = {}
        self.addons_by_name = {}
        self.addons_by_type = {}
        self.sensors_types = {}

        # addons
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
        # save addon by type
        for type_ in addon.TYPES:
            if type_ not in self.addons_by_type:
                self.addons_by_type[type_] = {}
            if addon.SUBTYPE in self.addons_by_type[type_]:
                raise ValueError(f'Subtype "{addon.SUBTYPE}" already registered in type "{type_}"')
            self.addons_by_type[type_][addon.SUBTYPE] = addon

        # save sensors types (by addons)
        self.sensors_types[addon.__class__.__name__] = {
            "types": addon.TYPES,
            "subtype": addon.SUBTYPE,
        }

        # save addon by name
        self.addons_by_name[addon.__class__.__name__] = addon

        # inject in sensors public addon methods
        blacklist = [
            "add_gpio",
            "update_gpio",
            "get_reserved_gpio",
            "update_value",
            "update",
            "add",
            "delete",
            "get_task",
            "process_event",
            "has_drivers",
            "send_command",
            "cleep_filesystem",
        ]
        methods = [
            method_name
            for method_name in dir(addon)
            if method_name not in blacklist
            and not method_name.startswith("_")
            and callable(getattr(addon, method_name))
        ]
        self.logger.debug('Addon "%s" public methods: %s', addon.__class__.__name__, methods)
        for method_name in methods:
            if hasattr(self, method_name): # pragma: no cover
                self.logger.error(
                    'Public method "%s" from addon "%s" is already referenced. Please rename it',
                    method_name, addon.__class__.__name__
                )
                continue
            self.logger.debug('Register method "%s" from addon "%s"', method_name, addon.__class__.__name__)
            setattr(self, method_name, getattr(addon, method_name))

    def _on_start(self):
        """
        Start application
        """
        # raspi gpios
        self.raspi_gpios = self._get_raspi_gpios()

        # update addons
        for _, addon in self.addons_by_name.items():
            addon.raspi_gpios = self.raspi_gpios

        # launch tasks
        sensors = self.get_module_devices()
        for _, sensor in sensors.items():
            addon = self._get_addon(sensor["type"], sensor["subtype"])
            if addon is None:
                continue
            self._start_sensor_task(addon.get_task(sensor), [sensor])

    def _on_stop(self):
        """
        Stop application
        """
        # stop tasks
        for _, task in self._tasks_by_device_uuid.items():
            task.stop()

    def on_event(self, event):
        """
        Event received

        Params:
            event (MessageRequest): event data
        """
        # drop startup events
        if event["startup"]:
            self.logger.debug("Drop startup event")
            return

        # driver event
        if event["event"] in ("system.driver.install", "system.driver.uninstall"):
            for _, addon in self.addons_by_name.items():
                if addon.has_drivers():
                    addon.process_event(event, None)

        # gpio event
        if event["event"] in ("gpios.gpio.on", "gpios.gpio.off"):
            # drop gpio init
            if event["params"]["init"]:
                self.logger.debug("Drop gpio init event")
                return

            # get uuid event
            gpio_uuid = event["device_id"]

            # search sensor
            sensor = self._search_by_gpio(gpio_uuid)
            self.logger.debug("Found sensor: %s", sensor)
            if not sensor:
                return

            # process event on addon
            addon = self._get_addon(sensor["type"], sensor["subtype"])
            self.logger.debug("Found addon: %s", addon)
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
        for device in devices.values():
            for gpio in device["gpios"]:
                if gpio["uuid"] == gpio_uuid:
                    # sensor found
                    return device

        # nothing found
        return None

    def get_module_config(self):
        """
        Get full module configuration

        Returns:
            dict: module configuration
        """
        config = {"drivers": {}, "sensorstypes": self.sensors_types}

        # add drivers
        for _, addon in self.addons_by_name.items():
            for driver_name, driver in addon.drivers.items():
                config["drivers"][driver_name] = driver.is_installed()

        return config

    def _get_gpio_uses(self, gpio):
        """
        Return number of device that are using specified gpio (multi sensors)

        Params:
             gpio (string): gpio name

        Returns:
            number of devices that are using the gpio
        """
        devices = self._get_devices()
        uses = 0
        for device in devices.values():
            for gpio_ in device["gpios"]:
                if gpio == gpio_["gpio"]:
                    uses += 1
        return uses

    def _get_raspi_gpios(self):
        """
        Get raspi gpios

        Returns:
            dict: raspi gpios
        """
        resp = self.send_command("get_raspi_gpios", "gpios")
        if resp.error:
            self.logger.error(resp.message)
            return {}

        return resp.data

    def _get_assigned_gpios(self):
        """
        Return assigned gpios

        Returns:
            list: assigned gpios
        """
        resp = self.send_command("get_assigned_gpios", "gpios")
        if resp.error:
            self.logger.error(resp.message)
            return []

        return resp.data

    def _get_addon(self, sensor_type, sensor_subtype):
        """
        Return addon

        Args:
            sensor_type (string): sensor type
            sensor_subtype (string): sensor subtype

        Returns:
            Sensor: sensor instance or None if not found
        """
        if sensor_type in self.addons_by_type and sensor_subtype in self.addons_by_type[sensor_type]:
            return self.addons_by_type[sensor_type][sensor_subtype]

        return None

    def _fill_sensor_gpios(self, sensor, gpios):
        """
        Fill sensor gpios field content.
        It will store only some useful fields from gpio like uuid, pin number and gpio name

        Args:
            sensor (dict): sensor data to fill
            gpios (list): list of gpios
        """
        if "gpios" not in sensor:
            sensor["gpios"] = []

        for gpio in gpios:
            sensor["gpios"].append(
                {
                    "uuid": gpio["uuid"],
                    "pin": gpio["pin"],
                    "gpio": gpio["gpio"],
                }
            )

    def _fix_gpio_device(self, gpio_device):
        """
        Replace uuid with device_uuid in gpio content

        Args:
            gpio_device (dict): gpio device

        Returns:
            dict: input gpio with valid data to request gpios app
        """
        self.logger.debug("Gpio to fix: %s", gpio_device)
        fixed_gpio_device = copy.deepcopy(gpio_device)
        if "uuid" in gpio_device:
            fixed_gpio_device["device_uuid"] = gpio_device["uuid"]
            del fixed_gpio_device["uuid"]

        return fixed_gpio_device

    def add_sensor(self, sensor_type, sensor_subtype, data):
        """
        Add sensor according to specified type and subtype

        Args:
            sensor_type (string): sensor type
            sensor_subtype (string): sensor subtype
            data (dict): sensor data (differs from kind of sensor)::

                {
                    name (str): sensor name,
                    gpio (str): used gpio
                    ...
                }

        Returns:
            list: list of created sensors::

                [ SensorInstance1, SensorInstance2, ...]
        """
        addon = self._get_addon(sensor_type, sensor_subtype)
        if addon is None:
            raise CommandError(f'Sensor subtype "{sensor_subtype}" doesn\'t exist')

        sensor_devices = []
        gpio_devices = []
        try:
            self.logger.debug('Addon "%s" add with data: %s', addon.__class__.__name__, data)
            (gpios, sensors) = addon.add(data).values()
            if not isinstance(gpios, list) or not isinstance(sensors, list): # pragma: no cover
                raise TypeError("Invalid gpios or sensors type. Must be a list")

            # add gpios
            self.logger.debug("Gpios: %s", gpios)
            for gpio in gpios:
                self.logger.debug("add_gpio with: %s", gpio)
                resp_gpio = self.send_command("add_gpio", "gpios", self._fix_gpio_device(gpio))
                if resp_gpio.error:
                    raise CommandError(resp_gpio.message)
                gpio_devices.append(resp_gpio.data)

            # fill sensors gpios
            for sensor_device in sensors:
                self._fill_sensor_gpios(sensor_device, gpio_devices)

            # add sensors
            for sensor in sensors:
                self.logger.debug("add_device with: %s", sensor)
                added_sensor = self._add_device(sensor)
                if added_sensor is None:
                    raise CommandError("Unable to save new sensor")
                sensor_devices.append(added_sensor)

            # start task
            self._start_sensor_task(addon.get_task(sensor_devices[0]), sensor_devices)

            return sensor_devices

        except Exception as error:
            self.logger.exception(
                'Error occured adding sensor "%s-%s": %s', sensor_type, sensor_subtype, data
            )

            # undo saved gpios
            for gpio in gpio_devices:
                self.send_command("delete_gpio", "gpios", {"device_uuid": gpio["uuid"]})

            # undo saved sensors
            for sensor in sensor_devices:
                self._delete_device(sensor["uuid"])

            raise CommandError("Error occured adding sensor") from error

    def delete_sensor(self, sensor_uuid):
        """
        Delete specified sensor

        Args:
            sensor_uuid (string): sensor identifier

        Returns:
            bool: True if deletion succeed
        """
        if not sensor_uuid:
            raise MissingParameter("Uuid parameter is missing")
        sensor = self._get_device(sensor_uuid)
        if sensor is None:
            raise InvalidParameter(f'Sensor with uuid "{sensor_uuid}" doesn\'t exist')

        # search addon
        addon = self._get_addon(sensor["type"], sensor["subtype"])
        if addon is None:
            raise CommandError(f'Unhandled sensor type "{sensor["type"]}-{sensor["subtype"]}"')

        try:
            # stop task
            self._stop_sensor_task(sensor)

            (gpios, sensors) = addon.delete(sensor).values()
            if not isinstance(gpios, list) or not isinstance(sensors, list): # pragma: no cover
                raise TypeError("Invalid gpios or sensors type. Must be a list")

            # unconfigure gpios
            self.logger.debug("Gpios: %s", gpios)
            for gpio in gpios:
                # is a reserved gpio
                self.logger.debug('is_reserved_gpio for gpio "%s"', gpio)
                resp = self.send_command(
                    "is_reserved_gpio", "gpios", {"gpio": gpio["uuid"]}
                )
                self.logger.debug("is_reserved_gpio: %s", resp)
                if resp.error:
                    raise CommandError(resp.message)
                reserved_gpio = resp.data

                # check if we can delete gpio
                delete_gpio = True
                if reserved_gpio:
                    # reserved gpio, don't delete it
                    delete_gpio = False
                elif self._get_gpio_uses(gpio["gpio"]) > 1:
                    # another device is using gpio, do not delete it in gpio module
                    self.logger.info(
                        "More than one sensor is using gpio, disable gpio deletion"
                    )
                    delete_gpio = False

                # delete device in gpio module
                if delete_gpio:
                    self.logger.debug(
                        'Delete gpio "%s" from gpios module', gpio["uuid"]
                    )
                    resp = self.send_command(
                        "delete_gpio", "gpios", {"device_uuid": gpio["uuid"]}
                    )
                    if resp.error:
                        self.logger.warning("Gpio can't be deleted: %s", resp.error)
                else:
                    self.logger.debug(
                        "Gpio device not deleted because other sensor is using it"
                    )

            # delete sensors
            for sensor in sensors:
                self._delete_device(sensor["uuid"])
                self.logger.debug('Sensor "%s" deleted successfully', sensor["uuid"])

            return True

        except Exception as error:
            self.logger.exception('Error occured deleting sensor "%s":', sensor_uuid)
            raise CommandError("Error deleting sensor") from error

    def update_sensor(self, sensor_uuid, data):
        """
        Update sensor

        Args:
            sensor_uuid (string): sensor uuid
            data (dict): sensor data::

                {
                    name (str): sensor name,
                    gpio (str): used gpio
                    ...
                }

        Returns:
            list: list of updated sensors::

                [SensorInstance1, SensorInstance2, ...]

        """
        if not sensor_uuid:
            raise MissingParameter("Uuid parameter is missing")
        sensor = self._get_device(sensor_uuid)
        if sensor is None:
            raise InvalidParameter(f'Sensor with uuid "{sensor_uuid}" doesn\'t exist')

        # search addon
        addon = self._get_addon(sensor["type"], sensor["subtype"])
        if addon is None:
            raise CommandError(f'Unhandled sensor type "{sensor["type"]}-{sensor["subtype"]}"')

        sensor_devices = []
        gpio_devices = []
        try:
            # prepare data mixing all params from all sensors
            (gpios, sensors) = addon.update(sensor, data).values()
            if not isinstance(gpios, list) or not isinstance(sensors, list): # pragma: no cover
                raise TypeError("Invalid gpios or sensors type. Must be a list")

            # update gpios
            for gpio in gpios:
                resp_gpio = self.send_command("update_gpio", "gpios", self._fix_gpio_device(gpio))
                if resp_gpio.error:
                    raise CommandError(resp_gpio.message)
                gpio_devices.append(resp_gpio.data)

            # update sensors
            for sensor in sensors:
                if not self._update_device(sensor["uuid"], sensor):
                    raise CommandError("Unable to update sensor")
                sensor_devices.append(sensor)

            # restart sensor task
            task = addon.get_task(sensor)
            if task:
                self._stop_sensor_task(sensor)
                self._start_sensor_task(task, [sensor])

            return sensor_devices

        except Exception as error:
            self.logger.exception(
                'Error occured updating sensor "%s": %s', sensor_uuid, data
            )
            raise CommandError("Error updating sensor") from error

    def _start_sensor_task(self, task, sensors):
        """
        Start specified sensor task

        Args:
            task (Task): task to start. If None nothing will be done
            sensors (list): sensors list. If None nothing will be done
        """
        # for some sensors there is no task because sensor value is updated by another way (gpio event...)
        if not task or not sensors:
            self.logger.debug("No task for sensors %s", sensors)
            return

        # save and start task
        sensor_name = None
        for sensor in sensors:
            self._tasks_by_device_uuid[sensor["uuid"]] = task
            sensor_name = sensor["name"]
        self.logger.debug('Start task for sensor "%s" [%s]', sensor_name, id(task))
        task.start()

    def _stop_sensor_task(self, sensor):
        """
        Stop sensor task
        sensor name is specified in specific parameter because sensor can contain different name after sensor update

        Args:
            sensor (dict): sensor data
        """
        # search for task
        task = None
        for (device_uuid, device_task) in self._tasks_by_device_uuid.items():
            if device_uuid == sensor["uuid"]:
                task = device_task
                break
        if task is None:
            self.logger.warning('Sensor "%s" has no task running', sensor["name"])
            return

        # stop task
        self.logger.debug('Stop task for sensor "%s" [%s]', sensor["name"], id(task))
        task.stop()

        # purge not running task
        for device_uuid in list(self._tasks_by_device_uuid.keys()):
            if not self._tasks_by_device_uuid[device_uuid].is_running():
                del self._tasks_by_device_uuid[device_uuid]

