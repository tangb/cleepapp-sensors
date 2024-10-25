#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from cleep.exception import InvalidParameter
from .sensor import Sensor

class SensorMotionGeneric(Sensor):
    """
    Sensor motion addon
    """

    TYPE_MOTION = "motion"
    TYPES = [TYPE_MOTION]
    SUBTYPE = "generic"

    def __init__(self, sensors):
        """
        Constructor

        Args:
            sensors (Sensors): Sensors instance
        """
        Sensor.__init__(self, sensors)

        # events
        self.sensors_motion_on = self._get_event("sensors.motion.on")
        self.sensors_motion_off = self._get_event("sensors.motion.off")

    def add(self, params):
        """
        Return sensor data to add.
        Can perform specific stuff

        Args:
            params (dict): add params::

                {
                    name (str): sensor name
                    gpio (str): used gpio
                    inverted (bool): True if gpio is inverted
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

        # check values
        self._check_parameters([
            {
                'name': 'name',
                'value': params.get("name"),
                'type': str,
                'validator': lambda val: self._search_device("name", params.get("name")) is None,
                'message': f'Name "{params.get("name")}" is already used',
            },
            {
                'name': 'gpio',
                'value': params.get("gpio"),
                'type': str,
                'validator': lambda val: params.get("gpio") not in assigned_gpios,
                'message': f'Gpio "{params.get("gpio")}" is already used',
            },
            {'name': 'inverted', 'value': params.get("inverted"), 'type': bool},
        ])
        # TODO add new validator directly in Cleep core
        self.logger.debug('Gpios: %s', self.raspi_gpios)
        if params.get("gpio") not in self.raspi_gpios:
            raise InvalidParameter(f'Gpio "{params.get("gpio")}" does not exist for this raspberry pi')

        # configure gpio
        gpio_data = {
            "name": params.get("name") + "_motion",
            "gpio": params.get("gpio"),
            "mode": "input",
            "keep": False,
            "inverted": params.get("inverted"),
        }

        sensor_data = {
            "name": params.get("name"),
            "gpios": [],
            "type": self.TYPE_MOTION,
            "subtype": self.SUBTYPE,
            "on": False,
            "inverted": params.get("inverted"),
            "lastupdate": 0,
            "lastduration": 0,
        }

        # read current gpio value
        resp = self.send_command("is_gpio_on", "gpios", {"gpio": params.get("gpio")})
        if not resp.error:
            sensor_data["on"] = resp.data
        sensor_data["lastupdate"] = int(time.time())

        return {
            "gpios": [
                gpio_data,
            ],
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
                    name (str): sensor name
                    inverted (bool): True if gpio is inverted
                }

        Returns:
            dict: sensor data to update::

                {
                    gpios (list): list of gpios data to update
                    sensors (list): list sensors data to update
                }

        """
        # check values
        self._check_parameters([
            {
                'name': 'sensor',
                'value': sensor,
                'type': dict,
                'validator': lambda val: self._search_device("uuid", val["uuid"]) is not None,
                'message': 'Sensor does not exist',
            },
            {
                'name': 'name',
                'value': params.get("name"),
                'type': str,
                'validator': lambda val: val == sensor['name'] or self._search_device("name", params.get("name")) is None,
                'message': f'Name "{params.get("name")}" is already used',
            },
            {'name': 'inverted', 'value': params.get("inverted"), 'type': bool},
        ])

        gpio_data = {
            "uuid": sensor["gpios"][0]["uuid"],
            "name": params.get("name") + "_motion",
            "keep": False,
            "inverted": params.get("inverted"),
        }

        # update sensor
        sensor["name"] = params.get("name")
        sensor["inverted"] = params.get("inverted")

        return {
            "gpios": [
                gpio_data,
            ],
            "sensors": [
                sensor,
            ],
        }

    def process_event(self, event, sensor):
        """
        Process received event

        Args:
            event (MessageRequest): event
            sensor (dict): sensor data
        """
        # get current time
        now = int(time.time())

        if event["event"] == "gpios.gpio.on" and not sensor["on"]:
            # sensor not yet triggered, trigger it
            self.logger.debug('Motion sensor "%s" turned on', sensor["name"])

            # motion sensor triggered
            sensor["lastupdate"] = now
            sensor["on"] = True
            self.update_value(sensor)

            # new motion event
            self.sensors_motion_on.send(
                params={"sensor": sensor["name"], "lastupdate": now},
                device_id=sensor["uuid"],
            )

        elif event["event"] == "gpios.gpio.off" and sensor["on"]:
            # sensor is triggered, need to stop it
            self.logger.debug('Motion sensor "%s" turned off', sensor["name"])

            # motion sensor triggered
            sensor["lastupdate"] = now
            sensor["on"] = False
            sensor["lastduration"] = event["params"]["duration"]
            self.update_value(sensor)

            # new motion event
            self.sensors_motion_off.send(
                params={
                    "sensor": sensor["name"],
                    "duration": sensor["lastduration"],
                    "lastupdate": now,
                },
                device_id=sensor["uuid"],
            )

    def _get_task(self, sensor):
        """
        Return sensor task
        """
        return None

