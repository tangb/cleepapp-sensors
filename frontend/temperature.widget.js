/**
 * Temperature widget directive
 * Display temperature dashboard widget
 */
angular
.module('Cleep')
.directive('widgetTemperatureDirective', ['cleepService', 'sensorsService',
function(cleepService, sensorsService) {

    var widgetTemperatureController = ['$scope', function($scope) {
        var self = this;
        self.device = $scope.device;
        self.graphOptions = {
            'type': 'line',
            'fields': ['timestamp', 'celsius'],
            'color': '#FF7F00',
            'label': 'Temperature (°C)'
        };
        self.hasDatabase = cleepService.isAppInstalled('database');
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
}]);

