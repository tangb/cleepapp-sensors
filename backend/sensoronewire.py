#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import glob
import time
from cleep.exception import CommandError
from .sensor import Sensor
from .sensorsutils import SensorsUtils
from .onewiredriver import OnewireDriver

class SensorOnewire(Sensor):
    """
    Sensor onewire addon
    """

    TYPE_TEMPERATURE = "temperature"
    TYPES = [TYPE_TEMPERATURE]
    SUBTYPE = "onewire"

    # members for driver
    USAGE_ONEWIRE = "onewire"
    ONEWIRE_RESERVED_GPIO = "GPIO4"

    ONEWIRE_PATH = "/sys/bus/w1/devices/"
    ONEWIRE_SLAVE = "w1_slave"

    def __init__(self, sensors):
        """
        Constructor

        Args:
            sensors (Sensors): Sensors instance
        """
        Sensor.__init__(self, sensors)

        # events
        self.sensors_temperature_update = self._get_event("sensors.temperature.update")

        # drivers
        self.onewire_driver = OnewireDriver()
        self._register_driver(self.onewire_driver)

    def add(self, params):
        """
        Return sensor data to add.
        Can perform specific stuff

        Args:
            params (dict): add params::

                {
                    name (str): sensor name
                    device (str): onewire device
                    path (str): onewire path
                    interval (int): interval
                    offset (int): offset
                    offset_unit (str): offset unit
                }

        Returns:
            dict: sensor data to add::

            {
                gpios (list): list of gpios data to add
                sensors (list): list sensors data to add
            }

        """
        # check parameters
        self._check_parameters([
            {
                "name": "name",
                "value": params.name,
                "type": str,
                "validator": lambda val: self._search_device("name", val) is None,
                "message": f'Name "{params.name}" is already used',
            },
            {
                "name": "device",
                "value": params.device,
                "type": str,
            },
            {
                "name": "path",
                "value": params.path,
                "type": str,
            },
            {
                "name": "interval",
                "value": params.interval,
                "type": int,
                "validator": lambda val: val >= 60,
                "message": "Interval must be greater or equal than 60",
            },
            {
                "name": "offset",
                "value": params.offset,
                "type": int
            },
            {
                "name": "offset_unit",
                "value": params.offset_unit,
                "type": str,
                "validator": lambda val: val in (SensorsUtils.TEMP_CELSIUS, SensorsUtils.TEMP_FAHRENHEIT),
                "message": 'Offset_unit value must be either "celsius" or "fahrenheit"',
            },
        ])

        # get 1wire gpio
        gpio_resp = self.sensors.send_command(
            "get_reserved_gpio", "gpios", {"usage": self.USAGE_ONEWIRE}
        )
        self.logger.debug("Get reserved gpio resp: %s", gpio_resp)
        gpio_device = gpio_resp.data

        # prepare sensor
        sensor_data = {
            "name": params.name,
            "gpios": [
                {
                    "gpio": gpio_device["gpio"],
                    "uuid": gpio_device["uuid"],
                    "pin": gpio_device["pin"],
                }
            ],
            "device": params.device,
            "path": params.path,
            "type": self.TYPE_TEMPERATURE,
            "subtype": self.SUBTYPE,
            "interval": params.interval,
            "offset": params.offset,
            "offsetunit": params.offset_unit,
            "lastupdate": int(time.time()),
            "celsius": None,
            "fahrenheit": None,
        }

        # read temperature
        (temp_c, temp_f) = self._read_onewire_temperature(sensor_data)
        sensor_data["celsius"] = temp_c
        sensor_data["fahrenheit"] = temp_f

        return {
            "gpios": [],
            "sensors": [
                sensor_data,
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
                    name (str): new sensor name
                    interval (int): new interval
                    offset (int): new offset
                    offset_unit (str): new offset unit
                }

        Returns:
            dict: sensor data to update::

                {
                    gpios (list): list of gpios data to add
                    sensors (list): list sensors data to add
                }

        """
        self._check_parameters([
            {
                "name": "sensor",
                "value": sensor,
                "type": dict,
                "validator": lambda val: "uuid" in val and self._search_device("uuid", val["uuid"]) is not None,
                "message": 'Sensor does not exist',
            },
            {
                "name": "name",
                "value": params.name,
                "type": str,
                "validator": lambda val: val == sensor["name"] or self._search_device("name", val) is None,
                "message": f'Name "{params.name}" is already used',
            },
            {
                "name": "interval",
                "value": params.interval,
                "type": int,
                "validator": lambda val: val >= 60,
                "message": "Interval must be greater or equal than 60",
            },
            {
                "name": "offset",
                "value": params.offset,
                "type": int
            },
            {
                "name": "offset_unit",
                "value": params.offset_unit,
                "type": str,
                "validator": lambda val: val in (SensorsUtils.TEMP_CELSIUS, SensorsUtils.TEMP_FAHRENHEIT),
                "message": 'Offset_unit value must be either "celsius" or "fahrenheit"',
            },
        ])

        # update sensor
        sensor["name"] = params.name
        sensor["interval"] = params.interval
        sensor["offset"] = params.offset
        sensor["offsetunit"] = params.offset_unit

        return {
            "gpios": [],
            "sensors": [
                sensor,
            ],
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
            raise CommandError("Onewire driver is not installed")

        devices = glob.glob(os.path.join(self.ONEWIRE_PATH, "28*"))
        self.logger.debug("Onewire devices: %s", devices)
        for device in devices:
            onewires.append(
                {
                    "device": os.path.basename(device),
                    "path": os.path.join(device, self.ONEWIRE_SLAVE),
                }
            )

        return onewires

    def process_event(self, event, sensor):
        """
        Event received specific process for onewire

        Args:
            event (MessageRequest): event
            sensor (dict): sensor data
        """
        if (
            event["event"] == "system.driver.install"
            and event["params"]["drivername"] == "onewire"
            and event["params"]["installing"] is False
        ):
            self.logger.debug('Process "onewire" driver install event')
            # reserve onewire gpio
            params = {
                "name": "reserved_onewire",
                "gpio": self.ONEWIRE_RESERVED_GPIO,
                "usage": self.USAGE_ONEWIRE,
            }
            resp = self.sensors.send_command("reserve_gpio", "gpios", params)
            self.logger.debug("Reserve gpio result: %s", resp)

        elif (
            event["event"] == "system.driver.uninstall"
            and event["params"]["drivername"] == "onewire"
            and event["params"]["uninstalling"] is False
        ):
            self.logger.debug('Process "onewire" driver uninstall event')
            # free onewire gpio
            resp = self.sensors.send_command(
                "get_reserved_gpios", "gpios", {"usage": self.USAGE_ONEWIRE}
            )
            self.logger.debug("Get_reserved_gpios response: %s", resp)
            if not resp.error and resp.data and len(resp.data) > 0:
                sensor = resp.data[0]
                resp = self.sensors.send_command(
                    "delete_gpio", "gpios", {"uuid": sensor["uuid"]}
                )
                self.logger.debug("Delete gpio result: %s", resp)

    def _read_onewire_temperature(self, sensor):
        """
        Read temperature from 1wire device

        Params:
            sensor (dict): sensor data

        Returns:
            tuple: temperature infos::

                (<celsius>, <fahrenheit>) or (None, None) if error occured

        """
        temp_c = None
        temp_f = None

        try:
            if os.path.exists(sensor["path"]):
                # we don't use cleep filesystem here because we only need a readonly access
                with open(sensor["path"], "r") as fdesc:
                    raw = fdesc.readlines()
                equals_pos = raw[1].find("t=")

                if equals_pos != -1:
                    temp_str = raw[1][equals_pos + 2 :].strip()

                    # check value
                    if temp_str in ("85000", "-62"):
                        # invalid value
                        raise ValueError(f'Invalid temperature "{temp_str}"')

                    # convert temperatures
                    temp_c = float(temp_str) / 1000.0
                    (temp_c, temp_f) = SensorsUtils.convert_temperatures_from_celsius(
                        temp_c, sensor["offset"], sensor["offsetunit"]
                    )

                else:
                    # no temperature found in file
                    sensor_path = sensor["path"]
                    raise ValueError(f'No temperature found for onewire "{sensor_path}"')

            else:
                # onewire device doesn't exist
                sensor_path = sensor["path"]
                raise ValueError(f'Onewire device "{sensor_path}" doesn\'t exist')

        except Exception:
            sensor_path = sensor["path"]
            self.logger.exception(
                f'Unable to read 1wire device file "{sensor_path}":'
            )

        return (temp_c, temp_f)

    def _task(self, sensor):
        """
        Onewire sensor task

        Args:
            sensor (dict): sensor data
        """
        # read values
        (temp_c, temp_f) = self._read_onewire_temperature(sensor)

        # update sensor
        sensor["celsius"] = temp_c
        sensor["fahrenheit"] = temp_f
        sensor["lastupdate"] = int(time.time())
        if not self.update_value(sensor):
            self.logger.error("Unable to update onewire device %s", sensor["uuid"])

        # and send event
        params = {
            "sensor": sensor["name"],
            "celsius": temp_c,
            "fahrenheit": temp_f,
            "lastupdate": int(time.time()),
        }
        self.sensors_temperature_update.send(params=params, device_id=sensor["uuid"])

    def _get_task(self, sensor):
        """
        Return sensor task

        Args:
            sensor (dict): sensor data
        """
        return self.task_factory.create_task(
            float(sensor["interval"]),
            self._task,
            [sensor]
        )

