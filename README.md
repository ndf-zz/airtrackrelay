# airtrackrelay

Insecure UDP socket server to collect Quectel GL300W GPS tracker
"Air Interface" reports and relay them to metarace telegraph as
JSON encoded objects.

Messages relayed to mqtt:

   - +ACK : Command acknowledge, type: 'drdack'
   - +RESP, +BUFF:
     - GTFRI, GTFRL : Location report, type: 'drdpos'
     - GTINF : Information report, type: 'drdstat'

All other Air Interface messages are logged, and discarded.

Configuration is via metarace sysconf section 'airtrackrelay' with the
following keys:

key	|	(type) Description [default]
---	|	---
topic	|	(string) MQTT relay topic ['tracking/data']
port	|	(int) UDP listen port [1911]

Tracker imeis are read from the section 'tracking' under the
key 'devices', which is a map of device ids to a dict object:


key	|	(type) Description [default]
---	|	---
imei	|	(string) Device IMEI
type	|	(string) Device type

Example config:

	{
	 "airtrackrelay": {
	  "port": 123456,
	  "topic": "tracking/data"
	 },
	 "tracking": {
	  "devices": {
	   "bob": { "imei": "012345678901234", "label": null,
	    "phone": "+12345678901", "type": null },
	   "gem": { "imei": "023456788901234", "label": null,
	    "phone": null, "type": null },
	  }
	 }
	}

Example Info Message:

	{"type": "drdstat", "drd": "bob", "devstate": "41", "rssi": "13",
	 "voltage": "4.08", "battery": "94", "charging": "0", "buffered": false,
	 "sendtime": "20220101023424" }

Example Location Message:

	{"type": "drdpos", "fix": true, "lat": "-13.567891",
	 "lon": "101.367815", "elev": "22.6", "speed": "12.7",
	 "hdop": "1", "drd": "gem", "fixtime": "20220101022231",
	 "buffered": false, "battery": "94", "sendtime": "20220101022231"}

Example Ack Message:

	{"type": "drdack", "drd": "gem", "ctype": "GTFRI", "cid": "1A3D",
	 "sendtime": "20220101031607", "req": ""}


Notes:

   - Tracker type is currently ignored, GL300W is assumed
   - No authentication is performed
   - Trackers to not provide any mechanism to prevent replay,
     modification or corruption
   - Message contents are not verified, parsed or converted


## Requirements

   - metarace >=2.0


## Installation

	$ pip3 install airtrackrelay

