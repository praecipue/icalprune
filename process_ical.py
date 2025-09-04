import gzip
import os, time
import urllib.request
from datetime import datetime, timedelta
from collections import OrderedDict
import re

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

RULES = [
    (['S'], re.compile(r'(?:\b|[0-9])sopr(?:an|\b)'), lambda ttype: True),
    (['A'], re.compile(r'(?:\b|[0-9])alt'), lambda ttype: True),
    (['T'], re.compile(r'(?:\b|[0-9])tenor'), lambda ttype: True),
    (['B'], re.compile(r'(?:\b|[0-9])bas'), lambda ttype: True),
    (['Z'], re.compile(r'(?:\b|[0-9])zarz[aą]d'), lambda ttype: True),
    (['t'], re.compile(r'tutti'), lambda ttype: True),
    (['S','A'], re.compile(r'\b(?:panie|dla +pan|pań)\b'), lambda ttype: ttype == 'summary'),
    (['T','B'], re.compile(r'\b(?:panowie|pan[óo]w)\b'), lambda ttype: ttype == 'summary'),
    (['t'], re.compile(r'\bwszys(?:cy|tkich)\b'), lambda ttype: ttype == 'summary'),
    ([''], re.compile(r'\b(?:próby + nie +ma|nie +ma +próby)\b'), lambda ttype: ttype == 'summary'),
]

def extract_info(summary, location, description):
    groups, grouplist = set(), []
    texts = [('summary', summary),('location', location),('description', description)]
    for ttype, t in texts:
        if not t:
            continue
        t = t.lower()
        for syms, pattern, ttype_check in RULES:
            if not ttype_check(ttype):
                continue
            newsyms = [ sym for sym in syms if sym not in groups ]
            if len(newsyms) > 0:
                if pattern.search(t):
                    grouplist.extend(newsyms)
                    groups.update(newsyms)
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
            #if '' in groups and len(groups) > 1:
            #    if description:
            #        description.append('\n(wykryto odwołaną próbę; wykryte grupy: [{}])'.format(''.join(groups)))
            #    groups = []
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
