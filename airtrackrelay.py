# SPDX-License-Identifier: MIT
"""airtrackrelay

 Read GPS tracker reports and relay to metarace telegraph
 as JSON encoded objects.

"""

import sys
import socket
import logging
import metarace
from metarace.strops import confopt_posint
from metarace.telegraph import telegraph
from Cryptodome.Cipher import AES
from struct import unpack

_LOGLEVEL = logging.INFO
_log = logging.getLogger('airtrackrelay')
_log.setLevel(_LOGLEVEL)

_PORT = 1911
_TOPIC = 'tracking/data'
# length of data point record in RESP:GTFRI
_FRILEN = 12
# offset to first data point in RESP:GTFRI
_FRIOFT = 7
_ZEROBLOCK = b'\x00' * 16
# default beaker encryption keys
_KEY1 = b'0123456789abcdef'
_KEY2 = b'89abcdef01234567'
# default beaker uid / config id
_UID = 0x45670123


class app:
    """UDP Tracking application"""

    def __init__(self):
        self._t = telegraph()
        self._topic = _TOPIC
        self._port = _PORT
        self._k1 = _KEY1
        self._k2 = _KEY2
        self._uid = _UID
        self._imeis = {}

    def _loadconfig(self):
        """Read config options from metarace sysconf"""
        if metarace.sysconf.has_option('airtrackrelay', 'topic'):
            self._topic = metarace.sysconf.get_str('airtrackrelay', 'topic',
                                                   _TOPIC)
        if metarace.sysconf.has_option('airtrackrelay', 'port'):
            self._port = metarace.sysconf.get_posint('airtrackrelay', 'port',
                                                     _PORT)
        if metarace.sysconf.has_option('airtrackrelay', 'k1'):
            keystr = metarace.sysconf.get_str('airtrackrelay', 'k1', None)
            if keystr:
                self._k1 = bytes.fromhex(keystr)
        if metarace.sysconf.has_option('airtrackrelay', 'k2'):
            keystr = metarace.sysconf.get_str('airtrackrelay', 'k2', None)
            if keystr:
                self._k2 = bytes.fromhex(keystr)
        if metarace.sysconf.has_option('airtrackrelay', 'uid'):
            self._uid = metarace.sysconf.get_posint('airtrackrelay', 'uid',
                                                    _UID)
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
        _log.debug('ACK: %r', obj)
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
        _log.debug('INF: %r', obj)
        self._t.publish_json(topic=self._topic, obj=obj)

    def _glfri(self, drd, msg, buff):
        """Process FRI/RTL message"""
        _log.debug('FRI/RTL: %r', msg)
        msgcnt = confopt_posint(msg[6], 1)
        oft = 0
        while oft < msgcnt:
            sp = oft * _FRILEN + _FRIOFT
            if len(msg) > sp + 6:
                flags = 0
                spd = msg[sp + 1]
                elev = msg[sp + 3]
                lng = msg[sp + 4]
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
                    'lng': lng,
                    'elev': elev,
                    'speed': spd,
                    'drd': drd,
                    'fixtime': utc,
                    'battery': batt,
                    'buffered': buff,
                    'flags': flags
                }
                _log.debug('LOC: %r', obj)
                self._t.publish_json(topic=self._topic, obj=obj)
            else:
                _log.debug('Short message: %r', msg)
                break
            oft += 1

    def _beaker(self, buf):
        """Handle AES128 encrypted Beaker location report"""
        # decrypt message
        cipher = AES.new(self._k2, AES.MODE_CBC, buf[0:16])
        msg = cipher.decrypt(buf[16:])
        pt = msg[0:32]
        mac = msg[32:]
        # verify plaintext
        cipher = AES.new(self._k1, AES.MODE_CBC, _ZEROBLOCK)
        mchk = cipher.encrypt(pt)
        # decode content
        if mchk[-16:] == mac:
            (imeival, utcval, dateval, latval, lngval, speedval, infoval,
             uidval) = unpack('<QLLllHHL', pt)
            if uidval == self._uid:
                drd = None
                imei = str(imeival)
                if imei in self._imeis:
                    drd = self._imeis[imei]
                else:
                    _log.info('Ignoring unknown beaker with imei: %r', imei)
                    return None
                # get hemisphere
                south = False
                if latval < 0:
                    south = True
                    latval = -latval
                lat = int(latval // 10000000)
                latstr = str(latval)
                lat += float('%s.%s' % (latstr[2:4], latstr[4:])) / 60.0
                if south:
                    lat = -lat

                # get lng
                west = False
                if lngval < 0:
                    west = True
                    lngval = -lngval
                lng = int(lngval // 10000000)
                lngstr = str(lngval)
                lng += float('%s.%s' % (lngstr[3:5], lngstr[5:])) / 60.0
                if west:
                    lng = -lng
                utcstr = str(utcval).rjust(8, '0')
                datestr = str(dateval).rjust(6, '0')
                utc = '%d-%s-%sT%s:%s:%s.%sZ' % (
                    2000 + int(datestr[4:6]), datestr[2:4], datestr[0:2],
                    utcstr[0:2], utcstr[2:4], utcstr[4:6], utcstr[6:8])

                # speed
                speed = '%0.1f' % (1.151 * speedval / 100.0)
                # battery - bottom 8 bits
                battery = '%d' % (infoval & 0xff)
                flags = infoval >> 8
                obj = {
                    'type': 'drdpos',
                    'fix': True,
                    'lat': '%0.6f' % (lat),
                    'lng': '%0.6f' % (lng),
                    'speed': speed,
                    'drd': drd,
                    'fixtime': utc,
                    'battery': battery,
                    'buffered': False,
                    'flags': flags
                }
                _log.debug('LOC: %r', obj)
                self._t.publish_json(topic=self._topic, obj=obj)
            else:
                _log.warning('Invalid uid/config id: %r != %r', uidval,
                             self._uid)
        else:
            _log.warning('Invalid MAC')

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
                if ctype in ['GTFRI', 'GTRTL', 'GTSOS', 'GTLOC'
                             ] and len(msg) > 20:
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
            if len(buf) == 64:
                # assume AES encrypted beaker format
                self._beaker(buf)
            elif buf.endswith(b'$'):
                if buf.startswith(b'+RESP') or buf.startswith(
                        b'+BUFF') or buf.startswith(b'+ACK'):
                    msg = buf.decode('iso8859-1').split(',')
                    self._glmsg(msg)
                else:
                    _log.debug('Unrecognised message:  %r', buf)
            else:
                _log.debug('Unrecognised message:  %r', buf)

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
