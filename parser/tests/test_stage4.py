import csv
import json
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stage4 import (FIELDS4, canonical_url, crawl, deduplicate, export,
                    normalize, parse_date, parse_details, parse_number)
from site4 import page


class LocalClient:
    def __init__(self):
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        from urllib.parse import urlsplit
        html = page(urlsplit(url).path)
        if html is None:
            raise ValueError('404 ' + url)
        return SimpleNamespace(content=html.encode('utf-8'), url=url)


class Stage4Tests(unittest.TestCase):
    def test_dates(self):
        for value in ('2026-10-16', '16.10.2026', '16/10/2026', 'wczoraj'):
            self.assertEqual(parse_date(value, date(2026,10,17)), '2026-10-16')
        self.assertIsNone(parse_date(''))
        with self.assertRaises(ValueError):
            parse_date('31.02.2026')

    def test_numbers(self):
        self.assertEqual(parse_number('1\u00a0200', True), 1200)
        self.assertEqual(parse_number('12,5 cm', unit='cm'), 12.5)
        self.assertEqual(parse_number('23 %', unit='%'), 23)
        for value in ('1.5', 'abc', 'NaN'):
            with self.assertRaises(ValueError):
                parse_number(value, True)

    def test_missing_and_invalid_values(self):
        issues = []
        record = normalize({'id': '1', 'cena': 'błąd', 'ocena': '9', 'waga_g': 'null', 'ean': '00123'},
                           'http://local/', date(2026,10,17), issues)
        self.assertIsNone(record['cena'])
        self.assertIsNone(record['waga_g'])
        self.assertIsNone(record['ocena'])
        self.assertEqual(record['ean'], '00123')
        self.assertEqual(len(issues), 2)

    def test_duplicates_fill_missing_report_conflict(self):
        rows = [{'id': '1', 'kolor': None, 'cena': Decimal('12')},
                {'id': '1', 'kolor': 'żółty', 'cena': Decimal('13')},
                {'id': '2', 'kolor': 'żółty', 'cena': Decimal('12')}]
        unique, removed, conflicts = deduplicate(rows)
        self.assertEqual(removed, 1)
        self.assertEqual(len(unique), 2)
        self.assertEqual(unique[0]['kolor'], 'żółty')
        self.assertEqual(unique[0]['cena'], Decimal('12'))
        self.assertEqual(len(conflicts), 1)

    def test_origin_and_fragments(self):
        self.assertEqual(canonical_url('/katalog/2#lista', 'http://local/katalog/1'), 'http://local/katalog/2')
        with self.assertRaises(ValueError):
            canonical_url('https://other/page', 'http://local/')

    def test_page_limit_fails_instead_of_partial_export(self):
        with self.assertRaisesRegex(ValueError, 'limit stron'):
            crawl('http://local/katalog/1', LocalClient(), max_pages=1)

    def test_full_crawl_export_and_no_duplicate_requests(self):
        client = LocalClient()
        rows, summary = crawl('http://local/katalog/1', client, date(2026,10,17))
        self.assertEqual(len(rows), 200)
        self.assertEqual(len(FIELDS4), 24)
        self.assertEqual(summary['rekordy_przed'], 208)
        self.assertEqual(summary['duplikaty_usuniete'], 8)
        self.assertEqual(summary['strony_katalogu'], 5)
        self.assertEqual(summary['strony_szczegolow'], 200)
        self.assertEqual(len(client.urls), len(set(client.urls)))
        self.assertEqual(summary['odrzucone_wartosci'], [])
        self.assertEqual(sum(r['waga_g'] is None for r in rows), 40)
        self.assertEqual(sum(r['kolor'] is None for r in rows), 40)
        for row in rows:
            i = int(row['id'])
            self.assertEqual(row['cena'], Decimal('1299.90') if i==199 else Decimal(50)+Decimal(i)/10)
            self.assertEqual(row['data_dodania'], '2026-10-16')
            self.assertEqual(row['stan_magazynowy'], i)
            self.assertEqual(row['dlugosc_cm'], 200+i/10)
            self.assertTrue(row['ean'].startswith('0'))
        with tempfile.TemporaryDirectory() as tmp:
            export(rows, summary, tmp)
            decoded = json.loads((Path(tmp)/'produkty.json').read_text(encoding='utf-8'))
            self.assertIsInstance(decoded[0]['cena'], (int,float))
            self.assertEqual(decoded[4]['kolor'], None)
            with (Path(tmp)/'produkty.csv').open(encoding='utf-8-sig',newline='') as f:
                csv_rows = list(csv.DictReader(f))
            self.assertEqual(len(csv_rows),200)
            self.assertEqual(csv_rows[4]['kolor'],'')
            self.assertEqual(csv_rows[0]['nazwa'],'Wędka Łódź 1')


if __name__ == '__main__':
    unittest.main()
