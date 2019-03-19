/**
 * Humidity widget
 * Display humidity dashboard widget
 */
var widgetHumidityDirective = function(raspiotService, sensorsService) {

    var widgetHumidityController = ['$scope', function($scope) {
        var self = this;
        self.device = $scope.device;
        self.graphOptions = {
            'type': 'line',
            'fields': ['timestamp', 'humidity'],
            'color': '#FF7F00',
            'label': 'Humidity (%)'
        };
        self.hasDatabase = raspiotService.hasModule('database');
    }];

    return {
        restrict: 'EA',
        templateUrl: 'humidity.widget.html',
        replace: true,
        scope: {
            'device': '='
        },
        controller: widgetHumidityController,
        controllerAs: 'widgetCtl'
    };
};

var RaspIot = angular.module('RaspIot');
RaspIot.directive('widgetHumidityDirective', ['raspiotService', 'sensorsService', widgetHumidityDirective]);

