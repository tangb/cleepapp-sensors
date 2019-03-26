/**
 * Sensors config directive
 * Handle sensors configuration
 */
var sensorsConfigDirective = function($rootScope, toast, raspiotService, sensorsService, confirm, $mdDialog) {

    var sensorsController = [function() {
        var self = this;
        self.raspiGpios = [];
        self.driverOnewire = false;
        self.installingDriver = false;
        self.devices = raspiotService.devices;
        self.name = '';
        self.selectedGpios = [{'gpio':null, 'label':'wire'}];
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
        self.types = [
            {label:'Motion', value:{type:self.TYPE_MOTION, subtype:self.SUBTYPE_GENERIC}},
            {label:'Temperature (onewire)', value:{type:self.TYPE_TEMPERATURE, subtype:self.SUBTYPE_ONEWIRE}},
            {label:'Temperature+humidity sensor (DHT22)', value:{type:self.TYPE_MULTI, subtype:self.SUBTYPE_DHT22}}
        ];
        self.type = self.types[0].value;

        /**
         * Search sensor by name
         */
        self._searchSensorsByName = function(name) {
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
        self._getSensorType = function(sensor) {
            for( type of self.types ) {
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
        self._resetEditorValues = function() {
            self.name = ''; 
            self.selectedGpios = [{'gpio':null, 'label':'wire'}];
            self.inverted = false;
            self.type = self.types[0].value;
            self.interval = self.intervals[1].value;
            self.offset = 0;
            self.offsetUnit = self.offsetUnits[0].value;
            self.onewires = [];
            self.onewire = '';
        };

        /** 
         * Close dialog
         */
        self.closeDialog = function() {
            //check values
            if( self.name.length===0 )
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
        self.cancelDialog = function() {
            $mdDialog.cancel();
        };  

        /**
         * Open dialog (internal use)
         */
        self._openDialog = function(update) {
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
         * Add device
         */
        self.openAddDialog = function() {
            self._resetEditorValues();
            self._openDialog(false)
                .then(function() {
                    if( self.type.type===self.TYPE_MOTION )
                    {
                        return sensorsService.addGenericMotionSensor(self.name, self.selectedGpios[0].gpio, self.inverted);
                    }
                    else if( self.type.type===self.TYPE_TEMPERATURE && self.type.subtype===self.SUBTYPE_ONEWIRE )
                    {
                        return sensorsService.addOnewireTemperatureSensor(self.name, self.onewire.device, self.onewire.path, self.interval, self.offset, self.offsetUnit, 'GPIO4');
                    }
                    else if( self.type.type===self.TYPE_MULTI && self.type.subtype===self.SUBTYPE_DHT22 )
                    {
                        return sensorsService.addDht22Sensor(self.name, self.selectedGpios[0].gpio, self.interval, self.offset, self.offsetUnit);
                    }
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
        self._fillEditorValues = function(device) {
            self.oldName = device.name;
            self.name = device.name;
            self.type = self._getSensorType(device);
            if( self.type.type===self.TYPE_MOTION )
            {
                self.selectedGpios = [{gpio:device.gpios[0].gpio, label:'data'}];
                self.inverted = device.inverted;
            }
            else if( self.type.type===self.TYPE_TEMPERATURE )
            {
                self.selectedGpios = [{gpio:device.gpios[0].gpio, label:'data'}];
                self.interval = device.interval;
                self.offset = device.offset;
                self.offsetUnit = device.offsetunit;
            }
            else if( self.type.type===self.TYPE_HUMIDITY )
            {
                self.selectedGpios = [{gpio:device.gpios[0].gpio, label:'data'}];
                self.interval = device.interval;
            }
            else if( self.type.subtype==self.SUBTYPE_DHT22 )
            {
                //need to know all dht22 sensors
                founds = self._searchSensorsByName(device.name);
                self.selectedGpios = [{gpio:device.gpios[0].gpio, label:'sensor wire'}];
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

        };

        /** 
         * Update device
         */
        self.openUpdateDialog = function(device) {

            self._fillEditorValues(device);

            //open dialog
            self._openDialog(true)
                .then(function() {
                    if( self.type.type===self.TYPE_MOTION )
                    {
                        return sensorsService.updateGenericMotionSensor(device.uuid, self.name, self.inverted);
                    }
                    else if( self.type.type===self.TYPE_TEMPERATURE && self.type.subtype===self.SUBTYPE_ONEWIRE )
                    {
                        return sensorsService.updateOnewireTemperatureSensor(device.uuid, self.name, self.interval, self.offset, self.offsetUnit);
                    }
                    else if( self.type.subtype===self.SUBTYPE_DHT22)
                    {
                        return sensorsService.updateDht22Sensor(self.oldName, self.name, self.interval, self.offset, self.offsetUnit);
                    }
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
        self.openDeleteDialog = function(device) {
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
        self.getOnewires = function() {
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

        /**
         * Install onewire driver
         */
        self.installOnewire = function()
        {
            self.installingDriver = true;

            sensorsService.installOnewire()
                .then(function(resp) {
                    //reload system config to handle restart
                    return raspiotService.reloadModuleConfig('system');
                })
                .then(function() {
                    self.driverOnewire = true;
                    toast.success('Driver installed. Please restart.');
                })
                .finally(function() {
                    self.installingDriver = false;
                });
        };

        /**
         * Init controller
         */
        self.init = function() {
            raspiotService.getModuleConfig('sensors')
                .then(function(config) {
                    self.raspiGpios = config.raspi_gpios;
                    self.driverOnewire = config.drivers.onewire;
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
RaspIot.directive('sensorsConfigDirective', ['$rootScope', 'toastService', 'raspiotService', 'sensorsService', 'confirmService', '$mdDialog', sensorsConfigDirective]);
RaspIot.filter('displayGpios', sensorGpiosFilter);

