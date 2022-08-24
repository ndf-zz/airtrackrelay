# airtrackrelay

Insecure UDP socket server to collect Quectel GPS tracker "Air Interface"
reports and relay them to metarace telegraph as JSON encoded objects.

Configuration is via metarace sysconf section 'airtrackrelay' with the
following keys:

key	|	(type) Description [default]
---	|	---
topic	|	(string) MQTT relay topic ['tracking/data']
port	|	(int) UDP listen port [1911]

Trackers imeis are read from the section 'tracking' under the
key 'devices', which is a map of device ids to a dict object:

key	|	(type) Description [default]
---	|	---
imei	|	(string) Device IMEI
label	|	(string) Text label [None]
phone	|	(string) Phone number for SMS commands [None]
type	|	(string) Device type

Notes:

   - No authentication is performed
   - All datagrams are delivered in clear text
   - Trackers to not provide any mechanism to prevent replay,
     modification or corruption

## Requirements

   - metarace >=2.0

## Installation

	$ pip3 install airtrackrelay

