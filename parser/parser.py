"""Etap 3.0: statyczny HTML (tabele i karty) -> wspólny plik CSV."""
import argparse
import csv
import re
import sys
import time
from decimal import Decimal
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

FIELDS = ('id', 'nazwa', 'cena', 'waluta', 'kategoria', 'producent',
          'dostepnosc', 'ocena', 'liczba_opinii', 'data_dodania', 'gwarancja', 'url')
ALIASES = {'producent': ('producent', 'marka'),
           'dostepnosc': ('dostepnosc', 'dostępność'),
           'ocena': ('ocena', 'ocena_srednia'),
           'url': ('url', 'link', 'odnośnik do produktu')}


def clean_text(value):
    """Usuwa nadmiar odstępów, także NBSP; brak pozostaje pusty."""
    text = ' '.join(str(value).split()) if value is not None else ''
    return '' if text.lower() in {'null', 'none', 'n/a', '-'} else text


def parse_price(value):
    """PL/EN: 1 299,00 zł, 1299.00, 1,299.00 EUR -> Decimal."""
    text = clean_text(value)
    if not text:
        return None
    text = re.sub(r'(?i)(PLN|EUR|USD|GBP|CZK|zł|Kč|[€$£])', '', text)
    text = re.sub(r'\s', '', text)
    if ',' in text and '.' in text:
        if not (re.fullmatch(r'\d{1,3}(?:\.\d{3})+,\d{1,2}', text)
                or re.fullmatch(r'\d{1,3}(?:,\d{3})+\.\d{1,2}', text)):
            raise ValueError(f'Nieprawidłowe separatory ceny: {value!r}')
        decimal_mark = ',' if text.rfind(',') > text.rfind('.') else '.'
        text = text.replace('.' if decimal_mark == ',' else ',', '')
    text = text.replace(',', '.')
    if not re.fullmatch(r'\d+(?:\.\d{1,2})?', text):
        raise ValueError(f'Nieprawidłowa cena: {value!r}')
    return Decimal(text)


def field_name(label, fields=FIELDS):
    label = clean_text(label).lower().replace(' ', '_').replace('-', '_')
    for field in fields:
        if label in (field, *[a.replace(' ', '_') for a in ALIASES.get(field, ())]):
            return field
    return None


def element_value(element, field):
    if field == 'url':
        link = element if element.name == 'a' else element.find('a', href=True)
        if link:
            return link.get('href', '')
    return element.get_text(' ', strip=True)


def normalize_record(raw, base_url):
    record = {field: clean_text(raw.get(field)) for field in FIELDS}
    record['cena'] = parse_price(record['cena'])
    if record['url']:
        record['url'] = urljoin(base_url, record['url'])
    return record


def parse_html(html, base_url, fields=FIELDS, normalizer=normalize_record):
    """Nagłówki tabel i semantyczne pola kart; bez zależności od kolejności pól."""
    soup = BeautifulSoup(html, 'html.parser')
    records = []
    counts = {'tabela': 0, 'karty': 0}
    for table in soup.find_all('table'):
        header = table.find('tr')
        if not header:
            continue
        columns = [field_name(c.get_text(' '), fields) for c in header.find_all(['th', 'td'])]
        if 'nazwa' not in columns or 'cena' not in columns:
            continue
        for row in table.find_all('tr'):
            if row is header:
                continue
            cells = row.find_all('td', recursive=False)
            if not cells:
                continue
            raw = {f: element_value(c, f) for f, c in zip(columns, cells) if f}
            if not clean_text(raw.get('nazwa')):
                continue
            records.append(normalizer(raw, base_url))
            counts['tabela'] += 1

    for card in soup.select('article, div.produkt, div.product'):
        if (card.find_parent(['article', 'table'])
                or card.find_parent('div', class_='produkt')
                or card.find_parent('div', class_='product')):
            continue
        raw = {}
        for field in fields:
            for alias in (field, *ALIASES.get(field, ())):
                value = card.get('data-' + alias.replace('_', '-'))
                element = card.select_one(f'[data-field="{alias}"], [class~="{alias}"]')
                if value is not None or element is not None:
                    raw[field] = value if value is not None else element_value(element, field)
                    break
        if not raw.get('nazwa'):
            continue
        records.append(normalizer(raw, base_url))
        counts['karty'] += 1
    return records, counts


class HttpClient:
    """Co najmniej 0,5 s od końca poprzedniego żądania do następnego."""
    def __init__(self, delay=0.5):
        self.delay = max(0.5, delay)
        self.last_finished = None
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'PJN-Lab1-Parser/0.1 (projekt studencki)'

    def _request(self, url):
        if self.last_finished is not None:
            time.sleep(max(0, self.delay - (time.monotonic() - self.last_finished)))
        try:
            response = self.session.get(url, timeout=30, allow_redirects=False)
            response.raise_for_status()
            return response
        finally:
            self.last_finished = time.monotonic()

    def get(self, url):
        origin = urlsplit(url).netloc
        for _ in range(6):
            response = self._request(url)
            if response.status_code not in (301, 302, 303, 307, 308):
                return response
            target = urljoin(url, response.headers.get('Location', ''))
            if urlsplit(target).netloc != origin:
                raise ValueError('Przekierowanie poza serwis: ' + target)
            url = target
        raise ValueError('Zbyt wiele przekierowań: ' + url)

    def close(self):
        self.session.close()


def export_csv(records, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('url', help='Adres HTTP(S) statycznego katalogu')
    cli.add_argument('--output', default='parser/output/etap3.csv')
    args = cli.parse_args(argv)
    client = HttpClient()
    try:
        response = client.get(args.url)
        # Bajty pozwalają BeautifulSoup uwzględnić deklarację <meta charset>.
        records, counts = parse_html(response.content, response.url)
        if len(records) < 60 or not all(counts.values()):
            raise ValueError(
                f'Wymagane >=60 rekordów z obu struktur; otrzymano {len(records)}, {counts}. '
                'Ten etap nie wykonuje JavaScriptu. Plik wynikowy nie został zmieniony.')
        export_csv(records, args.output)
        print(f'Zapisano {len(records)} rekordów, {len(FIELDS)} kolumn; {counts}; {args.output}')
        return 0
    except (requests.RequestException, ValueError, OSError) as error:
        print(f'Błąd: {error}', file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == '__main__':
    raise SystemExit(main())
