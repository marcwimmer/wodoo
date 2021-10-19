# -*- encoding: utf-8 -*-
import datetime
import time
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from pytz import timezone
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

def get_dates(start, end):
    start = str2date(start)
    end = str2date(end)
    if not start or not end:
        raise Exception("Missing start and end.")

    result = []
    c = start
    while c <= end:
        result.append(date2str(c))
        c = c + datetime.timedelta(days=1)
    return result

def ensure_strdate(day):
    return date2str(str2date(day))

def dayofweek(day, month=None, year=None):
    """
    if month and year is None, then day is date
    """
    d = day
    m = month
    y = year
    if not month and not year:
        day = str2date(day)
        d = day.day
        m = day.month
        y = day.year
    del day
    del month
    del year
    if m < 3:
        z = y - 1
    else:
        z = y
    dayofweek = (23 * m // 9 + d + 4 + y + z // 4 - z // 100 + z // 400)
    if m >= 3:
        dayofweek -= 2
    dayofweek = dayofweek % 7

    dayofweek -= 1
    if dayofweek == -1: dayofweek = 6

    return dayofweek

def get_localized_monthname(month, locale='de_DE'):
    if locale == 'de_DE':
        months = ['Januar', 'Februar', "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
    else:
        raise Exception('implement!')
    return months[month - 1]

def _get_date_ranges(start, end):
    first_of_month = time.strftime('%Y-%m-') + str(1)
    first_of_month = str2date(first_of_month)

    date_start = (first_of_month + relativedelta(months=start)).strftime(DEFAULT_SERVER_DATE_FORMAT)
    date_end = (first_of_month + relativedelta(months=end)).strftime(DEFAULT_SERVER_DATE_FORMAT)
    return {
        'date_start': date_start,
        'date_end': date_end,
    }

def is_dst(_date):
    """
    Liefert zu einem Datum bool bei Sommezeit zuruecken, ansonsten
    False fuer Normalzeit/Winterzeit
    """
    year = _date.year

    def get_last_sunday(year, month):
        day = 31
        while True:
            dt = datetime.datetime(year, month, day)
            dow = int(dt.strftime('%w'))
            if dow == 0: break
            day = day - 1
        return datetime.datetime(year, month, day)

    normal_time_start = get_last_sunday(year, 10)
    dst_time_start = get_last_sunday(year, 3)

    result = bool(_date >= dst_time_start and _date < normal_time_start)
    return result

def get_day_of_week(dt, lang='de_DE'):
    translations = {'de_DE': {'Monday': 'Montag', 'Tuesday': 'Dienstag', 'Wednesday': 'Mittwoch', 'Thursday': 'Donnerstag', 'Friday': 'Freitag', 'Saturday': 'Samstag', 'Sunday': 'Sonntag'}}
    result = dt.strftime('%A')
    result = translations.get(lang, {result: result}).get(result, result)
    return result

def convert_to_utc(d, tz='CET'):
    if not d:
        return d
    if is_dst(d):
        d = d - relativedelta(hours=1)
    from_tz = timezone(tz)
    d = from_tz.localize(d)
    d = d.astimezone(timezone('utc')).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
    return d

def convert_timezone(from_tz, datestring, to_tz, return_format=False):
    """
    Konvertiert einen datum string von einer zu ner anderen zeitzone
    Eventuell soll noch is_dst verwendet werden s.o.
    """
    if not to_tz: to_tz = 'UTC'
    if from_tz.upper() != 'UTC':
        timezoneoffset = datetime.datetime.now(timezone(from_tz)).strftime('%z')
        datestring = datestring + ' ' + timezoneoffset
        dt = parse(datestring)
    else:
        utc = datetime.datetime.strptime(datestring, '%Y-%m-%d %H:%M:%S')
        dt = utc.replace(tzinfo=timezone(from_tz))
    return dt.astimezone(timezone(to_tz)).strftime(return_format or DEFAULT_SERVER_DATETIME_FORMAT)

def get_time_from_float(_float):
    hour = int(_float)
    minutes = _float - hour
    return '%02.0f:%02.0f:00' % (hour, int(round(60.0 * minutes)))

def get_float_from_time(time):
    return float(time[0:2]) + (float(time[3:5]) / 60)

def get_month_list():
    months = []
    for i in range(1, 13):
        months.append((i, datetime.date(2011, i, 1).strftime('%B')))
    return months

def day_of_weeks_list(include_holiday=False):
    days = []
    days.append(('Mo', 'Monday'))
    days.append(('Tue', 'Tuesday'))
    days.append(('Wed', 'Wednesday'))
    days.append(('Th', 'Thursday'))
    days.append(('Fr', 'Friday'))
    days.append(('Sat', 'Saturday'))
    days.append(('Sun', 'Sunday'))
    if include_holiday:
        days.append(('Hol', 'Holiday'))
    return days

def date_type(d):
    if not d:
        return None

    if isinstance(d, str):
        if len(str) == len("00.00.0000"):
            return 'date'
        elif len(str) == len("00.00.0000 00:00:00"):
            return 'datetime'

    if isinstance(d, datetime.date):
        return 'date'

    if isinstance(d, datetime.datetime):
        return 'datetime'

def str2date(string):
    if not string:
        return False
    if isinstance(string, datetime.date):
        return string
    if isinstance(string, datetime.datetime):
        return string.date()
    return parse(string).date()

def str2datetime(string):
    if not string:
        return False
    if isinstance(string, datetime.datetime):
        return string
    if isinstance(string, datetime.date):
        return datetime(datetime.date.year, datetime.date.month, datetime.date.day, 0, 0, 0)
    return parse(string)

def date2str(date):
    if not date:
        return False
    if isinstance(date, str):
        return date
    return date.strftime("%Y-%m-%d")

def time2str(thetime):
    if not thetime:
        return False
    if isinstance(date, str):
        return date
    return thetime.strftime("%H-%M-%S")

def str2time(thetime):
    if not thetime:
        return False
    return parse(thetime).time()

def datediff(d1, d2):
    delta = d1 - d2
    return delta.days

def timediff(t1, t2, unit="hours"):
    t1_ms = (t1.hour * 60.0 * 60.0 + t1.minute * 60.0 + t1.second) * 1000.0
    t2_ms = (t2.hour * 60.0 * 60.0 + t2.minute * 60.0 + t2.second) * 1000.0

    delta_ms = max([t1_ms, t2_ms]) - min([t1_ms, t2_ms])

    if unit == "hours":
        return float(delta_ms) / 3600.0 / 1000.0
    else: raise Exception("not implemented unit: %s" % unit)

def datetime2str(time, date_format=False):
    if not time:
        return None
    if isinstance(time, str):
        if len(time) != 10:
            raise Exception("Invalid datetime: {}".format(time))
        return time
    if not date_format:
        return time.strftime("%Y-%m-%d %H:%M:%S")
    return time.strftime(date_format)

def date_in_range(date, start, end):
    """
    Checks wether date is between start and end;
    start, end can be string or python date

    if start is False, then start will be 01.01.1980
    if end is False, then End will be 31.12.2100
    """
    if isinstance(start, (datetime.date, datetime.datetime)):
        start = date2str(start)
    if isinstance(end, (datetime.date, datetime.datetime)):
        end = date2str(end)
    if isinstance(date, (datetime.date, datetime.datetime)):
        date = date2str(date)

    if not date:
        raise Exception("date is not given - cannot determine range")

    if not start:
        start = "1980-01-01"
    if not end:
        end = "2100-12-31"

    return date >= start and date <= end

def date_range_overlap(date_range1, date_range2):
    """
    Prueft, ob sich die angegebenen Datumsbereiche ueberschneiden

    :param date_range1:  Tuple (from, to)
    :param date_range2:  Tuple (from, to)
    :returns True or False:

    """
    d1 = date_range1
    d2 = date_range2

    assert all([isinstance(x, (list, tuple)) for x in [d1, d2]])
    assert all([len(x) == 2 for x in [d1, d2]])

    # convert all to strings
    def c(x):
        if isinstance(x, (datetime.datetime, datetime.date)):
            x = date2str(x)
        return x
    d1 = [c(x) for x in d1]
    d2 = [c(x) for x in d2]

    MIN = '1980-01-01'
    MAX = '2100-01-01'

    if not d1[0]:
        d1[0] = MIN
    if not d2[0]:
        d2[0] = MIN
    if not d1[1]:
        d1[1] = MAX
    if not d2[1]:
        d2[1] = MAX

    assert all([x[0] <= x[1] for x in [d1, d2]])

    if date_in_range(d1[0], d2[0], d2[1]):
        return True
    if date_in_range(d2[0], d1[0], d1[1]):
        return True
    if date_in_range(d1[1], d2[0], d2[1]):
        return True
    if date_in_range(d2[1], d1[0], d1[1]):
        return True
    if d1[0] < d2[0] and d1[1] > d2[1]:
        return True
    if d2[0] < d1[0] and d2[1] > d1[1]:
        return True
    return False


if __name__ == '__main__':
    from datetime import date
    d = str2datetime('1980-04-04 23:23:23')
    assert date_range_overlap((date(2013, 4, 4), date(2013, 4, 10)), (date(2013, 4, 5), date(2013, 4, 6)))
    assert date_range_overlap((date(2013, 4, 4), date(2013, 4, 10)), (date(2013, 4, 2), date(2013, 4, 12)))
    assert date_range_overlap((date(2013, 4, 4), date(2013, 4, 10)), (date(2013, 4, 9), date(2013, 4, 12)))
    assert not date_range_overlap((date(2013, 4, 4), date(2013, 4, 10)), (date(2013, 4, 2), date(2013, 4, 3)))
    assert date_range_overlap((date(2013, 4, 4), date(2013, 4, 10)), (date(2013, 4, 2), date(2013, 4, 4)))
    assert date_range_overlap((date(2013, 4, 4), date(2013, 4, 10)), (date(2013, 4, 2), date(2013, 4, 5)))
