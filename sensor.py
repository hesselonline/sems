""""Home Assistant component for accessing the GoodWe SEMS Portal API.
    Adapted from https://github.com/TimSoethout/goodwe-sems-home-assistant, but altered to use the SEMS API.
    API adaption heavily inspired by https://github.com/markruys/gw2pvo."""

import json
import logging
import time
from datetime import datetime, timedelta
import requests
import logging
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_NAME, POWER_WATT
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

DOMAIN = "sems"

CONF_STATION_ID = 'station_id'

DEFAULTNAME = "SEMS Portal"

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default = DEFAULTNAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_STATION_ID): cv.string
})

_LOGGER = logging.getLogger(__name__)




def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the GoodWe SEMS portal scraper platform."""
    # Add devices
    add_devices([SemsSensor(config[CONF_NAME], config)], True)

class GoodWeApi:

    def __init__(self, system_id, account, password):
        self.system_id = system_id
        self.account = account
        self.password = password
        self.token = '{"version":"","client":"web","language":"en"}'
        self.global_url = 'https://eu.semsportal.com/api/'
        self.base_url = self.global_url
        self.status = { -1 : 'Offline', 1 : 'Normal' }

    def getCurrentReadings(self):
        ''' Download the most recent readings from the GoodWe API. '''

        payload = {
            'powerStationId' : self.system_id
        }

        # goodwe_server
        data = self.call("v1/PowerStation/GetMonitorDetailByPowerstationId", payload)

        inverterData = data['inverter'][0]

        result = {
            'status'  : self.status[inverterData['status']],
            'pgrid_w' : inverterData['out_pac'],
            'eday_kwh' : inverterData['eday'],
            'etotal_kwh' : inverterData['etotal'],
            'emonth_kwh' : inverterData['emonth'],
            'grid_voltage' : self.parseValue(inverterData['output_voltage'], 'V'),
            'latitude' : data['info'].get('latitude'),
            'longitude' : data['info'].get('longitude'),
            'temperature' : inverterData['tempperature']
        }

          
        return result

    def call(self, url, payload):
        for i in range(1, 4):
            try:
                headers = {'Token': self.token }

                r = requests.post(self.base_url + url, headers=headers, data=payload, timeout=10)
                r.raise_for_status()
                data = r.json()
                _LOGGER.debug(data)

                if data['msg'] == 'success' and data['data'] is not None:
                    return data['data']
                else:
                    loginPayload = { 'account': self.account, 'pwd': self.password }
                    r = requests.post(self.global_url + 'v1/Common/CrossLogin', headers=headers, data=loginPayload, timeout=10)
                    r.raise_for_status()
                    data = r.json()
                    self.base_url = data['api']
                    self.token = json.dumps(data['data'])
            except requests.exceptions.RequestException as exp:
                _LOGGER.warning(exp)
            time.sleep(i ** 3)
        else:
            _LOGGER.error("Failed to call GoodWe API")

        return {}

    def parseValue(self, value, unit):
        try:
            return float(value.rstrip(unit))
        except ValueError as exp:
            _LOGGER.warning(exp)
            return 0


class SemsSensor(Entity):
    """Representation of the SEMS portal."""

    def __init__(self, name, config):
        """Initialize a SEMS sensor."""
        # self.rest = rest
        self._name = name
        self._config = config
        self._attributes = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name
    
    @property
    def unit_of_measurement(self):
        "Return the unit of measurement of the sensor"
        return POWER_WATT

    @property
    def state(self):
        return self._attributes['pgrid_w']
    
    @property
    def icon(self):
        return 'mdi:solar-power'

    @property
    def device_state_attributes(self):
        """Return the state attributes of the monitored installation."""
        return self._attributes

    def update(self):
        """Get the latest data from the SEMS API and updates the state."""
        _LOGGER.debug("update called.")
        
        try:
          station = self._config[CONF_STATION_ID]
          user = self._config[CONF_USERNAME]
          password = self._config[CONF_PASSWORD]

          gw = GoodWeApi(station, user, password)
          data = gw.getCurrentReadings()
        
          for key, value in data.items():
                if(key is not None and value is not None):
                    self._attributes[key] = value
                    _LOGGER.debug("Updated attribute %s: %s", key, value)
        except Exception as exception:
            _LOGGER.error(
                "Unable to fetch data from SEMS. %s", exception)
    