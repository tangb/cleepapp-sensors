/**
 * Temperature widget directive
 * Display temperature dashboard widget
 */
var widgetTemperatureDirective = function(raspiotService, sensorsService) {

    var widgetTemperatureController = ['$scope', function($scope) {
        var self = this;
        self.device = $scope.device;
        self.graphOptions = {
            'type': 'line',
            'fields': ['timestamp', 'celsius'],
            'color': '#FF7F00',
            'label': 'Temperature (°C)'
        };
        self.hasDatabase = raspiotService.hasModule('database');
    }];

    return {
        restrict: 'EA',
        templateUrl: 'temperature.widget.html',
        replace: true,
        scope: {
            'device': '='
        },
        controller: widgetTemperatureController,
        controllerAs: 'widgetCtl'
    };
};

var RaspIot = angular.module('RaspIot');
RaspIot.directive('widgetTemperatureDirective', ['raspiotService', 'sensorsService', widgetTemperatureDirective]);

