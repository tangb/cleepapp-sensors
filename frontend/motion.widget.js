/**
 * Motion widget directive
 * Display motion dashboard widget
 */
var widgetMotionDirective = function(raspiotService, sensorsService) {

    var widgetMotionController = ['$scope', function($scope) {
        var self = this;
        self.device = $scope.device;
        self.graphOptions = {
            'type': 'line',
            'color': '#24A222'
        };
        self.hasDatabase = raspiotService.isAppInstalled('database');

        //set background color at startup
        if( self.device && self.device.on )
        {
            self.device.__widget.mdcolors = '{background:"default-accent-400"}';
        }
    }];

    return {
        restrict: 'EA',
        templateUrl: 'motion.widget.html',
        replace: true,
        scope: {
            'device': '='
        },
        controller: widgetMotionController,
        controllerAs: 'widgetCtl'
    };
};

var RaspIot = angular.module('RaspIot');
RaspIot.directive('widgetMotionDirective', ['raspiotService', 'sensorsService', widgetMotionDirective]);

