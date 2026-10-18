"""Kontrolowany serwis testowy etapu 4.0, niezależny od www autora."""
import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


def data(i):
    return {
        'id': str(i), 'nazwa': f'Wędka Łódź {i}',
        'cena': ('1\u00a0299,90' if i == 199 else f'{50+i/10:.2f}'.replace('.', ',')) + (' EUR' if i % 5 == 0 else ' zł'),
        'waluta': 'EUR' if i % 5 == 0 else 'PLN', 'kategoria': 'Wędki',
        'producent': 'Marka testowa', 'dostepnosc': 'tak', 'ocena': '4,5',
        'liczba_opinii': str(i * 2), 'data_dodania': ['2026-10-16', '16.10.2026', 'wczoraj'][i % 3],
        'gwarancja': '24 miesiące', 'url': f'/produkt/{i}',
        'sku': f'SKU-{i:04}', 'podkategoria': 'Spinning', 'opis': f'Opis & jakość {i}',
        'waga_g': 'null' if i % 5 == 0 else f'{100+i} g',
        'dlugosc_cm': f'{200+i/10:.1f} cm', 'kolor': '' if i % 5 == 0 else 'żółty',
        'material': 'włókno węglowe', 'ean': f'059000{i:07}', 'dostawca': 'Dostawca testowy',
        'stawka_vat': '23 %', 'stan_magazynowy': str(i), 'jednostka': 'szt.'}


def page(path):
    path = urlsplit(path).path
    if path.startswith('/produkt/'):
        try:
            i = int(path.rsplit('/', 1)[1])
        except ValueError:
            return None
        if not 1 <= i <= 200:
            return None
        extras = list(data(i).items())[12:]
        if i % 2:
            body = '<dl>' + ''.join(f'<dt>{k}</dt><dd>{escape(v)}</dd>' for k,v in reversed(extras)) + '</dl>'
        else:
            body = '<table>' + ''.join(f'<tr><th>{k}</th><td>{escape(v)}</td></tr>' for k,v in extras) + '</table>'
        return '<meta charset="utf-8"><main id="szczegolyProduktu">' + body + '</main>'
    try:
        n = int(path.removeprefix('/katalog/'))
    except ValueError:
        return None
    if not 1 <= n <= 5:
        return None
    ids = list(range((n-1)*40+1, n*40+1))
    if n > 1:
        ids += [1, 2]  # 8 duplikatów rozrzuconych po czterech stronach
    body = '<meta charset="utf-8"><nav class="pagination">'
    body += ''.join(f'<a href="/katalog/{p}#lista">{p}</a>' for p in range(1,6)) + '</nav>'
    if n % 2:
        body += '<table><tr>' + ''.join(f'<th>{k}</th>' for k in list(data(1))[:12]) + '</tr>'
        for i in ids:
            body += '<tr>'
            for k,v in list(data(i).items())[:12]:
                body += '<td>' + (f'<a href="{v}">Szczegóły</a>' if k=='url' else escape(v)) + '</td>'
            body += '</tr>'
        body += '</table>'
    else:
        for i in ids:
            body += f'<article class="produkt" data-id="{i}">'
            for k,v in reversed(list(data(i).items())[1:12]):
                body += f'<a class="url" href="{v}">Szczegóły</a>' if k=='url' else f'<span data-field="{k}">{escape(v)}</span>'
            body += '</article>'
    return body


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        html = page(self.path)
        payload = (html or 'Nie znaleziono').encode('utf-8')
        self.send_response(200 if html else 404)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--port', type=int, default=8002)
    args = cli.parse_args()
    print(f'Serwis testowy: http://127.0.0.1:{args.port}/katalog/1', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
