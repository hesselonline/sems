# GoodWe SEMS Portal Component for Home Assistant
Home Assistant component for accessing the GoodWe SEMS Portal API.
Adapted from https://github.com/TimSoethout/goodwe-sems-home-assistant, which I used for a few months, but altered to use the SEMS API.
API adaption by hesselonline, heavily inspired by https://github.com/markruys/gw2pvo.
Adapted furthermore using MQTT messages using HA-discovery to create separate sensors.

Installation of this component is done by copying the __init__.py and manifest.json files to 
[homeassistant_config]/custom_components/sems folder.

In configuration.yaml add the custom_component as follows:

sems:
  broker: mqtt broker IP
  broker_user: mqtt broker login
  broker_pw: mqtt broker password
  username: sems login (full email)
  password: sems password
  station_id: your station ID
  scan_interval: 30 (optional, default is 60 seconds)

<br>
Station ID can be found by logging on to the SEMS portal (part of URL after https://www.semsportal.com/PowerStation/PowerStatusSnMin/).

