#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import glob
import time
from cleep.exception import MissingParameter, InvalidParameter, CommandError
from cleep.libs.internals.task import Task
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
        # check values
        if name is None or len(name) == 0:
            raise MissingParameter('Parameter "name" is missing')
        if self._search_device("name", name) is not None:
            raise InvalidParameter('Name "%s" is already used' % name)
        if device is None or len(device) == 0:
            raise MissingParameter('Parameter "device" is missing')
        if path is None or len(path) == 0:
            raise MissingParameter('Parameter "path" is missing')
        if interval is None:
            raise MissingParameter('Parameter "interval" is missing')
        if interval < 60:
            raise InvalidParameter("Interval must be greater or equal than 60")
        if offset is None:
            raise MissingParameter('Parameter "offset" is missing')
        if offset_unit is None or len(offset_unit) == 0:
            raise MissingParameter('Parameter "offset_unit" is missing')
        if not isinstance(offset_unit, str) or offset_unit not in (
            SensorsUtils.TEMP_CELSIUS,
            SensorsUtils.TEMP_FAHRENHEIT,
        ):
            raise InvalidParameter(
                'Offset_unit must be equal to "celsius" or "fahrenheit"'
            )

        # get 1wire gpio
        gpio_device = self.sensors.send_command(
            "get_reserved_gpio", "gpios", {"usage": self.USAGE_ONEWIRE}
        )
        self.logger.debug("gpio_device=%s" % gpio_device)

        # prepare sensor
        sensor = {
            "name": name,
            "gpios": [
                {
                    "gpio": gpio_device["gpio"],
                    "uuid": gpio_device["uuid"],
                    "pin": gpio_device["pin"],
                }
            ],
            "device": device,
            "path": path,
            "type": self.TYPE_TEMPERATURE,
            "subtype": self.SUBTYPE,
            "interval": interval,
            "offset": offset,
            "offsetunit": offset_unit,
            "lastupdate": int(time.time()),
            "celsius": None,
            "fahrenheit": None,
        }

        # read temperature
        (temp_c, temp_f) = self._read_onewire_temperature(sensor)
        sensor["celsius"] = temp_c
        sensor["fahrenheit"] = temp_f

        return {
            "gpios": [],
            "sensors": [
                sensor,
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
        if sensor is None:
            raise InvalidParameter("Sensor wasn't specified")
        if (
            "uuid" not in sensor or self._search_device("uuid", sensor["uuid"]) is None
        ):
            raise InvalidParameter('Sensor "%s" does not exist' % sensor["uuid"])
        if name is None or len(name) == 0:
            raise MissingParameter('Parameter "name" is missing')
        if name != sensor["name"] and self._search_device("name", name) is not None:
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

        # update sensor
        sensor["name"] = name
        sensor["interval"] = interval
        sensor["offset"] = offset
        sensor["offsetunit"] = offset_unit

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
        self.logger.debug("Onewire devices: %s" % devices)
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
            event (MessageRequest): gpio event
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
            self.logger.debug("Reserve gpio result: %s" % resp)

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
            self.logger.debug("Get_reserved_gpios response: %s" % resp)
            if not resp.error and resp.data and len(resp.data) > 0:
                sensor = resp.data[0]
                resp = self.sensors.send_command(
                    "delete_gpio", "gpios", {"uuid": sensor["uuid"]}
                )
                self.logger.debug("Delete gpio result: %s" % resp)

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
                        raise Exception('Invalid temperature "%s"' % temp_str)

                    # convert temperatures
                    temp_c = float(temp_str) / 1000.0
                    (temp_c, temp_f) = SensorsUtils.convert_temperatures_from_celsius(
                        temp_c, sensor["offset"], sensor["offsetunit"]
                    )

                else:
                    # no temperature found in file
                    raise Exception(
                        'No temperature found for onewire "%s"' % sensor["path"]
                    )

            else:
                # onewire device doesn't exist
                raise Exception('Onewire device "%s" doesn\'t exist' % sensor["path"])

        except Exception:
            self.logger.exception(
                'Unable to read 1wire device file "%s":' % sensor["path"]
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
            self.logger.error("Unable to update onewire device %s" % sensor["uuid"])

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
        return Task(float(sensor["interval"]), self._task, self.logger, [sensor])
