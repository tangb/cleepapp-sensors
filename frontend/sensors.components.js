angular
.module('Cleep')
.component('configSensorImg', {
    template: `
    <config-basic cl-title="$ctrl.clTitle">
        <cl-app-img
            ng-if="$ctrl.type.type === $ctrl.types.TEMPERATURE && $ctrl.type.subtype === $ctrl.subtypes.ONEWIRE"
            cl-src="images/ds18b20.png" cl-height="200px"
        ></cl-app-img>
        <cl-app-img
            ng-if="$ctrl.type.type === $ctrl.types.MOTION && $ctrl.type.subtype === $ctrl.subtypes.GENERIC"
            cl-src="images/pir_motion.png" cl-height="200px"
        ></cl-app-img>
        <cl-app-img
            ng-if="$ctrl.type.subtype === $ctrl.subtypes.DHT22"
            cl-src="images/dht22.png" cl-height="200px"
        ></cl-app-img>
    </config-basic>
    `,
    bindings: {
        clTitle: '@',
        type: '<',
        subtypes: '<',
        types: '<',
    },
});

angular
.module('Cleep')
.component('configSensorOnewire', {
    template: `
    <config-basic cl-title="$ctrl.title" ng-if="!$ctrl.hasDriverInstalled">
        <md-button
            class="md-raised md-accent"
            ng-disabled="$ctrl.installingDriver"
            ng-click="$ctrl.gotoDriversPage()"
        >
            <cl-icon cl-icon="plus"></cl-icon>
            Install driver
        </md-button>
    </config-basic>
    <config-select
        ng-if="$ctrl.hasDriverInstalled"
        cl-disabled="$ctrl.updateDevice"
        cl-title="Select onewire device to use" cl-btn-icon="magnify-scan" cl-btn-tooltip="Scan onewire bus"
        cl-items="$ctrl.onewires" cl-model="$ctrl.onewire" cl-click="$ctrl.getOnewires()"
    ></config-select>
    `,
    bindings: {
        drivers: '<',
        devices: '<',
        installingDriver: '<',
        updateDevice: '<',
        types: '<',
        subtypes: '<',
    },
    controller: function ($mdDialog, $location, sensorsService, toastService) {
        const ctrl = this;
        ctrl.hasDriverInstalled = false;
        ctrl.title = '';
        ctrl.onewires = [];
        ctrl.onewire = undefined;

        ctrl.$onChanges = function (changes) {
            if (changes.drivers?.currentValue) {
                ctrl.hasDriverInstalled = !!changes.drivers.currentValue['onewire'];
            }
            ctrl.setTitle();
        };

        ctrl.setTitle = function () {
            ctrl.title = ctrl.hasDriverInstalled ? 'Scan Onewire bus' : 'Onewire driver is not installed';
        };

        ctrl.getOnewires = function () {
            sensorsService.getOnewires()
                .then(function(resp) {
                    const onewires = []
                    for (const onewire of resp.data) {
                        const disabled = ctrl.devices.some((device) => ctrl.__compareDevices);
                        onewires.push({
                            label: onewire.device,
                            value: onewire,
                            disabled,
                        });
                    }
                    ctrl.onewires = onewires;
                    ctrl.onewire = ctrl.onewires[0];

                    if (!ctrl.onewires.length) {
                        toastService.info('No device detected. Please check connections or reboot raspberry if not already done.');
                    }
                });
        };

        ctrl.__compareDevices = function (a, b) {
            return a.type === ctrl.types.TEMPERATURE && a.subtype === ctrl.subtypes.ONEWIRE && a.device === b.device;
        };

        ctrl.gotoDriversPage = function () {
            $mdDialog.cancel();
            $location.url('/module/system?tab=drivers')
        };
    },
});

