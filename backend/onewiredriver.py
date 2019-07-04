#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
from raspiot.libs.drivers.driver import Driver
from raspiot.libs.configs.configtxt import ConfigTxt
from raspiot.libs.configs.etcmodules import EtcModules

class OnewireDriver(Driver):
    """
    Onewire driver
    """

    MODULE_ONEWIRETHERM = u'w1-therm' #deprecated ?
    MODULE_ONEWIREGPIO = u'w1-gpio'

    def __init__(self, cleep_filesystem):
        """
        Constructor

        Args:
            cleep_filesystem (CleepFilesystem): Cleep filesystem instance
        """
        Driver.__init__(self, cleep_filesystem, Driver.DRIVER_GPIO, u'Onewire')

        self.configtxt = ConfigTxt(self.cleep_filesystem)
        self.etcmodules = EtcModules(self.cleep_filesystem)

    def _install(self, params=None):
        """
        Install driver

        Args:
            params (any): extra parameters (optionnal)
        """
        if not self.etcmodules.enable_module(self.MODULE_ONEWIREGPIO) or not self.configtxt.enable_onewire():
            raise Exception(u'Unable to install onewire system module')

        return True

    def _uninstall(self, params=None):
        """
        Uninstall driver

        Args:
            params (any): extra parameters (optionnal)
        """
        if not self.etcmodules.disable_module(self.MODULE_ONEWIREGPIO) or not self.configtxt.disable_onewire():
            raise Exception(u'Unable to uninstall onewire system module')

        return True

    def is_installed(self):
        """
        Is driver installed ?

        Returns:
            bool: True if driver installed
        """
        return True if self.etcmodules.is_module_enabled(self.MODULE_ONEWIREGPIO) and self.configtxt.is_onewire_enabled() else False

