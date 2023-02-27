# airtrackrelay

UDP socket server to collect live tracking reports and
relay them to metarace telegraph as JSON encoded objects.

Supported tracking devices and messages:

   - Quectel GL300/320 "Air Interface"
      - +ACK : Command acknowledge, type: 'drdack'
      - +RESP, +BUFF:
      - GTFRI, GTRTL, GTSOS, GTLOC : Location report, type: 'drdpos'
      - GTINF : Information report, type: 'drdstat'
   - Beaker
      - AES128 Location, type 'drdpos'

Configuration is via metarace sysconf section 'airtrackrelay' with the
following keys:

key	|	(type) Description [default]
---	|	---
topic	|	(string) MQTT relay topic ['tracking/data']
port	|	(int) UDP listen port [1911]
k1	|	(string) Beaker K1, 128 bit hex string [null]
k2	|	(string) Beaker K2, 128 bit hex string [null]
uid	|	(int32) Beaker uid/config id [0x45670123]


Tracker imeis are read from the section 'tracking' under the
key 'devices', which is a map of device ids to a dict object:


key	|	(type) Description [default]
---	|	---
imei	|	(string) Device IMEI
type	|	(string) Device type

Example config:

	{
	 "airtrackrelay": {
	  "port": 12345,
	  "topic": "tracking/data",
          "key": "000102030405060708090a0b0c0d0e0f",
          "cbcsig": 1234567890
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

Example Ack Message:

	{"type": "drdack", "drd": "gem", "ctype": "GTFRI", "cid": "1A3D",
	 "sendtime": "20220101031607", "req": ""}

Example GL3xx Location Message:

	{"type": "drdpos", "fix": true, "lat": "-13.567891",
	 "lng": "101.367815", "elev": "22.6", "speed": "12.7",
	 "drd": "gem", "fixtime": "20220101022231",
	 "buffered": false, "battery": "94", "flags": 0}

Example Beaker Location Message:

	{"type": "drdpos", "fix": true, "lat": "-12.345666",
	 "lng": "101.123555", "speed": "0.0", "drd": "bob",
	 "fixtime": "2023-01-13T03:12:49.00Z", "battery": "100",
	 "buffered": false, "flags": 255}



## Requirements

   - metarace >=2.0


## Installation

	$ pip3 install airtrackrelay

