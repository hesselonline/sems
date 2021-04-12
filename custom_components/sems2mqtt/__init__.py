""""
Home Assistant component for accessing the GoodWe SEMS Portal API.
    Adapted from https://github.com/TimSoethout/goodwe-sems-home-assistant, but altered to use the SEMS API.
    API adaption by hesselonline, heavily inspired by https://github.com/markruys/gw2pvo.
    Adapted furthermore using MQTT messages using HA-discovery to create separate sensors.
    
Configuration (example):

sems2mqtt:
  broker: mqtt broker IP
  broker_user: mqtt broker login
  broker_pw: mqtt broker password
  username: sems login (email)
  password: sems password
  station_id: your station ID
  client: MQTT cient-id (optional, default is 'sems2mqtt')
  scan_interval: 150 (optional, default is 300 seconds, keep to 300 seconds or less!)
"""

import json
import logging
import time
from datetime import datetime, timedelta
import requests
import logging
import voluptuous as vol
import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt

from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, 
    CONF_SCAN_INTERVAL, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_BROKER = 'broker'
CONF_BROKER_USERNAME = 'broker_user'
CONF_BROKER_PASSWORD = 'broker_pw'
CONF_STATION_ID = 'station_id'
CONF_CLIENT = 'client'

DEFAULT_CL = 'sems2mqtt'
DOMAIN = 'sems2mqtt'
REGISTERED = 0
SCAN_INTERVAL = timedelta(seconds=300)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_BROKER): cv.string,
        vol.Required(CONF_BROKER_USERNAME): cv.string,
        vol.Required(CONF_BROKER_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_STATION_ID): cv.string,
        vol.Optional(CONF_CLIENT, default=DEFAULT_CL): cv.string,
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
    client = conf.get(CONF_CLIENT)
    scan_interval = conf.get(CONF_SCAN_INTERVAL)

    client_id = client
    auth = {'username':broker_user, 'password':broker_pw}
    port = 1883
    keepalive = 300
    
    def issue_pub_single(topic, payload, broker, port, auth, client):
        """ Helper function for publish.single."""
        return publish.single(
            topic,
            payload,
            qos=0,
            retain=True,
            hostname=broker,
            port=port,
            auth=auth,
            client_id=client,
            protocol=mqtt.MQTTv311,
        )

    async def async_get_sems_data(event_time):   
        """Get the topics from the SEMS API and send the corresponding sensor-data to the MQTT Broker."""

        async def getCurrentReadings(station_id):
            ''' Download the most recent readings from the GoodWe API. '''
            status = { -1 : 'Offline', 0 : 'Waiting', 1 : 'Online' }
            payload = {'powerStationId' : station_id}
            data = await call(
                "v1/PowerStation/GetMonitorDetailByPowerstationId",
                payload,
            )
            inverterData = data['inverter'][0]['invert_full']
            result = {
                'type': inverterData.get('model_type'),
                'status': status.get(inverterData.get('status'),'Unknown'),
                'pgrid_w': str(inverterData.get('pac')),
                'temperature': str(inverterData.get('tempperature')),
                'eday_kwh': str(inverterData.get('eday')),
                'etotal_kwh': str(inverterData.get('etotal')),
                'emonth_kwh': str(
                    round(
                        float(
                            inverterData.get('thismonthetotle')
                            + inverterData.get('eday')
                        ), 1)
                ),
                'grid_voltage' : str(inverterData.get('vac1')),
                'grid_current' : str(inverterData['iac1']),
                'grid_frequency' : str(inverterData.get('fac1')),
                'dc_voltage_str_1' : str(inverterData.get('vpv1')),
                'dc_current_str_1' : str(inverterData.get('ipv1')),
                'dc_voltage_str_2' : str(inverterData.get('vpv2')),
                'dc_current_str_2' : str(inverterData.get('ipv2')),
                'battery_soc' : str(inverterData.get('soc')),
                'battery_soh' : str(inverterData.get('soh'))
            }
            
            return result

        def issuePost(url, headers, payload, timeout):
            """Helper function for request.post()."""
            return requests.post(url, headers=headers, data=payload, timeout=timeout)
        
        def issueException():
            """Helper function for requests.exceptions."""
            return requests.exceptions.RequestException

        async def call(url, payload):
            token = '{"version":"","client":"web","language":"en"}'
            global_url = 'https://eu.semsportal.com/api/'
            base_url = global_url
            for i in range(1, 4):
                try:
                    headers = {'Token': token }
                    r = await hass.async_add_executor_job(
                        issuePost,
                        base_url + url,
                        headers,
                        payload,
                        20,
                    )
                    r.raise_for_status()
                    data = r.json()

                    if data['msg'] == 'success' and data['data'] is not None:
                        return data['data']
                    else:
                        loginPayload = { 'account': account, 'pwd': password }
                        r = await hass.async_add_executor_job(
                                issuePost,
                                global_url + 'v1/Common/CrossLogin',
                                headers,
                                loginPayload,
                                20,
                        )
                        r.raise_for_status()
                        data = r.json()
                        base_url = data['api']
                        token = json.dumps(data['data'])
                except await hass.async_add_executor_job(issueException) as exp:
                    _LOGGER.warning(exp)
                time.sleep((2*i) ** 2)
            else:
                _LOGGER.error("Failed to obtain data from the SEMS API")
                return {}

        def create_device(model):
            return { 
                'identifiers':'Goodwe Inverter',
                'name':'GoodWe Inverter',
                'model':model,
                'manufacturer':'GoodWe'
            }

        # body of async_get_sems_data()
        global REGISTERED
        try:
            account = username
            station = station_id
            user = username

            data = await getCurrentReadings(station)

            payload_type = {
                'name':'sems_inverter_type',
                'value_template':'{{ value_json.type }}',
                'icon':'mdi:solar-power',
                'state_topic':'sems/sensors',
                'unique_id':'sems_inverter_type_sensor',
                    'device': create_device(data['type'])
            }  
            payload_status = {
                'name':'sems_inverter_status',
                'value_template':'{{ value_json.status }}',
                'icon':'mdi:lan-connect',
                'state_topic':'sems/sensors',
                'unique_id':'sems_inverter_status_sensor',
                    'device': create_device(data['type'])
            }
            payload_pgrid_w = {
                'name':'sems_solar_power',
                'unit_of_meas':'W',
                'value_template':'{{ value_json.pgrid_w }}',
                'icon':'mdi:solar-power',
                'state_topic':'sems/sensors',
                'unique_id':'sems_solar_power_sensor',
                    'device': create_device(data['type'])
            }
            payload_temperature = {
                'name':'sems_inverter_temperature',
                'unit_of_meas':'°C',
                'value_template':'{{ value_json.temperature }}',
                'icon':'mdi:thermometer',
                'state_topic':'sems/sensors',
                'unique_id':'sems_inverter_temperature_sensor',
                    'device': create_device(data['type'])
            }
            payload_eday_kwh = {
                'name':'sems_produced_today',
                'unit_of_meas':'kWh',
                'value_template':'{{ value_json.eday_kwh }}',
                'icon':'mdi:flash',
                'state_topic':'sems/sensors',
                'unique_id':'sems_produced_today_sensor',
                    'device': create_device(data['type'])
            }
            payload_etotal_kwh = {
                'name':'sems_produced_total',
                'unit_of_meas':'kWh',
                'value_template':'{{ value_json.etotal_kwh }}',
                'icon':'mdi:flash',
                'state_topic':'sems/sensors',
                'unique_id':'sems_produced_total_sensor',
                    'device': create_device(data['type'])
            }
            payload_emonth_kwh = {
                'name':'sems_produced_this_month',
                'unit_of_meas':'kWh',
                'value_template':'{{ value_json.emonth_kwh }}',
                'icon':'mdi:flash',
                'state_topic':'sems/sensors',
                'unique_id':'sems_produced_this_month_sensor',
                    'device': create_device(data['type'])
            }
            payload_grid_voltage = {
                'name':'sems_grid_voltage',
                'unit_of_meas':'VAC',
                'value_template':'{{ value_json.grid_voltage }}',
                'icon':'mdi:current-ac',
                'state_topic':'sems/sensors',
                'unique_id':'sems_grid_voltage_sensor',
                    'device': create_device(data['type'])
            }
            payload_grid_current = {
                'name':'sems_grid_current',
                'unit_of_meas':'IAC',
                'value_template':'{{ value_json.grid_current }}',
                'icon':'mdi:current-ac',
                'state_topic':'sems/sensors',
                'unique_id':'sems_grid_current_sensor',
                    'device': create_device(data['type'])
            }
            payload_grid_frequency = {
                'name':'sems_grid_frequency',
                'unit_of_meas':'Hz',
                'value_template':'{{ value_json.grid_frequency }}',
                'icon':'mdi:current-ac',
                'state_topic':'sems/sensors',
                'unique_id':'sems_grid_frequency_sensor',
                    'device': create_device(data['type'])
            }
            payload_str_1_voltage = {
                'name':'sems_str_1_voltage',
                'unit_of_meas':'VDC',
                'value_template':'{{ value_json.dc_voltage_str_1 }}',
                'icon':'mdi:current-dc',
                'state_topic':'sems/sensors',
                'unique_id':'sems_str_1_voltage_sensor',
                    'device': create_device(data['type'])
            }
            payload_str_1_current = {
                'name':'sems_str_1_current',
                'unit_of_meas':'VDC',
                'value_template':'{{ value_json.dc_current_str_1 }}',
                'icon':'mdi:current-dc',
                'state_topic':'sems/sensors',
                'unique_id':'sems_str_1_current_sensor',
                    'device': create_device(data['type'])
            }
            payload_str_2_voltage = {
                'name':'sems_str_2_voltage',
                'unit_of_meas':'VDC',
                'value_template':'{{ value_json.dc_voltage_str_2 }}',
                'icon':'mdi:current-dc',
                'state_topic':'sems/sensors',
                'unique_id':'sems_str_2_voltage_sensor',
                    'device': create_device(data['type'])
            }
            payload_str_2_current = {
                'name':'sems_str_2_current',
                'unit_of_meas':'VDC',
                'value_template':'{{ value_json.dc_current_str_2 }}',
                'icon':'mdi:current-dc',
                'state_topic':'sems/sensors',
                'unique_id':'sems_str_2_current_sensor',
                    'device': create_device(data['type'])
            }
            payload_battery_soc = {
                'name':'sems_battery_soc',
                'unit_of_meas':'%',
                'value_template':'{{ value_json.battery_soc }}',
                'icon':'mdi:battery-charging',
                'state_topic':'sems/sensors',
                'unique_id':'sems_battery_soc_sensor',
                    'device': create_device(data['type'])
            }
            payload_battery_soh = {
                'name':'sems_battery_soh',
                'unit_of_meas':'%',
                'value_template':'{{ value_json.battery_soh }}',
                'icon':'mdi:medical-bag',
                'state_topic':'sems/sensors',
                'unique_id':'sems_battery_soh_sensor',
                    'device': create_device(data['type'])
            }

        except Exception as exception:
            _LOGGER.error(
                "Unable to fetch data from the SEMS API,",
                exception,
                "not available",
            )
        else:
            if REGISTERED == 0:
                for key,value in data.items():
                    if(key is not None and value is not None):
                        parameter = key
                        payload = "payload_"+str(parameter)
                        payload = locals()[payload]
                        payload = json.dumps(payload)
                        await hass.async_add_executor_job(
                            issue_pub_single, 
                            f'homeassistant/sensor/sems/{parameter}/config',
                            payload,
                            broker,
                            port,
                            auth,
                            client,
                        )
            REGISTERED = 1
            payload = json.dumps(data)
            payload = payload.replace(": ", ":")
            await hass.async_add_executor_job(
                issue_pub_single,
                'sems/sensors',
                payload,
                broker,
                port,
                auth,
                client,
            )

    async_track_time_interval(hass, async_get_sems_data, scan_interval)

    return True
