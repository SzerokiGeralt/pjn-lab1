"""Etap 4.0: paginacja, szczegóły, czyszczenie, deduplikacja, CSV i JSON."""
import argparse
import csv
import json
import re
from collections import Counter, deque
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup
import requests
from parser import ALIASES, FIELDS, HttpClient, clean_text, element_value, field_name, parse_html, parse_price

FIELDS4 = FIELDS + ('sku', 'podkategoria', 'opis', 'waga_g', 'dlugosc_cm',
                    'kolor', 'material', 'ean', 'dostawca', 'stawka_vat',
                    'stan_magazynowy', 'jednostka')
ALIASES.update({'waga_g': ('waga_g', 'waga'), 'dlugosc_cm': ('dlugosc_cm', 'długość'),
                'material': ('material', 'materiał'), 'stawka_vat': ('stawka_vat', 'vat'),
                'data_dodania': ('data_dodania', 'data dodania'),
                'liczba_opinii': ('liczba_opinii', 'liczba opinii'),
                'stan_magazynowy': ('stan_magazynowy', 'stan magazynowy')})
NUMERIC = ('cena', 'ocena', 'liczba_opinii', 'waga_g', 'dlugosc_cm', 'stawka_vat', 'stan_magazynowy')
PAGINATION = 'a[rel~="next"], .pagination a[href], nav[aria-label="Paginacja"] a[href]'


def canonical_url(value, base):
    url = urldefrag(urljoin(base, value))[0]
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or parsed.netloc != urlsplit(base).netloc:
        raise ValueError('Odnośnik poza serwisem lub nieobsługiwany adres: ' + url)
    return url


def parse_date(value, today=None):
    text = clean_text(value).lower()
    if not text:
        return None
    today = today or date.today()
    if text in ('dzisiaj', 'dziś', 'wczoraj'):
        return (today - timedelta(days=int(text == 'wczoraj'))).isoformat()
    for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError('Nieprawidłowa data: ' + text)


def parse_number(value, integer=False, unit=None):
    text = clean_text(value)
    if not text:
        return None
    if unit:
        text = re.sub(r'\s*' + re.escape(unit) + r'\s*$', '', text, flags=re.I)
    text = re.sub(r'\s', '', text).replace(',', '.')
    if not re.fullmatch(r'\d+(?:\.\d+)?', text):
        raise ValueError('Nieprawidłowa liczba: ' + text)
    number = Decimal(text)
    if integer and number != number.to_integral_value():
        raise ValueError('Wymagana liczba całkowita: ' + text)
    return int(number) if integer else float(number)


def currency_from_price(value):
    match = re.search(r'\b(PLN|EUR|USD|GBP|CZK)\b', str(value), re.I)
    if match:
        return match[1].upper()
    for symbol, code in (('zł', 'PLN'), ('€', 'EUR'), ('£', 'GBP'), ('Kč', 'CZK')):
        if symbol in str(value):
            return code
    # Sam symbol $ nie pozwala rozróżnić USD, CAD i AUD.
    return None


def normalize(raw, base, today, issues):
    record = {field: clean_text(raw.get(field)) or None for field in FIELDS4}
    conversions = {
        'cena': parse_price, 'data_dodania': lambda v: parse_date(v, today),
        'ocena': parse_number, 'liczba_opinii': lambda v: parse_number(v, True),
        'waga_g': lambda v: parse_number(v, unit='g'),
        'dlugosc_cm': lambda v: parse_number(v, unit='cm'),
        'stawka_vat': lambda v: parse_number(v, unit='%'),
        'stan_magazynowy': lambda v: parse_number(v, True),
    }
    for field, convert in conversions.items():
        try:
            record[field] = convert(record[field])
            if field == 'ocena' and record[field] is not None and not 0 <= record[field] <= 5:
                raise ValueError('Ocena poza zakresem 0–5')
        except ValueError as error:
            issues.append({'id': record['id'], 'pole': field, 'wartosc': raw.get(field), 'blad': str(error)})
            record[field] = None
    record['waluta'] = (record['waluta'] or currency_from_price(raw.get('cena')))
    if record['waluta']:
        record['waluta'] = record['waluta'].upper()
    availability = {'tak': 'Dostępny', 'true': 'Dostępny', '1': 'Dostępny',
                    'dostępny': 'Dostępny', 'nie': 'Niedostępny', 'false': 'Niedostępny',
                    '0': 'Niedostępny', 'niedostępny': 'Niedostępny'}
    if record['dostepnosc']:
        record['dostepnosc'] = availability.get(record['dostepnosc'].lower(), record['dostepnosc'])
    if record['url']:
        record['url'] = canonical_url(record['url'], base)
    return record


def parse_details(html):
    """Pola semantyczne, listy dt/dd i dwukolumnowe tabele specyfikacji."""
    soup = BeautifulSoup(html, 'html.parser')
    root = soup.select_one('#szczegolyProduktu, [data-product-detail], .szczegoly-produktu') or soup
    raw = {}
    for field in FIELDS4:
        for alias in (field, *ALIASES.get(field, ())):
            value = root.get('data-' + alias.replace('_', '-'))
            element = root.select_one(f'[data-field="{alias}"], [class~="{alias}"]')
            if value is not None or element is not None:
                raw[field] = value if value is not None else element_value(element, field)
                break
    for dt in root.select('dt'):
        dd = dt.find_next_sibling()
        field = field_name(dt.get_text(' '), FIELDS4)
        if field and dd and dd.name == 'dd':
            raw[field] = dd.get_text(' ', strip=True)
    for tr in root.select('tr'):
        cells = tr.find_all(['th', 'td'], recursive=False)
        if len(cells) == 2:
            field = field_name(cells[0].get_text(' '), FIELDS4)
            if field:
                raw[field] = cells[1].get_text(' ', strip=True)
    return raw


def merge_records(first, second, conflicts=None):
    """Uzupełnia braki; pierwsza niepusta wartość wygrywa konflikt."""
    result = dict(first)
    for key, value in second.items():
        if not clean_text(result.get(key)):
            result[key] = value
        elif clean_text(value) and result[key] != value and conflicts is not None:
            conflicts.append({'id': first.get('id'), 'pole': key,
                              'zachowano': str(result[key]), 'pominieto': str(value)})
    return result


def deduplicate(records):
    """Tożsamość: id, następnie SKU, następnie URL; nie łączymy po samej nazwie."""
    unique = []
    indexes = {}
    conflicts = []
    for record in records:
        identity = next(((k, record[k]) for k in ('id', 'sku', 'url') if record.get(k)), None)
        if identity is None:
            raise ValueError('Produkt bez id, SKU i URL')
        if identity in indexes:
            pos = indexes[identity]
            unique[pos] = merge_records(unique[pos], record, conflicts)
        else:
            indexes[identity] = len(unique)
            unique.append(record)
    return unique, len(records) - len(unique), conflicts


def crawl(start_url, client, today=None, max_pages=100):
    today = today or date.today()
    start_url = canonical_url(start_url, start_url)
    queue, visited = deque([start_url]), set()
    raw_records, issues = [], []
    counts = Counter()
    while queue:
        url = queue.popleft()
        if url in visited:
            continue
        if len(visited) >= max_pages:
            raise ValueError('Osiągnięto limit stron katalogu; wynik byłby niepełny')
        visited.add(url)
        response = client.get(url)
        records, structures = parse_html(response.content, response.url, FIELDS4,
                                         lambda raw, base: {**raw, 'url': canonical_url(raw['url'], base) if raw.get('url') else None})
        if not records:
            raise ValueError('Brak rekordów w HTML: ' + url + '. Etap 4.0 nie wykonuje JavaScriptu.')
        raw_records.extend(records)
        counts.update(structures)
        soup = BeautifulSoup(response.content, 'html.parser')
        for link in soup.select(PAGINATION):
            target = canonical_url(link['href'], response.url)
            if target not in visited and target not in queue:
                queue.append(target)
    # Każdy unikalny adres szczegółów pobieramy raz, także dla duplikatów na listach.
    details = {}
    merged = []
    for raw in raw_records:
        url = raw.get('url')
        if not url:
            raise ValueError('Brak odnośnika szczegółów produktu: ' + str(raw.get('id')))
        if url not in details:
            response = client.get(url)
            details[url] = parse_details(response.content)
            if not details[url]:
                raise ValueError('Nie rozpoznano żadnego pola szczegółów: ' + url)
        # Dane listy mają pierwszeństwo; szczegóły uzupełniają brakujące pola.
        merged.append(normalize(merge_records(raw, details[url]), url, today, issues))
    records, duplicates, conflicts = deduplicate(merged)
    observed_fields = [f for f in FIELDS4 if any(r[f] is not None for r in records)]
    if len(records) < 200 or len(observed_fields) < 18 or not all(counts[k] for k in ('tabela', 'karty')):
        raise ValueError(f'Nie spełniono 4.0: {len(records)} rekordów, {len(observed_fields)} pól z danymi, {dict(counts)}')
    summary = {'data_odniesienia': today.isoformat(), 'strony_katalogu': len(visited),
               'strony_szczegolow': len(details), 'rekordy_przed': len(merged),
               'rekordy_po': len(records), 'duplikaty_usuniete': duplicates,
               'duplikaty_po': 0, 'struktury': dict(counts), 'pola_z_danymi': observed_fields,
               'odrzucone_wartosci': issues, 'konflikty_duplikatow': conflicts}
    return records, summary


def json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(type(value).__name__)


def export(records, summary, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'produkty.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS4)
        writer.writeheader()
        writer.writerows(records)
    for name, data in [('produkty.json', records), ('podsumowanie.json', summary)]:
        (directory / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=json_value), encoding='utf-8')


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('url')
    cli.add_argument('--output-dir', default='parser/output/etap4')
    cli.add_argument('--today', type=date.fromisoformat, default=date.today(), help='Data odniesienia dla słowa wczoraj (YYYY-MM-DD)')
    cli.add_argument('--max-pages', type=int, default=100)
    args = cli.parse_args(argv)
    client = HttpClient()
    try:
        records, summary = crawl(args.url, client, args.today, args.max_pages)
        export(records, summary, args.output_dir)
        print(f"Zapisano {len(records)} produktów; usunięto {summary['duplikaty_usuniete']} duplikatów; katalog: {summary['strony_katalogu']}, szczegóły: {summary['strony_szczegolow']}")
        return 0
    except (ValueError, OSError, requests.RequestException) as error:
        print('Błąd: ' + str(error))
        return 1
    finally:
        client.close()


if __name__ == '__main__':
    raise SystemExit(main())
