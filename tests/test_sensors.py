import unittest
import logging
import context
import sys, os
sys.path.append('../')
#sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
from backend.sensors import Sensors
from raspiot.utils import InvalidParameter, CommandError

DEBUG = False
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO, format=u'%(asctime)s %(name)s %(levelname)s : %(message)s')

class SensorsTests(unittest.TestCase):

    def setUp(self):
        self.context = context.Context()
        self.context.add_command_handler('get_raspi_gpios', self.__get_raspi_gpios)
        self.module = self.context.setup_module(Sensors, DEBUG)

    def tearDown(self):
        self.context.clean(self.module)

    def test_get_module_config(self):
        config = self.module.get_module_config()
        self.assertIsNotNone(config)
        self.assertTrue('raspi_gpios' in config)
        self.assertTrue('drivers' in config)

    def __reserve_gpio(self):
        return {
            'error': False,
            'data': {
                'uuid': '123-456-789-123',
                'pin': 666
            }
        }

    def __read_onewire_temperature(self, sensor):
        return {
            'celsius': 666,
            'farenheit': 999
        }

    def __is_reserved_gpio(self):
        return {
            'error': False,
            'data': True
        }

    def __get_raspi_gpios(self):
        return {
            'error': False,
            'data': {'GPIO18': 56}
        }

    def __delete_gpio(self):
        return {
            'error': False,
            'data': True
        }

    def __get_assigned_gpios(self):
        return {
            'error': False,
            'data': []
        }

    """
    Create sensor
    """
    def test_create_temperature_onewire(self):
        self.context.add_command_handler('reserve_gpio', self.__reserve_gpio)
        self.module._read_onewire_temperature = self.__read_onewire_temperature

        sensor = self.module.add_temperature_onewire('name', 'onewire_device', 'onewire_path', 30, 0, 'celsius')

    def test_create_temperature_onewire(self):
        self.module._read_onewire_temperature = self.__read_onewire_temperature

        sensor = self.module.add_motion_generic('name', 'GPIO18', True)

    """
    Delete sensor
    """
    def test_delete_sensor_with_unknown_uuid(self):
        self.assertRaises(InvalidParameter, self.module.delete_sensor, '123456789')

    def test_delete_sensor_with_existing_uuid(self):
        self.context.add_command_handler('reserve_gpio', self.__reserve_gpio)
        self.context.add_command_handler('is_reserved_gpio', self.__is_reserved_gpio)
        self.context.add_command_handler('delete_gpio', self.__delete_gpio)
        self.module._read_onewire_temperature = self.__read_onewire_temperature

        sensor = self.module.add_temperature_onewire('name', 'onewire_device', 'onewire_path', 30, 0, 'celsius')
        self.assertTrue(self.module.delete_sensor(sensor['uuid']))

