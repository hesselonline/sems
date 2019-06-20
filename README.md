# GoodWe SEMS Portal MQTT Component for Home Assistant
Home Assistant component for accessing the GoodWe SEMS Portal API.
Adapted from https://github.com/TimSoethout/goodwe-sems-home-assistant but altered to use the SEMS API.
API adaption by hesselonline, heavily inspired by https://github.com/markruys/gw2pvo.
Adapted furthermore by bouwew, using MQTT messages using HA-discovery to create separate sensors.

NOTE: this component requires an MQTT-broker to be present in your network.
There is one available in the Hassio Official Add-ons.

Installation of this component is done by copying the files ```__init__.py``` and manifest.json to the
[homeassistant_config]/custom_components/sems2mqtt folder.

In configuration.yaml add the custom_component as follows:
```
sems2mqtt:
  broker: 192.168.1.10          mqtt broker IP
  broker_user: username         mqtt broker login
  broker_pw: password1          mqtt broker password
  username: john.doe@gmail.com  sems login (full email)
  password: password2           sems password
  station_id: your-station-ID   see remark below
  client: sems2mqtt             (optional, MQTT cient-id, default is 'sems2mqtt')
  scan_interval: 150            (optional, default is 300 seconds, keep to )
```

This component use MQTT-disovery to find the sensors. The various parameters collected from the API will be shown as separate sensors, not as one sensor with several attributes. The sensors will show up 

<br>
Station ID can be found by logging on to the SEMS portal (part of URL after https://www.semsportal.com/PowerStation/PowerStatusSnMin/).

