#!/usr/bin/env python
# -*- coding: utf-8 -*-


class SensorsUtils:
    """
    Sensors utils
    """

    TEMP_CELSIUS = "celsius"
    TEMP_FAHRENHEIT = "fahrenheit"

    @staticmethod
    def convert_temperatures_from_celsius(celsius, offset, offset_unit):
        """
        Convert temperatures from celsius

        Args:
            celsius (float): celsius temperature (without offset)
            offset (float): temperature offset
            offset_unit (string): temperature offset unit

        Returns:
            tuple: celsius and fahrenheit temperatures::

                (float: celsius, float: fahrenheit)

        """
        tempC = None
        tempF = None
        if offset is not None and offset != 0:
            if offset_unit == SensorsUtils.TEMP_CELSIUS:
                # apply offset on celsius value
                tempC = celsius + offset
                tempF = (tempC * 9 / 5) + 32
            else:
                # apply offset on computed fahrenheit value
                tempF = (celsius * 9 / 5) + 32 + offset
                tempC = (tempF - 32) * 5 / 9
        else:
            # no offset
            tempC = celsius
            tempF = (celsius * 9 / 5) + 32

        return (round(tempC, 2), round(tempF, 2))

    @staticmethod
    def convert_temperatures_from_fahrenheit(fahrenheit, offset, offset_unit):
        """
        Convert temperatures from fahrenheit

        Note:
            This function is protected because it is not use yet and we want to execute unit test on it
            It won't stay protected as soon as function is used.

        Args:
            fahrenheit (float): fahrenheit temperature (without offset)
            offset (float): temperature offset
            offset_unit (string): temperature offset unit

        Returns:

            tuple: celsius and fahrenheit temperatures::

                (float: celsius, float: fahrenheit)

        """
        tempC = None
        tempF = None
        if offset is not None and offset != 0:
            if offset_unit == SensorsUtils.TEMP_CELSIUS:
                # apply offset on celsius value
                tempC = (fahrenheit - 32) * 5 / 9 + offset
                tempF = (tempC * 9 / 5) + 32
            else:
                # apply offset on computed fahrenheit value
                tempF = fahrenheit + offset
                tempC = (tempF - 32) * 5 / 9
        else:
            # no offset
            tempF = fahrenheit
            tempC = (tempF - 32) * 5 / 9

        return (round(tempC, 2), round(tempF, 2))
