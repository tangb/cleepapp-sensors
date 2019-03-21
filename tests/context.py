from raspiot.libs.internals.crashreport import CrashReport
from raspiot.eventsFactory import EventsFactory
from raspiot.formattersFactory import FormattersFactory
from raspiot.libs.internals.cleepfilesystem import CleepFilesystem
from raspiot import bus
from raspiot.events import event
from threading import Event
import os
import logging

class Context():
    """
    Create context to be able to run tests
    """
    def __init__(self, debug_enabled=False):
        self.bootstrap = self.__build_bootstrap_objects(debug_enabled)
        self.__bus_command_handlers = {}

    def __build_bootstrap_objects(self, debug):
        debug = False
        crash_report = CrashReport(None, u'Test', u'0.0.0', {}, debug, True)

        events_factory = EventsFactory(debug)
        events_factory.get_event_instance = self._fake_events_factory_get_event_instance

        message_bus = bus.MessageBus(crash_report, debug)
        message_bus.push = self._fake_message_bus_push

        return {
            'message_bus': message_bus,
            'events_factory': events_factory,
            'formatters_factory': EventsFactory(debug),
            'cleep_filesystem': CleepFilesystem(),
            'crash_report': crash_report,
            'join_event': Event()
        }

    def setup_module(self, module_class, debug_enabled = False):
        """
        Instanciate specified module overwriting some stuff and initalizing it with appropriate content
        """
        #config
        module_class.CONFIG_DIR = '/tmp'
        
        #instanciate
        instance = module_class(self.bootstrap, debug_enabled)
        instance._configure()

        return instance

    def clean(self, instance):
        """
        Clean all stuff
        """
        #config
        path = os.path.join(instance.CONFIG_DIR, instance.MODULE_CONFIG_FILE)
        if os.path.exists(path):
            os.remove(path)

    def add_command_handler(self, command, handler):
        """
        Add command handler

        Args:
            command (string): name of command to handle
            handler (function): function to call when command triggered
        """
        self.__bus_command_handlers[command] = handler

    def _fake_message_bus_push(self, request, timeout):
        if request and request.command in self.__bus_command_handlers:
                return self.__bus_command_handlers[request.command]()

        return {
            'error': True,
            'data': None,
            'message': 'Command "%s" not handled. You will surely have "No response" exception or command may not be properly handled!.' % request.command
        }

    def _fake_events_factory_get_event_instance(self, event_name):
        e_ = event.Event
        e_.EVENT_NAME = event_name
        return e_(self.bootstrap['message_bus'], self.bootstrap['formatters_factory'], self.bootstrap['events_factory'])

