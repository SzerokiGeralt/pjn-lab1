"""Testy etapu 3.0; wyłącznie lokalne dane, bez internetu."""
import csv
import functools
import io
import tempfile
import threading
import sys
import unittest
from contextlib import redirect_stderr
from decimal import Decimal
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parser import FIELDS, HttpClient, clean_text, main, parse_html, parse_price

FIXTURE = Path(__file__).parent / 'fixtures' / 'catalogue.html'


class ParserTests(unittest.TestCase):
    def test_polish_and_foreign_prices(self):
        for text in ['1 299,00 zł', '1\u00a0299,00 PLN', '1299.00', '1,299.00 EUR', '1.299,00 €']:
            with self.subTest(text=text):
                self.assertEqual(parse_price(text), Decimal('1299.00'))

    def test_missing_and_invalid_price(self):
        self.assertIsNone(parse_price('null'))
        for text in ['za darmo', '12,34,56', '-10 zł', 'NaN', '12,34.56', '1.2,00']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_price(text)

    def test_text(self):
        self.assertEqual(clean_text('  Wędka\u00a0\n łódź '), 'Wędka łódź')
        self.assertEqual(clean_text(None), '')

    def test_both_structures_same_schema(self):
        records, counts = parse_html(FIXTURE.read_bytes(), 'http://localhost/catalogue.html')
        self.assertEqual(counts, {'tabela': 30, 'karty': 30})
        self.assertEqual(len(records), 60)
        self.assertEqual(len({r['id'] for r in records}), 60)
        for record in records:
            self.assertEqual(tuple(record), FIELDS)
            self.assertTrue(all(value != '' for value in record.values()))
            self.assertIsInstance(record['cena'], Decimal)
            self.assertTrue(record['url'].startswith('http://localhost/product.html?id='))
        self.assertEqual(records[0]['nazwa'], 'Wędka Łódź 1')
        self.assertEqual(records[-1]['nazwa'], 'Wędka Łódź 60')

    def test_delay(self):
        client = HttpClient()
        client.session = Mock()
        with patch('parser.time.monotonic', side_effect=[10, 10.1, 10.6]), patch('parser.time.sleep') as sleep:
            client.get('http://localhost/1')
            client.get('http://localhost/2')
        self.assertAlmostEqual(sleep.call_args.args[0], 0.4)

    def test_full_http_to_csv_and_empty_page(self):
        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass
        handler = functools.partial(QuietHandler, directory=str(FIXTURE.parent))
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / 'wynik.csv'
                base = f'http://127.0.0.1:{server.server_port}'
                self.assertEqual(main([base + '/catalogue.html', '--output', str(output)]), 0)
                with output.open(encoding='utf-8-sig', newline='') as stream:
                    rows = list(csv.DictReader(stream))
                self.assertEqual(len(rows), 60)
                self.assertEqual(rows[0]['nazwa'], 'Wędka Łódź 1')
                self.assertEqual(Decimal(rows[0]['cena']), Decimal('1299.00'))
                previous = output.read_bytes()
                with redirect_stderr(io.StringIO()):
                    self.assertEqual(main([base + '/', '--output', str(output)]), 1)
                    self.assertEqual(main([base + '/missing', '--output', str(output)]), 1)
                self.assertEqual(output.read_bytes(), previous)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
