#!/usr/bin/env python

import sys
import linktap
import time
import logging
import udi_interface

LOGGER = udi_interface.LOGGER
logging.getLogger('urllib3').setLevel(logging.INFO)


# TODO: make this an object, not a node!!
class Controller(object):
    def __init__(self, polyglot):
        self.name = 'LinkTap Controller'
        self.username = ''
        self.apiKey = ''
        self.data = None
        self.ready = False
        self.retry_count = 1
        self.poly = polyglot
        self.lt = None

        polyglot.subscribe(polyglot.DISCOVER, self.discover)
        polyglot.subscribe(polyglot.CUSTOMPARAMS, self.parameterHandler)
        polyglot.subscribe(polyglot.POLL, self.get_device_data)

        polyglot.ready()

    def get_link_tap_devices(self, lt):
        all_devices = lt.get_all_devices()
        if all_devices == 'error':
            LOGGER.info("get_link_tap_devices: The minimum interval of calling this API is 5 minutes.")
            self.data = None
            self.ready = False
            return False
        elif all_devices is None:
            LOGGER.info("Get all devices failed")
            self.data = None
            self.ready = False
            return False
        else:
            self.data = all_devices
            self.ready = True
            return True

    def get_device_data(self, flag):
        if not self.ready:
            return

        if flag == 'shortPoll':
            LOGGER.info('Calling get_link_tap_devices....')
            if self.get_link_tap_devices(self.lt):
                for ctl in self.data['devices']:
                    gw_name = ctl['name']
                    gw_address = ctl['gatewayId'][0:8].lower()
                    self.poly.getNode(gw_address).update(ctl)
                    for tl in ctl['taplinker']:
                        tl_name = tl['taplinkerName']
                        tl_address = tl['taplinkerId'][0:8].lower()
                        ws = self.lt.get_watering_status(tl['taplinkerId'])
                        self.poly.getNode(tl_address).update(tl, ws)

    def discover_retry(self):
        retry_count = str(self.retry_count)
        if self.retry_count <= 3000:
            LOGGER.info("discover_retry: Failed to start.  Retrying attempt: " + retry_count)
            self.retry_count += 1
            self.discover()
        else:
            LOGGER.info("discover_retry: Failed to start after 3000 retries.  Aborting")

    def discover(self):
        self.lt = linktap.LinkTap(self.username, self.apiKey)
        if self.get_link_tap_devices(self.lt):
            for ctl in self.data['devices']:
                gw_name = ctl['name']
                gw_address = ctl['gatewayId'][0:8].lower()
                self.poly.addNode(GatewayNode(self.poly, gw_address, gw_address, gw_name, ctl))
                time.sleep(2)
                for tl in ctl['taplinker']:
                    tl_name = tl['taplinkerName']
                    tl_address = tl['taplinkerId'][0:8].lower()
                    ws = self.lt.get_watering_status(tl['taplinkerId'])
                    self.poly.addNode(TapLinkNode(self.poly, gw_address, tl_address, tl_name, tl, self.lt, ws))
                    time.sleep(2)
            self.ready = True
        else:
            LOGGER.info("Failed to get devices.  Will retry in 5 minutes")
            self.ready = False
            time.sleep(300)
            self.discover_retry()

    # TODO: Use CUSTOMPARAMS event handler here
    def parameterHandler(self, params):
        valid_user = False
        valid_key = False

        self.poly.Notices.clear()

        if 'username' in params and params['username'] != '':
            self.username = params['username']
            valid_user = True
        else:
            self.poly.Notices['user'] = 'Please set username'

        if 'apiKey' in params and params['apiKey'] != '':
            self.apiKey = params['apiKey']
            valid_key = True
        else:
            self.poly.Notices['key'] = 'Please set api key'

        if valid_user and valid_key:
            self.discover()


# This should be the parent node!
class GatewayNode(udi_interface.Node):
    def __init__(self, polyglot, primary, address, name, gw):
        super(GatewayNode, self).__init__(polyglot, primary, address, name)
        self.gw = gw

        polyglot.subscribe(polyglot.START, self.start, address)

    def start(self):
        self.update(self.gw)

    def setOn(self, command):
        self.setDriver('ST', 1)

    def setOff(self, command):
        self.setDriver('ST', 0)

    def query(self):
        self.reportDrivers()

    def update(self, gw):
        if gw['status'] == 'Connected':
            self.setDriver('ST', 1)
        else:
            self.setDriver('ST', 0)


    # "Hints See: https://github.com/UniversalDevicesInc/hints"
    # hint = [1,2,3,4]
    drivers = [{'driver': 'ST', 'value': 0, 'uom': 2}]
    id = 'gateway'

    commands = {
                    'DON': setOn, 'DOF': setOff
                }


# child of gateway node
class TapLinkNode(udi_interface.Node):
    def __init__(self, polyglot, primary, address, name, tl, lt, ws):
        super(TapLinkNode, self).__init__(polyglot, primary, address, name)
        self.tl = tl
        self.lt = lt
        self.ws = ws
        self.primary = primary
        self.dev_suffix = '004B1200'
        self.taplinker = address + '004B1200'
        self.force = True

        polyglot.subscribe(polyglot.START, self.start, address)

    def start(self):
        self.update(self.tl, self.ws)
        self.force = False

    def update(self, tl, ws):
        if tl['status'] == 'Connected':
            self.setDriver('ST', 1, force=True)
        else:
            self.setDriver('ST', 0, force=True)

        self.setDriver('BATLVL', tl['batteryStatus'].strip('%'), force=self.force)
        self.setDriver('GV0', tl['signal'], force=self.force)


        if ws['status'] is not None:
            if ws['status']['onDuration']:
                self.setDriver('GV1', 1)
                self.setDriver('GV2', ws['status']['onDuration'])
            if ws['status']['total']:
                self.setDriver('GV3', ws['status']['total'])
                watering_total = int(ws['status']['total'])
                watering_duration = int(ws['status']['onDuration'])
                watering_elapsed = watering_total - watering_duration
                self.setDriver('GV4', watering_elapsed)
        else:
            self.setDriver('GV1', 0, force=self.force)
            self.setDriver('GV2', 0, force=self.force)
            self.setDriver('GV3', 0, force=self.force)
            self.setDriver('GV4', 0, force=self.force)

    def setOn(self, command):
        self.setDriver('ST', 1)

    def setOff(self, command):
        self.setDriver('ST', 0)

    def query(self):
        self.reportDrivers()

    def instantOn(self, command):
        val = command.get('value')
        taplinker = command.get('address') + self.dev_suffix
        gateway = self.primary + self.dev_suffix
        duration = int(val)

        # if duration == 0:
        #     action = False
        # else:
        #     action = True
        action = True
        eco = False

        self.lt.activate_instant_mode(gateway, taplinker, action, duration, eco)
        self.setDriver('GV1', 1)
        self.setDriver('GV2', duration)
        self.setDriver('GV3', duration)

    def instantOff(self, command):
        taplinker = command.get('address') + self.dev_suffix
        gateway = self.primary + self.dev_suffix
        duration = 0
        action = False
        eco = False

        self.lt.activate_instant_mode(gateway, taplinker, action, duration, eco)
        self.setDriver('GV1', 0)
        self.setDriver('GV2', duration)
        self.setDriver('GV3', duration)


    def intervalMode(self, command):
        taplinker = command.get('address') + self.dev_suffix
        gateway = self.primary + self.dev_suffix
        self.lt.activate_interval_mode(gateway, taplinker)

    def oddEvenMode(self, command):
        taplinker = command.get('address') + self.dev_suffix
        gateway = self.primary + self.dev_suffix
        self.lt.activate_odd_even_mode(gateway, taplinker)

    def sevenDayMode(self, command):
        taplinker = command.get('address') + self.dev_suffix
        gateway = self.primary + self.dev_suffix
        self.lt.activate_seven_day_mode(gateway, taplinker)

    def monthMode(self, command):
        taplinker = command.get('address') + self.dev_suffix
        gateway = self.primary + self.dev_suffix
        self.lt.activate_month_mode(gateway, taplinker)

    # "Hints See: https://github.com/UniversalDevicesInc/hints"
    # hint = [1,2,3,4]
    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 2},
        {'driver': 'BATLVL', 'value': 0, 'uom': 51},
        {'driver': 'GV0', 'value': 0, 'uom': 51},  # Signal
        {'driver': 'GV1', 'value': 0, 'uom': 2},  # Watering
        {'driver': 'GV2', 'value': 0, 'uom': 44},  # Remaining
        {'driver': 'GV3', 'value': 0, 'uom': 44},  # Total
        {'driver': 'GV4', 'value': 0, 'uom': 44},  # Elapsed
        {'driver': 'GV5', 'value': 0, 'uom': 44},  # Instant On Minutes
    ]

    id = 'taplinker'
    commands = {
                'GV5': instantOn, 'GV10': instantOff, 'GV6': intervalMode, 'GV7': oddEvenMode,
                'GV8': sevenDayMode, 'GV9': monthMode
                }


if __name__ == "__main__":
    try:
        polyglot = udi_interface.Interface([])
        polyglot.start('1.0.2')


        Controller(polyglot)
        LOGGER.info('Started LinkTap NodeServer')

        polyglot.updateProfile()
        polyglot.setCustomParamsDoc()

        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        polyglot.stop()
        sys.exit(0)
        """
        Catch SIGTERM or Control-C and exit cleanly.
        """
