angular
.module('Cleep')
.directive('sensorsConfigComponent', ['$rootScope', 'toastService', 'cleepService', 'sensorsService', 'confirmService', '$mdDialog', '$filter',
function($rootScope, toast, cleepService, sensorsService, confirm, $mdDialog, $filter) {

    var sensorsController = [function() {
        var self = this;
        self.drivers = {};
        self.devices = cleepService.devices;
        self.name = '';
        self.selectedGpios = [];
        self.inverted = false;
        self.onewires = [];
        self.onewire = '';
        self.intervals = [
            { label:'5 minutes', value: 300 },
            { label:'15 minutes', value: 900 },
            { label:'30 minutes', value: 1800 },
            { label:'1 hour', value: 3600 },
        ];
        self.interval = self.intervals[1].value;
        self.offset = 0;
        self.offsetUnits = [
            { label:'Celsius', value: 'celsius' },
            { label:'Fahrenheit', value: 'fahrenheit' },
        ];
        self.offsetUnit = self.offsetUnits[0].value;
        self.TYPES = {
            MULTI: 'multi',
            MOTION: 'motion',
            TEMPERATURE: 'temperature',
            HUMIDITY: 'humidity',
        };
        self.SUBTYPES = {
            GENERIC: 'generic',
            ONEWIRE: 'onewire',
            DHT22: 'dht22',
        };
        self.type = null;
        self.sensors = [];
        self.updateDevice = false;

        self._searchSensorsByName = function(name) {
            founds = [];

            for (var i=0; i<self.devices.length; i++) {
                if (self.devices[i].module==='sensors' && self.devices[i].name==name) {
                    founds.push(self.devices[i]);
                }
            }

            return founds;
        };

        self._getSensorType = function(sensor) {
            for( var type of self.types ) {
                if (type.value.type===sensor.type && type.value.subtype===sensor.subtype) {
                    // strict type found
                    return type.value;
                } else if (type.value.subtype===self.SUBTYPES.DHT22) {
                    // multi sensor DHT22
                    return type.value;
                }
            }

            // type not found, return default one
            console.error('No sensor type found, return default value');
            return self.types[0].value;
        };

        self._resetEditorValues = function() {
            self.name = ''; 
            self.inverted = false;
            self.type = self.types[0].value;
            self.onSensorTypeChanged();
            self.interval = self.intervals[1].value;
            self.offset = 0;
            self.offsetUnit = self.offsetUnits[0].value;
            self.onewires = [];
            self.onewire = '';
        };

        self.closeDialog = function(force=false) {
            if (force === true) {
                $mdDialog.cancel();
            } else if (self.name.length === 0) {
                toast.error('All fields are required');
            } else {   
                $mdDialog.hide();
            }   
        };

        self.cancelDialog = function() {
            $mdDialog.cancel();
        };  

        self._openDialog = function(updateDevice) {
            self.updateDevice = updateDevice;
            return $mdDialog.show({
                controller: function() { return self },
                controllerAs: '$ctrl',
                templateUrl: 'sensor.dialog.html',
                parent: angular.element(document.body),
                clickOutsideToClose: false,
                fullscreen: true,
            });
        };

        self.onSensorTypeChanged = function() {
            // based on type
            switch (self.type.type) {
                case self.TYPES.MOTION:
                case self.SUBTYPES.GENERIC:
                    // single pin
                    self.selectedGpios = [{'gpio':null, 'label':'gpio'}];
                    return;
            }

            // based on subtype
            switch (self.type.subtype) {
                case self.SUBTYPES.DHT22:
                    // single pin
                    self.selectedGpios = [{'gpio':null, 'label':'gpio'}];
                    return;
            }
        };

        self.getSensorData = function(type, subtype, update) {
            var data = {};
            if (self.type.type === self.TYPES.MOTION) {
                data = {
                    name: self.name,
                    gpio: self.selectedGpios[0].gpio,
                    inverted: self.inverted,
                };
            } else if (self.type.type === self.TYPES.TEMPERATURE && self.type.subtype === self.SUBTYPES.ONEWIRE) {
                data = {
                    name: self.name,
                    device: self.onewire.device,
                    path: self.onewire.path,
                    interval: self.interval,
                    offset: self.offset,
                    offset_unit: self.offsetUnit,
                };
            } else if (self.type.subtype === self.SUBTYPES.DHT22) {
                data = {
                    name: self.name,
                    gpio: self.selectedGpios[0].gpio,
                    interval: self.interval,
                    offset: self.offset,
                    offset_unit: self.offsetUnit,
                };
            }

            // if update remove gpio that cannot be modified
            if (update && (pos=Object.keys(data).indexOf('gpio')) !== -1) {
                delete data.gpio;
            }

            return data;
        };

        self.openAddDialog = function() {
            self._resetEditorValues();
            self._openDialog(false)
                .then(function(resp) {
                    const sensorData = self.getSensorData(self.type.type, self.type.subtype, false);
                    return sensorsService.addSensor(self.type.type, self.type.subtype, sensorData);
                })
                .then(function() {
                    return cleepService.reloadDevices();
                })
                .then(function() {
                    toast.success('Sensor added');
                })
                .finally(function() {
                    self._resetEditorValues();
                });
        };

        self._fillEditorValues = function(device) {
            self.name = device.name;
            self.type = self._getSensorType(device);

            // subtypes first!
            if (self.type.subtype === self.SUBTYPES.DHT22) {
                // need to know all dht22 sensors
                founds = self._searchSensorsByName(device.name);
                self.selectedGpios = [{gpio:device.gpios[0].gpio, label:'gpio'}];
                self.interval = device.interval;
                if (founds.length === 2) {
                    self.offset = founds[0].type === self.TYPES.TEMPERATURE ? founds[0].offset : founds[1].offset;
                    self.offsetUnit = founds[0].type === self.TYPES.TEMPERATURE ? founds[0].offsetunit : founds[1].offsetunit;
                } else if (founds.length === 1 && founds.type === self.TYPES.TEMPERATURE) {
                    self.offset = founds[0].offset;
                    self.offsetUnit = founds[0].offsetunit;
                } else {
                    self.offset = 0;
                    self.offsetUnit = 'celsius';
                }
            } else if (self.type.type === self.TYPES.MOTION) {
                self.selectedGpios = [{gpio:device.gpios[0].gpio, label:'gpio'}];
                self.inverted = device.inverted;
            } else if (self.type.type === self.TYPES.TEMPERATURE) {
                self.selectedGpios = [{gpio:device.gpios[0].gpio, label:'gpio'}];
                self.interval = device.interval;
                self.offset = device.offset;
                self.offsetUnit = device.offsetunit;
            } else if (self.type.type === self.TYPES.HUMIDITY) {
                self.selectedGpios = [{gpio:device.gpios[0].gpio, label:'gpio'}];
                self.interval = device.interval;
            }

        };

        self.openUpdateDialog = function(device) {
            self._fillEditorValues(device);

            // open dialog
            self._openDialog(true)
                .then(function() {
                    const sensorData = self.getSensorData(self.type.type, self.type.subtype, true);
                    return sensorsService.updateSensor(device.uuid, sensorData);
                })
                .then(function() {
                    return cleepService.reloadDevices();
                })
                .then(function() {
                    toast.success('Sensor updated');
                }) 
                .finally(function() {
                    self._resetEditorValues();
                }); 
        }; 

        self.openDeleteDialog = function(device) {
            confirm.open('Delete sensor?', 'All sensor data will be deleted and you will not be able to restore it!', 'Delete')
                .then(function() {
                    return sensorsService.deleteSensor(device.uuid);
                })
                .then(function() {
                    return cleepService.reloadDevices();
                })
                .then(function() {
                    toast.success('Sensor deleted');
                }); 
        };

        // TODO handle driver install event
        

        self.capitalize = function(str) {
            return str.charAt(0).toUpperCase() + str.slice(1);
        };

        self.onInit = function() {
            cleepService.getModuleConfig('sensors')
                .then(function(config) {
                    self.drivers = config.drivers;
                    var types = [];
                    for (const addon in config.sensorstypes) {
                        types.push({
                            label: self.capitalize(config.sensorstypes[addon].subtype) + ': ' + config.sensorstypes[addon].types.join('+'),
                            value: {
                                type: config.sensorstypes[addon].types[0],
                                subtype: config.sensorstypes[addon].subtype,
                            }
                        });
                    }
                    self.types = types;
                    self.type = self.types[0].value;
                });

            // add module actions to fabButton
            var actions = [{
                icon: 'plus',
                callback: self.openAddDialog,
                tooltip: 'Add sensor'
            }];
            $rootScope.$broadcast('enableFab', actions);
        };

        $rootScope.$watchCollection(
            () => cleepService.devices,
            (newDevices) => {
                if (!newDevices) {
                    return;
                }

                const devices = newDevices.filter((device) => device.module === 'sensors');

                const sensors = [];
                for (const device of devices) {
                    sensors.push({
                        icon: self.getSensorIcon(device.type),
                        title: self.getSensorTitle(device),
                        subtitle: self.getSensorSubtitle(device),
                        clicks: [
                            {
                                icon: 'pencil',
                                tooltip: 'Edit sensor',
                                click: self.openUpdateDialog,
                                meta: { device },
                            },
                            {
                                icon: 'delete',
                                tooltip: 'Delete sensor',
                                click: self.openDeleteDialog,
                                style: 'md-accent',
                                meta: { device },
                            },
                        ],
                    });
                }
                self.sensors = sensors;
            }
        );

        self.getSensorSubtitle = function (sensor) {
            let subtitle = 'Gpios: ' + sensor.gpios.map((gpio) => gpio.gpio).join(',');

            switch (sensor.type) {
                case 'temperature':
                    subtitle += ' - Offset: ' + (sensor.offsetunit === 'celsius' ? sensor.offset + '°C' : sensor.offset + '°F');
                    subtitle += ' - Freq: ' + (sensor.interval / 60) + 'mins';
                    break;
                case 'humidity':
                    subtitle += ' - Freq: ' + (sensor.interval / 60) + 'mins';
                    break;
                case 'motion':
                    break;
            }

            return subtitle;
        };

        self.getSensorTitle = function (sensor) {
            let title = '<strong>' + sensor.name + '</strong>: ';

            switch (sensor.type) {
                case 'temperature':
                    const value = (sensor.offsetunit === 'celsius' ? sensor.celsius : sensor.farenheit) || '-';
                    title += ' value: ' + (sensor.offsetunit === 'celsius' ? value + '°C' : value + '°F');
                    break;
                case 'humidity':
                    title += ' value: ' + (sensor.humidity || '-') + '%';
                    break;
                case 'motion':
                    title += ' value: ' + (sensor.on ? 'ON' : 'OFF');
                    title += ', last duration: ' + (sensor.lastduration || 0) + 'secs';
                    break;
            }

            title += ', last update: ' + $filter('hrDatetime')(sensor.lastupdate);

            return title;
        };

        self.getSensorIcon = function (sensorType) {
            switch (sensorType) {
                case 'motion': return 'motion-sensor';
                case 'temperature': return 'thermometer';
                case 'humidity': return 'water-percent';
                default: return 'lightbulb-question';
            }
        };

    }];

    var sensorsLink = function(scope, element, attrs, controller) {
        controller.onInit();
    };

    return {
        templateUrl: 'sensors.config.html',
        replace: true,
        scope: true,
        controller: sensorsController,
        controllerAs: '$ctrl',
        link: sensorsLink
    };
}]);

