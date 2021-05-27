#!/usr/bin/env python
# -*- coding: utf-8 -*-

from cleep.libs.drivers.driver import Driver
from cleep.libs.configs.configtxt import ConfigTxt
from cleep.libs.configs.etcmodules import EtcModules


class OnewireDriver(Driver):
    """
    Onewire driver
    """

    DRIVER_NAME = "onewire"
    MODULE_ONEWIRETHERM = "w1-therm"  # deprecated ?
    MODULE_ONEWIREGPIO = "w1-gpio"

    def __init__(self):
        """
        Constructor
        """
        Driver.__init__(self, Driver.DRIVER_ELECTRONIC, OnewireDriver.DRIVER_NAME)
        self.configtxt = None
        self.etcmodules = None

    def _on_registered(self):
        """
        Driver registered
        """
        self.configtxt = ConfigTxt(self.cleep_filesystem)
        self.etcmodules = EtcModules(self.cleep_filesystem)

    def _install(self, params=None):
        """
        Install driver

        Args:
            params (any): extra parameters (optionnal)
        """
        if (
            not self.etcmodules.enable_module(self.MODULE_ONEWIREGPIO)
            or not self.configtxt.enable_onewire()
        ):
            raise Exception("Unable to install onewire driver")

        return True

    def _uninstall(self, params=None):
        """
        Uninstall driver

        Args:
            params (any): extra parameters (optionnal)
        """
        if (
            not self.etcmodules.disable_module(self.MODULE_ONEWIREGPIO)
            or not self.configtxt.disable_onewire()
        ):
            raise Exception("Unable to uninstall onewire driver")

        return True

    def is_installed(self):
        """
        Is driver installed ?

        Returns:
            bool: True if driver installed
        """
        return self.etcmodules.is_module_enabled(self.MODULE_ONEWIREGPIO) and self.configtxt.is_onewire_enabled()

    def require_reboot(self):
        """
        Require reboot after driver install/uninstall

        Returns:
            True if reboot is required
        """
        return True

