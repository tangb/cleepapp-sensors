#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from cleep.exception import MissingParameter, InvalidParameter
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

    def add(self, name, gpio, inverted):
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
        if not gpio:
            raise MissingParameter('Parameter "gpio" is missing')
        if inverted is None:
            raise MissingParameter('Parameter "inverted" is missing')
        if gpio in assigned_gpios:
            raise InvalidParameter('Gpio "%s" is already used' % gpio)
        if gpio not in self.raspi_gpios:
            raise InvalidParameter(
                'Gpio "%s" does not exist for this raspberry pi' % gpio
            )

        # configure gpio
        gpio = {
            "name": name + "_motion",
            "gpio": gpio,
            "mode": "input",
            "keep": False,
            "inverted": inverted,
        }

        sensor = {
            "name": name,
            "gpios": [],
            "type": self.TYPE_MOTION,
            "subtype": self.SUBTYPE,
            "on": False,
            "inverted": inverted,
            "lastupdate": 0,
            "lastduration": 0,
        }

        # read current gpio value
        resp = self.send_command("is_gpio_on", "gpios", {"gpio": gpio})
        if not resp["error"]:
            sensor["on"] = resp["data"]
        sensor["lastupdate"] = int(time.time())

        return {
            "gpios": [
                gpio,
            ],
            "sensors": [
                sensor,
            ],
        }

    def update(self, sensor, name, inverted):
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
            raise MissingParameter('Parameter "sensor" is missing')
        if name is None or len(name) == 0:
            raise MissingParameter('Parameter "name" is missing')
        if name != sensor["name"] and self._search_device("name", name) is not None:
            raise InvalidParameter('Name "%s" is already used' % name)
        if inverted is None:
            raise MissingParameter('Parameter "inverted" is missing')
        if self._search_device("uuid", sensor["uuid"]) is None:
            raise InvalidParameter('Sensor "%s" does not exist' % sensor["uuid"])

        gpio = {
            "uuid": sensor["gpios"][0]["uuid"],
            "name": name + "_motion",
            "keep": False,
            "inverted": inverted,
        }

        # update sensor
        sensor["name"] = name
        sensor["inverted"] = inverted

        return {
            "gpios": [
                gpio,
            ],
            "sensors": [
                sensor,
            ],
        }

    def process_event(self, event, sensor):
        """
        Process received event

        Args:
            event (MessageRequest): gpio event
            sensor (dict): sensor data
        """
        # get current time
        now = int(time.time())

        if event["event"] == "gpios.gpio.on" and not sensor["on"]:
            # sensor not yet triggered, trigger it
            self.logger.debug('Motion sensor "%s" turned on' % sensor["name"])

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
            self.logger.debug('Motion sensor "%s" turned off' % sensor["name"])

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

