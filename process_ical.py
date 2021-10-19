import gzip
import os, time
import urllib.request
from datetime import datetime, timedelta
from collections import OrderedDict

import csv

URL = os.environ['INPUT_ICAL_URL']

HEADERS = [('User-agent', 'Mozilla/5.0'), ('Accept-Encoding', 'gzip, deflate')]

os.environ['TZ'] = 'Europe/Warsaw'
time.tzset()

def get_url_compressed(url):
    req = urllib.request.Request(url)
    for h, v in HEADERS:
        req.add_header(h, v)
    with urllib.request.urlopen(req) as response:
        enc = response.headers.get('Content-Encoding')
        ctype = response.headers.get('Content-Type')
        data = response.read()
        if enc == 'gzip':
            return gzip.decompress(data)
        return data

def unfoldlines(data):
    result = []
    line = []
    for parsedline in data.split('\r\n'):
        if len(parsedline) > 0:
            if parsedline[0].isspace():
                line.append(parsedline[1:])
            else:
                if line:
                    yield ''.join(line)
                line.clear()
                line.append(parsedline)
    else:
        if line:
            yield ''.join(line)

def unescape(value):
    return (
        value.replace(r'\N', '\n').replace(r'\n', '\n')
             .replace(r'\,', ',').replace(r'\;', ';')
             .replace(r'\\', '\\')
    )

def iter_params(params):
    for p in params:
        k, v = p.split('=', 1)
        yield k, v
FORMAT = '%Y%m%dT%H%M%S'
FORMATZ = f'{FORMAT}%z'

OUTFORMAT = FORMATZ

def parse_datetime(value):
    if value[-1] == 'Z':
        return datetime.strptime(value, FORMATZ)
    else:
        return datetime.strptime(value, FORMAT).astimezone()

def parse_date(value):
    return datetime.strptime(value, '%Y%m%d').astimezone()

def format_date(date):
    return date.strftime(OUTFORMAT)

RULES = OrderedDict([
    ('S', ['sopran']),
    ('A', ['alt']),
    ('T', ['tenor']),
    ('B', ['bas']),
    ('Z', ['zarzad', 'zarząd']),
    ('t', ['tutti']),
])

def extract_info(*texts):
    groups, grouplist = set(), []
    for t in texts:
        if not t:
            continue
        t = t.lower()
        for sym, patterns in RULES.items():
            if sym not in groups:
                for pattern in patterns:
                    if pattern in t:
                        groups.add(sym)
                        grouplist.append(sym)
                        break
    return grouplist


def process(bytedata, encoding='utf-8'):
    data = bytedata.decode(encoding)
    for line in unfoldlines(data):
        name, value = line.split(':', maxsplit=1)
        name, *params = name.split(';')
        if name == 'BEGIN':
            if value == 'VEVENT':
                description = []
                summary = []
                location = []
                uid = start = end = created = modified = None
        elif name == 'END':
            if value == 'VEVENT':
                if start is None:
                    continue
                if end is None:
                    duration = timedelta(seconds=0)
                else:
                    duration = end - start
                summary, location, description = '\n'.join(summary), '\n'.join(description), '\n'.join(location)
                groups = extract_info(summary, location, description)
                yield (
                    start, end, duration, summary, location,
                    description, uid, created, modified, groups
                )
                description = []
                summary = []
                location = []
                uid = start = end = created = modified = None
        elif name == 'DESCRIPTION':
            description.append(unescape(value))
        elif name == 'SUMMARY':
            summary.append(unescape(value))
        elif name == 'LOCATION':
            location.append(unescape(value))
        elif name == 'UID':
            uid = value
        elif name == 'DTSTART':
            for k, v in iter_params(params):
                if k == 'VALUE' and v == 'DATE':
                    start = parse_date(value)
                    break
            else:
                start = parse_datetime(value)
        elif name == 'DTEND':
            for k, v in iter_params(params):
                if k == 'VALUE' and v == 'DATE':
                    end = parse_date(value).replace(hour=23, minute=59, second=59)
                    break
            else:
                end = parse_datetime(value)
        elif name == 'CREATED':
            created = parse_datetime(value)
        elif name == 'LAST-MODIFIED':
            modified = parse_datetime(value)


def filter_time(eventlist, after):
    for e in eventlist:
        start, end, _, _, _, _, _, created, modified, _ = e
        if (start and start >= after) or (created and created >= after) or (modified and modified >= after):
            yield e

def dump_csv(eventlist, path):
    with open(path, 'w', newline='') as fd:
        writer = csv.writer(fd, delimiter='\t', quoting=csv.QUOTE_MINIMAL, escapechar='\\', lineterminator='\n')
        for (start, end, duration, summary, location, description,
                uid, created, modified, groups) in eventlist:
            writer.writerow((
                format_date(start) if start else '', duration.seconds, summary, location, description, uid,
                format_date(created) if created else '', format_date(modified) if modified else '', ''.join(groups)
            ))

if __name__ == "__main__":
    import sys
    os.makedirs('public', exist_ok=True)
    days = int(sys.argv[1])
    data = get_url_compressed(URL)
    dump_csv(filter_time(process(data), datetime.now().astimezone()-timedelta(days=days)), f'public/pruned.tsv')


