"""Etap 5.0: rzeczywista strona autora, Playwright + Edge, DOM i kontrola JSON."""
import argparse
import csv
import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from parser import HttpClient, clean_text
from stage4 import (FIELDS4, canonical_url, deduplicate, field_name, json_value,
                    normalize, PAGINATION)

FIELDS5 = tuple(f for f in FIELDS4 if f != 'gwarancja')
CARDS = '#listaProduktow article'
DETAIL = '#szczegolyProduktu'


def dump_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=json_value), encoding='utf-8')


def required(root, selector):
    element = root.select_one(selector)
    if element is None:
        raise ValueError('Brak elementu: ' + selector)
    return element.get_text(' ', strip=True)


def parse_cards(html, base):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for card in soup.select(CARDS):
        link = card.select_one('a[href*="product.html?"]')
        if link is None:
            raise ValueError('Karta bez linku do produktu')
        url = canonical_url(link['href'], base)
        ids = parse_qs(urlsplit(url).query).get('id', [])
        if len(ids) != 1:
            raise ValueError('Nieprawidłowy id w URL: ' + url)
        rows.append({'id': ids[0], 'url': url,
                     'nazwa': required(card, '.card-title'),
                     'kategoria': required(card, 'p.text-muted'),
                     'opis': required(card, '.card-text'),
                     'cena': required(card, 'p.fw-bold')})
    return rows


def parse_detail(html, listed, today, issues):
    soup = BeautifulSoup(html, 'html.parser')
    root = soup.select_one(DETAIL)
    if root is None or root.select_one('#demo.show') is None:
        raise ValueError('Dodatkowe informacje nie zostały rozwinięte')
    raw = dict(listed)
    raw['nazwa'] = required(root, 'h1')
    if raw['nazwa'] != listed['nazwa']:
        raise ValueError('Nazwa szczegółów nie odpowiada karcie')
    category_brand = required(root, 'p.text-muted').split(' · ', 1)
    if len(category_brand) != 2:
        raise ValueError('Nie rozpoznano kategorii i producenta')
    raw['kategoria'], raw['producent'] = category_brand
    raw['opis'] = required(root, 'p.lead')
    raw['cena'] = required(root, 'p.h3')
    currency = re.search(r'\b([A-Z]{3})\s*$', raw['cena'])
    if not currency:
        raise ValueError('Nie rozpoznano kodu waluty')
    raw['waluta'] = currency[1]
    raw['dostepnosc'] = required(root, 'p.mb-1')
    stock = re.fullmatch(r'Na stanie:\s*(\d+)\s+(.+)', required(root, 'p.mb-4'))
    if not stock:
        raise ValueError('Nie rozpoznano stanu magazynowego')
    raw['stan_magazynowy'], raw['jednostka'] = stock.groups()
    seen = set()
    for term in root.select('dt'):
        value = term.find_next_sibling()
        if value is None or value.name != 'dd':
            raise ValueError('Nazwa atrybutu bez wartości dd')
        field = field_name(term.get_text(' '), FIELDS5)
        if field:
            seen.add(field)
            raw[field] = value.get_text(' ', strip=True)
    expected = {'id', 'sku', 'ean', 'dostawca', 'stawka_vat', 'podkategoria',
                'ocena', 'waga_g', 'dlugosc_cm', 'kolor', 'material', 'data_dodania'}
    if not expected <= seen:
        raise ValueError('Brak nazw atrybutów: ' + ', '.join(sorted(expected-seen)))
    if str(raw['id']) != listed['id']:
        raise ValueError('Id szczegółów nie odpowiada karcie')
    rating = re.fullmatch(r'([\d.,]+)\s*/\s*5\s*\((\d+)\s+opinii\)', raw['ocena'])
    if rating:
        raw['ocena'], raw['liczba_opinii'] = rating.groups()
    elif clean_text(raw['ocena']).lower() == 'brak informacji':
        raw['ocena'] = raw['liczba_opinii'] = None
    else:
        raise ValueError('Nie rozpoznano oceny i liczby opinii')
    raw = {k: None if clean_text(v).lower() == 'brak informacji' else v for k,v in raw.items()}
    normalized = normalize(raw, listed['url'], today, issues)
    return {key: normalized[key] for key in FIELDS5}


def normalize_source(data, urls, today):
    rows, issues = [], []
    for item in data:
        identity = str(item['id'])
        if identity not in urls:
            raise ValueError('Produkt JSON nieodnaleziony w DOM: ' + identity)
        raw = {**item, 'producent': item.get('marka'), 'ocena': item.get('ocena_srednia'),
               'dostepnosc': 'Dostępny' if item.get('aktywny') else 'Niedostępny', 'url': urls[identity]}
        row = normalize(raw, urls[identity], today, issues)
        rows.append({key: row[key] for key in FIELDS5})
    return rows, issues


def compare_records(dom, source):
    expected = {row['id']: row for row in source}
    actual = {row['id']: row for row in dom}
    differences = []
    for identity in sorted(set(expected) | set(actual)):
        if identity not in expected or identity not in actual:
            differences.append({'id': identity, 'pole': 'rekord', 'blad': 'Brak rekordu w jednym źródle'})
            continue
        for field in FIELDS5:
            if actual[identity][field] != expected[identity][field]:
                differences.append({'id': identity, 'pole': field,
                                    'dom': actual[identity][field], 'json': expected[identity][field]})
    return differences


class Diagnostics:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.events = []

    def save(self, page, operation, attempt, error):
        name = f'{len(self.events)+1:03d}-{re.sub(r"[^a-zA-Z0-9_-]", "_", operation)}-proba-{attempt}'
        event = {'operacja': operation, 'proba': attempt, 'blad': str(error), 'pliki': [], 'bledy_zapisu': []}
        for suffix, write in [('.html', lambda p: p.write_text(page.content(), encoding='utf-8')),
                              ('.png', lambda p: page.screenshot(path=str(p), full_page=True, timeout=5000))]:
            path = self.directory / (name + suffix)
            try:
                write(path)
                event['pliki'].append(path.name)
            except Exception as capture_error:
                event['bledy_zapisu'].append(str(capture_error))
        self.events.append(event)
        dump_json(self.directory/'bledy.json', self.events)


def retry(operation, action, diagnostics, page, attempts=4, sleeper=time.sleep):
    if attempts < 1:
        raise ValueError('Liczba prób musi być dodatnia')
    for attempt in range(1, attempts+1):
        try:
            return action()
        except Exception as error:
            diagnostics.save(page, operation, attempt, error)
            if attempt == attempts:
                raise
            delay = 2 ** (attempt-1)
            print(f'Ponowienie {operation}: za {delay} s, próba {attempt+1}/{attempts}', flush=True)
            sleeper(delay)


class RequestGate:
    """Limit wszystkich żądań do serwisu; pamięciowy cache zasobów statycznych."""
    def __init__(self, base, last_finished=None):
        self.host = urlsplit(base).netloc
        self.last_finished = last_finished
        self.requests = 0
        self.cache = {}
        self.failures = []
        self.intervals = []

    def handle(self, route):
        request = route.request
        static = request.resource_type in ('script', 'stylesheet', 'image', 'font')
        if static and request.url in self.cache:
            route.fulfill(**self.cache[request.url])
            return
        local = urlsplit(request.url).netloc == self.host
        if local and self.last_finished is not None:
            time.sleep(max(0, 0.5-(time.monotonic()-self.last_finished)))
        started = time.monotonic()
        if local and self.last_finished is not None:
            self.intervals.append(started-self.last_finished)
        try:
            # Przekierowania nie mogą omijać limitera. Przeglądarka przejdzie
            # do Location, co wywoła ponownie tę funkcję.
            response = route.fetch(timeout=30000, max_redirects=0)
            headers = {k:v for k,v in response.headers.items() if k.lower() not in ('content-encoding','content-length')}
            payload = {'status': response.status, 'headers': headers, 'body': response.body()}
            if response.status >= 400:
                self.failures.append({'url': request.url, 'status': response.status})
            if static and response.ok:
                self.cache[request.url] = payload
            route.fulfill(**payload)
        except Exception as error:
            self.failures.append({'url': request.url, 'blad': str(error)})
            route.abort()
        finally:
            if local:
                self.requests += 1
                self.last_finished = time.monotonic()


class BrowserParser:
    def __init__(self, page, output, today, attempts=4, timeout=15000):
        self.page, self.output, self.today = page, Path(output), today
        self.attempts, self.timeout = attempts, timeout
        self.output.mkdir(parents=True, exist_ok=True)
        self.diagnostics = Diagnostics(self.output/'diagnostics')
        self.sources = set()
        page.set_default_timeout(timeout)
        page.on('response', self.observe_response)

    def observe_response(self, response):
        if response.request.resource_type in ('fetch', 'xhr') and 'json' in response.headers.get('content-type',''):
            self.sources.add(response.url)

    def run(self, name, action):
        return retry(name, action, self.diagnostics, self.page, self.attempts)

    def navigate(self, url):
        response = self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
        if response is None or not response.ok:
            raise ValueError('Błąd nawigacji HTTP: ' + url)

    def catalogue_page(self, url):
        self.navigate(url)
        self.page.wait_for_selector(CARDS)
        initial = self.page.locator(CARDS).count()
        batches = 0
        while True:
            self.page.wait_for_function("""() => !document.querySelector('#pokazWiecej .spinner-border')""")
            button = self.page.locator('#pokazWiecej button')
            if button.count() == 0:
                break
            before = self.page.locator(CARDS).count()
            button.click()
            self.page.wait_for_function("""before => document.querySelectorAll('#listaProduktow article').length > before
                && !document.querySelector('#pokazWiecej .spinner-border')""", arg=before)
            batches += 1
            if batches > 1000:
                raise ValueError('Przekroczono limit doładowań')
        html = self.page.content()
        soup = BeautifulSoup(html, 'html.parser')
        links = [canonical_url(a['href'], url) for a in soup.select(PAGINATION)]
        return parse_cards(html, url), initial, batches, links, html

    def catalogue(self, start):
        queue, visited, rows = [start], set(), []
        initial, batches = 0, 0
        while queue:
            url = queue.pop(0)
            if url in visited:
                continue
            if len(visited) >= 100:
                raise ValueError('Przekroczono limit podstron katalogu')
            part, first, loaded, links, html = self.run('katalog', lambda: self.catalogue_page(url))
            visited.add(url)
            rows.extend(part)
            initial += first
            batches += loaded
            (self.output/f'katalog-dom-{len(visited)}.html').write_text(html,encoding='utf-8')
            queue.extend(link for link in links if link not in visited and link not in queue)
        return rows, {'strony_katalogu': len(visited), 'dom_poczatkowy': initial, 'dom_koncowy': len(rows), 'doladowania': batches}

    def detail(self, listed, issues):
        self.navigate(listed['url'])
        self.page.wait_for_selector(DETAIL+' h1')
        button = self.page.locator(DETAIL+' button[data-bs-target="#demo"]')
        button.wait_for(state='visible')
        button.click()
        self.page.wait_for_selector(DETAIL+' #demo.show', state='visible')
        return parse_detail(self.page.content(), listed, self.today, issues)


def export5(rows, summary, output):
    output = Path(output)
    with (output/'produkty.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS5)
        writer.writeheader()
        writer.writerows(rows)
    dump_json(output/'produkty.json', rows)
    dump_json(output/'podsumowanie.json', summary)


def scrape(url, output, today, channel='msedge', headless=True, attempts=4):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    url = canonical_url(url,url)
    client = HttpClient()
    started = time.monotonic()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=channel, headless=headless)
        context = browser.new_context(viewport={'width':1280,'height':900}, locale='pl-PL')
        page = context.new_page()
        worker = BrowserParser(page, output, today, attempts)
        gate = RequestGate(url)
        context.route('**/*', gate.handle)
        try:
            raw = worker.run('surowy-html', lambda: client.get(url))
            gate.last_finished = client.last_finished
            (output/'katalog-surowy.html').write_bytes(raw.content)
            raw_count = len(BeautifulSoup(raw.content,'html.parser').select(CARDS))
            dom_started = time.monotonic()
            listings, summary = worker.catalogue(url)
            by_url = {}
            for listed in listings:
                by_url.setdefault(listed['url'], listed)
            if len(by_url)<400:
                raise ValueError(f'Za mało produktów w DOM: {len(by_url)}, wymagane minimum 400')
            rows, issues = [], []
            for index, listed in enumerate(by_url.values(),1):
                row = worker.run('produkt-'+listed['id'], lambda: worker.detail(listed, issues))
                rows.append(row)
                if index==1:
                    (output/'szczegoly-dom.html').write_text(page.content(),encoding='utf-8')
                if index%25==0:
                    print(f'Szczegóły: {index}/{len(by_url)}',flush=True)
            rows, removed, conflicts = deduplicate(rows)
            if len(rows)<400:
                raise ValueError('Po deduplikacji pozostało mniej niż 400 produktów')
            summary.update({'czas_dom_s': round(time.monotonic()-dom_started,3),
                            'surowy_html_rekordy': raw_count, 'strony_szczegolow': len(by_url),
                            'interakcje_szczegolow': len(by_url), 'rekordy_przed': len(listings),
                            'rekordy_po': len(rows), 'kolumny': len(FIELDS5),
                            'duplikaty_usuniete': len(listings)-len(rows), 'duplikaty_po': 0,
                            'konflikty_duplikatow': conflicts, 'odrzucone_wartosci': issues,
                            'data_odniesienia': today.isoformat(), 'silnik': 'Playwright / '+channel,
                            'headless': headless})
            # Źródło odkrywane z odpowiedzi sieciowych fetch/XHR, nie wpisane na sztywno.
            candidates = sorted(source for source in worker.sources if urlsplit(source).netloc==urlsplit(url).netloc)
            if not candidates:
                raise ValueError('Nie wykryto źródła JSON w ruchu sieciowym')
            client.last_finished = gate.last_finished
            urls = {r['id']:r['url'] for r in rows}
            def load_source():
                start = time.monotonic()
                for source_url in candidates:
                    response = client.get(source_url)
                    data = response.json()
                    if isinstance(data,list) and data and isinstance(data[0],dict) and 'id' in data[0] and 'cena' in data[0]:
                        source_rows, source_issues = normalize_source(data, urls, today)
                        source_rows, source_duplicates, _ = deduplicate(source_rows)
                        return source_url, data, source_rows, source_issues, source_duplicates, time.monotonic()-start
                raise ValueError('Wykryte JSON-y nie zawierają listy produktów')
            source_url, source_data, source_rows, source_issues, source_duplicates, elapsed = worker.run('zrodlo-json', load_source)
            differences = compare_records(rows,source_rows)
            dump_json(output/'zrodlo.json',source_data)
            dump_json(output/'porownanie.json',{'roznice':differences,'odrzucone_wartosci_json':source_issues})
            if differences or issues or source_issues:
                raise ValueError('Wynik wymaga sprawdzenia: różnice DOM/JSON lub odrzucone wartości; patrz porownanie.json')
            summary.update({'zrodlo_json':source_url,'rekordy_json':len(source_rows),
                            'duplikaty_json':source_duplicates,'czas_json_s':round(elapsed,3),
                            'porownane_pola':len(rows)*len(FIELDS5),'roznice_dom_json':len(differences),
                            'zadania_przegladarki_do_serwisu':gate.requests,
                            'minimalny_odstep_s':round(min(gate.intervals),6) if gate.intervals else None,
                            'bledy_sieciowe':gate.failures, 'nieudane_proby':worker.diagnostics.events,
                            'czas_calkowity_s':round(time.monotonic()-started,3)})
            export5(rows,summary,output)
            print(f'Gotowe: {len(rows)} produktów, {len(FIELDS5)} kolumn, różnice DOM/JSON: {len(differences)}',flush=True)
            return summary
        except Exception as error:
            # Błędy walidacji poza operacjami retry też otrzymują diagnostykę.
            worker.diagnostics.save(page,'przerwanie',1,error)
            raise
        finally:
            client.close()
            context.close()
            browser.close()


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('url')
    cli.add_argument('--output-dir',default='parser/output/etap5')
    cli.add_argument('--today',type=date.fromisoformat,default=date.today())
    cli.add_argument('--channel',default='msedge',help='msedge, chrome lub chromium (wymaga instalacji)')
    cli.add_argument('--headed',action='store_true')
    cli.add_argument('--attempts',type=int,choices=range(1,5),default=4)
    args = cli.parse_args(argv)
    try:
        scrape(args.url,args.output_dir,args.today,args.channel,not args.headed,args.attempts)
        return 0
    except Exception as error:
        print('Błąd: '+str(error),flush=True)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
