from cleep.libs.tests import session, lib
import unittest
import logging
import time
import sys, os
import shutil
import copy
from threading import Event
sys.path.append('../')
from backend.sensors import Sensors
from backend.sensor import Sensor
from backend.onewiredriver import OnewireDriver
from backend.sensorsutils import SensorsUtils
from backend.sensorshumidityupdateevent import SensorsHumidityUpdateEvent
from backend.sensorstemperatureupdateevent import SensorsTemperatureUpdateEvent
from backend.sensorsmotiononevent import SensorsMotionOnEvent
from backend.sensorsmotionoffevent import SensorsMotionOffEvent
from cleep.exception import InvalidParameter, MissingParameter, CommandError
from cleep.libs.tests.common import get_log_level
from cleep.libs.internals.task import Task
from unittest.mock import Mock, patch, mock_open

LOG_LEVEL = get_log_level()

class FakeSensor(Sensor):
    TYPES = ['test']
    SUBTYPE = 'fake'
    def __init__(self, sensors):
        Sensor.__init__(self, sensors)
        self.update_call = 0
        self.add_call = 0
        self.delete_call = 0
        self.raspi_gpios = None

    def injected_method(self):
        pass

    def update(self, sensor, name):
        self.update_call += 1
        gpio = {
            'name': name + '_fake',
        }
        sensor['name'] = name
        return {
            'gpios': [gpio,],
            'sensors': [sensor,],
        }

    def add(self, name, gpio):
        self.add_call += 1
        gpio = {
            'name': name + '_fake',
            'gpio': gpio,
        }
        sensor = {
            'name': name,
            'type': 'test',
            'subtype': 'fake',
        }
        return {
            'gpios': [gpio,],
            'sensors': [sensor],
        }

    def task(self):
        pass
    
    def get_task(self, sensors):
        self.task = Mock()
        return self.task



class FakeDriver():
    def __init__(self):
        self.name = 'fakedriver'

    def is_installed(self):
        return True



class SensorsUtilsTests(unittest.TestCase):

    def test_sensorsutils_convert_temperatures_from_celsius(self):
        (c,f) = SensorsUtils.convert_temperatures_from_celsius(20, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(c, 20, 'Celsius is invalid')
        self.assertEqual(f, 68, 'Fahrenheit is invalid')

        (c,f) = SensorsUtils.convert_temperatures_from_celsius(22, 8, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(c, 30, 'Celsius is invalid')
        self.assertEqual(f, 86, 'Fahrenheit is invalid')

        (c,f) = SensorsUtils.convert_temperatures_from_celsius(20, 10, SensorsUtils.TEMP_FAHRENHEIT)
        self.assertEqual(c, 25.56, 'Celsius is invalid')
        self.assertEqual(f, 78, 'Fahrenheit is invalid')

    def test_sensorsutils_convert_temperatures_from_fahrenheit(self):
        (c,f) = SensorsUtils.convert_temperatures_from_fahrenheit(68, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(c, 20, 'Celsius is invalid')
        self.assertEqual(f, 68, 'Fahrenheit is invalid')

        (c,f) = SensorsUtils.convert_temperatures_from_fahrenheit(78, 5, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(c, 30.56, 'Celsius is invalid')
        self.assertEqual(f, 87.0, 'Fahrenheit is invalid')

        (c,f) = SensorsUtils.convert_temperatures_from_fahrenheit(64, 10, SensorsUtils.TEMP_FAHRENHEIT)
        self.assertEqual(c, 23.33, 'Celsius is invalid')
        self.assertEqual(f, 74, 'Fahrenheit is invalid')


class SensorsTests(unittest.TestCase):

    ADD_GPIO_DATA = {
        'uuid': '123-456-789-123',
        'pin': 666,
        'gpio': 'GPIO18',
    }
    UPDATE_GPIO_DATA = {
        'uuid': '123-456-789-123',
        'pin': 666,
        'gpio': 'GPIO18',
    }

    def setUp(self):
        logging.basicConfig(level=LOG_LEVEL, format=u'%(asctime)s %(name)s:%(lineno)d %(levelname)s : %(message)s')
        self.session = session.TestSession(self)


    def init_session(self, start_module=True, mock_on_start=True, mock_on_stop=True):
        self.module = self.session.setup(Sensors, mock_on_start=mock_on_start, mock_on_stop=mock_on_stop)

        self.session.add_mock_command(self.session.make_mock_command('get_raspi_gpios', data={'GPIO18': 56}))

        # overwrite sensors by fake one
        self.module.addons_by_name = {}
        self.module.addons_by_type = {}
        self.module._tasks_by_device_uuid = {}
        self.addon = FakeSensor(self.module)
        self.module._register_addon(self.addon)

        if start_module:
            self.session.start_module(self.module)

    def tearDown(self):
        self.session.clean()

    def test_on_start(self):
        self.init_session(False, mock_on_start=False)
        sensor = {
            'uuid': '123-456-789',
            'type': 'test',
            'subtype': 'fake',
            'gpios': [{'gpio':'GPIO18', 'uuid':'666-666-666', 'pin':18}],
            'name': 'sensor1',
        }
        self.module._start_sensor_task = Mock()
        self.module.get_module_devices = Mock(return_value={
            sensor['uuid']: sensor
        })

        self.session.start_module(self.module)

        self.assertTrue(self.session.command_called('get_raspi_gpios'))
        self.assertIsNotNone(self.addon.raspi_gpios)
        self.module._start_sensor_task.assert_called_with(session.AnyArg(), [sensor])

    def test_on_start_with_unsupported_sensor_type(self):
        self.init_session(False, mock_on_start=False)
        sensor = {
            'uuid': '123-456-789',
            'type': 'dummy',
            'subtype': 'fake',
            'gpios': [{'gpio':'GPIO18', 'uuid':'666-666-666', 'pin':18}],
            'name': 'sensor1',
        }
        self.module._start_sensor_task = Mock()
        self.module.get_module_devices = Mock(return_value={
            sensor['uuid']: sensor
        })

        self.session.start_module(self.module)

        self.assertFalse(self.module._start_sensor_task.call_count)

    def test_register_addon_duplicate(self):
        self.init_session(True)
        with self.assertRaises(Exception) as cm:
            self.module._register_addon(self.addon)
        self.assertEqual(str(cm.exception), 'Subtype "fake" already registered in type "test"')

    def test_sensor_init_ok(self):
        self.init_session(True)
        # test addons init
        logging.debug('addons_by_name: %s' % self.module.addons_by_name)
        self.assertEqual(len(self.module.addons_by_name), 1)

        # test addon method injection
        self.assertTrue(hasattr(self.module, 'injected_method'))
        self.assertTrue(callable(getattr(self.module, 'injected_method')))

    def test_get_module_config(self):
        self.init_session(True)
        config = self.module.get_module_config()
        self.assertIsNotNone(config, 'Invalid config')
        self.assertTrue('drivers' in config, '"drivers" key doesn\'t exist in config')

    def test_get_module_config_with_driver(self):
        self.init_session(True)
        driver = FakeDriver()
        self.addon.drivers[driver.name] = driver

        config = self.module.get_module_config()
        self.assertTrue(driver.name in config['drivers'], 'Driver info should be returned')
        self.assertEqual(config['drivers'][driver.name], True, 'Driver should be returned as installed')

        driver.is_installed = lambda: False
        config = self.module.get_module_config()
        self.assertEqual(config['drivers'][driver.name], False, 'Driver should be returned as not installed')

    def test_get_module_devices(self):
        self.init_session(True)
        self.session.add_mock_command(self.session.make_mock_command('add_gpio', data=self.ADD_GPIO_DATA))

        data = {
            'name': 'aname',
            'gpio': 'GPIO18',
        }
        self.module.add_sensor('test', 'fake', data)
        devices = self.module.get_module_devices()
        self.assertIsNotNone(devices, 'get_module_devices returns None')
        self.assertEqual(len(devices), 1, 'get_module_devices should return single sensor')

    def test_get_raspi_gpios_with_error(self):
        self.init_session(True)
        self.session.set_mock_command_fail('get_raspi_gpios')

        res = self.module._get_raspi_gpios()
        self.assertTrue(type(res) is dict, 'Invalid type of _get_raspi_gpios. Must be dict')
        self.assertEqual(len(res), 0, '_get_raspi_gpios must return empty dict when error')

    def test_get_assigned_gpios(self):
        self.init_session(True)
        self.session.add_mock_command(self.session.make_mock_command('get_assigned_gpios', data=['GPIO18']))

        res = self.module._get_assigned_gpios()
        logging.debug('Assigned gpios: %s' % res)

        self.assertTrue(type(res) is list, 'Invalid type of _get_assigned_gpios. Must be list')
        self.assertNotEqual(len(res), 0, '_get_assigned_gpios must return non empty list')

    def test_get_assigned_gpios_with_error(self):
        self.init_session(True)
        self.session.add_mock_command(self.session.make_mock_command('get_assigned_gpios', fail=True))

        res = self.module._get_assigned_gpios()
        self.assertTrue(type(res) is list, 'Invalid type of _get_assigned_gpios. Must be list')
        self.assertEqual(len(res), 0, '_get_assigned_gpios must return empty list when error')

    def test_fix_gpio_device(self):
        self.init_session(True)
        gpio = {
            "gpio": "GPIO13",
            "inverted": False,
            "keep": False,
            "mode": "input",
            "name": "motion_motion",
            "on": False,
            "owner": "sensors",
            "pin": 33,
            "subtype": "input",
            "type": "gpio",
            "uuid": "6904d46d-f85f-4991-9255-e94dc68bda4a"
        }

        fixed = self.module._fix_gpio_device(gpio)
        logging.debug('Fixed 1: %s' % fixed)
        self.assertFalse('uuid' in fixed)
        self.assertTrue('device_uuid' in fixed)

        del gpio['uuid']
        fixed = self.module._fix_gpio_device(gpio)
        logging.debug('Fixed 2: %s' % fixed)
        self.assertFalse('uuid' in fixed)
        self.assertFalse('device_uuid' in fixed)
        self.assertEqual(len(fixed.keys()), len(gpio.keys()))

    def test_add_sensor(self):
        self.init_session(True)
        self.session.add_mock_command(self.session.make_mock_command('add_gpio', data=self.ADD_GPIO_DATA))
        mock_start = Mock()
        self.module._start_sensor_task = mock_start
        mock_stop = Mock()
        self.module._stop_sensor_task = mock_start

        data = {
            'name': 'aname',
            'gpio': 'GPIO18',
        }
        sensors = self.module.add_sensor('test', 'fake', data)
        self.assertTrue(isinstance(sensors, list), 'add_sensor should returns list')
        self.assertEqual(len(sensors), 1, 'add_sensor should returns one sensor')

        devices = self.module.get_module_devices()
        self.assertEqual(len(devices), 1, 'get_devices should return only one device')
        device = list(devices.values())[0]

        # check _fill_sensor
        self.assertEqual(len(device['gpios']), 1, 'Device gpios are missing')
        self.assertTrue('gpio' in device['gpios'][0], 'Device gpio should contains "gpio" field')
        self.assertTrue('pin' in device['gpios'][0], 'Device gpio should contains "pin" field')
        self.assertTrue('uuid' in device['gpios'][0], 'Device gpio should contains "uuid" field')

        # check command handlers
        self.assertEqual(self.session.command_call_count('add_gpio'), 1, 'add_gpio should be called once')

        # check task
        self.assertEqual(mock_start.call_count, 1, '_start_sensor_task should be called')
        self.assertEqual(mock_stop.call_count, 0, '_stop_sensor_task should not be called')

    def test_add_sensor_with_invalid_sensor_type(self):
        self.init_session(True)
        data = {
            'name': 'aname',
            'gpio': 'GPIO18',
        }
        with self.assertRaises(CommandError) as cm:
            self.module.add_sensor('test', 'temp', data)
        self.assertEqual(cm.exception.message, 'Sensor subtype "temp" doesn\'t exist')

    def test_add_sensor_with_add_gpio_failed(self):
        self.init_session(True)
        self.session.add_mock_command(self.session.make_mock_command('add_gpio', fail=True))
        self.session.add_mock_command(self.session.make_mock_command('delete_gpio', data=True))
        mock_start = Mock()
        self.module._start_sensor_task = mock_start
        mock_stop = Mock()
        self.module._stop_sensor_task = mock_start

        data = {
            'name': 'aname',
            'gpio': 'GPIO18',
        }
        with self.assertRaises(CommandError) as cm:
            self.module.add_sensor('test', 'fake', data)
        self.assertEqual(cm.exception.message, 'Error occured adding sensor')

        self.assertEqual(self.session.command_call_count('add_gpio'), 1, 'add_gpio should be called')
        self.assertEqual(self.session.command_call_count('delete_gpio'), 0, 'delete_gpio should not be called')

        devices = self.module.get_module_devices()
        self.assertEqual(len(devices), 0, 'No sensor should be saved')

        # check task
        self.assertEqual(mock_start.call_count, 0, '_start_sensor_task should not be called')
        self.assertEqual(mock_stop.call_count, 0, '_stop_sensor_task should not be called')

    def test_add_sensor_with_add_device_failed(self):
        self.init_session(True)
        self.session.add_mock_command(self.session.make_mock_command('add_gpio', data=self.ADD_GPIO_DATA))
        self.session.add_mock_command(self.session.make_mock_command('delete_gpio', data=True))
        self.module._add_device = Mock(return_value=None)
        mock_start = Mock()
        self.module._start_sensor_task = mock_start
        mock_stop = Mock()
        self.module._stop_sensor_task = mock_start

        data = {
            'name': 'aname',
            'gpio': 'GPIO18'
        }
        with self.assertRaises(CommandError) as cm:
            self.module.add_sensor('test', 'fake', data)
        self.assertEqual(cm.exception.message, 'Error occured adding sensor')

        self.assertEqual(self.session.command_call_count('add_gpio'), 1, 'add_gpio should be called')
        self.assertEqual(self.session.command_call_count('delete_gpio'), 1, 'delete_gpio should be called')

        devices = self.module.get_module_devices()
        self.assertEqual(len(devices), 0, 'No sensor should be saved')

        # check task
        self.assertEqual(mock_start.call_count, 0, '_start_sensor_task not should be called')
        self.assertEqual(mock_stop.call_count, 0, '_stop_sensor_task not should be called')

    def test_add_sensor_with_second_add_device_failed(self):
        sensor1 = {'name': 'aname_hum', 'type': 'hum', 'subtype': 'fake', 'gpios': []}
        sensor2 = {'name': 'aname_temp', 'type': 'temp', 'subtype': 'fake', 'gpios': []}
        gpio1 = {'name': 'aname', 'type': 'test', 'subtype': 'fake', 'gpios': [{'uuid': '123-456-789-123', 'pin': 666, 'gpio': 'GPIO18'}]}
        self.init_session(True)
        self.session.add_mock_command(self.session.make_mock_command('add_gpio', data=self.ADD_GPIO_DATA))
        self.session.add_mock_command(self.session.make_mock_command('delete_gpio', data=True))
        mock_start = Mock()
        self.module._start_sensor_task = mock_start
        mock_stop = Mock()
        self.module._stop_sensor_task = mock_start
        sensor1_uuid = copy.deepcopy(sensor1)
        sensor1_uuid.update({'uuid': '1234567890'})
        sensor2_uuid = copy.deepcopy(sensor2)
        sensor2_uuid.update({'uuid': '0987654321'})
        self.module._add_device = Mock(side_effect=[sensor1_uuid, None])
        self.addon.add = Mock(return_value={
            'gpios': [gpio1],
            'sensors': [sensor1, sensor2]
        })
        self.module._delete_device = Mock()

        data = {
            'name': 'aname',
            'gpio': 'GPIO18'
        }
        with self.assertRaises(CommandError) as cm:
            self.module.add_sensor('test', 'fake', data)
        self.assertEqual(cm.exception.message, 'Error occured adding sensor')

        self.assertEqual(self.session.command_call_count('add_gpio'), 1, 'add_gpio should be called')
        self.assertEqual(self.session.command_call_count('delete_gpio'), 1, 'delete_gpio should be called')

        devices = self.module.get_module_devices()
        self.assertEqual(len(devices), 0, 'No sensor should be saved')
        self.module._delete_device.assert_called_with(sensor1_uuid['uuid'])

        # check task
        self.assertEqual(mock_start.call_count, 0, '_start_sensor_task not should be called')
        self.assertEqual(mock_stop.call_count, 0, '_stop_sensor_task not should be called')

    def test_update_sensor(self):
        self.init_session(True)
        mock_start = Mock()
        mock_stop = Mock()
        self.session.add_mock_command(self.session.make_mock_command('add_gpio', data=self.UPDATE_GPIO_DATA))
        self.session.add_mock_command(self.session.make_mock_command('update_gpio', self.UPDATE_GPIO_DATA))
        self.module._start_sensor_task = mock_start
        self.module._stop_sensor_task = mock_stop

        data = {
            'name': 'aname',
            'gpio': 'gpio18',
        }
        sensors = self.module.add_sensor('test', 'fake', data)
        added_sensor = sensors[0]

        new_data = {
            'name': 'newname',
        }
        sensors = self.module.update_sensor(added_sensor['uuid'], new_data)
        self.assertTrue(isinstance(sensors, list), 'update_sensor should returns list')
        self.assertEqual(len(sensors), 1, 'update_sensor should return one sensor')

        devices = self.module.get_module_devices()
        self.assertEqual(len(devices), 1, 'get_module_devices should returns 1 device')
        updated_sensor = list(devices.values())[0]
        self.assertEqual(self.session.command_call_count('update_gpio'), 1, 'Update gpio should be called')

        # check _fill_sensor
        self.assertEqual(len(updated_sensor['gpios']), 1, 'Device gpios are missing')
        self.assertTrue('gpio' in updated_sensor['gpios'][0], 'Device gpio should contains "gpio" field')
        self.assertTrue('pin' in updated_sensor['gpios'][0], 'Device gpio should contains "pin" field')
        self.assertTrue('uuid' in updated_sensor['gpios'][0], 'Device gpio should contains "uuid" field')
        self.assertEqual(updated_sensor['gpios'][0]['gpio'], added_sensor['gpios'][0]['gpio'], 'Gpio field shouldn\'t be updated')
        self.assertEqual(updated_sensor['gpios'][0]['pin'], added_sensor['gpios'][0]['pin'], 'Pin field shouldn\'t be updated')
        self.assertEqual(updated_sensor['gpios'][0]['uuid'], added_sensor['gpios'][0]['uuid'], 'Pin field shouldn\'t be updated')

        # check task
        self.assertEqual(mock_start.call_count, 2, '_start_sensor_task should be called twice (add + update)')
        self.assertEqual(mock_stop.call_count, 1, '_stop_sensor_task should be called')

    def test_update_sensor_no_addon_found(self):
        self.init_session()
        sensor = {'uuid': '1234567890', 'name': 'aname', 'type': 'test', 'subtype': 'fake', 'gpios': [{'uuid': '123-456-789-123', 'pin': 666, 'gpio': 'GPIO18'}]}
        self.module._get_device = Mock(return_value=sensor)
        self.module._get_addon = Mock(return_value=None)

        with self.assertRaises(CommandError) as cm:
            self.module.update_sensor(sensor['uuid'], sensor)
        self.assertEqual(str(cm.exception), 'Unhandled sensor type "test-fake"')

    def test_update_sensor_with_invalid_params(self):
        self.init_session(True)
        data = {
            'name': 'aname',
            'gpio': 'gpio18',
        }

        with self.assertRaises(MissingParameter) as cm:
            self.module.update_sensor(None, data)
        self.assertEqual(cm.exception.message, 'Uuid parameter is missing')

        with self.assertRaises(MissingParameter) as cm:
            self.module.update_sensor('', data)
        self.assertEqual(cm.exception.message, 'Uuid parameter is missing')

        self.session.add_mock_command(self.session.make_mock_command('add_gpio', data=self.UPDATE_GPIO_DATA))
        sensors = self.module.add_sensor('test', 'fake', data)
        added_sensor = sensors[0]

        with self.assertRaises(InvalidParameter) as cm:
            self.module.update_sensor('666-666-666', data)
        self.assertEqual(cm.exception.message, 'Sensor with uuid "666-666-666" doesn\'t exist')

    def test_update_sensor_with_update_gpio_failed(self):
        self.init_session(True)
        self.session.add_mock_command(self.session.make_mock_command('add_gpio', data=self.UPDATE_GPIO_DATA))
        self.session.add_mock_command(self.session.make_mock_command('update_gpio', fail=True))
        mock_start = Mock()
        mock_stop = Mock()
        self.module._start_sensor_task = mock_start
        self.module._stop_sensor_task = mock_stop

        data = {
            'name': 'aname',
            'gpio': 'GPIO18',
        }
        sensors = self.module.add_sensor('test', 'fake', data)
        added_sensor = sensors[0]

        new_data = {
            'name': 'newname',
        }
        with self.assertRaises(CommandError) as cm:
            self.module.update_sensor(added_sensor['uuid'], new_data)
        self.assertEqual(cm.exception.message, 'Error updating sensor')

        devices = self.module.get_module_devices()
        self.assertEqual(len(devices), 1, 'One sensor should be exist')

        # check task
        self.assertEqual(mock_start.call_count, 1, '_start_sensor_task should be called only once (during add)')
        self.assertEqual(mock_stop.call_count, 0, '_stop_sensor_task not should be called')

    def test_update_sensor_with_update_device_failed(self):
        self.init_session(True)
        self.session.add_mock_command(self.session.make_mock_command('add_gpio', data=self.UPDATE_GPIO_DATA))
        self.module._update_device = Mock(return_value=None)
        self.session.add_mock_command(self.session.make_mock_command('update_gpio', fail=False))
        mock_start = Mock()
        mock_stop = Mock()
        self.module._start_sensor_task = mock_start
        self.module._stop_sensor_task = mock_stop

        data = {
            'name': 'aname',
            'gpio': 'GPIO18',
        }
        sensors = self.module.add_sensor('test', 'fake', data)
        added_sensor = sensors[0]

        new_data = {
            'name': 'newname',
        }
        with self.assertRaises(CommandError) as cm:
            self.module.update_sensor(added_sensor['uuid'], new_data)
        self.assertEqual(cm.exception.message, 'Error updating sensor')

        devices = self.module.get_module_devices()
        self.assertEqual(len(devices), 1, 'One sensor should be exist')

        # check task
        self.assertEqual(mock_start.call_count, 1, '_start_sensor_task should be called only once (during add)')
        self.assertEqual(mock_stop.call_count, 0, '_stop_sensor_task not should be called')

    def test_delete_sensor(self):
        self.init_session(True)
        self.session.add_mock_command(self.session.make_mock_command('add_gpio', data=self.UPDATE_GPIO_DATA))
        self.session.add_mock_command(self.session.make_mock_command('delete_gpio', data=True))
        self.session.add_mock_command(self.session.make_mock_command('is_reserved_gpio', data=False))
        mock_start = Mock()
        mock_stop = Mock()
        self.module._start_sensor_task = mock_start
        self.module._stop_sensor_task = mock_stop

        data = {
            'name': 'aname',
            'gpio': 'GPIO18',
        }
        sensors = self.module.add_sensor('test', 'fake', data)
        added_sensor = sensors[0]

        res = self.module.delete_sensor(added_sensor['uuid'])
        self.assertTrue(isinstance(res, bool), 'delete_sensor should returns bool')

        devices = self.module.get_module_devices()
        self.assertEqual(len(devices), 0, 'get_module_devices should returns 0 device')

        self.assertEqual(self.session.command_call_count('delete_gpio'), 1, 'Delete gpio should be called')

        # check task
        self.assertEqual(mock_start.call_count, 1, '_start_sensor_task should be called only once (during add)')
        self.assertEqual(mock_stop.call_count, 1, '_stop_sensor_task should be called once (during deletion)')

    def test_delete_sensor_no_addon_found(self):
        self.init_session()
        sensor = {'uuid': '1234567890', 'name': 'aname', 'type': 'test', 'subtype': 'fake', 'gpios': [{'uuid': '123-456-789-123', 'pin': 666, 'gpio': 'GPIO18'}]}
        self.module._get_device = Mock(return_value=sensor)
        self.module._get_addon = Mock(return_value=None)

        with self.assertRaises(CommandError) as cm:
            self.module.delete_sensor('1234567890')
        self.assertEqual(str(cm.exception), 'Unhandled sensor type "test-fake"')

    def test_delete_sensor_with_invalid_params(self):
        self.init_session(True)
        with self.assertRaises(MissingParameter) as cm:
            self.module.delete_sensor(None)
        self.assertEqual(cm.exception.message, 'Uuid parameter is missing')

        with self.assertRaises(MissingParameter) as cm:
            self.module.delete_sensor('')
        self.assertEqual(cm.exception.message, 'Uuid parameter is missing')

        with self.assertRaises(InvalidParameter) as cm:
            self.module.delete_sensor('123-456-123')
        self.assertEqual(cm.exception.message, 'Sensor with uuid "123-456-123" doesn\'t exist')

    def test_delete_sensor_with_is_reserved_gpio_failed(self):
        self.init_session(True)
        self.session.add_mock_command(self.session.make_mock_command('add_gpio', self.UPDATE_GPIO_DATA))
        self.session.add_mock_command(self.session.make_mock_command('delete_gpio', data=True))
        self.session.add_mock_command(self.session.make_mock_command('is_reserved_gpio', fail=True))

        data = {
            'name': 'aname',
            'gpio': 'GPIO18',
        }
        sensors = self.module.add_sensor('test', 'fake', data)
        added_sensor = sensors[0]

        with self.assertRaises(CommandError) as cm:
            self.module.delete_sensor(added_sensor['uuid'])
        self.assertEqual(cm.exception.message, 'Error deleting sensor')

    def test_delete_sensor_with_delete_gpio_failed(self):
        self.init_session(True)
        self.session.add_mock_command(self.session.make_mock_command('add_gpio', data=self.UPDATE_GPIO_DATA))
        self.session.add_mock_command(self.session.make_mock_command('is_reserved_gpio', fail=False))
        self.session.add_mock_command(self.session.make_mock_command('delete_gpio', fail=True))

        data = {
            'name': 'aname',
            'gpio': 'GPIO18',
        }
        sensors = self.module.add_sensor('test', 'fake', data)
        added_sensor = sensors[0]

        try:
            self.module.delete_sensor(added_sensor['uuid'])
        except:
            self.fail('Should not failed deleting gpio device')

    def test_delete_sensor_with_reserved_gpio(self):
        self.init_session(True)
        self.session.add_mock_command(self.session.make_mock_command('add_gpio', self.UPDATE_GPIO_DATA))
        self.session.add_mock_command(self.session.make_mock_command('delete_gpio', data=True))
        self.session.add_mock_command(self.session.make_mock_command('is_reserved_gpio', data=True))
        mock_start = Mock()
        mock_stop = Mock()
        self.module._start_sensor_task = mock_start
        self.module._stop_sensor_task = mock_stop

        data = {
            'name': 'aname',
            'gpio': 'GPIO18',
        }
        sensors = self.module.add_sensor('test', 'fake', data)
        added_sensor = sensors[0]

        res = self.module.delete_sensor(added_sensor['uuid'])
        self.assertTrue(isinstance(res, bool), 'delete_sensor should returns bool')

        devices = self.module.get_module_devices()
        self.assertEqual(len(devices), 0, 'get_module_devices should returns 0 device')

        self.assertEqual(self.session.command_call_count('delete_gpio'), 0, 'Delete gpio should not be called for reserved gpio')

        # check task
        self.assertEqual(mock_start.call_count, 1, '_start_sensor_task should be called only once (during add)')
        self.assertEqual(mock_stop.call_count, 1, '_stop_sensor_task should be called once (during deletion)')

    def test_delete_sensor_with_gpio_still_used(self):
        self.init_session(True)
        self.session.add_mock_command(self.session.make_mock_command('delete_gpio', data=True))
        self.session.add_mock_command(self.session.make_mock_command('is_reserved_gpio', data=False))

        sensor1 = {
            'uuid': '123-456-789',
            'type': 'test',
            'subtype': 'fake',
            'gpios': [{'gpio':'GPIO18', 'uuid':'666-666-666', 'pin':18}],
            'name': 'sensor1',
        }
        sensor2 = {
            'uuid': '321-654-987',
            'type': 'test',
            'subtype': 'fake',
            'gpios': [{'gpio':'GPIO18', 'uuid':'666-666-666', 'pin':18}],
            'name': 'sensor2',
        }
        self.module._add_device(sensor1)
        self.module._add_device(sensor2)

        res = self.module.delete_sensor(sensor1['uuid'])
        self.assertTrue(res, 'Sensor should be deleted')
        self.assertEqual(self.session.command_call_count('delete_gpio'), 0, 'Gpio should not be deleted')

    def test_search_by_gpio(self):
        self.init_session(True)
        self.session.add_mock_command(self.session.make_mock_command('add_gpio', self.ADD_GPIO_DATA))

        data = {
            'name': 'aname',
            'gpio': 'GPIO18',
        }
        sensors = self.module.add_sensor('test', 'fake', data)
        added_sensor = sensors[0]
        logging.error(added_sensor)

        sensor = self.module._search_by_gpio(added_sensor['gpios'][0]['uuid'])
        self.assertIsNotNone(sensor)
        self.assertEqual(sensor['name'], data['name'], 'Found sensor should have same name')

    def test_search_by_gpio_with_unknown_gpio_uuid(self):
        self.init_session(True)
        self.session.add_mock_command(self.session.make_mock_command('add_gpio', self.ADD_GPIO_DATA))

        data = {
            'name': 'aname',
            'gpio': 'GPIO18',
        }
        sensors = self.module.add_sensor('test', 'fake', data)
        added_sensor = sensors[0]
        logging.error(added_sensor)

        sensor = self.module._search_by_gpio('666-666-666-666')
        self.assertIsNone(sensor)

    """
    Event
    """
    def test_receive_startup_event_rejected(self):
        self.init_session(True)
        mock = Mock()
        self.addon.process_event = mock

        event = {
            'startup': True,
            'event': 'system.startup.fake'
        }
        self.module.on_event(event)
        self.assertEqual(mock.call_count, 0, 'Addon process_event should not be called')

    def test_receive_install_driver_event(self):
        self.init_session(True)
        self.addon.process_event = Mock()
        self.addon.has_drivers = Mock(return_value=True)

        install_event = {
            'startup': False,
            'event': 'system.driver.install'
        }
        self.module.on_event(install_event)
        self.assertEqual(self.addon.process_event.call_count, 1, 'Addon process_event should be called')
        self.assertEqual(self.addon.process_event.call_args.args[0], install_event, 'Process_event first param should be event')
        self.assertIsNone(self.addon.process_event.call_args.args[1], 'Process_event sensors value should be None for driver event')

    def test_receive_uninstall_driver_event(self):
        self.init_session(True)
        self.addon.process_event = Mock()
        self.addon.has_drivers = Mock(return_value=True)

        uninstall_event = {
            'startup': False,
            'event': 'system.driver.uninstall'
        }
        self.module.on_event(uninstall_event)
        self.assertEqual(self.addon.process_event.call_count, 1, 'Addon process_event should be called')
        self.assertEqual(self.addon.process_event.call_args.args[0], uninstall_event, 'Process_event first param should be event')
        self.assertIsNone(self.addon.process_event.call_args.args[1], 'Process_event sensors value should be None for driver event')

    def test_receive_drop_init_gpio_event(self):
        self.init_session(True)
        self.addon.process_event = Mock()

        event = {
            'event': 'gpios.gpio.on',
            'startup': False,
            'params': {
                'init': True
            }
        }
        self.module.on_event(event)
        self.assertEqual(self.addon.process_event.call_count, 0, 'Init gpio event should be dropped')

    def test_receive_gpio_event(self):
        self.init_session(True)
        mock = Mock()
        self.addon.process_event = mock
        self.module._search_by_gpio = Mock(return_value={
            'uuid': '123-456-789',
            'type': 'test',
            'subtype': 'fake',
            'name': 'aname',
        })

        event = {
            'event': 'gpios.gpio.on',
            'startup': False,
            'device_id': '123-456-789',
            'params': {
                'init': False,
            }
        }
        self.module.on_event(event)
        self.assertEqual(mock.call_count, 1, 'Addon process_event should be called')

    def test_receive_gpio_event_with_no_sensor_found(self):
        self.init_session(True)
        mock = Mock()
        self.addon.process_event = mock
        self.module._search_by_gpio = Mock(return_value=None)

        event = {
            'event': 'gpios.gpio.on',
            'startup': False,
            'device_id': '123-456-789',
            'params': {
                'init': False,
            }
        }
        self.module.on_event(event)
        self.assertEqual(mock.call_count, 0, 'Addon process_event should not be called')

    def test_receive_gpio_event_with_no_addon_found(self):
        self.init_session(True)
        mock = Mock()
        self.addon.process_event = mock
        self.module._search_by_gpio = Mock(return_value={
            'uuid': '123-456-789',
            'type': 'invalidtype',
            'subtype': 'fake',
            'name': 'aname',
        })

        event = {
            'event': 'gpios.gpio.on',
            'startup': False,
            'device_id': '123-456-789',
            'params': {
                'init': False,
            }
        }
        self.module.on_event(event)
        self.assertEqual(mock.call_count, 0, 'Addon process_event should not be called')

    """
    Task
    """
    def test_start_sensor_task(self):
        self.init_session(True)
        sensor = {
            'name': 'aname',
            'gpios': [{
                'uuid': '987-654-321',
                'gpio': 'GPIO18',
                'pin': 18
            }],
            'uuid': '123-456-789'
        }
        mock_task = Mock()
        self.module._start_sensor_task(mock_task, [sensor,])
        
        self.assertEqual(len(self.module._tasks_by_device_uuid), 1, 'Start_sensor_task should save task')
        self.assertEqual(list(self.module._tasks_by_device_uuid.keys())[0], sensor['uuid'], 'Task should be saved with sensor uuid')
        mock_task.start.assert_called()

    def test_start_sensor_task_with_two_sensors(self):
        self.init_session(True)
        sensor1 = {
            'name': 'aname',
            'gpios': [{
                'uuid': '987-654-321',
                'gpio': 'GPIO18',
                'pin': 18
            }],
            'uuid': '123-456-789'
        }
        sensor2 = {
            'name': 'aname2',
            'gpios': [{
                'uuid': '987-654-321',
                'gpio': 'GPIO19',
                'pin': 19
            }],
            'uuid': '321-654-987'
        }
        mock_task = Mock()
        self.module._start_sensor_task(mock_task, [sensor1, sensor2])
        
        self.assertEqual(len(self.module._tasks_by_device_uuid), 2, 'Start_sensor_task should save task for each sensor')
        self.assertTrue(all(key in [sensor1['uuid'], sensor2['uuid']] for key in self.module._tasks_by_device_uuid.keys()), 'Task should be saved with sensors uuid')
        self.assertEqual(self.module._tasks_by_device_uuid[sensor1['uuid']], self.module._tasks_by_device_uuid[sensor2['uuid']], 'Same task should be save for all sensors')
        mock_task.start.assert_called()

    def test_start_sensor_task_with_no_task(self):
        self.init_session(True)
        sensor = {
            'name': 'aname',
            'gpios': [{
                'uuid': '987-654-321',
                'gpio': 'GPIO18',
                'pin': 18
            }],
            'uuid': '123-456-789'
        }
        self.module._start_sensor_task(None, [sensor,])
        
        self.assertEqual(len(self.module._tasks_by_device_uuid), 0, 'Start_sensor_task should not save task if no task specified')

    def test_stop_sensor_task(self):
        self.init_session(True)
        sensor = {
            'name': 'aname',
            'gpios': [{
                'uuid': '987-654-321',
                'gpio': 'GPIO18',
                'pin': 18
            }],
            'uuid': '123-456-789'
        }
        mock_task = Mock()
        mock_task.is_running.return_value = False
        self.module._start_sensor_task(mock_task, [sensor,])
        
        self.module._stop_sensor_task(sensor)
        
        self.assertEqual(len(self.module._tasks_by_device_uuid), 0, 'Task should be deleted when stopped')
        mock_task.stop.assert_called()

    def test_stop_sensor_task_with_unknow_sensor(self):
        self.init_session(True)
        sensor = {
            'name': 'aname',
            'gpios': [{
                'uuid': '987-654-321',
                'gpio': 'GPIO18',
                'pin': 18
            }],
            'uuid': '123-456-789'
        }
        mock_task = Mock()
        self.module._start_sensor_task(mock_task, [sensor,])
        
        self.module._stop_sensor_task({
            'name': 'othersensor',
            'uuid': '666-666-999'
        })
        
        self.assertEqual(len(self.module._tasks_by_device_uuid), 1, 'Task should not be deleted')
        mock_task.stop.assert_not_called()
 
    def test_configure_start_sensor_task(self):
        self.init_session(True)
        self.session.add_mock_command(self.session.make_mock_command('add_gpio', data=self.ADD_GPIO_DATA))

        data = {
            'name': 'aname',
            'gpio': 'GPIO18',
        }
        sensors = self.module.add_sensor('test', 'fake', data)
        added_sensor = sensors[0]

        self.session.respawn_module()
        # we can't check if task is started because addon cannot be loaded during respawn :(




class SensorTests(unittest.TestCase):

    def setUp(self):
        self.sensors = Mock()
        self.sensor = Sensor(self.sensors)

    def test_register_driver(self):
        driver = FakeDriver()
        self.sensor._register_driver(driver)

        self.sensors._register_driver.assert_called_with(driver)
        self.assertEqual(len(self.sensor.drivers), 1)

    def test_has_drivers(self):
        driver = FakeDriver()
        self.sensor._register_driver(driver)

        self.assertTrue(self.sensor.has_drivers())

    def test_get_event(self):
        self.sensor._get_event('dummy.event.test')

        self.sensors._get_event.assert_called_with('dummy.event.test')

    def test_send_command(self):
        self.sensor.send_command('test', 'dummy', {'param': 123}, 5.0)

        self.sensors.send_command.Assert_called_with('test', 'dummy', {'param': 123}, 5.0)

    def test_update_value(self):
        sensor = {
            'name': 'aname',
            'gpios': [{
                'uuid': '987-654-321',
                'gpio': 'GPIO18',
                'pin': 18
            }],
            'uuid': '123-456-789'
        }

        self.sensor.update_value(sensor)

        self.sensors._update_device.assert_called_with(sensor['uuid'], sensor)

    def test_search_device(self):
        self.sensor._search_device('key', 'value')

        self.sensors._search_device.assert_called_with('key', 'value')

    def test_search_devices(self):
        self.sensor._search_devices('key', 'value')

        self.sensors._search_devices.assert_called_with('key', 'value')

    def test_search_by_gpio(self):
        self.sensor._search_by_gpio('GPIO18')

        self.sensors._search_by_gpio.assert_called_with('GPIO18')

    def test_get_device(self):
        self.sensor._get_device('123-456')

        self.sensors._get_device.assert_called_with('123-456')

    def test_get_assigned_gpios(self):
        self.sensor._get_assigned_gpios()

        self.assertTrue(self.sensors._get_assigned_gpios.called)

    def test_delete(self):
        sensor = {
            'name': 'aname',
            'gpios': [{
                'uuid': '987-654-321',
                'gpio': 'GPIO18',
                'pin': 18
            }],
            'uuid': '123-456-789'
        }
        data = self.sensor.delete(sensor)

        self.assertDictEqual(data, {
            'gpios': sensor['gpios'],
            'sensors': [sensor],
        })

    def test_get_task(self):
        sensor = {
            'name': 'aname',
            'gpios': [{
                'uuid': '987-654-321',
                'gpio': 'GPIO18',
                'pin': 18
            }],
            'uuid': '123-456-789'
        }
        mock_task = Mock()
        self.sensor._get_task = mock_task

        # first call should create task singleton
        task = self.sensor.get_task([sensor])
        self.assertEqual(task, mock_task.return_value)
        mock_task.assert_called_with([sensor])

        # next call should return same singleton
        self.assertEqual(self.sensor.get_task([sensor]), mock_task.return_value)

    


class OnewireSensorTests(unittest.TestCase):

    ONEWIRE_PATH = '/tmp/onewire'

    def setUp(self):
        logging.basicConfig(level=LOG_LEVEL, format=u'%(asctime)s %(name)s:%(lineno)d %(levelname)s : %(message)s')
        self.session = session.TestSession(self)
        self.module = self.session.setup(Sensors)

        if not os.path.exists(self.ONEWIRE_PATH):
            os.makedirs(self.ONEWIRE_PATH)

        self.session.add_mock_command(self.session.make_mock_command('get_raspi_gpios', data={
            'error': False,
            'data': {'GPIO18': 56}
        }))
        self.session.start_module(self.module)

    def tearDown(self):
        if os.path.exists(self.ONEWIRE_PATH):
            shutil.rmtree(self.ONEWIRE_PATH)
        self.session.clean()

    def get_addon(self):
        try:
            addon = self.module.addons_by_name['SensorOnewire']
            addon.ONEWIRE_PATH = self.ONEWIRE_PATH
            return addon
        except:
            return None

    def test_sensor_init_ok(self):
        # test addons init
        self.assertTrue('SensorOnewire' in self.module.addons_by_name)

        # test addon method injection
        self.assertTrue(hasattr(self.module, 'get_onewire_devices'))
        self.assertTrue(callable(getattr(self.module, 'get_onewire_devices')))

    def test_driver_registered(self):
        addon = self.get_addon()
        self.assertEqual(len(addon.drivers), 1, 'Onewire driver should be registered')
        self.assertTrue(isinstance(list(addon.drivers.values())[0], OnewireDriver), 'Driver should be OnewireDriver instance')

    def test_read_onewire_temperature(self):
        addon = self.get_addon()
        path = os.path.join(addon.ONEWIRE_PATH, '28-0000054c2ec2', 'w1_slave')
        os.makedirs(os.path.dirname(path))
        with open(path, 'w') as f:
            f.write('7c 01 4b 46 7f ff 04 10 09 : crc=09 YES\n7c 01 4b 46 7f ff 04 10 09 t=23750')
            f.close()

        sensor = {
            'uuid': '123-456-789',
            'type': 'temperature',
            'subtype': 'onewire',
            'device': 'xxxxxxx',
            'path': path,
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
        }
        (c,f) = addon._read_onewire_temperature(sensor)
        self.assertIsNotNone(c, 'Celsius temperature should not be invalid')
        self.assertIsNotNone(f, 'Fahrenheit temperature should not be invalid')
        self.assertEqual(c, 23.75, 'Celsius value is invalid')
        self.assertEqual(f, 74.75, 'Fahrenheit value is invalid')

    def test_read_onewire_temperature_with_celsius_offset(self):
        addon = self.get_addon()
        path = os.path.join(addon.ONEWIRE_PATH, '28-0000054c2ec2', 'w1_slave')
        os.makedirs(os.path.dirname(path))
        with open(path, 'w') as f:
            f.write('7c 01 4b 46 7f ff 04 10 09 : crc=09 YES\n7c 01 4b 46 7f ff 04 10 09 t=23750')
            f.close()

        sensor = {
            'uuid': '123-456-789',
            'type': 'temperature',
            'subtype': 'onewire',
            'device': 'xxxxxxx',
            'path': path,
            'offset': 5,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
        }
        (c,f) = addon._read_onewire_temperature(sensor)
        self.assertEqual(c, 28.75, 'Celsius value is invalid')
        self.assertEqual(f, 83.75, 'Fahrenheit value is invalid')

    def test_read_onewire_temperature_with_fahrenheit_offset(self):
        addon = self.get_addon()
        path = os.path.join(addon.ONEWIRE_PATH, '28-0000054c2ec2', 'w1_slave')
        os.makedirs(os.path.dirname(path))
        with open(path, 'w') as f:
            f.write('7c 01 4b 46 7f ff 04 10 09 : crc=09 YES\n7c 01 4b 46 7f ff 04 10 09 t=23750')
            f.close()

        sensor = {
            'uuid': '123-456-789',
            'type': 'temperature',
            'subtype': 'onewire',
            'device': 'xxxxxxx',
            'path': path,
            'offset': 10,
            'offsetunit': SensorsUtils.TEMP_FAHRENHEIT,
        }
        (c,f) = addon._read_onewire_temperature(sensor)
        self.assertEqual(c, 29.31, 'Celsius value is invalid')
        self.assertEqual(f, 84.75, 'Fahrenheit value is invalid')

    def test_read_onewire_temperature_with_invalid_path(self):
        addon = self.get_addon()
        path = os.path.join(addon.ONEWIRE_PATH, '28-0000054c2ec2', 'w1_slave_invalid')
        sensor = {
            'uuid': '123-456-789',
            'type': 'temperature',
            'subtype': 'onewire',
            'device': 'xxxxxxx',
            'path': path,
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
        }

        (c,f) = addon._read_onewire_temperature(sensor)
        self.assertIsNone(c, 'Celsius must be None')
        self.assertIsNone(f, 'Fahrenheit must be None')

    def test_read_onewire_temperature_with_invalid_onewire_value_returned(self):
        addon = self.get_addon()
        path = os.path.join(addon.ONEWIRE_PATH, '28-0000054c2ec2', 'w1_slave')
        os.makedirs(os.path.dirname(path))
        with open(path, 'w') as f:
            f.write('7c 01 4b 46 7f ff 04 10 09 : crc=09 YES\n7c 01 4b 46 7f ff 04 10 09 t=85000')
            f.close()
        sensor = {
            'uuid': '123-456-789',
            'type': 'temperature',
            'subtype': 'onewire',
            'device': 'xxxxxxx',
            'path': path,
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
        }

        (c,f) = addon._read_onewire_temperature(sensor)

        self.assertIsNone(c, 'Celsius must be None')
        self.assertIsNone(f, 'Fahrenheit must be None')

    def test_read_onewire_temperature_with_invalid_onewire_data_returned(self):
        addon = self.get_addon()
        path = os.path.join(addon.ONEWIRE_PATH, '28-0000054c2ec2', 'w1_slave')
        os.makedirs(os.path.dirname(path))
        with open(path, 'w') as f:
            f.write('7c 01 4b 46 7f ff 04 10 09 : crc=09 YES\n7c 01 4b 46 7f ff 04 10 09 xxxccvvv')
            f.close()
        sensor = {
            'uuid': '123-456-789',
            'type': 'temperature',
            'subtype': 'onewire',
            'device': 'xxxxxxx',
            'path': path,
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
        }

        (c,f) = addon._read_onewire_temperature(sensor)

        self.assertIsNone(c, 'Celsius must be None')
        self.assertIsNone(f, 'Fahrenheit must be None')

    def test_add(self):
        self.session.add_mock_command(self.session.make_mock_command('get_reserved_gpio', data={
            'gpio': 'GPIO18',
            'pin': 18,
            'uuid': '123-456-789'
        }))
        addon = self.get_addon()
        addon._read_onewire_temperature = Mock(return_value=(20, 68))

        res = addon.add('name', 'device', 'path', 120, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertTrue('gpios' in res, 'Gpios should be part of result')
        self.assertEqual(len(res['gpios']), 0, 'Gpios should not contains one value')
        self.assertTrue('sensors' in res, 'Sensors should be part of result')
        self.assertEqual(len(res['sensors']), 1, 'Sensors should contains one value')
        self.assertEqual(addon._read_onewire_temperature.call_count, 1, 'read_onewire_temperature should be called')

        sensor = res['sensors'][0]
        self.assertTrue('name' in sensor, '"name" field must exist in onewire sensor')
        self.assertEqual(sensor['name'], 'name', 'Name should be the same than param')
        self.assertTrue('lastupdate' in sensor, '"lastupdate" field must exist in onewire sensor')
        self.assertTrue('celsius' in sensor, '"celsius" field must exist in onewire sensor')
        self.assertTrue('fahrenheit' in sensor, '"fahrenheit" field must exist in onewire sensor')
        self.assertTrue('type' in sensor, '"type" field must exist in onewire sensor')
        self.assertEqual(sensor['type'], 'temperature', 'Type should be temperature')
        self.assertTrue('subtype' in sensor, '"subtype" field must exist in onewire sensor')
        self.assertEqual(sensor['subtype'], 'onewire', 'Subtype should be onewire')
        self.assertTrue('offset' in sensor, '"offset" field must exist in onewire sensor')
        self.assertEqual(sensor['offset'], 0, 'Offset should be same than param')
        self.assertTrue('device' in sensor, '"device" field must exist in onewire sensor')
        self.assertEqual(sensor['device'], 'device', 'Device should be same than param')
        self.assertTrue('path' in sensor, '"path" field must exist in onewire sensor')
        self.assertEqual(sensor['path'], 'path', 'Path should be same than param')
        self.assertTrue('offsetunit' in sensor, '"offsetunit" field must exist in onewire sensor')
        self.assertEqual(sensor['offsetunit'], SensorsUtils.TEMP_CELSIUS, 'Offset_unit should be same than param')
        self.assertTrue('interval' in sensor, '"interval" field must exist in onewire sensor')
        self.assertEqual(sensor['interval'], 120, 'Interval should be same than param')

    def test_add_invalid_params(self):
        addon = self.get_addon()
        default_search_device = addon._search_device

        with self.assertRaises(MissingParameter) as cm:
            addon.add(None, 'device', 'path', 120, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "name" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('', 'device', 'path', 120, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "name" is invalid (specified="")')
        addon._search_device = lambda k,v: {'name': 'name'}
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('name', 'device', 'path', 120, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Name "name" is already used')
        addon._search_device = default_search_device

        with self.assertRaises(MissingParameter) as cm:
            addon.add('name', None, 'path', 120, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "device" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('name', '', 'path', 120, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "device" is invalid (specified="")')

        with self.assertRaises(MissingParameter) as cm:
            addon.add('name', 'device', None, 120, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "path" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('name', 'device', '', 120, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "path" is invalid (specified="")')

        with self.assertRaises(MissingParameter) as cm:
            addon.add('name', 'device', 'path', None, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "interval" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('name', 'device', 'path', 59, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Interval must be greater or equal than 60')

        with self.assertRaises(MissingParameter) as cm:
            addon.add('name', 'device', 'path', 120, None, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "offset" is missing')

        with self.assertRaises(MissingParameter) as cm:
            addon.add('name', 'device', 'path', 120, 0, None)
        self.assertEqual(cm.exception.message, 'Parameter "offset_unit" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('name', 'device', 'path', 120, 0, '')
        self.assertEqual(cm.exception.message, 'Parameter "offset_unit" is invalid (specified="")')
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('name', 'device', 'path', 120, 0, 'test')
        self.assertEqual(cm.exception.message, 'Offset_unit value must be either "celsius" or "fahrenheit"')

    def test_update(self):
        sensor = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'interval': 120,
            'type': 'temperature',
            'subtype': 'onewire',
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
            'device': 'xxxxxx',
            'path': 'path',
            'celsius': 20,
            'fahrenheit': 68,
        }
        addon = self.get_addon()
        def search_device_found_by_uuid(key, value):
            if key=='uuid':
                return {'name': 'name'}
            return None
        addon._search_device = search_device_found_by_uuid

        res = addon.update(sensor, 'newname', 180, 5, SensorsUtils.TEMP_FAHRENHEIT)
        self.assertTrue('gpios' in res, 'Gpios should be part of result')
        self.assertEqual(len(res['gpios']), 0, 'Gpios should not contains one value')
        self.assertTrue('sensors' in res, 'Sensors should be part of result')
        self.assertEqual(len(res['sensors']), 1, 'Sensors should contains one value')

        updated_sensor = res['sensors'][0]
        self.assertTrue('name' in updated_sensor, '"name" field must exist in onewire sensor')
        self.assertEqual(updated_sensor['name'], 'newname', '"name" should not be updated')
        self.assertTrue('lastupdate' in updated_sensor, '"lastupdate" field must exist in onewire sensor')
        self.assertEqual(sensor['lastupdate'], updated_sensor['lastupdate'], '"lastupdate" should not be updated')
        self.assertTrue('celsius' in updated_sensor, '"celsius" field must exist in onewire sensor')
        self.assertEqual(sensor['celsius'], updated_sensor['celsius'], '"celsius" should not be updated')
        self.assertTrue('fahrenheit' in updated_sensor, '"fahrenheit" field must exist in onewire sensor')
        self.assertEqual(sensor['fahrenheit'], updated_sensor['fahrenheit'], '"fahrenheit" should not be updated')
        self.assertTrue('type' in updated_sensor, '"type" field must exist in onewire sensor')
        self.assertEqual(sensor['type'], updated_sensor['type'], '"type" should not be updated')
        self.assertTrue('subtype' in updated_sensor, '"subtype" field must exist in onewire sensor')
        self.assertEqual(sensor['subtype'], updated_sensor['subtype'], '"subtype" should not be updated')
        self.assertTrue('offset' in updated_sensor, '"offset" field must exist in onewire sensor')
        self.assertEqual(updated_sensor['offset'], 5, '"offset" should be updated')
        self.assertTrue('device' in updated_sensor, '"device" field must exist in onewire sensor')
        self.assertEqual(sensor['device'], updated_sensor['device'], '"offset" should not be updated')
        self.assertTrue('path' in updated_sensor, '"path" field must exist in onewire sensor')
        self.assertEqual(sensor['path'], updated_sensor['path'], '"path" should not be updated')
        self.assertTrue('offsetunit' in updated_sensor, '"offsetunit" field must exist in onewire sensor')
        self.assertEqual(updated_sensor['offsetunit'], SensorsUtils.TEMP_FAHRENHEIT, '"offsetunit" should be updated')
        self.assertTrue('interval' in updated_sensor, '"interval" field must exist in onewire sensor')
        self.assertEqual(updated_sensor['interval'], 180, '"interval" should be updated')

    def test_update_invalid_params(self):
        sensor = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'interval': 120,
            'type': 'temperature',
            'subtype': 'onewire',
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
            'device': 'xxxxxx',
            'path': 'path',
            'celsius': 20,
            'fahrenheit': 68,
        }
        addon = self.get_addon()

        def search_device_found_by_uuid(key, value):
            if key=='uuid':
                return {'name': 'name'}
            return None

        with self.assertRaises(MissingParameter) as cm:
            addon.update(None, 'name', 120, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "sensor" is missing')
        addon._search_device = lambda k,v: None
        with self.assertRaises(InvalidParameter) as cm:
            addon.update(sensor, 'name', 120, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Sensor does not exist')

        addon._search_device = search_device_found_by_uuid
        with self.assertRaises(MissingParameter) as cm:
            addon.update(sensor, None, 120, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "name" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            addon.update(sensor, '', 120, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "name" is invalid (specified="")')
        addon._search_device = lambda k,v: {'name': 'name'}
        with self.assertRaises(InvalidParameter) as cm:
            addon.update(sensor, 'newname', 120, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Name "newname" is already used')
        
        with self.assertRaises(MissingParameter) as cm:
            addon.update(sensor, 'name', None, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "interval" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            addon.update(sensor, 'name', 30, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Interval must be greater or equal than 60')

        with self.assertRaises(MissingParameter) as cm:
            addon.update(sensor, 'name', 120, None, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "offset" is missing')

        with self.assertRaises(MissingParameter) as cm:
            addon.update(sensor, 'name', 120, 0, None)
        self.assertEqual(cm.exception.message, 'Parameter "offset_unit" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            addon.update(sensor, 'name', 120, 0, '')
        self.assertEqual(cm.exception.message, 'Parameter "offset_unit" is invalid (specified="")')
        with self.assertRaises(InvalidParameter) as cm:
            addon.update(sensor, 'name', 120, 0, 'invalid')
        self.assertEqual(cm.exception.message, 'Offset_unit value must be either "celsius" or "fahrenheit"')

    def test_task(self):
        sensor = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'interval': 120,
            'type': 'temperature',
            'subtype': 'onewire',
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
            'device': 'xxxxxx',
            'path': 'path',
            'celsius': 22,
            'fahrenheit': 71,
        }
        addon = self.get_addon()
        mock_read_temp = Mock(return_value=(20, 68))
        addon._read_onewire_temperature = mock_read_temp
        mock_update_value = Mock()
        addon.update_value = mock_update_value

        addon._task(sensor)
        self.assertEqual(mock_read_temp.call_count, 1, 'read_onewire_temperature should be called')
        self.assertEqual(mock_update_value.call_count, 1, 'update_value should be called')
        self.assertEqual(self.session.event_call_count('sensors.temperature.update'), 1, 'Event temperature update should be called')
        self.session.assert_event_called_with('sensors.temperature.update', {
            'celsius': 20,
            'fahrenheit': 68, 
            'sensor': 'name',
            'lastupdate': session.AnyArg()
        })

    def test_task_update_failed(self):
        sensor = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'interval': 120,
            'type': 'temperature',
            'subtype': 'onewire',
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
            'device': 'xxxxxx',
            'path': 'path',
            'celsius': 22,
            'fahrenheit': 71,
        }
        addon = self.get_addon()
        mock_read_temp = Mock(return_value=(20, 68))
        addon._read_onewire_temperature = mock_read_temp
        addon.update_value = Mock(return_value=False)

        try:
            addon._task(sensor)
        except:
            self.fail('Task should not fail')

        self.assertEqual(self.session.event_call_count('sensors.temperature.update'), 1, 'Event temperature update should be called')
        self.session.assert_event_called_with('sensors.temperature.update', {
            'celsius': 20,
            'fahrenheit': 68, 
            'sensor': 'name',
            'lastupdate': session.AnyArg()
        })


    def test_get_task(self):
        sensor = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'interval': 120,
            'type': 'temperature',
            'subtype': 'onewire',
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
            'device': 'xxxxxx',
            'path': 'path',
            'celsius': 22,
            'fahrenheit': 71,
        }
        addon = self.get_addon()

        task = addon.get_task(sensor)
        logging.info('==> %s', task)
        # self.assertEqual(task, sensor.mock_task)
        self.assertTrue(isinstance(task, Task), 'Get_task should returns a Task instance')
        self.assertFalse(task.is_running(), 'Task should not be launched')

    def test_process_event_install_driver(self):
        event = {
            'startup': False,
            'event': 'system.driver.install',
            'params': {
                'drivername': 'onewire',
                'installing': False,
            }
        }
        addon = self.get_addon()
        self.session.add_mock_command(self.session.make_mock_command('reserve_gpio', data=None))
        self.session.add_mock_command(self.session.make_mock_command('delete_gpio', data=None))
        
        addon.process_event(event, None)
        self.assertEqual(self.session.command_call_count('reserve_gpio'), 1, 'Reserve_gpio should be called')
        self.assertEqual(self.session.command_call_count('delete_gpio'), 0, 'Delete_gpio should not be called')

    def test_process_event_install_unhandled_driver(self):
        event = {
            'startup': False,
            'event': 'system.driver.install',
            'params': {
                'drivername': 'unhandled'
            }
        }
        addon = self.get_addon()
        self.session.add_mock_command(self.session.make_mock_command('reserve_gpio', data=None))
        self.session.add_mock_command(self.session.make_mock_command('delete_gpio', data=None))
        
        addon.process_event(event, None)
        self.assertEqual(self.session.command_call_count('reserve_gpio'), 0, 'Reserve_gpio should not be called')
        self.assertEqual(self.session.command_call_count('delete_gpio'), 0, 'Delete_gpio should not be called')

    def test_process_event_uninstall_driver(self):
        event = {
            'startup': False,
            'event': 'system.driver.uninstall',
            'params': {
                'drivername': 'onewire',
                'uninstalling': False,
            }
        }
        addon = self.get_addon()
        self.session.add_mock_command(self.session.make_mock_command('reserve_gpio', data=None))
        self.session.add_mock_command(self.session.make_mock_command('delete_gpio', data=None))
        self.session.add_mock_command(self.session.make_mock_command('get_reserved_gpios', data=[{'gpio': 'GPIO4', 'uuid':'123-456-789'}]))
        
        addon.process_event(event, None)
        self.assertEqual(self.session.command_call_count('reserve_gpio'), 0, 'Reserve_gpio should not be called')
        self.assertEqual(self.session.command_call_count('get_reserved_gpios'), 1, 'Get_reserved_gpio should be called')
        self.assertEqual(self.session.command_call_count('delete_gpio'), 1, 'Delete_gpio should be called')

    def test_process_event_uninstall_unhandled_driver(self):
        event = {
            'startup': False,
            'event': 'system.driver.uninstall',
            'params': {
                'drivername': 'unhandled'
            }
        }
        addon = self.get_addon()
        self.session.add_mock_command(self.session.make_mock_command('reserve_gpio', data=None))
        self.session.add_mock_command(self.session.make_mock_command('delete_gpio', data=None))
        
        addon.process_event(event, None)
        self.assertEqual(self.session.command_call_count('reserve_gpio'), 0, 'Reserve_gpio should not be called')
        self.assertEqual(self.session.command_call_count('delete_gpio'), 0, 'Delete_gpio should not be called')

    def test_get_onewire_devices(self):
        addon = self.get_addon()
        driver = addon.drivers['onewire']
        driver.is_installed = lambda: True
        path = os.path.join(addon.ONEWIRE_PATH, '28-0000054c2ec2', 'w1_slave')
        os.makedirs(os.path.dirname(path))
        path = os.path.join(addon.ONEWIRE_PATH, '28-0000054c2ec4', 'w1_slave')
        os.makedirs(os.path.dirname(path))

        devices = addon.get_onewire_devices()
        self.assertTrue(isinstance(devices, list), 'Get_onewire_devices should returns list')
        self.assertEqual(len(devices), 2, 'Number of returned onewire devices is invalid')
        device = devices[0]
        self.assertTrue('path' in device, 'Field "path" should exists in onewire device')
        self.assertTrue('device' in device, 'Field "device" should exists in onewire device')

    def test_get_onewire_devices_with_driver_not_installed(self):
        addon = self.get_addon()
        driver = addon.drivers['onewire']
        driver.is_installed = lambda: False

        with self.assertRaises(CommandError) as cm:
            addon.get_onewire_devices()
        self.assertEqual(cm.exception.message, 'Onewire driver is not installed')





class MotionGenericSensorTests(unittest.TestCase):

    def setUp(self):
        logging.basicConfig(level=LOG_LEVEL, format=u'%(asctime)s %(name)s:%(lineno)d %(levelname)s : %(message)s')
        self.session = session.TestSession(self)

        self.module = self.session.setup(Sensors)
        self.module.raspi_gpios = {'GPIO18': 56}
        self.session.add_mock_command(self.session.make_mock_command('get_raspi_gpios', data={'GPIO18': 56}))
        self.session.add_mock_command(self.session.make_mock_command('get_assigned_gpios', data=[]))
        self.session.add_mock_command(self.session.make_mock_command('is_gpio_on', data=False))
        self.session.start_module(self.module)

    def tearDown(self):
        self.session.clean()

    def get_addon(self):
        try:
            addon = self.module.addons_by_name['SensorMotionGeneric']
            addon.raspi_gpios = {'GPIO18': 56}
            return addon
        except:
            return None

    def test_sensor_init_ok(self):
        # test addons init
        self.assertTrue('SensorMotionGeneric' in self.module.addons_by_name)

    def test_add(self):
        self.session.add_mock_command(self.session.make_mock_command('get_reserved_gpio', data={
            'gpio': 'GPIO18',
            'pin': 18,
            'uuid': '123-456-789'
        }))
        addon = self.get_addon()

        res = addon.add('name', 'GPIO18', False)

        self.assertTrue('gpios' in res, 'Gpios should be part of result')
        self.assertEqual(len(res['gpios']), 1, 'Gpios should contains value')
        self.assertTrue('sensors' in res, 'Sensors should be part of result')
        self.assertEqual(len(res['sensors']), 1, 'Sensors should contains one value')
        self.assertEqual(self.session.command_call_count('is_gpio_on'), 1, 'Command is_gpio_on should be called')

        sensor = res['sensors'][0]
        logging.debug('Sensor: %s' % sensor)
        self.assertTrue('name' in sensor, '"name" field must exist in generic motion sensor')
        self.assertEqual(sensor['name'], 'name', 'Name should be the same than param')
        self.assertTrue('lastupdate' in sensor, '"lastupdate" field must exist in generic motion sensor')
        self.assertTrue('lastduration' in sensor, '"lastduration" field must exist in generic motion sensor')
        self.assertTrue('type' in sensor, '"type" field must exist in generic motion sensor')
        self.assertEqual(sensor['type'], 'motion', 'Type should be temperature')
        self.assertTrue('subtype' in sensor, '"subtype" field must exist in generic motion sensor')
        self.assertEqual(sensor['subtype'], 'generic', 'Subtype should be generic motion')
        self.assertTrue('on' in sensor, '"on" field should exist in generic motion sensor')
        self.assertTrue(isinstance(sensor['on'], bool), '"on" field should be bool')
        self.assertTrue('inverted' in sensor, '"inverted" field should exist in generic motion sensor')
        self.assertTrue(isinstance(sensor['inverted'], bool), '"inverted" field should be bool')

    def test_add_is_gpio_on_failed(self):
        get_reserved_gpio_mock = self.session.make_mock_command('get_reserved_gpio', data=[{
            'gpio': 'GPIO18',
            'pin': 18,
            'uuid': '123-456-789'
        }])
        self.session.add_mock_command(get_reserved_gpio_mock)
        self.session.set_mock_command_fail('is_gpio_on')
        addon = self.get_addon()

        addon.add('name', 'GPIO18', False)

        self.assertEqual(self.session.command_call_count('is_gpio_on'), 1, 'Command is_gpio_on should be called')

    def test_add_invalid_params(self):
        addon = self.get_addon()
        default_search_device = addon._search_device
        default_get_assigned_gpios = addon._get_assigned_gpios

        with self.assertRaises(MissingParameter) as cm:
            addon.add(None, 'GPIO18', False)
        self.assertEqual(cm.exception.message, 'Parameter "name" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('', 'GPIO18', False)
        self.assertEqual(cm.exception.message, 'Parameter "name" is invalid (specified="")')
        addon._search_device = lambda k,v: {'name': 'name'}
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('name', 'GPIO18', False)
        self.assertEqual(cm.exception.message, 'Name "name" is already used')
        addon._search_device = default_search_device
        addon._get_assigned_gpios = lambda: ['GPIO18']
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('name', 'GPIO18', False)
        self.assertEqual(cm.exception.message, 'Gpio "GPIO18" is already used')
        addon._get_assigned_gpios = default_get_assigned_gpios

        with self.assertRaises(MissingParameter) as cm:
            addon.add('name', None, False)
        self.assertEqual(cm.exception.message, 'Parameter "gpio" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('name', '', False)
        self.assertEqual(cm.exception.message, 'Parameter "gpio" is invalid (specified="")')
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('name', 'GPIO666', False)
        self.assertEqual(cm.exception.message, 'Gpio "GPIO666" does not exist for this raspberry pi')

        with self.assertRaises(MissingParameter) as cm:
            addon.add('name', 'GPIO18', None)
        self.assertEqual(cm.exception.message, 'Parameter "inverted" is missing')

    def test_update(self):
        sensor = {
            'lastupdate': 12345678,
            'lastduration': 123,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'motion',
            'subtype': 'generic',
            'on': False,
            'inverted': False,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}]
        }
        addon = self.get_addon()
        def search_device_found_by_uuid(key, value):
            if key=='uuid':
                return {'name': 'name'}
            return None
        addon._search_device = search_device_found_by_uuid

        res = addon.update(sensor, 'newname', True)
        self.assertTrue('gpios' in res, 'Gpios should be part of result')
        self.assertEqual(len(res['gpios']), 1, 'Gpios should contains value')
        self.assertTrue('sensors' in res, 'Sensors should be part of result')
        self.assertEqual(len(res['sensors']), 1, 'Sensors should contains one value')

        updated_sensor = res['sensors'][0]
        self.assertTrue('name' in sensor, '"name" field must exist in generic motion sensor')
        self.assertEqual(updated_sensor['name'], 'newname', 'Name should be the same than param')
        self.assertTrue('lastupdate' in sensor, '"lastupdate" field must exist in generic motion sensor')
        self.assertTrue('lastduration' in sensor, '"lastduration" field must exist in generic motion sensor')
        self.assertTrue('type' in sensor, '"type" field must exist in generic motion sensor')
        self.assertEqual(sensor['type'], 'motion', 'Type should be temperature')
        self.assertTrue('subtype' in sensor, '"subtype" field must exist in generic motion sensor')
        self.assertEqual(sensor['subtype'], 'generic', 'Subtype should be generic motion')
        self.assertTrue('on' in sensor, '"on" field should exist in generic motion sensor')
        self.assertTrue(isinstance(sensor['on'], bool), '"on" field should be bool')
        self.assertTrue('inverted' in sensor, '"inverted" field should exist in generic motion sensor')
        self.assertTrue(isinstance(sensor['inverted'], bool), '"inverted" field should be bool')
        self.assertEqual(sensor['inverted'], True, '"inverted" field should be True')

    def test_update_invalid_params(self):
        sensor = {
            'lastupdate': 12345678,
            'lastduration': 123,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'motion',
            'subtype': 'generic',
            'on': False,
            'inverted': False,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}]
        }
        addon = self.get_addon()
        default_search_device = addon._search_device

        def search_device_not_found_by_uuid(key, value):
            if key=='uuid':
                return None
            return {'name': 'name'}

        with self.assertRaises(MissingParameter) as cm:
            addon.update(None, 'name', False)
        self.assertEqual(cm.exception.message, 'Parameter "sensor" is missing')

        addon._search_device = Mock(return_value=sensor)
        with self.assertRaises(MissingParameter) as cm:
            addon.update(sensor, None, False)
        self.assertEqual(cm.exception.message, 'Parameter "name" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            addon.update(sensor, '', False)
        self.assertEqual(cm.exception.message, 'Parameter "name" is invalid (specified="")')
        addon._search_device = Mock(return_value={'name': 'name'})
        with self.assertRaises(InvalidParameter) as cm:
            addon.update(sensor, 'newname', False)
        self.assertEqual(cm.exception.message, 'Name "newname" is already used')
        addon._search_device = default_search_device

        addon._search_device = search_device_not_found_by_uuid
        with self.assertRaises(InvalidParameter) as cm:
            addon.update(sensor, 'name', False)
        self.assertEqual(cm.exception.message, 'Sensor does not exist')
        addon._search_device = default_search_device

        addon._search_device = Mock(return_value=sensor)
        with self.assertRaises(MissingParameter) as cm:
            addon.update(sensor, 'name', None)
        self.assertEqual(cm.exception.message, 'Parameter "inverted" is missing')

    def test_get_task(self):
        addon = self.get_addon()

        task = addon.get_task(None)
        self.assertTrue(task is None, 'No task should be returned')

    def test_process_event_gpio_on(self):
        event = {
            'startup': False,
            'event': 'gpios.gpio.on',
            'params': {
                'uuid': '123-456-789'
            }
        }
        sensor = {
            'lastupdate': 12345678,
            'lastduration': 123,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'motion',
            'subtype': 'generic',
            'on': False,
            'inverted': False,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}]
        }
        addon = self.get_addon()
                
        addon.process_event(event, sensor)
        self.session.assert_event_called('sensors.motion.on')
        self.assertEqual(self.session.event_call_count('sensors.motion.off'), 0, 'Sensors.motion.off should not be called')
        self.session.assert_event_called_with('sensors.motion.on', {
            'lastupdate': session.AnyArg(),
            'sensor': 'name',
        })

    def test_process_event_gpio_on_not_triggered(self):
        event = {
            'startup': False,
            'event': 'gpios.gpio.on',
            'params': {
                'uuid': '123-456-789',
                'duration': 666,
            }
        }
        sensor = {
            'lastupdate': 12345678,
            'lastduration': 123,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'motion',
            'subtype': 'generic',
            'on': True,
            'inverted': False,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}]
        }
        addon = self.get_addon()
                
        addon.process_event(event, sensor)
        self.assertEqual(self.session.event_call_count('sensors.motion.on'), 0, 'Sensors.motion.on event not should be called')
        self.assertEqual(self.session.event_call_count('sensors.motion.off'), 0, 'Sensors.motion.off should not be called')

    def test_process_event_gpio_off(self):
        event = {
            'startup': False,
            'event': 'gpios.gpio.off',
            'params': {
                'uuid': '123-456-789',
                'duration': 666,
            }
        }
        sensor = {
            'lastupdate': 12345678,
            'lastduration': 123,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'motion',
            'subtype': 'generic',
            'on': True,
            'inverted': False,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}]
        }
        addon = self.get_addon()
                
        addon.process_event(event, sensor)
        self.assertEqual(self.session.event_call_count('sensors.motion.on'), 0, 'Sensors.motion.on event not should be called')
        self.assertEqual(self.session.event_call_count('sensors.motion.off'), 1, 'Sensors.motion.off should be called')
        self.session.assert_event_called_with('sensors.motion.off', {
            'lastupdate': session.AnyArg(),
            'sensor': 'name',
            'duration': 666
        })

    def test_process_event_gpio_off_not_triggered(self):
        event = {
            'startup': False,
            'event': 'gpios.gpio.off',
            'params': {
                'uuid': '123-456-789',
                'duration': 666,
            }
        }
        sensor = {
            'lastupdate': 12345678,
            'lastduration': 123,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'motion',
            'subtype': 'generic',
            'on': False,
            'inverted': False,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}]
        }
        addon = self.get_addon()
                
        addon.process_event(event, sensor)
        self.assertEqual(self.session.event_call_count('sensors.motion.on'), 0, 'Sensors.motion.on event not should be called')
        self.assertEqual(self.session.event_call_count('sensors.motion.off'), 0, 'Sensors.motion.off should not be called')





class Dht22SensorTests(unittest.TestCase):

    def setUp(self):
        logging.basicConfig(level=LOG_LEVEL, format=u'%(asctime)s %(name)s:%(lineno)d %(levelname)s : %(message)s')
        self.session = session.TestSession(self)

        self.module = self.session.setup(Sensors)
        self.module.raspi_gpios = {'GPIO18': 56}
        self.session.add_mock_command(self.session.make_mock_command('get_raspi_gpios', data={'GPIO18': 56}))
        self.session.add_mock_command(self.session.make_mock_command('get_assigned_gpios', data=[]))
        self.session.start_module(self.module)

    def tearDown(self):
        self.session.clean()

    def get_addon(self):
        try:
            addon = self.module.addons_by_name['SensorDht22']
            addon.raspi_gpios = {'GPIO18': 56}
            return addon
        except:
            return None

    def test_sensor_init_ok(self):
        # test addons init
        self.assertTrue('SensorDht22' in self.module.addons_by_name)

    def test_get_dht22_devices(self):
        addon = self.get_addon()
        addon._search_devices = lambda k,v: [
            {
                'uuid': '123-456-789',
                'type': 'temperature',
                'subtype': 'dht22',
                'name': 'test'
            },
            {
                'uuid': '456-789-123',
                'type': 'motion',
                'subtype': 'invalid',
                'name': 'test'
            },
            {
                'uuid': '789-456-132',
                'type': 'humidity',
                'subtype': 'dht22',
                'name': 'test'
            },
            {
                'uuid': '789-123-456',
                'type': 'humidity',
                'subtype': 'invalid',
                'name': 'noname'
            },
        ]

        (temp, hum) = addon._get_dht22_devices('name')
        self.assertIsNotNone(temp, 'Temperature device should be found')
        self.assertIsNotNone(hum, 'Humidity device should be found')
        self.assertEqual(temp['name'], 'test', 'Temperature device should have searched name')
        self.assertEqual(hum['name'], 'test', 'Humidity device should have searched name')
        self.assertEqual(temp['type'], 'temperature', 'Temperature device should have temperature type')
        self.assertEqual(hum['type'], 'humidity', 'Humidity device should have humidity type')
        self.assertEqual(temp['subtype'], 'dht22', 'Temperature device should have dht22 subtype')
        self.assertEqual(hum['subtype'], 'dht22', 'Humidity device should have dht22 subtype')

    def test_read_dht22(self):
        addon = self.get_addon()
        sensor = {
            'uuid': '789-456-132',
            'type': 'humidity',
            'subtype': 'dht22',
            'name': 'test',
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
        }
        addon._execute_command = Mock(return_value={
            'error': '',
            'celsius': 20,
            'humidity': 48,
        })

        (c, f, h) = addon._read_dht22(sensor)
        self.assertEqual(c, 20, 'Celsius value is invalid')
        self.assertEqual(f, 68, 'Fahrenheit value is invalid')
        self.assertEqual(h, 48, 'Humidity value is invalid')

    def test_read_dht22_command_error(self):
        addon = self.get_addon()
        sensor = {
            'uuid': '789-456-132',
            'type': 'humidity',
            'subtype': 'dht22',
            'name': 'test',
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
        }
        addon._execute_command = Mock(return_value={
            'error': 'error occured',
            'celsius': 20,
            'humidity': 48,
        })

        (c, f, h) = addon._read_dht22(sensor)
        self.assertIsNone(c, 'Celsius value should be None')
        self.assertIsNone(f, 'Fahrenheit value should be None')
        self.assertIsNone(h, 'Humidity value should be None')

    def test_read_dht22_exception_occured(self):
        addon = self.get_addon()
        sensor = {
            'uuid': '789-456-132',
            'type': 'humidity',
            'subtype': 'dht22',
            'name': 'test',
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
        }
        addon._execute_command = Mock(side_effect=Exception('Test exception'))

        (c, f, h) = addon._read_dht22(sensor)
        self.assertIsNone(c, 'Celsius value should be None')
        self.assertIsNone(f, 'Fahrenheit value should be None')
        self.assertIsNone(h, 'Humidity value should be None')

    def test_add(self):
        self.session.add_mock_command(self.session.make_mock_command('get_assigned_gpios', data={
            'error': False,
            'msg': None,
            'data': [],
        }))
        addon = self.get_addon()

        res = addon.add('name', 'GPIO18', 100, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertTrue('gpios' in res, 'Gpios should be part of result')
        self.assertEqual(len(res['gpios']), 1, 'Gpios should contains value')
        self.assertTrue('sensors' in res, 'Sensors should be part of result')
        self.assertEqual(len(res['sensors']), 2, 'Sensors should contains two values')

        temp = res['sensors'][0]
        hum = res['sensors'][1]

        self.assertTrue('name' in temp, '"name" field must exist in dht22 sensor')
        self.assertEqual(temp['name'], 'name', 'Name should be the same than param')
        self.assertTrue('lastupdate' in temp, '"lastupdate" field must exist in dht22 sensor')
        self.assertTrue('type' in temp, '"type" field must exist in dht22 sensor')
        self.assertEqual(temp['type'], 'temperature', 'Type should be temperature')
        self.assertTrue('subtype' in temp, '"subtype" field must exist in dht22 sensor')
        self.assertEqual(temp['subtype'], 'dht22', 'Subtype should be dht22')
        self.assertTrue('celsius' in temp, '"celsius" field should exist in dht22 sensor')
        # TODO can be tested once dht22 bin updated self.assertTrue(isinstance(temp['celsius'], float), '"celsius" field should be float')
        self.assertTrue('fahrenheit' in temp, '"fahrenheit" field should exist in dht22 sensor')
        # TODO can be tested once dht22 bin updated self.assertTrue(isinstance(temp['fahrenheit'], float), '"fahrenheit" field should be float')
        self.assertTrue('offset' in temp, '"offset" field should exist in generic motion sensor')
        self.assertTrue(isinstance(temp['offset'], int), '"offset" field should be int')
        self.assertEqual(temp['offset'], 0, 'Invalid "offset" value')
        self.assertTrue('offsetunit' in temp, '"offsetunit" field should exist in generic motion sensor')
        self.assertTrue(isinstance(temp['offsetunit'], str), '"offsetunit" field should be int')
        self.assertEqual(temp['offsetunit'], SensorsUtils.TEMP_CELSIUS, 'Invalid "offsetunit" value')
        self.assertTrue('interval' in temp, '"interval" field must exist in dht22 sensor')
        self.assertEqual(temp['interval'], 100, 'Interval should be 100')

        self.assertTrue('name' in hum, '"name" field must exist in dht22 sensor')
        self.assertEqual(hum['name'], 'name', 'Name should be the same than param')
        self.assertTrue('lastupdate' in hum, '"lastupdate" field must exist in dht22 sensor')
        self.assertTrue('type' in hum, '"type" field must exist in dht22 sensor')
        self.assertEqual(hum['type'], 'humidity', 'Type should be humidity')
        self.assertTrue('subtype' in hum, '"subtype" field must exist in dht22 sensor')
        self.assertEqual(hum['subtype'], 'dht22', 'Subtype should be dht22')
        self.assertTrue('humidity' in hum, '"fahrenheit" field should exist in dht22 sensor')
        #TODO can be tested once dht22 bin updated self.assertTrue(isinstance(hum['humidity'], float), '"fahrenheit" field should be float')
        self.assertTrue('interval' in hum, '"interval" field must exist in dht22 sensor')
        self.assertEqual(hum['interval'], 100, 'Interval should be 100')

    def test_add_invalid_params(self):
        addon = self.get_addon()
        default_search_device = addon._search_device
        default_get_assigned_gpios = addon._get_assigned_gpios

        with self.assertRaises(MissingParameter) as cm:
            addon.add(None, 'GPIO18', 100, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "name" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('', 'GPIO18', 100, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "name" is invalid (specified="")')
        addon._search_device = Mock(return_value={'name': 'name'})
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('name', 'GPIO18', 100, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Name "name" is already used')
        addon._search_device = default_search_device

        addon._get_assigned_gpios = Mock(return_value=['GPIO18'])
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('name', 'GPIO18', 100, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Gpio "GPIO18" is already used')
        addon._get_assigned_gpios = default_get_assigned_gpios
        with self.assertRaises(MissingParameter) as cm:
            addon.add('name', None, 100, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "gpio" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('name', '', 100, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "gpio" is invalid (specified="")')
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('name', 'GPIO666', 100, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Gpio "GPIO666" does not exist for this raspberry pi')

        with self.assertRaises(MissingParameter) as cm:
            addon.add('name', 'GPIO18', None, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "interval" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('name', 'GPIO18', 59, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Interval must be greater or equal than 60')

        with self.assertRaises(MissingParameter) as cm:
            addon.add('name', 'GPIO18', 100, None, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "offset" is missing')

        with self.assertRaises(MissingParameter) as cm:
            addon.add('name', 'GPIO18', 100, 0, None)
        self.assertEqual(cm.exception.message, 'Parameter "offset_unit" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('name', 'GPIO18', 100, 0, '')
        self.assertEqual(cm.exception.message, 'Parameter "offset_unit" is invalid (specified="")')
        with self.assertRaises(InvalidParameter) as cm:
            addon.add('name', 'GPIO18', 100, 0, 'invalid')
        self.assertEqual(cm.exception.message, 'Offset_unit value must be either "celsius" or "fahrenheit"')

    def test_update_from_temperature_sensor(self):
        self.session.add_mock_command(self.session.make_mock_command('get_assigned_gpios', data={
            'error': False,
            'msg': None,
            'data': [],
        }))
        temp = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'temperature',
            'subtype': 'dht22',
            'interval': 100,
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}],
            'celsius': 20,
            'fahrenheit': 68,
        }
        hum = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'humidity',
            'subtype': 'dht22',
            'interval': 100,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}],
            'humidity': 58,
        }
        addon = self.get_addon()
        def search_device_found_by_uuid(key, value):
            if key=='uuid':
                return {'name': 'name'}
            return None
        addon._search_device = search_device_found_by_uuid
        addon._get_dht22_devices = Mock(return_value=(temp, hum))

        res = addon.update(temp, 'newname', 120, 5, SensorsUtils.TEMP_FAHRENHEIT)
        self.assertTrue('gpios' in res, 'Gpios should be part of result')
        self.assertEqual(len(res['gpios']), 1, 'Gpios should contains value')
        self.assertTrue('sensors' in res, 'Sensors should be part of result')
        self.assertEqual(len(res['sensors']), 2, 'Sensors should contains two values')

        temp = res['sensors'][0]
        hum = res['sensors'][1]

        self.assertTrue('name' in temp, '"name" field must exist in dht22 sensor')
        self.assertEqual(temp['name'], 'newname', 'Name should be the same than param')
        self.assertTrue('lastupdate' in temp, '"lastupdate" field must exist in dht22 sensor')
        self.assertTrue('type' in temp, '"type" field must exist in dht22 sensor')
        self.assertEqual(temp['type'], 'temperature', 'Type should be temperature')
        self.assertTrue('subtype' in temp, '"subtype" field must exist in dht22 sensor')
        self.assertEqual(temp['subtype'], 'dht22', 'Subtype should be dht22')
        self.assertTrue('celsius' in temp, '"celsius" field should exist in dht22 sensor')
        #TODO can be tested once dht22 bin updated self.assertTrue(isinstance(temp['celsius'], float), '"celsius" field should be float')
        self.assertTrue('fahrenheit' in temp, '"fahrenheit" field should exist in dht22 sensor')
        #TODO can be tested once dht22 bin updated self.assertTrue(isinstance(temp['fahrenheit'], float), '"fahrenheit" field should be float')
        self.assertTrue('offset' in temp, '"offset" field should exist in generic motion sensor')
        self.assertTrue(isinstance(temp['offset'], int), '"offset" field should be int')
        self.assertEqual(temp['offset'], 5, 'Invalid "offset" value')
        self.assertTrue('offsetunit' in temp, '"offsetunit" field should exist in generic motion sensor')
        self.assertTrue(isinstance(temp['offsetunit'], str), '"offsetunit" field should be int')
        self.assertEqual(temp['offsetunit'], SensorsUtils.TEMP_FAHRENHEIT, 'Invalid "offsetunit" value')
        self.assertTrue('interval' in temp, '"interval" field must exist in dht22 sensor')
        self.assertEqual(temp['interval'], 120, 'Interval should be 120')

        self.assertTrue('name' in hum, '"name" field must exist in dht22 sensor')
        self.assertEqual(hum['name'], 'newname', 'Name should be the same than param')
        self.assertTrue('lastupdate' in hum, '"lastupdate" field must exist in dht22 sensor')
        self.assertTrue('type' in hum, '"type" field must exist in dht22 sensor')
        self.assertEqual(hum['type'], 'humidity', 'Type should be humidity')
        self.assertTrue('subtype' in hum, '"subtype" field must exist in dht22 sensor')
        self.assertEqual(hum['subtype'], 'dht22', 'Subtype should be dht22')
        self.assertTrue('humidity' in hum, '"fahrenheit" field should exist in dht22 sensor')
        #TODO can be tested once dht22 bin updated self.assertTrue(isinstance(hum['humidity'], float), '"fahrenheit" field should be float')
        self.assertTrue('interval' in hum, '"interval" field must exist in dht22 sensor')
        self.assertEqual(hum['interval'], 120, 'Interval should be 120')

    def test_update_from_humidity_sensor(self):
        self.session.add_mock_command(self.session.make_mock_command('get_assigned_gpios', data={
            'error': False,
            'msg': None,
            'data': [],
        }))
        temp = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'temperature',
            'subtype': 'dht22',
            'interval': 100,
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}],
            'celsius': 20,
            'fahrenheit': 68,
        }
        hum = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'humidity',
            'subtype': 'dht22',
            'interval': 100,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}],
            'humidity': 58,
        }
        addon = self.get_addon()
        def search_device_found_by_uuid(key, value):
            if key=='uuid':
                return {'name': 'name'}
            return None
        addon._search_device = search_device_found_by_uuid
        addon._get_dht22_devices = lambda n: (temp, hum)

        res = addon.update(hum, 'newname', 120, 5, SensorsUtils.TEMP_FAHRENHEIT)
        self.assertTrue('gpios' in res, 'Gpios should be part of result')
        self.assertEqual(len(res['gpios']), 1, 'Gpios should contains value')
        self.assertTrue('sensors' in res, 'Sensors should be part of result')
        self.assertEqual(len(res['sensors']), 2, 'Sensors should contains two values')

        temp = res['sensors'][0]
        hum = res['sensors'][1]

        self.assertTrue('name' in temp, '"name" field must exist in dht22 sensor')
        self.assertEqual(temp['name'], 'newname', 'Name should be the same than param')
        self.assertTrue('lastupdate' in temp, '"lastupdate" field must exist in dht22 sensor')
        self.assertTrue('type' in temp, '"type" field must exist in dht22 sensor')
        self.assertEqual(temp['type'], 'temperature', 'Type should be temperature')
        self.assertTrue('subtype' in temp, '"subtype" field must exist in dht22 sensor')
        self.assertEqual(temp['subtype'], 'dht22', 'Subtype should be dht22')
        self.assertTrue('celsius' in temp, '"celsius" field should exist in dht22 sensor')
        #TODO can be tested once dht22 bin updated self.assertTrue(isinstance(temp['celsius'], float), '"celsius" field should be float')
        self.assertTrue('fahrenheit' in temp, '"fahrenheit" field should exist in dht22 sensor')
        #TODO can be tested once dht22 bin updated self.assertTrue(isinstance(temp['fahrenheit'], float), '"fahrenheit" field should be float')
        self.assertTrue('offset' in temp, '"offset" field should exist in generic motion sensor')
        self.assertTrue(isinstance(temp['offset'], int), '"offset" field should be int')
        self.assertEqual(temp['offset'], 5, 'Invalid "offset" value')
        self.assertTrue('offsetunit' in temp, '"offsetunit" field should exist in generic motion sensor')
        self.assertTrue(isinstance(temp['offsetunit'], str), '"offsetunit" field should be int')
        self.assertEqual(temp['offsetunit'], SensorsUtils.TEMP_FAHRENHEIT, 'Invalid "offsetunit" value')
        self.assertTrue('interval' in temp, '"interval" field must exist in dht22 sensor')
        self.assertEqual(temp['interval'], 120, 'Interval should be 120')

        self.assertTrue('name' in hum, '"name" field must exist in dht22 sensor')
        self.assertEqual(hum['name'], 'newname', 'Name should be the same than param')
        self.assertTrue('lastupdate' in hum, '"lastupdate" field must exist in dht22 sensor')
        self.assertTrue('type' in hum, '"type" field must exist in dht22 sensor')
        self.assertEqual(hum['type'], 'humidity', 'Type should be humidity')
        self.assertTrue('subtype' in hum, '"subtype" field must exist in dht22 sensor')
        self.assertEqual(hum['subtype'], 'dht22', 'Subtype should be dht22')
        self.assertTrue('humidity' in hum, '"fahrenheit" field should exist in dht22 sensor')
        #TODO can be tested once dht22 bin updated self.assertTrue(isinstance(hum['humidity'], float), '"fahrenheit" field should be float')
        self.assertTrue('interval' in hum, '"interval" field must exist in dht22 sensor')
        self.assertEqual(hum['interval'], 120, 'Interval should be 120')

    def test_update_invalid_params(self):
        temp = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'temperature',
            'subtype': 'dht22',
            'interval': 100,
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}],
            'celsius': 20,
            'fahrenheit': 68,
        }
        addon = self.get_addon()
        default_search_device = addon._search_device

        addon = self.get_addon()
        default_search_device = addon._search_device

        with self.assertRaises(MissingParameter) as cm:
            addon.update(None, 'name', 100, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "sensor" is missing')

        with self.assertRaises(MissingParameter) as cm:
            addon.update(temp, None, 100, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "name" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            addon.update(temp, '', 100, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "name" is invalid (specified="")')
        addon._search_device = Mock(return_value={'name': 'name'})
        with self.assertRaises(InvalidParameter) as cm:
            addon.update(temp, 'newname', 100, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Name "newname" is already used')
        addon._search_device = default_search_device

        with self.assertRaises(MissingParameter) as cm:
            addon.update(temp, 'name', None, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "interval" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            addon.update(temp, 'name', 59, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Interval must be greater or equal than 60')

        with self.assertRaises(MissingParameter) as cm:
            addon.update(temp, 'name', 100, None, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "offset" is missing')

        with self.assertRaises(MissingParameter) as cm:
            addon.update(temp, 'name', 100, 0, None)
        self.assertEqual(cm.exception.message, 'Parameter "offset_unit" is missing')
        with self.assertRaises(InvalidParameter) as cm:
            addon.update(temp, 'name', 100, 0, '')
        self.assertEqual(cm.exception.message, 'Parameter "offset_unit" is invalid (specified="")')
        with self.assertRaises(InvalidParameter) as cm:
            addon.update(temp, 'name', 100, 0, 'invalid')
        self.assertEqual(cm.exception.message, 'Offset_unit value must be either "celsius" or "fahrenheit"')

    def test_delete(self):
        temp = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'temperature',
            'subtype': 'dht22',
            'interval': 100,
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}],
            'celsius': 20,
            'fahrenheit': 68,
        }
        hum = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'humidity',
            'subtype': 'dht22',
            'interval': 100,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}],
            'humidity': 58,
        }
        self.session.add_mock_command(self.session.make_mock_command('get_assigned_gpios', data={
            'error': False,
            'msg': None,
            'data': [],
        }))
        addon = self.get_addon()
        addon._get_dht22_devices = lambda n: (temp, hum)

        res = addon.delete(temp)
        self.assertTrue('gpios' in res, 'Gpios should be part of result')
        self.assertEqual(len(res['gpios']), 1, 'Gpios should contains value')
        self.assertTrue('sensors' in res, 'Sensors should be part of result')
        self.assertEqual(len(res['sensors']), 2, 'Sensors should contains two values')

        temp = res['sensors'][0]
        hum = res['sensors'][1]
        self.assertIsNotNone(temp, 'Temperature sensor should be returned')
        self.assertIsNotNone(temp, 'Humidity sensor should be returned')

    def test_delete_invalid_params(self):
        addon = self.get_addon()

        with self.assertRaises(MissingParameter) as cm:
            addon.update(None, 'name', 100, 0, SensorsUtils.TEMP_CELSIUS)
        self.assertEqual(cm.exception.message, 'Parameter "sensor" is missing')

    def test_get_task(self):
        temp = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'temperature',
            'subtype': 'dht22',
            'interval': 100,
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}],
            'celsius': 20,
            'fahrenheit': 68,
        }
        hum = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'humidity',
            'subtype': 'dht22',
            'interval': 100,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}],
            'humidity': 58,
        }
        self.session.add_mock_command(self.session.make_mock_command('get_assigned_gpios', data={
            'error': False,
            'msg': None,
            'data': [],
        }))
        addon = self.get_addon()
        addon._get_dht22_devices = lambda n: (temp, hum)

        task = addon.get_task(temp)
        self.assertTrue(isinstance(task, Task), 'Get_task should returns a Task instance')
        self.assertFalse(task.is_running(), 'Task should not be launched')

    def test_task(self):
        temp = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'temperature',
            'subtype': 'dht22',
            'interval': 100,
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}],
            'celsius': 20,
            'fahrenheit': 68,
        }
        hum = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'humidity',
            'subtype': 'dht22',
            'interval': 100,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}],
            'humidity': 58,
        }
        addon = self.get_addon()
        addon._read_dht22 = Mock(return_value=(30, 86, 69))
        mock_update_value = Mock()
        addon.update_value = mock_update_value

        addon._task(temp, hum)
        self.assertEqual(mock_update_value.call_count, 2, 'Update_value should be called')
        self.assertEqual(self.session.event_call_count('sensors.temperature.update'), 1, 'Temperature event should be called')
        self.assertEqual(self.session.event_call_count('sensors.humidity.update'), 1, 'Humidity event should be called')

    def test_task_temperature_only(self):
        temp = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'temperature',
            'subtype': 'dht22',
            'interval': 100,
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}],
            'celsius': 20,
            'fahrenheit': 68,
        }
        addon = self.get_addon()
        addon._read_dht22 = lambda s: (30, 86, 69)
        mock_update_value = Mock()
        addon.update_value = mock_update_value

        addon._task(temp, None)
        self.assertEqual(mock_update_value.call_count, 1, 'Update_value should be called')
        self.assertEqual(self.session.event_call_count('sensors.temperature.update'), 1, 'Temperature event should be called')
        self.assertEqual(self.session.event_call_count('sensors.humidity.update'), 0, 'Humidity event should not be called')
        self.session.assert_event_called_with('sensors.temperature.update', {
            'celsius': 30,
            'fahrenheit': 86,
            'sensor': 'name',
            'lastupdate': session.AnyArg()
        })

    def test_task_humidity_only(self):
        hum = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'humidity',
            'subtype': 'dht22',
            'interval': 100,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}],
            'humidity': 58,
        }
        addon = self.get_addon()
        addon._read_dht22 = Mock(return_value=(30, 86, 69))
        mock_update_value = Mock()
        addon.update_value = mock_update_value

        addon._task(None, hum)
        self.assertEqual(mock_update_value.call_count, 1, 'Update_value should be called')
        self.assertEqual(self.session.event_call_count('sensors.temperature.update'), 0, 'Temperature event should not be called')
        self.assertEqual(self.session.event_call_count('sensors.humidity.update'), 1, 'Humidity event should be called')
        self.session.assert_event_called_with('sensors.humidity.update', {
            'humidity': 69,
            'sensor': 'name',
            'lastupdate': session.AnyArg()
        })

    def test_task_no_data_read(self):
        temp = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'temperature',
            'subtype': 'dht22',
            'interval': 100,
            'offset': 0,
            'offsetunit': SensorsUtils.TEMP_CELSIUS,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}],
            'celsius': 20,
            'fahrenheit': 68,
        }
        hum = {
            'lastupdate': 12345678,
            'uuid': '123-456-789',
            'name': 'name',
            'type': 'humidity',
            'subtype': 'dht22',
            'interval': 100,
            'gpios': [{'gpio':'GPIO18', 'pin':18, 'uuid':'123-456-789'}],
            'humidity': 58,
        }
        addon = self.get_addon()
        addon._read_dht22 = Mock(return_value=(None, None, None))
        addon.update_value = Mock()

        addon._task(temp, hum)

        self.assertFalse(addon.update_value.called)



class TestsOnewireDriver(unittest.TestCase):

    def setUp(self):
        logging.basicConfig(level=LOG_LEVEL, format=u'%(asctime)s %(name)s:%(lineno)d %(levelname)s : %(message)s')
        self.lib = lib.TestLib()

    def init_session(self):
        self.fs = Mock()
        self.driver = OnewireDriver()
        self.driver.cleep_filesystem = Mock()
        self.driver._on_registered()

    @patch('backend.onewiredriver.ConfigTxt')
    @patch('backend.onewiredriver.EtcModules')
    def test_install(self, mock_etcmodules, mock_configtxt):
        self.init_session()

        self.assertTrue(self.driver._install())

        mock_configtxt.return_value.enable_onewire.assert_called()
        mock_etcmodules.return_value.enable_module.assert_called_with('w1-gpio')

    @patch('backend.onewiredriver.ConfigTxt')
    @patch('backend.onewiredriver.EtcModules')
    def test_install_failed(self, mock_etcmodules, mock_configtxt):
        self.init_session()

        mock_etcmodules.return_value.enable_module.return_value = False
        with self.assertRaises(Exception) as cm:
            self.driver._install()
        self.assertEqual(str(cm.exception), 'Unable to install onewire driver')

        mock_configtxt.return_value.enable_onewire.return_value = False
        with self.assertRaises(Exception) as cm:
            self.driver._install()
        self.assertEqual(str(cm.exception), 'Unable to install onewire driver')
        
    @patch('backend.onewiredriver.ConfigTxt')
    @patch('backend.onewiredriver.EtcModules')
    def test_uninstall(self, mock_etcmodules, mock_configtxt):
        self.init_session()

        try:
            self.driver._uninstall()
        except:
            self.fail('Uninstall should not fail')

        self.assertFalse(mock_configtxt.return_value.enable_i2c.called)
        self.assertFalse(mock_etcmodules.return_value.enable_module.called)
        mock_configtxt.return_value.disable_onewire.assert_called()
        mock_etcmodules.return_value.disable_module.assert_called_with('w1-gpio')

    @patch('backend.onewiredriver.ConfigTxt')
    @patch('backend.onewiredriver.EtcModules')
    def test_uninstall_failed(self, mock_etcmodules, mock_configtxt):
        self.init_session()

        mock_etcmodules.return_value.disable_module.return_value = False
        with self.assertRaises(Exception) as cm:
            self.driver._uninstall()
        self.assertEqual(str(cm.exception), 'Unable to uninstall onewire driver')

        mock_configtxt.return_value.disable_onewire.return_value = False
        with self.assertRaises(Exception) as cm:
            self.driver._uninstall()
        self.assertEqual(str(cm.exception), 'Unable to uninstall onewire driver')

    @patch('backend.onewiredriver.ConfigTxt')
    @patch('backend.onewiredriver.EtcModules')
    def test_is_installed_installed(self, mock_etcmodules, mock_configtxt):
        self.init_session()
        mock_configtxt.return_value.is_onewire_enabled.return_value = True
        mock_etcmodules.return_value.is_module_enabled.return_value = True

        self.assertTrue(self.driver.is_installed())

    @patch('backend.onewiredriver.ConfigTxt')
    @patch('backend.onewiredriver.EtcModules')
    def test_is_installed_not_installed(self, mock_etcmodules, mock_configtxt):
        self.init_session()

        mock_configtxt.return_value.is_onewire_enabled.return_value = False
        mock_etcmodules.return_value.is_module_enabled.return_value = True
        self.assertFalse(self.driver.is_installed())

        mock_configtxt.return_value.is_onewire_enabled.return_value = True
        mock_etcmodules.return_value.is_module_enabled.return_value = False
        self.assertFalse(self.driver.is_installed())

        mock_configtxt.return_value.is_onewire_enabled.return_value = False
        mock_etcmodules.return_value.is_module_enabled.return_value = False
        self.assertFalse(self.driver.is_installed())

    def test_require_reboot(self):
        self.init_session()

        self.assertTrue(self.driver.require_reboot())



class TestsSensorsHumidityUpdateEvent(unittest.TestCase):

    def setUp(self):
        logging.basicConfig(level=LOG_LEVEL, format=u'%(asctime)s %(name)s:%(lineno)d %(levelname)s : %(message)s')
        self.session = session.TestSession(self)
        self.event = self.session.setup_event(SensorsHumidityUpdateEvent)

    @unittest.skip('need cleep 0.0.27')
    def test_event_params(self):
        self.assertCountEqual(self.event.EVENT_PARAMS, ['sensor', 'lastupdate', 'humidity'])





class TestsSensorsTemperatureUpdateEvent(unittest.TestCase):

    def setUp(self):
        logging.basicConfig(level=LOG_LEVEL, format=u'%(asctime)s %(name)s:%(lineno)d %(levelname)s : %(message)s')
        self.session = session.TestSession(self)
        self.event = self.session.setup_event(SensorsTemperatureUpdateEvent)

    @unittest.skip('need cleep 0.0.27')
    def test_event_params(self):
        self.assertCountEqual(self.event.EVENT_PARAMS, ['sensor', 'lastupdate', 'temperature'])





class TestsSensorsMotionOnEvent(unittest.TestCase):

    def setUp(self):
        logging.basicConfig(level=LOG_LEVEL, format=u'%(asctime)s %(name)s:%(lineno)d %(levelname)s : %(message)s')
        self.session = session.TestSession(self)
        self.event = self.session.setup_event(SensorsMotionOnEvent)

    @unittest.skip('need cleep 0.0.27')
    def test_event_params(self):
        self.assertCountEqual(self.event.EVENT_PARAMS, ['sensor', 'lastupdate'])





class TestsSensorsMotionOffEvent(unittest.TestCase):

    def setUp(self):
        logging.basicConfig(level=LOG_LEVEL, format=u'%(asctime)s %(name)s:%(lineno)d %(levelname)s : %(message)s')
        self.session = session.TestSession(self)
        self.event = self.session.setup_event(SensorsMotionOffEvent)

    @unittest.skip('need cleep 0.0.27')
    def test_event_params(self):
        self.assertCountEqual(self.event.EVENT_PARAMS, ['sensor', 'lastupdate'])




if __name__ == '__main__':
    # coverage run --omit="*/lib/python*/*","test_*" --concurrency=thread test_sensors.py; coverage report -m -i
    unittest.main()

