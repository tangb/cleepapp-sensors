/**
 * Sensors service
 * Handle sensors module requests
 */
angular.module('Cleep')
.service('sensorsService', ['$q', '$rootScope', 'rpcService', 'cleepService',
function($q, $rootScope, rpcService, cleepService) {
    var self = this;
    
    /**
     * Init module devices
     */
    self.initDevices = function(devices) {   
        for (var uuid in devices) {
            if (devices[uuid].type === 'motion') {
                // change current color if gpio is on
                if( devices[uuid].on ) {
                    devices[uuid].__widget.mdcolors = '{background:"default-accent-400"}';
                }
            }
        }

        return devices;
    };

    /**
     * Add new sensor
     */
    self.addSensor = function(type, subtype, data) {
        return rpcService.sendCommand('add_sensor', 'sensors', {'sensor_type': type, 'sensor_subtype': subtype, 'data': data});
    };

    /**
     * Delete sensor
     */
    self.deleteSensor = function(uuid) {
        return rpcService.sendCommand('delete_sensor', 'sensors', {'sensor_uuid': uuid});
    }

    /**
     * Update sensor
     */
    self.updateSensor = function(uuid, data) {
        return rpcService.sendCommand('update_sensor', 'sensors', {'sensor_uuid': uuid, 'data': data});
    }

    /**
     * Get onewires devices
     */
    self.getOnewires = function() {
        return rpcService.sendCommand('get_onewire_devices', 'sensors');
    };

    /**
     * Catch motion on event
     */
    $rootScope.$on('sensors.motion.on', function(event, uuid, params) {
        for (var i=0; i<cleepService.devices.length; i++) {
            if( cleepService.devices[i].uuid === uuid ) {
                cleepService.devices[i].lastupdate = params.lastupdate;
                cleepService.devices[i].on = true;
                cleepService.devices[i].__widget.mdcolors = '{background:"default-accent-400"}';
                break;
            }
        }
    });

    /**
     * Catch motion off event
     */
    $rootScope.$on('sensors.motion.off', function(event, uuid, params) {
        for (var i=0; i<cleepService.devices.length; i++) {
            if (cleepService.devices[i].uuid === uuid) {
                cleepService.devices[i].lastupdate = params.lastupdate;
                cleepService.devices[i].on = false;
                cleepService.devices[i].__widget.mdcolors = '{background:"default-primary-300"}';
                break;
            }
        }
    });

    /**
     * Catch temperature events
     */
    $rootScope.$on('sensors.temperature.update', function(event, uuid, params) {
        for (var i=0; i<cleepService.devices.length; i++) {
            if (cleepService.devices[i].uuid===uuid) {
                cleepService.devices[i].lastupdate = params.lastupdate;
                cleepService.devices[i].celsius = params.celsius;
                cleepService.devices[i].fahrenheit = params.fahrenheit;
                break;
            }
        }
    });

    /**
     * Catch humidity events
     */
    $rootScope.$on('sensors.humidity.update', function(event, uuid, params) {
        for (var i=0; i<cleepService.devices.length; i++) {   
            if (cleepService.devices[i].uuid===uuid) {
                cleepService.devices[i].lastupdate = params.lastupdate;
                cleepService.devices[i].humidity = params.humidity;
                break;
            }
        }
    });

}]);

