""""
Home Assistant component for accessing the GoodWe SEMS Portal API.
    Adapted from https://github.com/TimSoethout/goodwe-sems-home-assistant, but altered to use the SEMS API.
    API adaption heavily inspired by https://github.com/markruys/gw2pvo.
    Adapted furthermore using MQTT messages using HA-discovery to create separate sensors.
"""

import json
import logging
import time
from datetime import datetime, timedelta
import requests
import logging
import voluptuous as vol
import paho.mqtt.client as mqtt

from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, 
    CONF_SCAN_INTERVAL, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

__version__ = 0.1.0

_LOGGER = logging.getLogger(__name__)

REGISTERED = 0

CONF_BROKER = 'broker'
CONF_STATION_ID = 'station_id'
CONF_BROKER_USERNAME = 'broker_user'
CONF_BROKER_password = 'broker_pw'

DEFAULTNAME = "SEMS Portal"
DOMAIN = 'sems'

SCAN_INTERVAL = timedelta(seconds=60)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_BROKER): cv.string,
        vol.Required(CONF_BROKER_USERNAME): cv.string,
        vol.Required(CONF_BROKER_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_STATION_ID): cv.string
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
            cv.time_period,
    }),
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass, config):
    """Initialize the SEMS MQTT consumer"""
    conf = config[DOMAIN]
    broker = conf.get(CONF_BROKER)
    broker_user = conf.get(CONF_BROKER_USERNAME)
    broker_pw = conf.get(CONF_BROKER_PASSWORD)
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    station_id = conf.get(CONF_STATION_ID)
    scan_interval = conf.get(CONF_SCAN_INTERVAL)

   client_id = 'HomeAssistant'
   port = 1883
   keepalive = 55

   mqttc = mqtt.Client(client_id, protocol=mqtt.MQTTv311)
   mqttc.username_pw_set(broker_user, password=broker_pw)
   mqttc.connect(broker, port=port, keepalive=keepalive)

   async def async_stop_sems(event):
      """Stop the SEMS MQTT component."""
      mqttc.disconnect()

   hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_sems)

async def async_get_sems_data(event_time):   
      """Get the topics from the SEMS API and send to the MQTT Broker."""
      payload_powerBattery = {
                     'name':'aurum_powerBattery',
                     'unit_of_meas':'W',
                     'value_template':'{{ value_json.powerBattery}}',
                     'icon':'mdi:flash',
                     'state_topic':'aurum/sensors'
                    }
  
class GoodWeApi:

    def __init__(self, system_id, account, password):
        self.system_id = system_id
        self.account = account
        self.password = password
        self.token = '{"version":"","client":"web","language":"en"}'
        self.global_url = 'https://eu.semsportal.com/api/'
        self.base_url = self.global_url
        self.status = { -1 : 'Offline', 1 : 'Online' }

    def getCurrentReadings(self):
        ''' Download the most recent readings from the GoodWe API. '''
        payload = {'powerStationId' : self.system_id}
        data = self.call("v1/PowerStation/GetMonitorDetailByPowerstationId", payload)
        inverterData = data['inverter'][0]['invert_full']
        result = {
                'type'  : inverterData['model_type'],
                'status'  : self.status[inverterData['status']],
                'pgrid_w' : str(inverterData['pac']),
                'temperature' : str(inverterData['tempperature']),
                'eday_kwh' : str(inverterData['eday']),
                'etotal_kwh' : str(inverterData['etotal']),
                'emonth_kwh' : str(inverterData['thismonthetotle']+inverterData['eday']),
                'grid_voltage' : str(inverterData['vac1']),
                'grd_frequency' : str(inverterData['fac1'])
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

_LOGGER.debug("update called.")

global REGISTERED
if REGISTERED == 0:
    try:
        station = self._config[CONF_STATION_ID]
        user = self._config[CONF_USERNAME]
        password = self._config[CONF_PASSWORD]
        gw = GoodWeApi(station, user, password)
        data = gw.getCurrentReadings()
    
        payload_type                {
                                'name':'inverter_type',
                                'value_template':'{{ value_json.type }}',
                                'icon':'mdi:flash',
                                'state_topic':'sems/sensors',
                                'unique_id':'sems_inverter_type_sensor',
                                    'device':   {
                                                'identifiers':'Goodwe Inverter',
                                                'name':'GoodWe Inverter',
                                                'model':data['type'],
                                                'manufacturer':'GoodWe'
                                                }
                                }    
        payload_status =            {
                                'name':'inverter_status',
                                'value_template':'{{ value_json.status }}',
                                'icon':'mdi:flash',
                                'state_topic':'sems/sensors',
                                'unique_id':'sems_inverter_status_sensor',
                                    'device':   {
                                                'identifiers':'Goodwe Inverter',
                                                'name':'GoodWe Inverter',
                                                'model':data['type'],
                                                'manufacturer':'GoodWe'
                                                }
                                }
        payload_pgrid_w =           {
                                'name':'solar_power',
                                'unit_of_meas':'W',
                                'value_template':'{{ value_json.pgrid_w }}',
                                'icon':'mdi:flash',
                                'state_topic':'sems/sensors',
                                'unique_id':'sems_solar_power_sensor',
                                    'device':   {
                                                'identifiers':'Goodwe Inverter',
                                                'name':'GoodWe Inverter',
                                                'model':data['type'],
                                                'manufacturer':'GoodWe'
                                                }
                                }
        payload_temperature =       {
                                'name':'inverter_temperature',
                                'unit_of_meas':'°C',
                                'value_template':'{{ value_json.temperature }}',
                                'icon':'mdi:flash',
                                'state_topic':'sems/sensors',
                                'unique_id':'sems_inverter_temperature_sensor',
                                    'device':   {
                                                'identifiers':'Goodwe Inverter',
                                                'name':'GoodWe Inverter',
                                                'model':data['type'],
                                                'manufacturer':'GoodWe'
                                                }
                                }
        payload_eday_kwh =          {
                                'name':'produced_today',
                                'unit_of_meas':'kWh',
                                'value_template':'{{ value_json.eday_kwh }}',
                                'icon':'mdi:flash',
                                'state_topic':'sems/sensors',
                                'unique_id':'sems_produced_today_sensor',
                                    'device':   {
                                                'identifiers':'Goodwe Inverter',
                                                'name':'GoodWe Inverter',
                                                'model':data['type'],
                                                'manufacturer':'GoodWe'
                                                }
                                }
        payload_etotal_kwh =        {
                                'name':'produced_total',
                                'unit_of_meas':'kWh',
                                'value_template':'{{ value_json.etotal_kwh }}',
                                'icon':'mdi:flash',
                                'state_topic':'sems/sensors',
                                'unique_id':'sems_produced_total_sensor',
                                    'device':   {
                                                'identifiers':'Goodwe Inverter',
                                                'name':'GoodWe Inverter',
                                                'model':data['type'],
                                                'manufacturer':'GoodWe'
                                                }
                                }
        payload_emonth_kwh =        {
                                'name':'produced_this_month',
                                'unit_of_meas':'kWh',
                                'value_template':'{{ value_json.emonth_kwh }}',
                                'icon':'mdi:flash',
                                'state_topic':'sems/sensors',
                                'unique_id':'sems_produced_this_month_sensor',
                                    'device':   {
                                                'identifiers':'Goodwe Inverter',
                                                'name':'GoodWe Inverter',
                                                'model':data['type'],
                                                'manufacturer':'GoodWe'
                                                }
                                }
        payload_grid_voltage =      {
                                'name':'grid_voltage',
                                'unit_of_meas':'VAC',
                                'value_template':'{{ value_json.grid_voltage }}',
                                'icon':'mdi:flash',
                                'state_topic':'sems/sensors',
                                'unique_id':'sems_grid_voltage_sensor',
                                    'device':   {
                                                'identifiers':'Goodwe Inverter',
                                                'name':'GoodWe Inverter',
                                                'model':data['type'],
                                                'manufacturer':'GoodWe'
                                                }
                                }
        payload_grid_frequency =    {
                                'name':'grid_frequency',
                                'unit_of_meas':'',
                                'value_template':'{{ value_json.grid_frequency }}',
                                'icon':'mdi:flash',
                                'state_topic':'sems/sensors',
                                'unique_id':'sems_grid_frequency_sensor',
                                    'device':   {
                                                'identifiers':'Goodwe Inverter',
                                                'name':'GoodWe Inverter',
                                                'model':data['type'],
                                                'manufacturer':'GoodWe'
                                                }
                                }

        data=json.dumps(data)
        data = data.replace(": ", ":")
        _LOGGER.debug("Updated sems data")
    except Exception as exception:
        _LOGGER.error("Unable to fetch data from SEMS. %s", exception)
    
