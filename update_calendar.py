"""Generate a subscribed iCalendar from Peristeri BC's official fixture page."""
import hashlib
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

SOURCE = 'https://www.peristeribc.gr/programme/'
OUTPUT = Path(__file__).with_name('peristeri.ics')
ATHENS = ZoneInfo('Europe/Athens')


def esc(s):
    return str(s).replace('\\', '\\\\').replace('\n', '\\n').replace(',', '\\,').replace(';', '\\;')


def parse():
    req = Request(SOURCE, headers={'User-Agent': 'Mozilla/5.0 (compatible; PersonalCalendar/1.0)'})
    with urlopen(req, timeout=35) as response:
        html = response.read()
    soup = BeautifulSoup(html, 'html.parser')
    cards = soup.select('.jet-listing-grid__item[data-post-id]')
    if not cards:
        raise RuntimeError('No fixture cards found; site layout may have changed. Calendar left untouched.')
    matches = {}
    for card in cards:
        fields = [x.get_text(' ', strip=True) for x in card.select('.jet-listing-dynamic-field__content')]
        if not fields or fields[0] != 'Εντός':
            continue
        date = next((x for x in fields if re.fullmatch(r'\d{2}\.\d{2}\.\d{2}', x)), None)
        clock = next((x for x in fields if re.fullmatch(r'\d{1,2}:\d{2}', x)), None)
        if not date or not clock:
            continue
        # The official page occasionally lists suspicious early-morning times.
        # Skip rather than put a misleading fixture on the calendar.
        hh = int(clock.split(':')[0])
        if hh < 10 or hh > 23:
            print(f'Skipping suspicious time: {card.get("data-post-id")} {date} {clock}')
            continue
        teams = [p.get_text(' ', strip=True) for p in card.select('p') if p.get_text(' ', strip=True)]
        opponents = [t for t in teams if 'ΠΕΡΙΣΤΕΡΙ' not in t.upper() and 'PERISTERI' not in t.upper()]
        if not opponents:
            continue
        text = card.get_text(' ', strip=True)
        league = 'BCL' if re.search(r'\bBCL\b', text) else ('Stoiximan GBL' if 'Stoiximan GBL' in text else 'Άλλη διοργάνωση')
        when = datetime.strptime(f'{date} {clock}', '%d.%m.%y %H:%M').replace(tzinfo=ATHENS)
        key = card['data-post-id']
        matches[key] = (when, opponents[-1], league)
    if not matches:
        raise RuntimeError('No valid home fixtures found. Calendar left untouched.')
    return matches


def generate(matches):
    now = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Peristeri BC Home Fixtures//EL',
             'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', 'X-WR-CALNAME:Περιστέρι BC - Εντός έδρας',
             'X-WR-TIMEZONE:Europe/Athens', 'REFRESH-INTERVAL;VALUE=DURATION:P1D']
    for key, (start, opponent, league) in sorted(matches.items(), key=lambda x:x[1][0]):
        end = start + timedelta(hours=2)
        lines += ['BEGIN:VEVENT', f'UID:peristeribc-{key}@peristeri-bc-calendar',
                  f'DTSTAMP:{now}', f'DTSTART:{start.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}',
                  f'DTEND:{end.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}',
                  f'SUMMARY:{esc("Περιστέρι BC - " + opponent)}',
                  f'DESCRIPTION:{esc(league + " | Επίσημο πρόγραμμα: " + SOURCE)}',
                  'LOCATION:Κλειστό Γυμναστήριο Ανδρέας Παπανδρέου, Περιστέρι',
                  f'URL:{SOURCE}', 'END:VEVENT']
    lines.append('END:VCALENDAR')
    # RFC 5545 uses CRLF line endings.
    return ('\r\n'.join(lines) + '\r\n').encode('utf-8')


def main():
    matches = parse()
    data = generate(matches)
    if not OUTPUT.exists() or OUTPUT.read_bytes() != data:
        OUTPUT.write_bytes(data)
    print(f'Calendar updated with {len(matches)} home fixtures')


if __name__ == '__main__':
    main()
