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

        polyglot.subscribe(polyglot.DISCOVER, self.discover)
        polyglot.subscribe(polyglot.CUSTOMPARAMS, self.parameterHandler)

        polyglot.ready()

    def get_link_tap_devices(self):
        lt = linktap.LinkTap(self.username, self.apiKey)
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

    # TODO: : move into each node?
    def longPoll(self):
        if self.ready:
            if self.get_link_tap_devices():
                self.update()
            else:
                LOGGER.info("LinkTap Devices API returned None")
        else:
            pass


    def discover_retry(self):
        retry_count = str(self.retry_count)
        if self.retry_count <= 3000:
            LOGGER.info("discover_retry: Failed to start.  Retrying attempt: " + retry_count)
            self.retry_count += 1
            self.discover()
        else:
            LOGGER.info("discover_retry: Failed to start after 3000 retries.  Aborting")

    def discover(self):
        if self.get_link_tap_devices():
            for ctl in self.data['devices']:
                gw_name = ctl['name']
                gw_address = ctl['gatewayId'][0:8].lower()
                self.addNode(GatewayNode(self, gw_address, gw_address, gw_name, ctl))
                time.sleep(2)
                for tl in ctl['taplinker']:
                    tl_name = tl['taplinkerName']
                    tl_address = tl['taplinkerId'][0:8].lower()
                    self.addNode(TapLinkNode(self, gw_address, tl_address, tl_name, tl))
                    time.sleep(2)
            self.ready = True
            self.update()
        else:
            LOGGER.info("Failed to get devices.  Will retry in 5 minutes")
            self.ready = False
            time.sleep(300)
            self.discover_retry()

    # TODO: Use CUSTOMPARAMS event handler here
    def parameterHandler(self, params):
        valid_user = False
        valid_key = False

        sel.poly.Notices.clear()

        if 'username' in params and params['username'] != '':
            self.username = params['username']
            valid_user = True
        else:
            self.poly.Notices = 'Please set username'

        if 'apiKey' in params and params['apiKey'] != '':
            self.apiKey = params['apiKey']
            valid_key = True
        else:
            self.poly.Notices = 'Please set api key'

        if valid_user and valid_key:
            self.discover()


# This should be the parent node!
class GatewayNode(udi_interface.Node):
    def __init__(self, polyglot, primary, address, name, gw):
        super(GatewayNode, self).__init__(polyglot, primary, address, name)
        self.gw = gw

        polyglot.subscribe(polyglot.POLL, this.poll)
        polyglot.subscribe(polyglot.START, this.update, address)

    def poll(self, flag):
        if flag == 'shortPoll':
            this.update()

    def setOn(self, command):
        self.setDriver('ST', 1)

    def setOff(self, command):
        self.setDriver('ST', 0)

    def query(self):
        self.reportDrivers()

    def update(self):
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
    def __init__(self, polyglot, primary, address, name, tl):
        super(TapLinkNode, self).__init__(polyglot, primary, address, name)
        self.tl = tl
        self.primary = primary
        self.dev_suffix = '004B1200'

        polyglot.subscribe(polyglot.POLL, this.poll)
        polyglot.subscribe(polyglot.START, this.update, address)

    def update(self):
        if tl['status'] == 'Connected':
            self.setDriver('ST', 1, force=True)
        else:
            self.setDriver('ST', 0, force=True)

        self.setDriver('BATLVL', tl['batteryStatus'].strip('%'), force=True)
        # self.setDriver('GV0', tl['signal'].strip('%'), force=True)
        self.setDriver('GV0', tl['signal'], force=True)
        if tl['watering'] is not None:
            self.setDriver('GV1', 1, force=True)
            for key in tl['watering']:
                if key == 'remaining':
                    self.setDriver('GV2', tl['watering'][key], force=True)
                if key == 'total':
                    self.setDriver('GV3', tl['watering'][key], force=True)
        else:
            self.setDriver('GV1', 0, force=True)
            self.setDriver('GV2', 0, force=True)
            self.setDriver('GV3', 0, force=True)

    def poll(self, flag):
        if flag == 'shortPoll':
            self.update()

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

        # TODO: review this, should we do linktap.LinkTap() only once on start?
        lt = linktap.LinkTap(self.controller.username, self.controller.apiKey)
        lt.activate_instant_mode(gateway, taplinker, action, duration, eco)
        self.setDriver('GV1', 1)
        self.setDriver('GV2', duration)
        self.setDriver('GV3', duration)

    def instantOff(self, command):
        taplinker = command.get('address') + self.dev_suffix
        gateway = self.primary + self.dev_suffix
        duration = 0
        action = False
        eco = False

        lt = linktap.LinkTap(self.controller.username, self.controller.apiKey)
        lt.activate_instant_mode(gateway, taplinker, action, duration, eco)
        self.setDriver('GV1', 0)
        self.setDriver('GV2', duration)
        self.setDriver('GV3', duration)


    def intervalMode(self, command):
        taplinker = command.get('address') + self.dev_suffix
        gateway = self.primary + self.dev_suffix
        lt = linktap.LinkTap(self.controller.username, self.controller.apiKey)
        lt.activate_interval_mode(gateway, taplinker)

    def oddEvenMode(self, command):
        taplinker = command.get('address') + self.dev_suffix
        gateway = self.primary + self.dev_suffix
        lt = linktap.LinkTap(self.controller.username, self.controller.apiKey)
        lt.activate_odd_even_mode(gateway, taplinker)

    def sevenDayMode(self, command):
        taplinker = command.get('address') + self.dev_suffix
        gateway = self.primary + self.dev_suffix
        lt = linktap.LinkTap(self.controller.username, self.controller.apiKey)
        lt.activate_seven_day_mode(gateway, taplinker)

    def monthMode(self, command):
        taplinker = command.get('address') + self.dev_suffix
        gateway = self.primary + self.dev_suffix
        lt = linktap.LinkTap(self.controller.username, self.controller.apiKey)
        lt.activate_month_mode(gateway, taplinker)

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
        polyglot.start('1.0.0')

        Controller(polyglot)
        LOGGER.info('Started LinkTap NodeServer')

        polyglot.uploadProfile()
        polyglot.setCustomParamsDoc()

        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        polyglot.stop()
        sys.exit(0)
        """
        Catch SIGTERM or Control-C and exit cleanly.
        """
