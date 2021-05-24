#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import time
from cleep.exception import MissingParameter, InvalidParameter
from cleep.libs.internals.console import Console
from cleep.libs.internals.task import Task
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
        # get assigned gpios
        assigned_gpios = self._get_assigned_gpios()

        # check values
        if name is None or len(name) == 0:
            raise MissingParameter('Parameter "name" is missing')
        if self._search_device("name", name) is not None:
            raise InvalidParameter('Name "%s" is already used' % name)
        if interval is None:
            raise MissingParameter('Parameter "interval" is missing')
        if interval < 60:
            raise InvalidParameter("Interval must be greater than 60")
        if offset is None:
            raise MissingParameter('Parameter "offset" is missing')
        if offset_unit is None or len(offset_unit) == 0:
            raise MissingParameter('Parameter "offset_unit" is missing')
        if offset_unit not in (
            SensorsUtils.TEMP_CELSIUS,
            SensorsUtils.TEMP_FAHRENHEIT,
        ):
            raise InvalidParameter(
                'Offset_unit must be equal to "celsius" or "fahrenheit"'
            )
        if gpio is None or len(gpio) == 0:
            raise MissingParameter('Parameter "gpio" is missing')
        if gpio in assigned_gpios:
            raise InvalidParameter('Gpio "%s" is already used' % gpio)
        if gpio not in self.raspi_gpios:
            raise InvalidParameter(
                'Gpio "%s" does not exist for this raspberry pi' % gpio
            )

        gpio_data = {
            "name": name + "_dht22",
            "gpio": gpio,
            "mode": "input",
            "keep": False,
            "inverted": False,
        }

        temperature_data = {
            "name": name,
            "gpios": [],
            "type": self.TYPE_TEMPERATURE,
            "subtype": self.SUBTYPE,
            "interval": interval,
            "offset": offset,
            "offsetunit": offset_unit,
            "lastupdate": int(time.time()),
            "celsius": None,
            "fahrenheit": None,
        }

        humidity_data = {
            "name": name,
            "gpios": [],
            "type": self.TYPE_HUMIDITY,
            "subtype": self.SUBTYPE,
            "interval": interval,
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
        # check params
        if sensor is None:
            raise MissingParameter('Parameter "sensor" is missing')
        if name is None or len(name) == 0:
            raise MissingParameter('Parameter "name" is missing')
        if sensor["name"] != name and self._search_device("name", name) is not None:
            raise InvalidParameter('Name "%s" is already used' % name)
        if interval is None:
            raise MissingParameter('Parameter "interval" is missing')
        if interval < 60:
            raise InvalidParameter("Interval must be greater or equal than 60")
        if offset is None:
            raise MissingParameter('Parameter "offset" is missing')
        if offset_unit is None or len(offset_unit) == 0:
            raise MissingParameter('Parameter "offset_unit" is missing')
        if offset_unit not in (
            SensorsUtils.TEMP_CELSIUS,
            SensorsUtils.TEMP_FAHRENHEIT,
        ):
            raise InvalidParameter(
                'Offset_unit value must be either "celsius" or "fahrenheit"'
            )

        # search all sensors with same name
        old_name = sensor["name"]
        (temperature_device, humidity_device) = self._get_dht22_devices(sensor["name"])

        # reconfigure gpio
        gpios = []
        if old_name != name:
            gpios.append(
                {
                    "uuid": (temperature_device or humidity_device)["gpios"][0]["uuid"],
                    "name": name + "_dht22",
                    "mode": "input",
                    "keep": False,
                    "inverted": False,
                }
            )

        # temperature sensor
        sensors = []
        if temperature_device:
            temperature_device["name"] = name
            temperature_device["interval"] = interval
            temperature_device["offset"] = offset
            temperature_device["offsetunit"] = offset_unit
            sensors.append(temperature_device)

        # humidity sensor
        if humidity_device:
            humidity_device["name"] = name
            humidity_device["interval"] = interval
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
        if sensor is None:
            raise MissingParameter('Parameter "sensor" is missing')

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
        self.logger.debug('Read DHT22 sensor values from command "%s"' % cmd)
        resp = console.command(cmd, timeout=11)
        self.logger.debug("Read DHT command response: %s" % resp)
        if resp["error"] or resp["killed"]:
            self.logger.error("DHT22 command failed: %s" % resp)

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
                    "Error occured during DHT22 command execution: %s" % data["error"]
                )
                raise Exception("DHT22 command failed")

            # get DHT22 values
            (temp_c, temp_f) = SensorsUtils.convert_temperatures_from_celsius(
                data["celsius"], sensor["offset"], sensor["offsetunit"]
            )
            hum_p = data["humidity"]
            self.logger.info(
                "Read values from DHT22: %s°C, %s°F, %s%%" % (temp_c, temp_f, hum_p)
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
        (temp_c, temp_f, hum_p) = self._read_dht22((temperature_device or humidity_device))

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

        return Task(
            float(sensor["interval"]),
            self._task,
            self.logger,
            [temperature_device, humidity_device],
        )
