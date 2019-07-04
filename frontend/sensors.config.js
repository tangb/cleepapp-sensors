/**
 * Sensors config directive
 * Handle sensors configuration
 */
var sensorsConfigDirective = function($rootScope, toast, raspiotService, sensorsService, confirm, $mdDialog, $location) {

    var sensorsController = [function() {
        var self = this;
        self.drivers = {};
        self.devices = raspiotService.devices;
        self.name = '';
        self.selectedGpios = [];
        self.inverted = false;
        self.onewires = [];
        self.onewire = '';
        self.intervals = [
            {label:'5 minutes', value:300},
            {label:'15 minutes', value:900},
            {label:'30 minutes', value:1800},
            {label:'1 hour', value:3600}
        ];
        self.interval = self.intervals[1].value;
        self.offset = 0;
        self.offsetUnits = [
            {label:'Celsius', value:'celsius'},
            {label:'Fahrenheit', value:'fahrenheit'}
        ];
        self.offsetUnit = self.offsetUnits[0].value;
        self.TYPE_MULTI = 'multi'
        self.TYPE_MOTION = 'motion';
        self.TYPE_TEMPERATURE = 'temperature';
        self.TYPE_HUMIDITY = 'humidity';
        self.SUBTYPE_GENERIC = 'generic';
        self.SUBTYPE_ONEWIRE = 'onewire';
        self.SUBTYPE_DHT22 = 'dht22';
        self.types = [];
        //    {label:'Motion', value:{type:self.TYPE_MOTION, subtype:self.SUBTYPE_GENERIC}},
        //    {label:'Temperature (onewire)', value:{type:self.TYPE_TEMPERATURE, subtype:self.SUBTYPE_ONEWIRE}},
        //    {label:'Temperature+humidity sensor (DHT22)', value:{type:self.TYPE_MULTI, subtype:self.SUBTYPE_DHT22}}
        //];
        self.type = null; //self.types[0].value;

        /**
         * Search sensor by name
         */
        self._searchSensorsByName = function(name)
        {
            founds = [];

            for( var i=0; i<self.devices.length; i++ ) {
                if( self.devices[i].module==='sensors' && self.devices[i].name==name )
                {
                    founds.push(self.devices[i]);
                }
            }

            return founds;
        };

        /**
         * Return sensor type according to types member
         */
        self._getSensorType = function(sensor)
        {
            for( var type of self.types ) {
                if( type.value.type===sensor.type && type.value.subtype===sensor.subtype ) {
                    //strict type found
                    return type.value;
                }
                else if( type.value.subtype===self.SUBTYPE_DHT22 )
                {
                    //multi sensor DHT22
                    return type.value;
                }
            }

            //type not found, return default one
            console.error('No sensor type found, return default value');
            return self.types[0].value;
        };

        /** 
         * Reset editor's values
         */
        self._resetEditorValues = function()
        {
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

        /**
         * Goto drivers page
         */
        self.installDrivers = function()
        {
            self.closeDialog(true);
            $location.url('/module/system?tab=drivers')
        };

        /** 
         * Close dialog
         */
        self.closeDialog = function(force=false)
        {
            if( force===true )
            {
                $mdDialog.hide();
            }
            else if( self.name.length===0 )
            {   
                toast.error('All fields are required');
            }   
            else
            {   
                $mdDialog.hide();
            }   
        };

        /** 
         * Cancel dialog
         */
        self.cancelDialog = function()
        {
            $mdDialog.cancel();
        };  

        /**
         * Open dialog (internal use)
         */
        self._openDialog = function(update)
        {
            return $mdDialog.show({
                controller: function() { return self; },
                controllerAs: 'sensorsCtl',
                templateUrl: update ? 'updateSensor.dialog.html' : 'addSensor.dialog.html',
                parent: angular.element(document.body),
                clickOutsideToClose: false,
                fullscreen: true
            });
        };

        /**
         * Event when sensor type changed.
         * Used to define gpio component configuration (pin name)
         */
        self.onSensorTypeChanged = function()
        {
            if( self.type.type===self.TYPE_MOTION && self.type.subtype===self.SUBTYPE_GENERIC ||
                self.type.subtype===self.SUBTYPE_DHT22 )
            {
                //single pin
                self.selectedGpios = [{'gpio':null, 'label':'gpio'}];
            }
        };

        /**
         * Returns data to add or update sensor
         */
        self.getSensorData = function(type, subtype, update)
        {
            var data = {};
            if( self.type.type===self.TYPE_MOTION )
            {
                data = {
                    name: self.name,
                    gpio: self.selectedGpios[0].gpio,
                    inverted: self.inverted,
                };
            }
            else if( self.type.type===self.TYPE_TEMPERATURE && self.type.subtype===self.SUBTYPE_ONEWIRE )
            {
                data = {
                    name: self.name,
                    device: self.onewire.device,
                    path: self.onewire.path,
                    interval: self.interval,
                    offset: self.offset,
                    offset_unit: self.offsetUnit,
                };
            }
            else if( self.type.subtype===self.SUBTYPE_DHT22 )
            {
                data = {
                    name: self.name,
                    gpio: self.selectedGpios[0].gpio,
                    interval: self.interval,
                    offset: self.offset,
                    offset_unit: self.offsetUnit,
                };
            }

            //if update remove gpio that cannot be modified
            if( update && (pos=Object.keys(data).indexOf('gpio'))!==-1 ) {
                delete data.gpio;
            }

            return data;
        };

        /**
         * Add device
         */
        self.openAddDialog = function()
        {
            self._resetEditorValues();
            self._openDialog(false)
                .then(function() {
                    return sensorsService.addSensor(self.type.type, self.type.subtype, self.getSensorData(self.type.type, self.type.subtype, false));
                })
                .then(function() {
                    return raspiotService.reloadDevices();
                })
                .then(function() {
                    toast.success('Sensor added');
                })
                .finally(function() {
                    self._resetEditorValues();
                });
        };

        /**
         * Fill editor values
         */
        self._fillEditorValues = function(device)
        {
            self.name = device.name;
            self.type = self._getSensorType(device);

            //subtypes first!
            if( self.type.subtype==self.SUBTYPE_DHT22 )
            {
                //need to know all dht22 sensors
                founds = self._searchSensorsByName(device.name);
                self.selectedGpios = [{gpio:device.gpios[0].gpio, label:'gpio'}];
                self.interval = device.interval;
                if( founds.length===2 )
                {
                    self.offset = founds[0].type===self.TYPE_TEMPERATURE ? founds[0].offset : founds[1].offset;
                    self.offsetUnit = founds[0].type===self.TYPE_TEMPERATURE ? founds[0].offsetunit : founds[1].offsetunit;
                }
                else if( founds.length===1 && founds.type===self.TYPE_TEMPERATURE )
                {
                    self.offset = founds[0].offset;
                    self.offsetUnit = founds[0].offsetunit;
                }
                else
                {
                    self.offset = 0;
                    self.offsetUnit = 'celsius';
                }
            }
            else if( self.type.type===self.TYPE_MOTION )
            {
                self.selectedGpios = [{gpio:device.gpios[0].gpio, label:'gpio'}];
                self.inverted = device.inverted;
            }
            else if( self.type.type===self.TYPE_TEMPERATURE )
            {
                self.selectedGpios = [{gpio:device.gpios[0].gpio, label:'gpio'}];
                self.interval = device.interval;
                self.offset = device.offset;
                self.offsetUnit = device.offsetunit;
            }
            else if( self.type.type===self.TYPE_HUMIDITY )
            {
                self.selectedGpios = [{gpio:device.gpios[0].gpio, label:'gpio'}];
                self.interval = device.interval;
            }

        };

        /** 
         * Update device
         */
        self.openUpdateDialog = function(device)
        {
            self._fillEditorValues(device);

            //open dialog
            self._openDialog(true)
                .then(function() {
                    return sensorsService.updateSensor(device.uuid, self.getSensorData(self.type.type, self.type.subtype, true));
                })
                .then(function() {
                    return raspiotService.reloadDevices();
                })
                .then(function() {
                    toast.success('Sensor updated');
                }) 
                .finally(function() {
                    self._resetEditorValues();
                }); 
        }; 

        /** 
         * Delete device
         */
        self.openDeleteDialog = function(device)
        {
            confirm.open('Delete sensor?', 'All sensor data will be deleted and you will not be able to restore it!', 'Delete')
                .then(function() {
                    return sensorsService.deleteSensor(device.uuid);
                })
                .then(function() {
                    return raspiotService.reloadDevices();
                })
                .then(function() {
                    toast.success('Sensor deleted');
                }); 
        };

        /**
         * Get onewire devices
         */
        self.getOnewires = function()
        {
            sensorsService.getOnewires()
                .then(function(resp) {
                    //disable already used items
                    for( var i=0; i<resp.data.length; i++ )
                    {
                        var found = false;
                        for( var j=0; j<self.devices.length; j++ )
                        {
                            if( self.devices[j].type==='temperature' && self.devices[j].subtype==='onewire' && self.devices[j].device===resp.data[i].device )
                            {
                                found = true;
                                break;
                            }
                        }

                        resp.data[i].disable = false;
                        if( found )
                        {
                            resp.data[i].disable = true;
                        }
                    }

                    //fill onewire devices
                    self.onewires = resp.data;
                    self.onewire = self.onewires[0];

                    //toast
                    if( self.onewires.length===0 )
                    {
                        toast.info('No device detected. Please check connections or reboot raspberry if not already done.');
                    }
                });
        };

        //TODO handle driver install event
        

        self.capitalize = function(str)
        {
            return str.charAt(0).toUpperCase() + str.slice(1);
        };

        /**
         * Init controller
         */
        self.init = function()
        {
            raspiotService.getModuleConfig('sensors')
                .then(function(config) {
                    self.drivers = config.drivers;
                    var types = [];
                    for( var addon in config.sensorstypes) {
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

            //add module actions to fabButton
            var actions = [{
                icon: 'plus',
                callback: self.openAddDialog,
                tooltip: 'Add sensor'
            }];
            $rootScope.$broadcast('enableFab', actions);
        };

    }];

    var sensorsLink = function(scope, element, attrs, controller) {
        controller.init();
    };

    return {
        templateUrl: 'sensors.config.html',
        replace: true,
        scope: true,
        controller: sensorsController,
        controllerAs: 'sensorsCtl',
        link: sensorsLink
    };
};

var sensorGpiosFilter = function($filter) {
    return function(gpios) {
        if( gpios && angular.isArray(gpios) )
        {
            names = [];
            for( var i=0; i<gpios.length; i++)
            {
                names.push(gpios[i].gpio);
            }
            return names.join(',');
        }
    };
};

var RaspIot = angular.module('RaspIot');
RaspIot.directive('sensorsConfigDirective', ['$rootScope', 'toastService', 'raspiotService', 'sensorsService', 'confirmService', '$mdDialog', '$location', sensorsConfigDirective]);
RaspIot.filter('displayGpios', sensorGpiosFilter);

