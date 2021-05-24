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
        temp_c = None
        temp_f = None
        if offset is not None and offset != 0:
            if offset_unit == SensorsUtils.TEMP_CELSIUS:
                # apply offset on celsius value
                temp_c = celsius + offset
                temp_f = (temp_c * 9 / 5) + 32
            else:
                # apply offset on computed fahrenheit value
                temp_f = (celsius * 9 / 5) + 32 + offset
                temp_c = (temp_f - 32) * 5 / 9
        else:
            # no offset
            temp_c = celsius
            temp_f = (celsius * 9 / 5) + 32

        return (round(temp_c, 2), round(temp_f, 2))

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
        temp_c = None
        temp_f = None
        if offset is not None and offset != 0:
            if offset_unit == SensorsUtils.TEMP_CELSIUS:
                # apply offset on celsius value
                temp_c = (fahrenheit - 32) * 5 / 9 + offset
                temp_f = (temp_c * 9 / 5) + 32
            else:
                # apply offset on computed fahrenheit value
                temp_f = fahrenheit + offset
                temp_c = (temp_f - 32) * 5 / 9
        else:
            # no offset
            temp_f = fahrenheit
            temp_c = (temp_f - 32) * 5 / 9

        return (round(temp_c, 2), round(temp_f, 2))

