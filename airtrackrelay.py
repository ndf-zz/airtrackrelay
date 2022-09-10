# SPDX-License-Identifier: MIT
"""airtrackrelay

 Read Quectel GPS tracker plain text "Air Interface" reports
 and relay them to metarace telegraph as JSON encoded objects.

"""

import sys
import socket
import logging
import metarace
from metarace.strops import confopt_posint
from metarace.telegraph import telegraph

_LOGLEVEL = logging.DEBUG
_log = logging.getLogger('airtrackrelay')
_log.setLevel(_LOGLEVEL)

_PORT = 1911
_TOPIC = 'tracking/data'
# length of data point record in RESP:GTFRI
_FRILEN = 12
# offset to first data point in RESP:GTFRI
_FRIOFT = 7


class app:
    """UDP Tracking application"""

    def __init__(self):
        self._t = telegraph()
        self._topic = _TOPIC
        self._port = _PORT
        self._imeis = {}

    def _loadconfig(self):
        """Read config options from metarace sysconf"""
        if metarace.sysconf.has_option('airtrackrelay', 'topic'):
            self._topic = metarace.sysconf.get_str('airtrackrelay', 'topic',
                                                   _TOPIC)
        if metarace.sysconf.has_option('airtrackrelay', 'port'):
            self._port = metarace.sysconf.get_posint('airtrackrelay', 'port',
                                                     _PORT)
        if metarace.sysconf.has_option('tracking', 'devices'):
            drds = metarace.sysconf.get('tracking', 'devices')
            for drd in drds:
                self._imeis[drds[drd]['imei']] = drd
            _log.debug('%s configured drds: %r', len(self._imeis), self._imeis)

    def _glack(self, drd, msg, ctype):
        """Process an ACK message"""
        ctm = msg[-2]
        cid = msg[-3].upper()
        ctyp = msg[-4]
        obj = {
            'type': 'drdack',
            'drd': drd,
            'ctype': ctype,
            'cid': cid,
            'sendtime': ctm,
            'req': ctyp
        }
        _log.info('ACK: %r', obj)
        self._t.publish_json(topic=self._topic, obj=obj)

    def _glinf(self, drd, msg, buff):
        """Process an INF message"""
        # Message is an INFO update
        devstate = msg[4]
        rssi = msg[6]
        volt = msg[11]
        chrg = msg[12]
        batt = msg[18]
        sutc = msg[-2]  # message send time in UTC
        obj = {
            'type': 'drdstat',
            'drd': drd,
            'devstate': devstate,
            'rssi': rssi,
            'voltage': volt,
            'battery': batt,
            'charging': chrg,
            'buffered': buff,
            'sendtime': sutc
        }
        _log.info('INF: %r', obj)
        self._t.publish_json(topic=self._topic, obj=obj)

    def _glfri(self, drd, msg, buff):
        """Process FRI/RTL message"""
        _log.debug('FRI/RTL: %r', msg)
        msgcnt = confopt_posint(msg[6], 1)
        oft = 0
        while oft < msgcnt:
            sp = oft * _FRILEN + _FRIOFT
            if len(msg) > sp + 6:
                hdop = msg[sp]
                spd = msg[sp + 1]
                elev = msg[sp + 3]
                lon = msg[sp + 4]
                lat = msg[sp + 5]
                utc = msg[sp + 6]  # GPS fix time in UTC
                batt = msg[-3]  # battery level ??
                sutc = msg[-2]  # message send time in UTC
                fix = False
                if hdop != '0':
                    fix = True
                obj = {
                    'type': 'drdpos',
                    'fix': fix,
                    'lat': lat,
                    'lon': lon,
                    'elev': elev,
                    'speed': spd,
                    'hdop': hdop,
                    'drd': drd,
                    'fixtime': utc,
                    'buffered': buff,
                    'battery': batt,
                    'sendtime': sutc
                }
                _log.info('LOC: %r', obj)
                self._t.publish_json(topic=self._topic, obj=obj)
            else:
                _log.debug('Short message: %r', msg)
                break
            oft += 1

    def _glmsg(self, msg):
        """Handle a GL2xx,GL3xx Air Interface Message"""
        if len(msg) > 3:
            mtype, ctype = msg[0].split(':', 1)
            imei = msg[2]
            drd = None
            if imei in self._imeis:
                drd = self._imeis[imei]
            else:
                _log.info('Ignoring unknown tracker with imei: %r', imei)
                return None

            if mtype == u'+ACK' and len(msg) > 6:
                self._glack(drd, msg, ctype)
            elif mtype in ['+RESP', '+BUFF']:
                buff = mtype == '+BUFF'
                if ctype in ['GTFRI', 'GTRTL', 'GTSOS'] and len(msg) > 20:
                    self._glfri(drd, msg, buff)
                elif ctype in ['GTINF'] and len(msg) > 24:
                    self._glinf(drd, msg, buff)
                else:
                    _log.debug('Message from %r not relayed: %r', drd, msg)
            else:
                _log.debug('Invalid message type: %r', mtype)
        else:
            _log.debug('Invalid message: %r', msg)

    def _recvmsg(self, buf):
        """Receive messages from buf"""
        try:
            if buf.endswith(b'$'):
                if buf.startswith(b'+RESP') or buf.startswith(
                        b'+BUFF') or buf.startswith(b'+ACK'):
                    msg = buf.decode('iso8859-1').split(',')
                    self._glmsg(msg)
                else:
                    _log.debug('Unrecognised message:  %r', buf)
            else:
                _log.debug('Missing end character:  %r', buf)

        except Exception as e:
            _log.error('%s reading message: %s', e.__class__.__name__, e)

    def run(self):
        _log.info('Starting')
        self._loadconfig()

        # start telegraph thread
        self._t.start()

        # blocking read from UDP socket
        s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        s.bind(('::', self._port))
        _log.debug('Listening on UDP port %r', self._port)
        try:
            while True:
                b, addr = s.recvfrom(4096)
                _log.debug('RECV: %r %r', addr, b)
                self._recvmsg(b)
        finally:
            self._t.wait()
            self._t.exit()
            self._t.join()
        return 0


def main():
    ch = logging.StreamHandler()
    ch.setLevel(_LOGLEVEL)
    fh = logging.Formatter(metarace.LOGFORMAT)
    ch.setFormatter(fh)
    logging.getLogger().addHandler(ch)

    # initialise the base library
    metarace.init()

    # Create and start tracker app
    a = app()
    return a.run()


if __name__ == '__main__':
    sys.exit(main())
