#!/usr/bin/env python
# -*- coding: utf-8 -*-


class Sensor:
    """
    Sensor base class

    Sensor instance must declare following members:
     - TYPES (list): list of supported sensors types (temperature, motion, humidity, pressure...)
     - SUBTYPE (string): name of subtype. Usually name of sensor type (dht, onewire...)
    """

    def __init__(self, sensors):
        """
        Constructor

        Args:
            sensors (Sensors): Sensors instance
        """
        self.sensors = sensors
        self.task_factory = sensors.task_factory
        self.logger = sensors.logger
        # will be filled by sensors during module configuration
        self.raspi_gpios = {}
        self.drivers = {}
        self.cleep_filesystem = sensors.cleep_filesystem
        self.__task = None
        self._check_parameters = sensors._check_parameters

        # trick to avoid pylint errors about protected function access
        self.sensors_fn = {
            "register_driver": self.sensors._register_driver,
            "get_event": self.sensors._get_event,
            "update_device": self.sensors._update_device,
            "search_device": self.sensors._search_device,
            "search_devices": self.sensors._search_devices,
            "search_by_gpio": self.sensors._search_by_gpio,
            "get_device": self.sensors._get_device,
            "get_assigned_gpios": self.sensors._get_assigned_gpios,
        }

    def _register_driver(self, driver):
        """
        Register driver

        Args:
            driver (Driver): driver instance
        """
        self.sensors_fn["register_driver"](driver)
        self.drivers[driver.name] = driver

    def has_drivers(self):
        """
        Has addon drivers registered ?

        Returns:
            bool: True if a driver is registered
        """
        return len(self.drivers) > 0

    def _get_event(self, event_name):
        """
        Returns event name

        Returns:
            event (Event): event or None
        """
        return self.sensors_fn["get_event"](event_name)

    def send_command(self, command, to, params=None, timeout=3.0):
        """
        Send command on internal bus
        """
        return self.sensors.send_command(command, to, params, timeout)

    def update_value(self, sensor):
        """
        Update sensor values (timestamp, temperature, motion status...)

        Args:
            sensor (dict): sensor data
        """
        return self.sensors_fn["update_device"](sensor["uuid"], sensor)

    def _search_device(self, key, value):
        """
        Search first device that matches specified criteria

        Args:
            key (string): field key
            value (string): field value
        """
        return self.sensors_fn["search_device"](key, value)

    def _search_devices(self, key, value):
        """
        Search add devices that match specified criteria

        Args:
            key (string): field key
            value (string): field value
        """
        return self.sensors_fn["search_devices"](key, value)

    def _search_by_gpio(self, gpio_uuid):
        """
        Search sensor connected to specified gpio_uuid

        Params:
            gpio_uuid (string): gpio uuid to search

        Returns:
            dict: sensor data or None if nothing found
        """
        return self.sensors_fn["search_by_gpio"](gpio_uuid)

    def _get_device(self, uuid):
        """
        Return device according to uuid

        Args:
            uuid (string): device uuid
        """
        return self.sensors_fn["get_device"](uuid)

    def _get_assigned_gpios(self):
        """
        Return assigned gpios

        Returns:
            dict: assigned gpios
        """
        return self.sensors_fn["get_assigned_gpios"]()

    def update(self, sensor, params):  # pragma: no cover
        """
        Returns sensor data to update
        Can perform specific stuff

        Args:
            sensor (dict): existing sensor to update
            params (dict): update params. Varies according to sensor::

                {
                    param1 (any),
                    param2 (any),
                    ...
                }

        Returns:
            dict: sensor data to update::

                {
                    gpios (list): list of gpios data to add
                    sensors (list): list sensors data to add
                }

        """
        raise NotImplementedError(
            f'Function "update" must be implemented in "{self.__class__.__name__}"'
        )

    def add(self, params):  # pragma: no cover
        """
        Return sensor data to add.
        Can perform specific stuff

        Args:
            params (dict): add params. Varies according to sensor::

                {
                    param1 (any),
                    param2 (any),
                    ...
                }

        Returns:
            dict: sensor data to add::

                {
                    gpios (list): list of gpios data to add
                    sensors (list): list sensors data to add
                }

        """
        raise NotImplementedError(
            f'Function "add" must be implemented in "{self.__class__.__name__}"'
        )

    def delete(self, sensor):
        """
        Returns sensor data to delete

        Note:
            Can be overwritten to fit to custom sensor data

        Returns:
            dict: sensor data to delete::

                {
                    gpios (list): list of gpios data to add
                    sensors (list): list sensors data to add
                }

        """
        return {
            "gpios": sensor["gpios"],
            "sensors": [
                sensor,
            ],
        }

    def get_task(self, sensor):
        """
        Prepare specific sensor task

        Args:
            sensor (dict): sensor instance

        Returns:
            Task: task instance that will be launched by sensors instance or None if no task needed
        """
        # instanciate singleton
        if self.__task is None:
            self.__task = self._get_task(sensor)

        return self.__task

    def _get_task(self, sensor):  # pragma: no cover
        """
        Prepare specific sensor task

        Args:
            sensors (list): list of sensors data (dict)

        Returns:
            Task: task instance that will be launched by sensors instance or None if no task needed
        """
        raise NotImplementedError(
            f'Function "get_task" must be implemented in "{self.__class__.__name__}"'
        )

    def process_event(self, event, sensor):  # pragma: no cover
        """
        Process received event. Can be a gpio or driver event

        Args:
            event (MessageRequest): event
            sensor (dict): sensor data
        """
        return
