/**
 * Humidity widget
 * Display humidity dashboard widget
 */
angular
.module('Cleep')
.directive('widgetHumidityDirective', ['cleepService', 'sensorsService',
function(cleepService, sensorsService) {

    var widgetHumidityController = ['$scope', function($scope) {
        var self = this;
        self.device = $scope.device;
        self.graphOptions = {
            'type': 'line',
            'fields': ['timestamp', 'humidity'],
            'color': '#FF7F00',
            'label': 'Humidity (%)'
        };
        self.hasDatabase = cleepService.isAppInstalled('database');
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
}]);
