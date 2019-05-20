import unittest
import logging
import time
import sys, os
import shutil
sys.path.append('../')
from backend.sensors import Sensors
from raspiot.utils import InvalidParameter, MissingParameter, CommandError
from raspiot.libs.tests import session

class SensorsTests(unittest.TestCase):

    ONEWIRE_PATH = '/tmp/onewire'

    def setUp(self):
        self.session = session.Session(logging.ERROR)
        self.session.add_command_handler('get_raspi_gpios', self.__get_raspi_gpios)
        self.session.add_command_handler('get_assigned_gpios', self.__get_assigned_gpios)
        self.module = self.session.setup(Sensors, False)

        if os.path.exists(self.ONEWIRE_PATH):
            shutil.rmtree(self.ONEWIRE_PATH)

    def tearDown(self):
        self.module.uninstall_onewire_driver()
        if os.path.exists(self.ONEWIRE_PATH):
            shutil.rmtree(self.ONEWIRE_PATH)
        self.session.clean()

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
        self.assertEqual(self.session.get_event_send_calls('sensors.motion.on'), 1, '"sensors.motion.on" wasn\'t called once')

    def test_get_module_devices(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)

        sensor = self.module.add_motion_generic('name', 'GPIO18', True)
        devices = self.module.get_module_devices()
        self.assertIsNotNone(devices, 'get_module_devices returns None')
        self.assertEqual(len(devices), 1, 'get_module_devices should return single sensor')

    def test_get_raspiot_gpios_with_error(self):
        self.session.disable_command_handler('get_raspi_gpios')

        res = self.module.get_raspi_gpios()
        self.assertTrue(type(res) is dict, 'Invalid type of get_raspi_gpios. Must be dict')
        self.assertEqual(len(res), 0, 'get_raspi_gpios must return empty dict when error')

    def test_get_assigned_gpios_with_error(self):
        self.session.disable_command_handler('get_assigned_gpios')

        res = self.module.get_assigned_gpios()
        self.assertTrue(type(res) is dict, 'Invalid type of get_assigned_gpios. Must be dict')
        self.assertEqual(len(res), 0, 'get_assigned_gpios must return empty dict when error')

    def test_start_task_with_dht22_removing_temperature(self):
        self.session.add_command_handler('get_reserved_gpio', self.__get_reserved_gpio)
        self.session.add_command_handler('is_reserved_gpio', self.__is_reserved_gpio_false)
        self.session.add_command_handler('delete_gpio', self.__delete_gpio)
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)

        #add dht22 multi sensor
        (temp, hum) = self.module.add_dht22('dht', 'GPIO18', 60, 0, 'celsius')
        #only one task must run for multi sensors like DHT22
        self.assertEqual(len(self.module._tasks), 1, 'Invalid number of tasks running')
        #delete one of 2 sensors (temperature one)
        self.assertTrue(self.module.delete_sensor(temp['uuid']))
        #only one task must run event if one of 2 devices deleted
        self.assertEqual(len(self.module._tasks), 1, 'Invalid number of tasks running')
        #restart module to check if only one sensor task is properly launched
        self.module = self.session.respawn_module()
        #check if one task still running while only one sensor exists for multi sensor device
        self.assertEqual(len(self.module._tasks), 1, 'Invalid number of tasks running')

    def test_start_task_with_dht22_removing_humidity(self):
        self.session.add_command_handler('is_reserved_gpio', self.__is_reserved_gpio_false)
        self.session.add_command_handler('delete_gpio', self.__delete_gpio)
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)

        #add dht22 multi sensor
        (temp, hum) = self.module.add_dht22('dht', 'GPIO18', 60, 0, 'celsius')
        #only one task must run for multi sensors like DHT22
        self.assertEqual(len(self.module._tasks), 1, 'Invalid number of tasks running')
        #delete one of 2 sensors (humidity one)
        self.assertTrue(self.module.delete_sensor(hum['uuid']))
        #only one task must run event if one of 2 devices deleted
        self.assertEqual(len(self.module._tasks), 1, 'Invalid number of tasks running')
        #restart module to check if only one sensor task is properly launched
        self.module = self.session.respawn_module()
        #check if one task still running while only one sensor exists for multi sensor device
        self.assertEqual(len(self.module._tasks), 1, 'Invalid number of tasks running')

    def test_no_task_for_motion_sensor(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)

        sensor = self.module.add_motion_generic('name', 'GPIO18', True)
        self.assertEqual(len(self.module._tasks), 0, 'Invalid number of tasks running. It must be 0')

        #make sure task is not launched during module startup
        self.session.respawn_module()
        self.assertEqual(len(self.module._tasks), 0, 'Invalid number of tasks running. It must be 0')

    def test_task_stopped_when_all_sensors_of_multi_sensors_deleted(self):
        self.session.add_command_handler('is_reserved_gpio', self.__is_reserved_gpio_false)
        self.session.add_command_handler('delete_gpio', self.__delete_gpio)
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)

        #add dht22 multi sensor
        (temp, hum) = self.module.add_dht22('dht', 'GPIO18', 60, 0, 'celsius')
        self.assertEqual(len(self.module._tasks), 1, 'Invalid number of tasks running')
        self.assertTrue(self.module.delete_sensor(hum['uuid']))
        self.assertEqual(len(self.module._tasks), 1, 'Invalid number of tasks running')
        self.assertTrue(self.module.delete_sensor(temp['uuid']))
        self.assertEqual(len(self.module._tasks), 0, 'Invalid number of tasks running')

        self.module = self.session.respawn_module()
        self.assertEqual(len(self.module._tasks), 0, 'Invalid number of tasks running')


    """
    Event
    """
    def test_receive_startup_event(self):
        event = {
            'startup': True,
            'event': 'system.startup.fake'
        }
        self.assertIsNone(self.module.event_received(event))

    def test_receive_init_gpio_event(self):
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

    def test_receive_gpio_event_on_and_off(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        sensor = self.module.add_motion_generic('name', 'GPIO18', False)
        self.assertFalse(sensor['on'], 'Device status should be off')

        event = {
            'event': 'gpios.gpio.on',
            'startup': False,
            'device_id': sensor['gpios'][0]['gpio_uuid'],
            'params': {
                'init': False
            }
        }
        self.assertIsNone(self.module.event_received(event))
        sensor = self.module._get_device(sensor['uuid'])
        self.assertTrue(sensor['on'], 'Device status should be on')

        event = {
            'event': 'gpios.gpio.off',
            'startup': False,
            'device_id': sensor['gpios'][0]['gpio_uuid'],
            'params': {
                'init': False,
                'duration': 6
            }
        }
        self.assertIsNone(self.module.event_received(event))
        sensor = self.module._get_device(sensor['uuid'])
        self.assertFalse(sensor['on'], 'Device status should be off')
        self.assertEqual(self.session.get_event_send_calls('sensors.motion.on'), 1, '"sensors.motion.on" wasn\'t triggered')
        self.assertEqual(self.session.get_event_send_calls('sensors.motion.off'), 1, '"sensors.motion.off" wasn\'t triggered')

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
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)

        #add motion sensor
        sensor = self.module.add_motion_generic('name', 'GPIO18', False)

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
        self.assertEqual(self.session.get_event_send_calls('sensors.motion.on'), 1, '"sensors.motion.on" wasn\'t triggered')
        self.assertEqual(self.session.get_event_send_calls('sensors.motion.off'), 0, '"sensors.motion.off" was triggered')

    """
    Create sensor
    """
    def test_add_temperature_onewire(self):
        self.session.add_command_handler('get_reserved_gpio', self.__get_reserved_gpio)
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.module._read_onewire_temperature = self.__read_onewire_temperature

        sensor = self.module.add_temperature_onewire('name', 'onewire_device', 'onewire_path', 60, 0, 'celsius')
        self.assertIsNotNone(sensor)
        self.assertTrue(type(sensor) is dict, 'add_temperature_onewire has invalid output result')
        self.assertTrue('uuid' in sensor)
        self.assertEqual(sensor['name'], 'name', 'saved device has incorrect name')

    def test_add_temperature_onewire_ko(self):
        self.session.add_command_handler('get_reserved_gpio', self.__get_reserved_gpio_ko)
        with self.assertRaises(CommandError) as cm:
            self.module.add_temperature_onewire('name', 'onewire_device', 'onewire_path', 60, 0, 'celsius')
        self.assertEqual(cm.exception.message, 'TEST: forced error')

        self.session.add_command_handler('get_reserved_gpio', self.__get_reserved_gpio)
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.module._add_device = self.__add_device_ko
        with self.assertRaises(CommandError) as cm:
            self.module.add_temperature_onewire('name', 'onewire_device', 'onewire_path', 60, 0, 'celsius')
        self.assertEqual(cm.exception.message, 'Unable to add onewire temperature sensor')

    def test_add_motion_generic(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)

        sensor = self.module.add_motion_generic('name', 'GPIO18', False)
        self.assertIsNotNone(sensor)
        self.assertTrue(type(sensor) is dict, 'add_motion_generic has invalid output result')
        self.assertTrue('uuid' in sensor)
        self.assertEqual(sensor['name'], 'name', 'Saved device has incorrect name')
        self.assertFalse(sensor['on'], 'Saved device has incorrect status (should be off)')

    def test_add_motion_generic_inverted(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)

        sensor = self.module.add_motion_generic('name', 'GPIO18', True)
        self.assertIsNotNone(sensor)
        self.assertTrue(type(sensor) is dict, 'add_motion_generic has invalid output result')
        self.assertTrue('uuid' in sensor)
        self.assertEqual(sensor['name'], 'name', 'Saved device has incorrect name')
        self.assertTrue(sensor['on'], 'Saved device has incorrect status (should be on)')

    def test_add_motion_generic_ko(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ko)
        with self.assertRaises(CommandError) as cm:
            self.module.add_motion_generic('name', 'GPIO18', False)
        self.assertEqual(cm.exception.message, 'TEST: forced error')

        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.module._add_device = self.__add_device_ko
        with self.assertRaises(CommandError) as cm:
            self.module.add_motion_generic('name', 'GPIO18', False)
        self.assertEqual(cm.exception.message, 'Unable to add motion sensor')

    def test_add_dht22(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)

        sensors = self.module.add_dht22('name', 'GPIO18', 60, 0, 'celsius')
        self.assertIsNotNone(sensors)
        self.assertTrue(type(sensors) is tuple, 'add_dht22 has invalid output result')
        self.assertEqual(len(sensors), 2, 'add_dht22 does not return 2 sensors')
        self.assertTrue('uuid' in sensors[0])
        self.assertEqual(sensors[0]['name'], 'name', 'saved device has incorrect name')

    def test_add_dht22_ko(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ko)
        with self.assertRaises(CommandError) as cm:
            self.module.add_dht22('name', 'GPIO18', 60, 0, 'celsius')
        self.assertEqual(cm.exception.message, 'TEST: forced error')

        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.module._add_device = self.__add_device_ko_temperature
        with self.assertRaises(CommandError) as cm:
            self.module.add_dht22('name', 'GPIO18', 60, 0, 'celsius')
        self.assertEqual(cm.exception.message, 'Unable to add DHT22 temperature sensor')

        self.module._add_device = self.__add_device_ko_humidity
        with self.assertRaises(CommandError) as cm:
            self.module.add_dht22('name', 'GPIO18', 60, 0, 'celsius')
        self.assertEqual(cm.exception.message, 'Unable to add DHT22 humidity sensor')

    def test_stop_task(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)

        sensor = self.module.add_motion_generic('name', 'GPIO18', True)
        self.module._stop()

    """
    Update sensor
    """
    def test_update_motion_generic(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.session.add_command_handler('update_gpio', self.__update_gpio)

        sensor = self.module.add_motion_generic('name', 'GPIO18', True)
        updated = self.module.update_motion_generic(sensor['uuid'], 'newname1', False)
        self.assertTrue(type(updated) is dict, 'Invalid output value')
        self.assertEqual(updated['name'], 'newname1', 'Updated sensor has invalid new name')
        self.assertEqual(updated['inverted'], False, 'Updated sensor has invalid inverted value')

    def test_update_motion_generic_ko(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.session.add_command_handler('update_gpio', self.__update_gpio)
        self.module._update_device = self.__update_device_ko

        sensor = self.module.add_motion_generic('name', 'GPIO18', True)
        with self.assertRaises(CommandError) as cm:
            self.module.update_motion_generic(sensor['uuid'], 'newname2', False)
        self.assertEqual(cm.exception.message, 'Unable to update sensor')

    def test_update_temperature_onewire(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.session.add_command_handler('update_gpio', self.__update_gpio)
        self.session.add_command_handler('get_reserved_gpio', self.__get_reserved_gpio)
        self.module._read_onewire_temperature = self.__read_onewire_temperature

        sensor = self.module.add_temperature_onewire('name', 'onewire_device', 'onewire_path', 60, 0, 'celsius')
        updated = self.module.update_temperature_onewire(sensor['uuid'], 'newname3', 60, 30, 'fahrenheit')
        self.assertTrue(type(updated) is dict, 'Invalid output value')
        self.assertEqual(updated['name'], 'newname3', 'Updated sensor has invalid new name')
        self.assertEqual(updated['interval'], 60, 'Updated sensor has invalid interval')
        self.assertEqual(updated['offset'], 30, 'Updated sensor has invalid offset')
        self.assertEqual(updated['offsetunit'], 'fahrenheit', 'Updated sensor has invalid offsetunit')

    def test_update_temperature_onewire_invalid_params(self):
        with self.assertRaises(MissingParameter) as cm:
            self.module.update_temperature_onewire(None, 'name', 60, 0, 'celsius')
        self.assertEqual(cm.exception.message, 'Uuid parameter is missing')
        with self.assertRaises(MissingParameter) as cm:
            self.module.update_temperature_onewire('', 'name', 60, 0, 'celsius')
        self.assertEqual(cm.exception.message, 'Uuid parameter is missing')
        with self.assertRaises(InvalidParameter) as cm:
            self.module.update_temperature_onewire('uuid', 'name', None, 0, 'celsius')
        self.assertEqual(cm.exception.message, 'Sensor "uuid" doesn\'t exist')

        self.session.add_command_handler('get_reserved_gpio', self.__get_reserved_gpio)
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.module._read_onewire_temperature = self.__read_onewire_temperature
        sensor = self.module.add_temperature_onewire('name', 'onewire_device', 'onewire_path', 60, 0, 'celsius')

        with self.assertRaises(MissingParameter) as cm:
            self.module.update_temperature_onewire(sensor['uuid'], 'newname', None, 0, 'celsius')
        self.assertEqual(cm.exception.message, 'Parameter "interval" is missing')
        with self.assertRaises(MissingParameter) as cm:
            self.module.update_temperature_onewire(sensor['uuid'], 'newname', 60, None, 'celsius')
        self.assertEqual(cm.exception.message, 'Parameter "offset" is missing')
        with self.assertRaises(MissingParameter) as cm:
            self.module.update_temperature_onewire(sensor['uuid'], 'newname', 60, 0, None)
        self.assertEqual(cm.exception.message, 'Parameter "offset_unit" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            self.module.update_temperature_onewire(sensor['uuid'], 'newname', 60, 0, 'dummy')
        self.assertEqual(cm.exception.message, 'Offset_unit value must be either "celsius" or "fahrenheit"')
        with self.assertRaises(InvalidParameter) as cm:
            self.module.update_temperature_onewire(sensor['uuid'], 'newname', 30, 0, 'celsius')
        self.assertEqual(cm.exception.message, 'Interval must be greater or equal than 60')

    def test_update_temperature_onewire_ko(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.session.add_command_handler('update_gpio', self.__update_gpio)
        self.session.add_command_handler('get_reserved_gpio', self.__get_reserved_gpio)
        self.module._update_device = self.__update_device_ko
        self.module._read_onewire_temperature = self.__read_onewire_temperature

        sensor = self.module.add_temperature_onewire('name', 'onewire_device', 'onewire_path', 60, 0, 'celsius')
        with self.assertRaises(CommandError) as cm:
            self.module.update_temperature_onewire(sensor['uuid'], 'newname4', 60, 30, 'fahrenheit')
        self.assertEqual(cm.exception.message, 'Unable to update sensor')

    def test_update_dht22(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.session.add_command_handler('update_gpio', self.__update_gpio)

        (temp, hum) = self.module.add_dht22('name', 'GPIO18', 60, 0, 'celsius')
        updated = self.module.update_dht22('name', 'newname5', 90, 5, 'fahrenheit')
        self.assertTrue(type(updated) is tuple, 'Invalid output value')
        self.assertEqual(len(updated), 2, 'Invalid output value')
        self.assertEqual(updated[0]['name'], 'newname5', 'Updated sensor has invalid new name')
        self.assertEqual(updated[0]['offsetunit'], 'fahrenheit', 'Updated sensor has invalid offsetunit')
        self.assertEqual(updated[0]['offset'], 5, 'Updated sensor has invalid offset')
        self.assertEqual(updated[0]['interval'], 90, 'Updated sensor has invalid interval')
        self.assertEqual(updated[1]['name'], 'newname5', 'Updated sensor has invalid new name')
        self.assertEqual(updated[1]['interval'], 90, 'Updated sensor has invalid interval')

    def test_update_dht22_with_only_humidity_sensor(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.session.add_command_handler('is_reserved_gpio', self.__is_reserved_gpio_false)
        self.session.add_command_handler('update_gpio', self.__update_gpio)

        (temp, hum) = self.module.add_dht22('name', 'GPIO18', 60, 0, 'celsius')
        self.assertTrue(self.module.delete_sensor(temp['uuid']), 'Unable to delete temperature sensor')

        updated = self.module.update_dht22('name', 'newname5', 120, 5, 'fahrenheit')
        self.assertTrue(type(updated) is tuple, 'Invalid output value')
        self.assertEqual(len(updated), 2, 'Invalid output value')
        self.assertIsNone(updated[0], 'Updated temperature sensor should be None')
        self.assertEqual(updated[1]['name'], 'newname5', 'Updated sensor has invalid new name')
        self.assertEqual(updated[1]['interval'], 120, 'Updated sensor has invalid interval')

    def test_update_dht22_with_only_temperature_sensor(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.session.add_command_handler('is_reserved_gpio', self.__is_reserved_gpio_false)
        self.session.add_command_handler('update_gpio', self.__update_gpio)

        (temp, hum) = self.module.add_dht22('name', 'GPIO18', 60, 0, 'celsius')
        self.assertTrue(self.module.delete_sensor(hum['uuid']), 'Unable to delete humidity sensor')

        updated = self.module.update_dht22('name', 'newname5', 120, 5, 'fahrenheit')
        self.assertTrue(type(updated) is tuple, 'Invalid output value')
        self.assertEqual(len(updated), 2, 'Invalid output value')
        self.assertEqual(updated[0]['name'], 'newname5', 'Update sensor has invalid new name')
        self.assertEqual(updated[0]['offsetunit'], 'fahrenheit', 'Updated sensor has invalid offsetunit')
        self.assertEqual(updated[0]['offset'], 5, 'Updated sensor has invalid offset')
        self.assertEqual(updated[0]['interval'], 120, 'Updated sensor has invalid interval')
        self.assertIsNone(updated[1], 'Updated humidity sensor should be None')

    def test_update_dht22_ko(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.session.add_command_handler('update_gpio', self.__update_gpio)

        sensor = self.module.add_dht22('name', 'GPIO18', 60, 0, 'celsius')

        #update gpio failed
        self.module._update_device = self.__update_device_ko_temperature
        self.session.disable_command_handler('update_gpio')
        with self.assertRaises(CommandError) as cm:
            self.module.update_dht22('name', 'newname8', 60, 30, 'fahrenheit')
        self.assertEqual(cm.exception.message, 'TEST: command disabled for tests')
        self.session.enable_command_handler('update_gpio')

        #update temperature failed
        self.module._update_device = self.__update_device_ko_temperature
        with self.assertRaises(CommandError) as cm:
            self.module.update_dht22('name', 'newname8', 60, 30, 'fahrenheit')
        self.assertEqual(cm.exception.message, 'Unable to update DHT22 temperature sensor')

        #update humidity failed
        self.module._update_device = self.__update_device_ko_humidity
        with self.assertRaises(CommandError) as cm:
            self.module.update_dht22('name', 'newname8', 60, 30, 'fahrenheit')
        self.assertEqual(cm.exception.message, 'Unable to update DHT22 humidity sensor')

    def test_update_dht22_invalid_params(self):
        with self.assertRaises(InvalidParameter) as cm:
            self.module.update_dht22('old_name', 'name', 60, 0, 'celsius')
        self.assertEqual(cm.exception.message, 'DHT22 sensor with name "old_name" doesn\'t exist')

        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        sensor = self.module.add_dht22('name', 'GPIO18', 60, 0, 'celsius')
        sensor = self.module.add_dht22('name2', 'GPIO19', 60, 0, 'celsius')

        with self.assertRaises(MissingParameter) as cm:
            self.module.update_dht22('name', None, 60, 0, 'celsius')
        self.assertEqual(cm.exception.message, 'Parameter "new_name" is missing')
        with self.assertRaises(MissingParameter) as cm:
            self.module.update_dht22('name', '', 60, 0, 'celsius')
        self.assertEqual(cm.exception.message, 'Parameter "new_name" is missing')
        with self.assertRaises(MissingParameter) as cm:
            self.module.update_dht22('name', 'newname', None, 0, 'celsius')
        self.assertEqual(cm.exception.message, 'Parameter "interval" is missing')
        with self.assertRaises(MissingParameter) as cm:
            self.module.update_dht22('name', 'newname', 60, None, 'celsius')
        self.assertEqual(cm.exception.message, 'Parameter "offset" is missing')
        with self.assertRaises(MissingParameter) as cm:
            self.module.update_dht22('name', 'newname', 60, 0, None)
        self.assertEqual(cm.exception.message, 'Parameter "offset_unit" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            self.module.update_dht22('name', 'newname', 60, 0, 'dummy')
        self.assertEqual(cm.exception.message, 'Offset_unit value must be either "celsius" or "fahrenheit"')
        with self.assertRaises(InvalidParameter) as cm:
            self.module.update_dht22('name', 'newname', 30, 0, 'celsius')
        self.assertEqual(cm.exception.message, 'Interval must be greater or equal than 60')
        with self.assertRaises(InvalidParameter) as cm:
            self.module.update_dht22('name', 'name2', 60, 0, 'celsius')
        self.assertEqual(cm.exception.message, 'Name "name2" is already used')

    def test_read_dht(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.session.add_command_handler('update_gpio', self.__update_gpio)

        self.module.DHT22_CMD = 'echo "{\\\"celsius\\\": 20.0, \\\"humidity\\\": 50.0, \\\"error\\\": \\\"\\\", \\\"dummy\\\": \\\"%s\\\"}"'
        (temp, hum) = self.module.add_dht22('name', 'GPIO18', 60, 0, 'celsius')
        self.module._read_dht(temp, hum)
        self.assertEqual(self.session.get_event_send_calls('sensors.humidity.update'), 1, '"sensors.humidity.update" wasn\'t called once')
        self.assertEqual(self.session.get_event_send_calls('sensors.temperature.update'), 1, '"sensors.temperature.update" wasn\'t called once')

    def test_read_dht_with_no_value_returned(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.session.add_command_handler('update_gpio', self.__update_gpio)

        self.module.DHT22_CMD = 'echo "{\\\"celsius\\\": null, \\\"humidity\\\": null, \\\"error\\\": \\\"\\\", \\\"dummy\\\": \\\"%s\\\"}"'
        (temp, hum) = self.module.add_dht22('name', 'GPIO18', 60, 0, 'celsius')
        self.module._read_dht(temp, hum)
        self.assertEqual(self.session.get_event_send_calls('sensors.humidity.update'), 0, '"sensors.humidity.update" wasn\'t called once')
        self.assertEqual(self.session.get_event_send_calls('sensors.temperature.update'), 0, '"sensors.temperature.update" wasn\'t called once')

    def test_read_dht22(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.session.add_command_handler('update_gpio', self.__update_gpio)
        self.module.DHT22_CMD = 'echo "{\\\"celsius\\\": 20.0, \\\"humidity\\\": 50.0, \\\"error\\\": \\\"\\\", \\\"dummy\\\": \\\"%s\\\"}"'

        (temp, hum) = self.module.add_dht22('name', 'GPIO18', 60, 0, 'celsius')
        values = self.module._read_dht22(temp)
        self.assertTrue(type(values) is tuple, 'Invalid output type')
        self.assertEqual(len(values), 3, 'Invalid output content')
        self.assertEqual(values[0], 20.0, 'Invalid celsius temperature')
        self.assertEqual(values[1], 68.0, 'Invalid fahrenheit temperature')
        self.assertEqual(values[2], 50.0, 'Invalid humidity')

    def test_read_dht22_ko(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.session.add_command_handler('update_gpio', self.__update_gpio)
        self.module.DHT22_CMD = 'echo "{\\\"celsius\\\": 20.0, \\\"humidity\\\": 50.0, \\\"error\\\": \\\"TEST: forced error\\\", \\\"dummy\\\": \\\"%s\\\"}"'

        (temp, hum) = self.module.add_dht22('name', 'GPIO18', 60, 0, 'celsius')
        values = self.module._read_dht22(temp)
        self.assertTrue(type(values) is tuple, 'Invalid output type')
        self.assertEqual(len(values), 3, 'Invalid output content')
        self.assertIsNone(values[0], 'Invalid value, must be None')
        self.assertIsNone(values[1], 'Invalid value, must be None')
        self.assertIsNone(values[2], 'Invalid value, must be None')

    def test_read_temperature(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.session.add_command_handler('update_gpio', self.__update_gpio)
        self.session.add_command_handler('get_reserved_gpio', self.__get_reserved_gpio)
        self.module._read_onewire_temperature = self.__read_onewire_temperature

        sensor = self.module.add_temperature_onewire('name', 'device_onewire', 'path_onewire', 60, 0, 'celsius')
        self.module._read_temperature(sensor)
        self.assertEqual(self.session.get_event_send_calls('sensors.temperature.update'), 1, '"sensors.temperature.update" wasn\'t called once')

    def test_read_temperature_ko(self):
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.session.add_command_handler('update_gpio', self.__update_gpio)
        self.session.add_command_handler('get_reserved_gpio', self.__get_reserved_gpio)
        self.module._read_onewire_temperature = self.__read_onewire_temperature_ko

        sensor = self.module.add_temperature_onewire('name', 'device_onewire', 'path_onewire', 60, 0, 'celsius')
        self.module._read_temperature(sensor)
        self.assertEqual(self.session.get_event_send_calls('sensors.temperature.update'), 0, '"sensors.temperature.update" should not be called')

    """
    Delete sensor
    """
    def test_delete_sensor_with_missing_uuid(self):
        self.assertRaises(MissingParameter, self.module.delete_sensor, None)

    def test_delete_sensor_with_unknown_uuid(self):
        self.assertRaises(InvalidParameter, self.module.delete_sensor, '123456789')

    def test_delete_with_command_error(self):
        self.session.disable_command_handler('is_reserved_gpios')
        self.session.add_command_handler('get_reserved_gpio', self.__get_reserved_gpio)
        self.module._read_onewire_temperature = self.__read_onewire_temperature

        sensor = self.module.add_temperature_onewire('name', 'onewire_device', 'onewire_path', 60, 0, 'celsius')
        self.assertRaises(CommandError, self.module.delete_sensor, sensor['uuid'])

    def test_delete_sensor_with_existing_uuid(self):
        self.session.add_command_handler('get_reserved_gpio', self.__get_reserved_gpio)
        self.session.add_command_handler('is_reserved_gpio', self.__is_reserved_gpio_true)
        self.session.add_command_handler('delete_gpio', self.__delete_gpio)
        self.module._read_onewire_temperature = self.__read_onewire_temperature

        sensor = self.module.add_temperature_onewire('name', 'onewire_device', 'onewire_path', 60, 0, 'celsius')
        self.assertTrue(self.module.delete_sensor(sensor['uuid']))

    def test_delete_multi_sensor(self):
        self.session.add_command_handler('get_reserved_gpio', self.__get_reserved_gpio)
        self.session.add_command_handler('is_reserved_gpio', self.__is_reserved_gpio_false)
        self.session.add_command_handler('delete_gpio', self.__delete_gpio)
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)

        (temp, hum) = self.module.add_dht22('dht', 'GPIO18', 60, 0, 'celsius')
        self.assertTrue(self.module.delete_sensor(temp['uuid']))
        self.assertTrue(self.module.delete_sensor(hum['uuid']))

    def test_delete_sensor_with_delete_gpio_error(self):
        self.session.add_command_handler('is_reserved_gpio', self.__is_reserved_gpio_false)
        self.session.add_command_handler('delete_gpio', self.__delete_gpio_with_error)
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)

        sensor = self.module.add_motion_generic('name', 'GPIO18', False)
        with self.assertRaises(CommandError) as cm:
            self.module.delete_sensor(sensor['uuid'])
        self.assertEqual(cm.exception.message, 'TEST: delete gpio with error')

    def test_delete_sensor_with_delete_device_ko(self):
        self.session.add_command_handler('is_reserved_gpio', self.__is_reserved_gpio_false)
        self.session.add_command_handler('delete_gpio', self.__delete_gpio)
        self.session.add_command_handler('add_gpio', self.__add_gpio_ok)
        self.module._delete_device = self.__delete_device_ko

        sensor = self.module.add_motion_generic('name', 'GPIO18', False)
        with self.assertRaises(CommandError) as cm:
            self.module.delete_sensor(sensor['uuid'])
        self.assertEqual(cm.exception.message, 'Unable to delete sensor')

    """
    Onewire
    """
    def test_is_onewire_driver_installed(self):
        res = self.module.is_onewire_driver_installed()
        self.assertTrue(type(res) is bool, 'result of is_onewire_driver_installed must be bool')

    def test_uninstall_onewire_driver(self):
        self.session.add_command_handler('reboot_system', lambda: {'error': False, 'data':True})

        res = self.module.uninstall_onewire_driver()
        self.assertTrue(res, 'Unable to uninstall onewire driver')
        self.assertFalse(self.module.is_onewire_driver_installed(), 'onewire driver is not installed while it doesn\'t')
        self.assertEqual(self.session.get_command_handler_calls('reboot_system'), 1, '"reboot_system" was not called')

    def test_install_onewire_driver(self):
        self.session.add_command_handler('reserve_gpio', self.__reserve_gpio)
        self.session.add_command_handler('reboot_system', lambda: {'error': False, 'data':True})

        res = self.module.install_onewire_driver()
        self.assertTrue(res)
        self.assertTrue(self.module.is_onewire_driver_installed(), 'onewire driver is not installed while it does')
        self.assertEqual(self.session.get_command_handler_calls('reboot_system'), 1, '"reboot_system" was not called')

    def test_get_onewire_devices(self):
        self.session.add_command_handler('reserve_gpio', self.__reserve_gpio)
        self.module.install_onewire_driver()
        self.module.ONEWIRE_PATH = self.ONEWIRE_PATH
        os.mkdir(self.module.ONEWIRE_PATH)
        os.mkdir(os.path.join(self.module.ONEWIRE_PATH, '28-0000054c2ec2'))
        with open(os.path.join(self.module.ONEWIRE_PATH, '28-0000054c2ec2', 'w1_slave'), 'w+') as f:
            f.close()
        
        devices = self.module.get_onewire_devices()
        self.assertTrue(type(devices) is list, 'Invalid type returned')
        self.assertEqual(len(devices), 1, 'Invalid data content returned')
        self.assertTrue('device' in devices[0], 'Item does not contain "device" key')
        self.assertTrue('path' in devices[0], 'Item does not contain "path" key')
        self.assertEqual(devices[0]['device'], '28-0000054c2ec2', 'Device is invalid')
        self.assertEqual(devices[0]['path'], '/tmp/onewire/28-0000054c2ec2/w1_slave', 'Path is invalid')

    def test_get_onewire_devices_ko(self):
        self.module.ONEWIRE_PATH = None
    

        self.session.add_command_handler('reserve_gpio', self.__reserve_gpio)
        self.module.install_onewire_driver()
        self.module.ONEWIRE_PATH = self.ONEWIRE_PATH
        os.mkdir(self.module.ONEWIRE_PATH)
        os.mkdir(os.path.join(self.module.ONEWIRE_PATH, '28-0000054c2ec2'))
        with open(os.path.join(self.module.ONEWIRE_PATH, '28-0000054c2ec2', 'w1_slave'), 'w+') as f:
            f.close()
        
        devices = self.module.get_onewire_devices()
        self.assertTrue(type(devices) is list, 'Invalid type returned')
        self.assertEqual(len(devices), 1, 'Invalid data content returned')
        self.assertTrue('device' in devices[0], 'Item does not contain "device" key')
        self.assertTrue('path' in devices[0], 'Item does not contain "path" key')
        self.assertEqual(devices[0]['device'], '28-0000054c2ec2', 'Device is invalid')
        self.assertEqual(devices[0]['path'], '/tmp/onewire/28-0000054c2ec2/w1_slave', 'Path is invalid')

    def test_get_onewire_devices_with_invalid_onewire_path(self):
        self.session.add_command_handler('reserve_gpio', self.__reserve_gpio)
        self.module.ONEWIRE_PATH = self.ONEWIRE_PATH
        self.module.install_onewire_driver()
        self.module.get_onewire_devices()
        
    def test_get_onewire_devices_with_driver_not_installed(self):
        with self.assertRaises(CommandError) as cm:
            self.module.get_onewire_devices()
        self.assertEqual(cm.exception.message, 'Onewire driver is not installed')

    def test_read_onewire_temperature(self):
        self.session.add_command_handler('reserve_gpio', self.__reserve_gpio)
        self.module.install_onewire_driver()
        self.module.ONEWIRE_PATH = self.ONEWIRE_PATH
        os.mkdir(self.module.ONEWIRE_PATH)
        os.mkdir(os.path.join(self.module.ONEWIRE_PATH, '28-0000054c2ec2'))
        with open(os.path.join(self.module.ONEWIRE_PATH, '28-0000054c2ec2', 'w1_slave'), 'w+') as f:
            f.write('7c 01 4b 46 7f ff 04 10 09 : crc=09 YES\n7c 01 4b 46 7f ff 04 10 09 t=23750')
            f.close()

        devices = self.module.get_onewire_devices()
        self.assertTrue(type(devices) is list, 'Invalid type returned')
        self.assertEqual(len(devices), 1, 'Invalid data content returned')
        sensor = {
            'path': devices[0]['path'],
            'offset': 0,
            'offsetunit': 'celsius'
        }
        temps = self.module._read_onewire_temperature(sensor)
        self.assertTrue(type(temps) is tuple, 'Output is invalid')
        self.assertEqual(len(temps), 2, 'Output content is invalid')
        self.assertEqual(temps[0], 23.75)
        self.assertEqual(temps[1], 74.75)

    def test_read_onewire_celsius_temperature_with_celsius_offset(self):
        self.session.add_command_handler('reserve_gpio', self.__reserve_gpio)
        self.module.install_onewire_driver()
        self.module.ONEWIRE_PATH = self.ONEWIRE_PATH
        os.mkdir(self.module.ONEWIRE_PATH)
        os.mkdir(os.path.join(self.module.ONEWIRE_PATH, '28-0000054c2ec2'))
        with open(os.path.join(self.module.ONEWIRE_PATH, '28-0000054c2ec2', 'w1_slave'), 'w+') as f:
            f.write('7c 01 4b 46 7f ff 04 10 09 : crc=09 YES\n7c 01 4b 46 7f ff 04 10 09 t=23750')
            f.close()

        devices = self.module.get_onewire_devices()
        self.assertTrue(type(devices) is list, 'Invalid type returned')
        self.assertEqual(len(devices), 1, 'Invalid data content returned')
        sensor = {
            'path': devices[0]['path'],
            'offset': 2,
            'offsetunit': 'celsius'
        }
        temps = self.module._read_onewire_temperature(sensor)
        self.assertTrue(type(temps) is tuple, 'Output is invalid')
        self.assertEqual(len(temps), 2, 'Output content is invalid')
        self.assertEqual(temps[0], 25.75)
        self.assertEqual(temps[1], 78.35)

    def test_read_onewire_celsius_temperature_with_fahrenheit_offset(self):
        self.session.add_command_handler('reserve_gpio', self.__reserve_gpio)
        self.module.install_onewire_driver()
        self.module.ONEWIRE_PATH = self.ONEWIRE_PATH
        os.mkdir(self.module.ONEWIRE_PATH)
        os.mkdir(os.path.join(self.module.ONEWIRE_PATH, '28-0000054c2ec2'))
        with open(os.path.join(self.module.ONEWIRE_PATH, '28-0000054c2ec2', 'w1_slave'), 'w+') as f:
            f.write('7c 01 4b 46 7f ff 04 10 09 : crc=09 YES\n7c 01 4b 46 7f ff 04 10 09 t=23750')
            f.close()

        devices = self.module.get_onewire_devices()
        self.assertTrue(type(devices) is list, 'Invalid type returned')
        self.assertEqual(len(devices), 1, 'Invalid data content returned')
        sensor = {
            'path': devices[0]['path'],
            'offset': 10,
            'offsetunit': 'fahrenheit'
        }
        temps = self.module._read_onewire_temperature(sensor)
        self.assertTrue(type(temps) is tuple, 'Output is invalid')
        self.assertEqual(len(temps), 2, 'Output content is invalid')
        self.assertEqual(temps[0], 29.31)
        self.assertEqual(temps[1], 84.75)

    def test_convert_temperatures_from_fahrenheit(self):
        temps = self.module._convert_temperatures_from_fahrenheit(80.0, 0, 'celsius')
        self.assertTrue(type(temps) is tuple, 'Output is invalid')
        self.assertEqual(len(temps), 2, 'Output content is invalid')
        self.assertEqual(temps[0], 26.67)
        self.assertEqual(temps[1], 80.0)

    def test_convert_temperatures_from_fahrenheit_with_celsius_offset(self):
        temps = self.module._convert_temperatures_from_fahrenheit(80.0, 5, 'celsius')
        self.assertTrue(type(temps) is tuple, 'Output is invalid')
        self.assertEqual(len(temps), 2, 'Output content is invalid')
        self.assertEqual(temps[0], 31.67)
        self.assertEqual(temps[1], 89.0)

    def test_convert_temperatures_from_fahrenheit_with_fahrenheit_offset(self):
        temps = self.module._convert_temperatures_from_fahrenheit(80.0, 15, 'fahrenheit')
        self.assertTrue(type(temps) is tuple, 'Output is invalid')
        self.assertEqual(len(temps), 2, 'Output content is invalid')
        self.assertEqual(temps[0], 35.0)
        self.assertEqual(temps[1], 95.0)

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

    def __get_reserved_gpio(self):
        return {
            'error': False,
            'data': {
                'gpio': 'GPIO04',
                'name': 'test',
                'pin': 666,
                'uuid': '987-765-543-321'
            }
        }

    def __get_reserved_gpio_ko(self):
        return {
            'error': True,
            'message': 'TEST: forced error',
            'data': None
        }

    def __add_gpio_ok(self):
        return {
            'error': False,
            'data': {
                'uuid': '123-456-789-123',
                'pin': 666
            }
        }

    def __add_gpio_ko(self):
        return {
            'error': True,
            'message': 'TEST: forced error',
            'data': None
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
        return (666, 999)

    def __read_onewire_temperature_ko(self, sensor):
        return (None, None)

    def __is_reserved_gpio_true(self):
        return {
            'error': False,
            'data': True
        }

    def __is_reserved_gpio_false(self):
        return {
            'error': False,
            'data': False
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

    def __delete_gpio_with_error(self):
        return {
            'error': True,
            'data': False,
            'message': 'TEST: delete gpio with error'
        }

    def __get_assigned_gpios(self):
        return {
            'error': False,
            'data': []
        }

    def __delete_device_ok(self, uuid):
        return True

    def __delete_device_ko(self, uuid):
        return False

    def __update_device_ok(self, uuid, sensor):
        return True

    def __update_device_ko(self, uuid, sensor):
        return False

    def __update_device_ko_temperature(self, uuid, sensor):
        if sensor['type']==Sensors.TYPE_TEMPERATURE:
            return False
        return True

    def __update_device_ko_humidity(self, uuid, sensor):
        if sensor['type']==Sensors.TYPE_HUMIDITY:
            return False
        return True

    def __add_device_ok(self, sensor):
        sensor['uuid'] = '123-456-789-123'
        return sensor

    def __add_device_ko(self, sensor):
        return None

    def __add_device_ko_temperature(self, sensor):
        if sensor['type']==Sensors.TYPE_TEMPERATURE:
            return None
        sensor['uuid'] = '123-456-789-123'
        return sensor

    def __add_device_ko_humidity(self, sensor):
        if sensor['type']==Sensors.TYPE_HUMIDITY:
            return None
        sensor['uuid'] = '123-456-789-123'
        return sensor


if __name__ == '__main__':
    unittest.main()

