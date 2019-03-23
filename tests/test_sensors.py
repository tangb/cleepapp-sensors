import unittest
import logging
import time
import sys, os
sys.path.append('../')
from backend.sensors import Sensors
from raspiot.utils import InvalidParameter, CommandError
from raspiot.libs.tests import moduleContext

DEBUG = False
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO, format=u'%(name)-12s[%(filename)s:%(lineno)d] %(levelname)-5s : %(message)s')

class SensorsTests(unittest.TestCase):

    def setUp(self):
        self.context = moduleContext.ModuleContext(DEBUG)
        self.context.add_command_handler('get_raspi_gpios', self.__get_raspi_gpios)
        self.context.add_command_handler('get_assigned_gpios', self.__get_assigned_gpios)
        self.module = self.context.setup_module(Sensors, DEBUG)

    def tearDown(self):
        if self.module:
            self.module.stop()
        self.context.clean(self.module)

    """
    Core
    """
    def test_sensor_init_ok(self):
        self.assertIsNotNone(self.module.sensors_motion_on)
        self.assertIsNotNone(self.module.sensors_motion_off)
        self.assertIsNotNone(self.module.sensors_temperature_update)
        self.assertIsNotNone(self.module.sensors_humidity_update)

    def test_get_module_config(self):
        config = self.module.get_module_config()
        self.assertIsNotNone(config, 'Invalid config')
        self.assertTrue('raspi_gpios' in config, '"raspi_config" key doesn\'t exist in config')
        self.assertTrue('drivers' in config, '"drivers" key doesn\'t exist in config')
        self.assertEqual(self.context.get_event_send_calls('sensors.motion.on'), 1, '"sensors.motion.on" wasn\'t called once')

    def test_get_module_devices(self):
        self.context.add_command_handler('add_gpio', self.__add_gpio)

        sensor = self.module.add_motion_generic('name', 'GPIO18', True)
        devices = self.module.get_module_devices()
        self.assertIsNotNone(devices, 'get_module_devices returns None')
        self.assertEqual(len(devices), 1, 'get_module_devices should return single sensor')

    """
    Event
    """
    def test_receive_startup_event(self):
        event = {
            'startup': True,
            'event': 'system.startup.fake'
        }
        self.assertIsNone(self.module.event_received(event))

    def test_receive_gpio_event(self):
        event = {
            'event': 'gpios.gpio.on',
            'startup': False,
            'params': {
                'init': True
            }
        }
        self.assertIsNone(self.module.event_received(event))

        event = {
            'event': 'gpios.gpio.off',
            'startup': False,
            'params': {
                'init': True
            }
        }
        self.assertIsNone(self.module.event_received(event))

    def test_receive_gpio_event_of_unknown_device(self):
        event = {
            'event': 'gpios.gpio.off',
            'startup': False,
            'device_id': '123-456-789-123',
            'params': {
                'init': False
            }
        }
        self.assertIsNone(self.module.event_received(event))

    def test_receive_gpio_event_of_unknown_device(self):
        event = {
            'event': 'gpios.gpio.off',
            'startup': False,
            'device_id': '123-456-789-123',
            'params': {
                'init': False
            }
        }
        self.assertIsNone(self.module.event_received(event))

    def test_receive_gpio_event_of_motion_sensor(self):
        self.context.add_command_handler('add_gpio', self.__add_gpio)

        #add motion sensor
        sensor = self.module.add_motion_generic('name', 'GPIO18', True)

        #receive gpio event
        event = {
            'event': 'gpios.gpio.on',
            'startup': False,
            'device_id': sensor['gpios'][0]['gpio_uuid'],
            'params': {
                'init': False
            }
        }
        self.assertIsNone(self.module.event_received(event))
        
        #check if motion event triggered
        self.assertEqual(self.context.get_event_send_calls('sensors.motion.on'), 1, '"sensors.motion.on" wasn\'t triggered')
        self.assertEqual(self.context.get_event_send_calls('sensors.motion.off'), 0, '"sensors.motion.off" was triggered')

    """
    Create sensor
    """
    def test_add_temperature_onewire(self):
        self.context.add_command_handler('reserve_gpio', self.__reserve_gpio)
        self.context.add_command_handler('add_gpio', self.__add_gpio)
        self.module._read_onewire_temperature = self.__read_onewire_temperature

        sensor = self.module.add_temperature_onewire('name', 'onewire_device', 'onewire_path', 30, 0, 'celsius')
        self.assertIsNotNone(sensor)
        self.assertTrue(type(sensor) is dict, 'add_temperature_onewire has invalid output result')
        self.assertTrue('uuid' in sensor)
        self.assertEqual(sensor['name'], 'name', 'saved device has incorrect name')

    def test_add_motion_generic(self):
        self.context.add_command_handler('add_gpio', self.__add_gpio)

        sensor = self.module.add_motion_generic('name', 'GPIO18', True)
        self.assertIsNotNone(sensor)
        self.assertTrue(type(sensor) is dict)
        self.assertTrue(type(sensor) is dict, 'add_motion_generic has invalid output result')
        self.assertTrue('uuid' in sensor)
        self.assertEqual(sensor['name'], 'name', 'saved device has incorrect name')

    def test_add_dht22(self):
        self.context.add_command_handler('add_gpio', self.__add_gpio)

        sensors = self.module.add_dht22('name', 'GPIO18', 30, 0, 'celsius')
        self.assertIsNotNone(sensors)
        self.assertTrue(type(sensors) is tuple, 'add_dht22 has invalid output result')
        self.assertEqual(len(sensors), 2, 'add_dht22 does not return 2 sensors')
        self.assertTrue('uuid' in sensors[0])
        self.assertEqual(sensors[0]['name'], 'name', 'saved device has incorrect name')

    def test_stop_task(self):
        self.context.add_command_handler('add_gpio', self.__add_gpio)

        sensor = self.module.add_motion_generic('name', 'GPIO18', True)
        self.module._stop()

    """
    Update sensor
    """
    def test_update_motion_generic(self):
        self.context.add_command_handler('add_gpio', self.__add_gpio)
        self.context.add_command_handler('update_gpio', self.__update_gpio)

        sensor = self.module.add_motion_generic('name', 'GPIO18', True)
        updated = self.module.update_motion_generic(sensor['uuid'], 'newname', False)
        self.assertIsNotNone(updated)
        self.assertEqual(updated['name'], 'newname', 'updated motion sensor has invalid new name')

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

    def test_delete_multi_sensor(self):
        self.context.add_command_handler('reserve_gpio', self.__reserve_gpio)
        self.context.add_command_handler('is_reserved_gpio', self.__is_reserved_gpio)
        self.context.add_command_handler('delete_gpio', self.__delete_gpio)
        self.context.add_command_handler('add_gpio', self.__add_gpio)
        self.module._read_onewire_temperature = self.__read_onewire_temperature

        (temp, hum) = self.module.add_dht22('dht', 'GPIO18', 30, 0, 'celsius')
        self.assertTrue(self.module.delete_sensor(temp['uuid']))
        self.assertTrue(self.module.delete_sensor(hum['uuid']))

    """
    Onewire
    """
    def test_is_onewire_driver_installed(self):
        res = self.module.is_onewire_driver_installed()
        self.assertTrue(type(res) is bool, 'result of is_onewire_driver_installed must be bool')

    def test_uninstall_onewire(self):
        res = self.module.uninstall_onewire_driver()
        self.assertTrue(res, 'Unable to uninstall onewire driver')
        self.assertFalse(self.module.is_onewire_driver_installed(), 'onewire driver is not installed while it doesn\'t')

    def test_install_onewire_driver(self):
        res = self.module.install_onewire_driver()
        self.assertTrue(res)
        self.assertTrue(self.module.is_onewire_driver_installed(), 'onewire driver is not installed while it does')

    """
    Mocks
    """
    def __reserve_gpio(self):
        return {
            'error': False,
            'data': {
                'uuid': '123-456-789-123',
                'pin': 666,
            }
        }

    def __add_gpio(self):
        return {
            'error': False,
            'data': {
                'uuid': '123-456-789-123',
                'pin': 666
            }
        }

    def __update_gpio(self):
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

if __name__ == '__main__':
    unittest.main()

