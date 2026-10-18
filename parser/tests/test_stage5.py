import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stage5 import FIELDS5, compare_records, normalize_source, parse_cards, parse_detail, retry


def detail_html(reverse=False,opened=True):
    fields=[('Podkategoria','Spinning'),('Ocena','4,8 / 5 (12 opinii)'),
            ('Waga','brak informacji'),('Długość','210 cm'),('Kolor','brak informacji'),
            ('Materiał','włókno'),('Data dodania','wczoraj'),('SKU','S-1'),
            ('EAN','00123456789'),('Dostawca','Firma'),('VAT','23'),('Id','1')]
    if reverse:
        fields.reverse()
    pairs=''.join(f'<dt>{k}</dt><dd>{v}</dd>' for k,v in fields)
    return '''<main id="szczegolyProduktu"><h1>Wędka</h1>
    <p class="text-muted">Wędki · Marka</p><p class="lead">Opis</p>
    <p class="h3">1 299,00 zł PLN</p><p class="mb-1">Dostępny</p>
    <p class="mb-4">Na stanie: 8 szt.</p>''' + f'<div id="demo" class="collapse {"show" if opened else ""}"><dl>{pairs}</dl></div></main>'


class Stage5Tests(unittest.TestCase):
    def test_shuffled_labels_and_missing_values(self):
        listed={'id':'1','url':'http://local/product.html?id=1','nazwa':'Wędka'}
        issues=[]
        a=parse_detail(detail_html(),listed,date(2026,10,18),issues)
        b=parse_detail(detail_html(True),listed,date(2026,10,18),issues)
        self.assertEqual(a,b)
        self.assertEqual(len(a),23)
        self.assertEqual(a['cena'],Decimal('1299.00'))
        self.assertEqual(a['data_dodania'],'2026-10-17')
        self.assertEqual(a['ean'],'00123456789')
        self.assertIsNone(a['kolor'])
        self.assertIsNone(a['waga_g'])
        self.assertEqual(a['liczba_opinii'],12)
        self.assertEqual(issues,[])

    def test_must_expand_and_match_product(self):
        listed={'id':'1','url':'http://local/product.html?id=1','nazwa':'Wędka'}
        with self.assertRaisesRegex(ValueError,'rozwinięte'):
            parse_detail(detail_html(opened=False),listed,date.today(),[])
        with self.assertRaisesRegex(ValueError,'Id szczegółów'):
            parse_detail(detail_html(),{**listed,'id':'2'},date.today(),[])

    def test_retry_delays_diagnostics_and_limit(self):
        action=Mock(side_effect=[ValueError('1'),ValueError('2'),ValueError('3'),'ok'])
        diagnostics=Mock()
        sleep=Mock()
        self.assertEqual(retry('x',action,diagnostics,Mock(),4,sleep),'ok')
        self.assertEqual([c.args[0] for c in sleep.call_args_list],[1,2,4])
        self.assertEqual(diagnostics.save.call_count,3)
        action=Mock(side_effect=ValueError('fail'))
        diagnostics=Mock()
        with self.assertRaises(ValueError):
            retry('x',action,diagnostics,Mock(),2,Mock())
        self.assertEqual(action.call_count,2)
        self.assertEqual(diagnostics.save.call_count,2)

    def test_compare_detects_wrong_field_and_missing_id(self):
        row={f:None for f in FIELDS5}
        row.update(id='1',cena=Decimal('1.20'))
        changed={**row,'cena':Decimal('120')}
        differences=compare_records([row],[changed])
        self.assertEqual(differences[0]['pole'],'cena')
        self.assertEqual(compare_records([row],[])[0]['pole'],'rekord')

    def test_catalogue_uses_link_identity(self):
        html='''<div id="listaProduktow"><article><h3 class="card-title">Wędka</h3>
        <p class="text-muted">Wędki</p><p class="card-text">Opis</p>
        <p class="fw-bold">12 PLN</p><a href="./product.html?id=7">Produkt</a></article></div>'''
        rows=parse_cards(html,'http://local/catalogue.html')
        self.assertEqual(rows[0]['id'],'7')
        self.assertEqual(rows[0]['url'],'http://local/product.html?id=7')


if __name__=='__main__':
    unittest.main()
