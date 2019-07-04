/**
 * Sensors service
 * Handle sensors module requests
 */
var sensorsService = function($q, $rootScope, rpcService, raspiotService) {
    var self = this;
    
    /**
     * Init module devices
     */
    self.initDevices = function(devices) {   
        for( var uuid in devices )
        {   
            if( devices[uuid].type==='motion' )
            {
                //change current color if gpio is on
                if( devices[uuid].on )
                {   
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
        return rpcService.sendCommand('add_sensor', 'sensors', {'type': type, 'subtype': subtype, 'data': data});
    };

    /**
     * Delete sensor
     */
    self.deleteSensor = function(uuid) {
        return rpcService.sendCommand('delete_sensor', 'sensors', {'uuid': uuid});
    }

    /**
     * Update sensor
     */
    self.updateSensor = function(uuid, data) {
        return rpcService.sendCommand('update_sensor', 'sensors', {'uuid': uuid, 'data': data});
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
        for( var i=0; i<raspiotService.devices.length; i++ )
        {   
            if( raspiotService.devices[i].uuid===uuid )
            {   
                raspiotService.devices[i].lastupdate = params.lastupdate;
                raspiotService.devices[i].on = true;
                raspiotService.devices[i].__widget.mdcolors = '{background:"default-accent-400"}';
                break;
            }   
        }   
    });

    /**
     * Catch motion off event
     */
    $rootScope.$on('sensors.motion.off', function(event, uuid, params) {
        for( var i=0; i<raspiotService.devices.length; i++ )
        {   
            if( raspiotService.devices[i].uuid===uuid )
            {
                raspiotService.devices[i].lastupdate = params.lastupdate;
                raspiotService.devices[i].on = false;
                raspiotService.devices[i].__widget.mdcolors = '{background:"default-primary-300"}';
                break;
            }   
        }   
    });

    /**
     * Catch temperature events
     */
    $rootScope.$on('sensors.temperature.update', function(event, uuid, params) {
        for( var i=0; i<raspiotService.devices.length; i++ )
        {   
            if( raspiotService.devices[i].uuid===uuid )
            {   
                raspiotService.devices[i].lastupdate = params.lastupdate;
                raspiotService.devices[i].celsius = params.celsius;
                raspiotService.devices[i].fahrenheit = params.fahrenheit;
                break;
            }   
        }   
    });

    /**
     * Catch humidity events
     */
    $rootScope.$on('sensors.humidity.update', function(event, uuid, params) {
        for( var i=0; i<raspiotService.devices.length; i++ )
        {   
            if( raspiotService.devices[i].uuid===uuid )
            {   
                raspiotService.devices[i].lastupdate = params.lastupdate;
                raspiotService.devices[i].humidity = params.humidity;
                break;
            }   
        }   
    });

};
    
var RaspIot = angular.module('RaspIot');
RaspIot.service('sensorsService', ['$q', '$rootScope', 'rpcService', 'raspiotService', sensorsService]);

