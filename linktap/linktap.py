#!/usr/bin/env python3

try:
import udi_interface
import sys
import requests

LOGGER = udi_interface.LOGGER

class LinkTap:
    def __init__(self, username, apiKey):
        self.base_url = 'https://www.link-tap.com/api/'
        self.username = username
        self.apiKey = apiKey

    def call_api(self, url, payload):
        try:
            r = requests.post(url, data=payload)
            if r.status_code == requests.codes.ok:
                data = r.json()
                if data['result'] == 'error':
                    return 'error'
                elif data is None:
                    return 'error'
                else:
                    return data
            else:
                return 'error'
        except requests.exceptions.RequestException:
            LOGGER.info("Request failed: RequestException")
            pass
        except socket.gaierror:
            LOGGER.info("Request failed: gaierror Name does not resolve")
            pass
        except urllib3.exceptions.NewConnectionError:
            LOGGER.info("Request failed: NewConnectionError")
            pass
        except urllib3.exceptions.MaxRetryError:
            LOGGER.info("Request failed: MaxRetryError")
            pass
        except requests.exceptions.ConnectionError:
            LOGGER.info("Request failed: ConnectionError")
            pass

    def activate_instant_mode(self, gatewayId, taplinkerId, action, duration, eco):
        url = self.base_url + 'activateInstantMode'

        # autoBack:  Re-activate watering plan after Instant Mode
        auto_back = "true"

        if action:
            action = "true"
        else:
            action = "false"

        if eco:
            eco = "true"
        else:
            eco = "false"

        payload = {'username': self.username,
                   'apiKey': self.apiKey,
                   'gatewayId': gatewayId,
                   'taplinkerId': taplinkerId,
                   'action': action,
                   'duration': duration,
                   'eco': eco,
                   'autoBack': auto_back,
                   }
        ret = self.call_api(url, payload)
        return ret

    def activate_interval_mode(self, gatewayId, taplinkerId):
        url = self.base_url + 'activateIntervalMode'

        payload = {'username': self.username,
                   'apiKey': self.apiKey,
                   'gatewayId': gatewayId,
                   'taplinkerId': taplinkerId
                   }
        ret = self.call_api(url, payload)
        return ret

    def activate_odd_even_mode(self, gatewayId, taplinkerId):
        url = self.base_url + 'activateOddEvenMode'

        payload = {'username': self.username,
                   'apiKey': self.apiKey,
                   'gatewayId': gatewayId,
                   'taplinkerId': taplinkerId
                   }
        ret = self.call_api(url, payload)
        return ret

    def activate_seven_day_mode(self, gatewayId, taplinkerId):
        url = self.base_url + 'activateSevenDayMode'

        payload = {'username': self.username,
                   'apiKey': self.apiKey,
                   'gatewayId': gatewayId,
                   'taplinkerId': taplinkerId
                   }
        ret = self.call_api(url, payload)
        return ret

    def activate_month_mode(self, gatewayId, taplinkerId):
        url = self.base_url + 'activateMonthMode'

        payload = {'username': self.username,
                   'apiKey': self.apiKey,
                   'gatewayId': gatewayId,
                   'taplinkerId': taplinkerId
                   }
        ret = self.call_api(url, payload)
        return ret

    def get_all_devices(self):
        url = self.base_url + 'getAllDevices'
        payload = {'username': self.username, 'apiKey': self.apiKey}
        ret = self.call_api(url, payload)
        return ret

    def get_watering_status(self, taplinkerId):
        url = self.base_url + 'getWateringStatus'
        payload = {'username': self.username,
                   'apiKey': self.apiKey,
                   'taplinkerId': taplinkerId
                   }
        ret = self.call_api(url, payload)
        return ret


if __name__ == "__main__":
    try:
        import json

        with open('test_data.json') as json_file:
            all_devices = json.load(json_file)

        for ctl in all_devices['devices']:
            print('Name: ' + ctl['name'])
            print('Gateway ID: ' + ctl['gatewayId'])
            print('ISY GW ID: ' + ctl['gatewayId'][0:8].lower())
            for tl in ctl['taplinker']:
                print('TL Name: ' + tl['taplinkerName'])
                print('TL ID: ' + tl['taplinkerId'][0:8].lower())

        for gw in all_devices['devices']:
            for tl in gw['taplinker']:
                if tl['taplinkerId'][0:8].lower():
                    if tl['status'] == 'Connected':
                        print("setting driver ON")
                    else:
                        print("setting driver OFF")
                    if tl['watering'] is not None:
                        for i in tl['watering']:
                            print(i)
                            print(tl['watering'][i])

    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
