import hashlib
import json
import re
from fractions import Fraction


Point = tuple[Fraction, Fraction]
_STATION_ID = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}')
_MAX_SQLITE_ID = 2**63 - 1


def rational(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, str, Fraction)):
        raise ValueError(f'{label} must be an exact rational number')
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError(f'{label} must be an exact rational number') from error


def point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError('a point requires two coordinates')
    return rational(value[0], 'x coordinate'), rational(value[1], 'y coordinate')


def twice_signed_area(vertices):
    a, b, c = vertices
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def require_id(value, label):
    if type(value) is not int or not 0 < value <= _MAX_SQLITE_ID:
        raise ValueError(f'{label} must be a positive SQLite integer')
    return value


def require_station_id(value):
    if not isinstance(value, str) or _STATION_ID.fullmatch(value) is None:
        raise ValueError('invalid station identifier')
    return value


def wire_rational(value):
    if not isinstance(value, str):
        raise ValueError('wire rational must be a string')
    number = rational(value, 'wire rational')
    if value != str(number):
        raise ValueError('wire rational must be canonical')
    return number


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def sha256_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON field {key!r}')
        result[key] = value
    return result


def load_json(text):
    if not isinstance(text, str):
        raise ValueError('expected JSON text')
    return json.loads(text, object_pairs_hook=_unique_object)
