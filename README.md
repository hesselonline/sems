# GoodWe SEMS Portal Component for Home Assistant
Home Assistant component for accessing the GoodWe SEMS Portal API.
Adapted from https://github.com/TimSoethout/goodwe-sems-home-assistant, which I used for a few months, but altered to use the SEMS API.
API adaption heavily inspired by https://github.com/markruys/gw2pvo.

Installation of this component is done by copying the sensor.py, __init__.py and manifest.json files to [homeassistant_config]/custom_components/sems folder.

In configuration.yaml add the sensor as follows:

    - platform: sems                                                                                                                             username: yourusernamehere
      password: secretpasswordfromsemsportal
      station_id: stationidhere
      name: (optional, name for sensor)
<br>
Station ID can be found by logging on to the SEMS portal (part of URL after https://www.semsportal.com/PowerStation/PowerStatusSnMin/).

