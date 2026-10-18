import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analysis4 import analyze,describe


class AnalysisTests(unittest.TestCase):
    def test_known_statistics(self):
        result=describe([1,2,3,4])
        self.assertEqual(result['srednia'],2.5)
        self.assertEqual(result['mediana'],2.5)
        self.assertEqual(result['q1'],1.75)
        self.assertEqual(result['q3'],3.25)
        self.assertEqual(result['moda'],[])
        self.assertEqual(describe([2,2,3])['moda'],[2])

    def test_currency_groups_missing_and_correlation(self):
        rows=[dict(id=str(i),cena=price,waluta=currency,ocena=None,liczba_opinii=i*2,
                   waga_g=None,dlugosc_cm=None,stawka_vat=23,stan_magazynowy=i)
              for i,(price,currency) in enumerate([(10,'PLN'),(20,'PLN'),(100,'EUR')],1)]
        report=analyze(rows,dict(duplikaty_usuniete=1,duplikaty_po=0))
        self.assertEqual(report['statystyki']['cena_PLN']['srednia'],15)
        self.assertEqual(report['statystyki']['cena_EUR']['srednia'],100)
        self.assertEqual(report['braki']['waga_g']['procent'],100)
        self.assertAlmostEqual(report['korelacja']['pearson_r'],1)
