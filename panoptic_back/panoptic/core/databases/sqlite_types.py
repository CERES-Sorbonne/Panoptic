"""sqlite3 adapter/converter for datetime.datetime.

Python 3.12 deprecated sqlite3's built-in datetime adapter and "timestamp"
converter. These replacements do exactly the same thing, so the stored text
and the values read back do not change. Importing this module registers them
for the whole process.
"""
import datetime
import sqlite3


def _adapt_datetime(val: datetime.datetime) -> str:
    return val.isoformat(" ")


def _convert_timestamp(val: bytes) -> datetime.datetime:
    # Same parsing as the old built-in converter (not fromisoformat, which
    # accepts and rejects different strings).
    datepart, timepart = val.split(b" ")
    year, month, day = map(int, datepart.split(b"-"))
    timepart_full = timepart.split(b".")
    hours, minutes, seconds = map(int, timepart_full[0].split(b":"))
    if len(timepart_full) == 2:
        microseconds = int('{:0<6.6}'.format(timepart_full[1].decode()))
    else:
        microseconds = 0
    return datetime.datetime(year, month, day, hours, minutes, seconds, microseconds)


sqlite3.register_adapter(datetime.datetime, _adapt_datetime)
# Converter names match declared types case-insensitively ("TIMESTAMP" columns).
sqlite3.register_converter("timestamp", _convert_timestamp)
