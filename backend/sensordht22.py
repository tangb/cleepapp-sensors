#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import time
from cleep.exception import InvalidParameter
from cleep.libs.internals.console import Console
from .sensor import Sensor
from .sensorsutils import SensorsUtils


class SensorDht22(Sensor):
    """
    Sensor DHT22 addon
    """

    TYPE_HUMIDITY = "humidity"
    TYPE_TEMPERATURE = "temperature"
    TYPES = [TYPE_TEMPERATURE, TYPE_HUMIDITY]
    SUBTYPE = "dht22"

    DHT22_CMD = "/usr/local/bin/dht22 %s"

    def __init__(self, sensors):
        """
        Constructor

        Args:
            sensors (Sensors): Sensors instance
        """
        Sensor.__init__(self, sensors)

        # events
        self.sensors_temperature_update = self._get_event("sensors.temperature.update")
        self.sensors_humidity_update = self._get_event("sensors.humidity.update")

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

        for device in self._search_devices("name", name):
            if device["subtype"] == self.SUBTYPE:
                if device["type"] == self.TYPE_TEMPERATURE:
                    temperature_device = device
                elif device["type"] == self.TYPE_HUMIDITY:
                    humidity_device = device

        return (temperature_device, humidity_device)

    def add(self, params):
        """
        Return sensor data to add.
        Can perform specific stuff

        Args:
            params (dict): sensor params::

                {
                    name (str): sensor name
                    gpio (str): gpio name
                    interval (int): interval value
                    offset (int): offset value
                    offset_unit (str): offset unit
                }

        Returns:
            dict: sensor data to add::

                {
                    gpios (list): list of gpios data to add
                    sensors (list): list sensors data to add
                }

        """
        # get assigned gpios
        assigned_gpios = self._get_assigned_gpios()

        # check parameters
        self._check_parameters(
            [
                {
                    "name": "name",
                    "value": params.get("name"),
                    "type": str,
                    "validator": lambda val: self._search_device("name", val) is None,
                    "message": f'Name "{params.get("name")}" is already used',
                },
                {
                    "name": "gpio",
                    "value": params.get("gpio"),
                    "type": str,
                    "validator": lambda val: params.get("gpio") not in assigned_gpios,
                    "message": f'Gpio "{params.get("gpio")}" is already used',
                },
                {
                    "name": "interval",
                    "value": params.get("interval"),
                    "type": int,
                    "validator": lambda val: val >= 60,
                    "message": "Interval must be greater or equal than 60",
                },
                {
                    "name": "offset",
                    "value": params.get("offset"),
                    "type": int,
                },
                {
                    "name": "offset_unit",
                    "value": params.get("offset_unit"),
                    "type": str,
                    "validator": lambda val: val
                    in (SensorsUtils.TEMP_CELSIUS, SensorsUtils.TEMP_FAHRENHEIT),
                    "message": 'Offset_unit value must be either "celsius" or "fahrenheit"',
                },
            ]
        )
        # TODO add new validator in Cleep core
        if params.get("gpio") not in self.raspi_gpios:
            raise InvalidParameter(
                f'Gpio "{params.get("gpio")}" does not exist for this raspberry pi'
            )

        gpio_data = {
            "name": params.get("name") + "_dht22",
            "gpio": params.get("gpio"),
            "mode": "input",
            "keep": False,
            "inverted": False,
        }

        temperature_data = {
            "name": params.get("name"),
            "gpios": [],
            "type": self.TYPE_TEMPERATURE,
            "subtype": self.SUBTYPE,
            "interval": params.get("interval"),
            "offset": params.get("offset"),
            "offsetunit": params.get("offset_unit"),
            "lastupdate": int(time.time()),
            "celsius": None,
            "fahrenheit": None,
        }

        humidity_data = {
            "name": params.get("name"),
            "gpios": [],
            "type": self.TYPE_HUMIDITY,
            "subtype": self.SUBTYPE,
            "interval": params.get("interval"),
            "lastupdate": int(time.time()),
            "humidity": None,
        }

        return {
            "gpios": [
                gpio_data,
            ],
            "sensors": [
                temperature_data,
                humidity_data,
            ],
        }

    def update(self, sensor, params):
        """
        Returns sensor data to update
        Can perform specific stuff

        Args:
            sensor (dict): sensor data
            params (dict): update params::

                {
                    name (str): sensor name
                    interval (int): interval value
                    offset (int): offset value
                    offset_unit (str): offset unit
                }

        Returns:
            dict: sensor data to update::

                {
                    gpios (list): list of gpios data to add
                    sensors (list): list sensors data to add
                }

        """
        # check parameters
        self._check_parameters(
            [
                {
                    "name": "sensor",
                    "value": sensor,
                    "type": dict,
                },
                {
                    "name": "name",
                    "value": params.get("name"),
                    "type": str,
                    "validator": lambda val: sensor["name"] == val
                    or self._search_device("name", val) is None,
                    "message": f'Name "{params.get("name")}" is already used',
                },
                {
                    "name": "interval",
                    "value": params.get("interval"),
                    "type": int,
                    "validator": lambda val: val >= 60,
                    "message": "Interval must be greater or equal than 60",
                },
                {
                    "name": "offset",
                    "value": params.get("offset"),
                    "type": int,
                },
                {
                    "name": "offset_unit",
                    "value": params.get("offset_unit"),
                    "type": str,
                    "validator": lambda val: val
                    in (SensorsUtils.TEMP_CELSIUS, SensorsUtils.TEMP_FAHRENHEIT),
                    "message": 'Offset_unit value must be either "celsius" or "fahrenheit"',
                },
            ]
        )

        # search all sensors with same name
        old_name = sensor["name"]
        (temperature_device, humidity_device) = self._get_dht22_devices(sensor["name"])

        # reconfigure gpio
        gpios = []
        if old_name != params.get("name"):
            gpios.append(
                {
                    "uuid": (temperature_device or humidity_device)["gpios"][0]["uuid"],
                    "name": params.get("name") + "_dht22",
                    "mode": "input",
                    "keep": False,
                    "inverted": False,
                }
            )

        # temperature sensor
        sensors = []
        if temperature_device:
            temperature_device["name"] = params.get("name")
            temperature_device["interval"] = params.get("interval")
            temperature_device["offset"] = params.get("offset")
            temperature_device["offsetunit"] = params.get("offset_unit")
            sensors.append(temperature_device)

        # humidity sensor
        if humidity_device:
            humidity_device["name"] = params.get("name")
            humidity_device["interval"] = params.get("interval")
            sensors.append(humidity_device)

        return {
            "gpios": gpios,
            "sensors": sensors,
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
        # check params
        self._check_parameters([{"name": "sensor", "value": sensor, "type": dict}])

        # search all sensors with same name
        (temperature_device, humidity_device) = self._get_dht22_devices(sensor["name"])

        # gpios
        gpios = [
            (temperature_device or humidity_device)["gpios"][0],
        ]

        # sensors
        sensors = []
        if temperature_device:
            sensors.append(temperature_device)
        if humidity_device:
            sensors.append(humidity_device)

        return {
            "gpios": gpios,
            "sensors": sensors,
        }

    def _execute_command(self, sensor):  # pragma: no cover
        """
        Execute dht22 binary command
        Useful for unit testing
        """
        console = Console()
        cmd = self.DHT22_CMD % sensor["gpios"][0]["pin"]
        self.logger.debug('Read DHT22 sensor values from command "%s"', cmd)
        resp = console.command(cmd, timeout=11)
        self.logger.debug("Read DHT command response: %s", resp)
        if resp["error"] or resp["killed"]:
            self.logger.error("DHT22 command failed: %s", resp)

        return json.loads(resp["stdout"][0])

    def _read_dht22(self, sensor):
        """
        Read temperature from dht22 sensor

        Params:
            sensor (dict): sensor data

        Returns:
            tuple: (temp celsius, temp fahrenheit, humidity)
        """
        temp_c = None
        temp_f = None
        hum_p = None

        try:
            # get values from external binary (binary hardcoded timeout set to 10 seconds)
            data = self._execute_command(sensor)

            # check read errors
            if len(data["error"]) > 0:
                self.logger.error(
                    "Error occured during DHT22 command execution: %s", data["error"]
                )
                raise RuntimeError("DHT22 command failed")

            # get DHT22 values
            (temp_c, temp_f) = SensorsUtils.convert_temperatures_from_celsius(
                data["celsius"], sensor["offset"], sensor["offsetunit"]
            )
            hum_p = data["humidity"]
            self.logger.info(
                "Read values from DHT22: %s°C, %s°F, %s%%", temp_c, temp_f, hum_p
            )

        except Exception:
            self.logger.exception("Error executing DHT22 command")

        return (temp_c, temp_f, hum_p)

    def _task(self, temperature_device, humidity_device):
        """
        DHT22 task

        Args:
            temperature_device (dict): temperature sensor
            humidity_device (dict): humidity sensor
        """
        # read values
        (temp_c, temp_f, hum_p) = self._read_dht22(
            (temperature_device or humidity_device)
        )

        now = int(time.time())
        if temperature_device and temp_c is not None and temp_f is not None:
            # temperature values are valid, update sensor values
            temperature_device["celsius"] = temp_c
            temperature_device["fahrenheit"] = temp_f
            temperature_device["lastupdate"] = now

            # and send event if update succeed (if not device may has been removed)
            if self.update_value(temperature_device):
                params = {
                    "sensor": temperature_device["name"],
                    "celsius": temp_c,
                    "fahrenheit": temp_f,
                    "lastupdate": now,
                }
                self.sensors_temperature_update.send(
                    params=params, device_id=temperature_device["uuid"]
                )

        if humidity_device and hum_p is not None:
            # humidity value is valid, update sensor value
            humidity_device["humidity"] = hum_p
            humidity_device["lastupdate"] = now

            # and send event if update succeed (if not device may has been removed)
            if self.update_value(humidity_device):
                params = {
                    "sensor": humidity_device["name"],
                    "humidity": hum_p,
                    "lastupdate": now,
                }
                self.sensors_humidity_update.send(
                    params=params, device_id=humidity_device["uuid"]
                )

        if temp_c is None and temp_f is None and hum_p is None:
            self.logger.warning("No value returned by DHT22 sensor!")

    def _get_task(self, sensor):
        """
        Prepare task for DHT sensor only. It should have 2 devices with the same name.

        Args:
            sensor (dict): one of DHT22 sensor (temperature or humidity)

        Returns:
            Task: sensor task
        """
        # search all sensors with same name
        (temperature_device, humidity_device) = self._get_dht22_devices(sensor["name"])

        return self.task_factory.create_task(
            float(sensor["interval"]), self._task, [temperature_device, humidity_device]
        )
