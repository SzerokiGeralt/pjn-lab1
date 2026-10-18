"""Test przeglądarkowy retry i diagnostyki na stronie autora.
Uruchom serwer www na 8003 przed testem. Test wymaga internetu (Bootstrap).
"""
import json
import sys
from datetime import date
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stage5 import BrowserParser,RequestGate


def main():
    output=Path(__file__).resolve().parents[1]/'output'/'test-browser5'
    root=Path(__file__).resolve().parents[2]
    source=json.loads((root/'www'/'products.json').read_text(encoding='utf-8'))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context()
        page=context.new_page()
        gate=RequestGate('http://127.0.0.1:8003/')
        context.route('**/*',gate.handle)
        worker=BrowserParser(page,output,date(2026,10,18),attempts=2,timeout=5000)
        injections=[]
        def fail_once(route):
            if not injections:
                injections.append(route.request.url)
                route.fulfill(status=503,content_type='application/json',body='{}')
            else:
                route.fallback()
        context.route('**/products.json',fail_once)
        listed={'id':'1','url':'http://127.0.0.1:8003/product.html?id=1','nazwa':source[0]['nazwa']}
        issues=[]
        result=worker.run('awaria-json',lambda:worker.detail(listed,issues))
        assert result['sku']==source[0]['sku'] and not issues
        assert len(worker.diagnostics.events)==1
        event=worker.diagnostics.events[0]
        assert len(event['pliki'])==2 and not event['bledy_zapisu']
        assert (output/'diagnostics'/event['pliki'][1]).read_bytes().startswith(b'\x89PNG')
        assert len(injections)==1
        # Ponowne renderowanie losuje kolejność, ale wynik ma pozostać taki sam.
        second=worker.run('kolejnosc',lambda:worker.detail(listed,issues))
        assert result==second
        report={'retry_po_503':'OK','html_i_png':'OK','powtorna_losowa_kolejnosc':'OK','bledy_oczekiwane':1}
        (output/'wynik.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(report,flush=True)
        browser.close()


if __name__=='__main__':
    main()
