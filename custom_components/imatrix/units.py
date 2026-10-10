"""Resolve stable sensor semantics without relying on API unit spelling."""
import re
from typing import NamedTuple


class UnitResolution(NamedTuple):
    unit: str | None
    device_class: str | None
    kind: str
    scale: float = 1.0
    offset: float = 0.0
    source: str = 'api'
    supported: bool = True


# Canonical HA units preserve existing temperature and data-rate statistics.
PROFILES = {
    'temperature': ('°C', 'temperature'),
    'humidity': ('%', 'humidity'),
    'battery': ('%', 'battery'),
    'percent': ('%', None),
    'pressure': ('kPa', 'pressure'),
    'voltage': ('V', None),
    'duration': ('s', None),
    'count': (None, None),
    'angle': ('°', None),
    'distance': ('m', None),
    'signal': ('dB', 'signal_strength'),
    'signal_power': ('dBm', 'signal_strength'),
    'data_rate': ('Bps', None),
    'unitless': (None, None),
}


def normalize(text):
    return re.sub(r'[^a-z0-9]+', '', str(text or '').casefold())


def sensor_kind(name):
    """Use sensor meaning; never infer physical units from a numeric value."""
    name = normalize(name)
    if name in ('temperature', 'dewpoint', 'heatindex', 'wetbulb'):
        return 'temperature'
    if name == 'humidity':
        return 'humidity'
    if name == 'batterylevel':
        return 'battery'
    if name == 'batteryvoltage':
        return 'voltage'
    if name in ('airvpd', 'vpd', 'pressure', 'barometricpressure'):
        return 'pressure'
    if name in ('latitude', 'longitude'):
        return 'angle'
    if name == 'altitude':
        return 'distance'
    if name.endswith(('rxdatarate', 'txdatarate')):
        return 'data_rate'
    if name.endswith('duration'):
        return 'duration'
    if name in ('devices', 'activedevices', 'bootcount', 'openevents', 'opencount',
                'nosatellites', 'nobledevices', 'noactivebledevices'):
        return 'count'
    if name == 'wifinoise':
        return 'signal_power'
    if name.endswith(('rssi', 'rsrp', 'rsrq', 'sinr')):
        return 'signal'
    if name in ('tamper', 'wifichannel', '4gcarrier', '4gband', '4gnetworktype',
                '4gber', 'hdop', 'fixquality'):
        return 'unitless'
    return None


def parse_unit(raw):
    """Return dimension, scale and offset to its canonical unit.

    Byte/bit prefixes are case-sensitive: Bps and bps are different.
    """
    text = re.sub(r'\s+', '', str(raw or '').strip())
    if text in ('B/s', 'Bps', 'B/sec', 'B/s.'): return ('data_rate', 1.0, 0.0)
    if text in ('bps', 'b/s', 'bit/s'): return ('data_rate', 1 / 8, 0.0)
    key = normalize(raw)
    if key in ('degc', 'c', 'celsius', 'degreecelsius', 'degreescelsius'):
        return ('temperature', 1.0, 0.0)
    if key in ('degf', 'f', 'fahrenheit', 'degreefahrenheit', 'degreesfahrenheit'):
        return ('temperature', 5 / 9, -160 / 9)
    if key in ('k', 'kelvin'): return ('temperature', 1.0, -273.15)
    if str(raw or '').strip() in ('%', '%RH') or key in ('rh', 'percent', 'percentage', 'level'):
        return ('percent', 1.0, 0.0)
    if key == 'kpa': return ('pressure', 1.0, 0.0)
    if key == 'pa': return ('pressure', .001, 0.0)
    if key in ('hpa', 'mbar'): return ('pressure', .1, 0.0)
    if key in ('v', 'volt', 'volts'): return ('voltage', 1.0, 0.0)
    if key in ('mv', 'millivolt', 'millivolts'): return ('voltage', .001, 0.0)
    if key in ('s', 'sec', 'secs', 'second', 'seconds'): return ('duration', 1.0, 0.0)
    if key in ('ms', 'millisecond', 'milliseconds'): return ('duration', .001, 0.0)
    if key in ('count', 'counts', 'things', 'devices'): return ('count', 1.0, 0.0)
    if key in ('deg', 'degree', 'degrees') or str(raw or '').strip() == '°':
        return ('angle', 1.0, 0.0)
    if key in ('m', 'meter', 'meters', 'metre', 'metres'): return ('distance', 1.0, 0.0)
    if key == 'db': return ('signal', 1.0, 0.0)
    if key == 'dbm': return ('signal_power', 1.0, 0.0)
    if key in ('bytespersecond', 'bytepersecond'): return ('data_rate', 1.0, 0.0)
    if key in ('bitspersecond', 'bitpersecond'): return ('data_rate', 1 / 8, 0.0)
    return None


def resolve_unit(name, raw):
    kind = sensor_kind(name)
    parsed = parse_unit(raw)
    if kind is None:
        if parsed is None:
            return UnitResolution(None, None, 'unknown', source='unknown', supported=False)
        kind = parsed[0]
    unit, device_class = PROFILES[kind]
    if parsed is None:
        return UnitResolution(unit, device_class, kind, source='sensor_name')
    dimension, scale, offset = parsed
    if dimension == kind or (kind in ('battery', 'humidity') and dimension == 'percent'):
        return UnitResolution(unit, device_class, kind, scale, offset)
    # Never label incompatible values as though they were in the expected unit.
    return UnitResolution(unit, device_class, kind, source='conflict', supported=False)
