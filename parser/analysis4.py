"""Kontrola jakości i statystyki eksportu etapu 4.0; ceny osobno dla walut."""
import argparse
import json
import os
import statistics as st
from collections import Counter
from pathlib import Path

NUMERIC = ('cena', 'ocena', 'liczba_opinii', 'waga_g', 'dlugosc_cm', 'stawka_vat', 'stan_magazynowy')


def describe(values):
    if not values:
        return None
    q1,median,q3 = st.quantiles(values, n=4, method='inclusive') if len(values)>1 else [values[0]]*3
    counts = Counter(values)
    return {'n': len(values), 'srednia': st.mean(values), 'mediana': st.median(values),
            'moda': st.multimode(values) if max(counts.values())>1 else [],
            'q1': q1, 'q3': q3, 'min': min(values), 'max': max(values)}


def analyze(records, summary):
    if not records:
        raise ValueError('Brak danych do analizy')
    result = {'rekordy': len(records), 'duplikaty_przed': summary['duplikaty_usuniete'],
              'duplikaty_po': summary['duplikaty_po'], 'braki': {}, 'typy': {},
              'statystyki': {}, 'odstajace': {}}
    for field in records[0]:
        missing = sum(r[field] is None or r[field]=='' for r in records)
        result['braki'][field] = {'liczba': missing, 'procent': 100*missing/len(records)}
        result['typy'][field] = dict(Counter(type(r[field]).__name__ for r in records if r[field] is not None))
    for field in NUMERIC:
        groups = sorted({r['waluta'] or 'BRAK_WALUTY' for r in records}) if field=='cena' else [None]
        for currency in groups:
            subset = [r for r in records if r[field] is not None and (field!='cena' or (r['waluta'] or 'BRAK_WALUTY')==currency)]
            values = [r[field] for r in subset]
            if any(type(v) not in (int,float) for v in values):
                raise ValueError('Nieliczbowy typ w kolumnie ' + field)
            name = field + ('_' + currency if currency else '')
            stats = describe(values)
            result['statystyki'][name] = stats
            if stats:
                iqr = stats['q3']-stats['q1']
                low,high = stats['q1']-1.5*iqr, stats['q3']+1.5*iqr
                result['odstajace'][name] = [{'id': r['id'], 'wartosc': r[field]} for r in subset if not low <= r[field] <= high]
    pairs = [(r['stan_magazynowy'],r['liczba_opinii']) for r in records if r['stan_magazynowy'] is not None and r['liczba_opinii'] is not None]
    try:
        correlation = st.correlation([x for x,y in pairs],[y for x,y in pairs]) if len(pairs)>1 else None
    except st.StatisticsError:
        correlation = None
    result['korelacja'] = {'cechy': ['stan_magazynowy','liczba_opinii'], 'n': len(pairs), 'pearson_r': correlation}
    return result


def charts(records, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(output.resolve() / '.matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    groups = sorted({r['waluta'] or 'BRAK_WALUTY' for r in records if r['cena'] is not None})
    if not groups:
        raise ValueError('Brak cen do wykresów')
    samples = [[r['cena'] for r in records if (r['waluta'] or 'BRAK_WALUTY')==g and r['cena'] is not None] for g in groups]
    fig, axes = plt.subplots(len(groups), 1, figsize=(7, 3*len(groups)), squeeze=False)
    for ax,g,values in zip(axes[:,0],groups,samples):
        ax.hist(values,bins=15,edgecolor='black')
        ax.set(xlabel='Cena ('+g+')',ylabel='Liczba produktów',title='Rozkład cen '+g)
    fig.tight_layout()
    fig.savefig(output/'histogram.png',dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(1,len(groups),figsize=(7,4),squeeze=False)
    for ax,g,values in zip(axes[0],groups,samples):
        ax.boxplot(values)
        ax.set(ylabel='Cena ('+g+')',title=g,xticks=[])
    fig.tight_layout()
    fig.savefig(output/'boxplot.png',dpi=150)
    plt.close(fig)


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('directory',nargs='?',default='parser/output/etap4')
    args=cli.parse_args()
    directory=Path(args.directory)
    records=json.loads((directory/'produkty.json').read_text(encoding='utf-8'))
    summary=json.loads((directory/'podsumowanie.json').read_text(encoding='utf-8'))
    report=analyze(records,summary)
    (directory/'analiza.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    charts(records,directory)
    print('Zapisano analizę, histogram i boxplot w',directory)


if __name__=='__main__':
    main()
