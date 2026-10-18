"""Analiza finalnych danych DOM z etapu 5.0 i zgodności ze źródłem JSON."""
import argparse
import json
import os
from pathlib import Path
from analysis4 import analyze, charts


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('directory',nargs='?',default='parser/output/etap5')
    args=cli.parse_args()
    directory=Path(args.directory)
    records=json.loads((directory/'produkty.json').read_text(encoding='utf-8'))
    summary=json.loads((directory/'podsumowanie.json').read_text(encoding='utf-8'))
    report=analyze(records,summary)
    report['kontrola_zrodla']={
        'porownane_pola':summary['porownane_pola'],
        'roznice_dom_json':summary['roznice_dom_json'],
        'wniosek':'Wartości odstające są zgodne ze źródłem JSON; nie wynikają z rozbieżności ekstrakcji DOM.'
                  if summary['roznice_dom_json']==0 else 'Różnice ze źródłem wymagają sprawdzenia.'}
    report['korelacja']['komentarz']='Korelacja opisuje współzmienność stanu magazynowego i liczby opinii w wygenerowanym katalogu. Nie dowodzi wpływu zapasu na opinie ani związku przyczynowego.'
    (directory/'analiza.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    charts(records,directory)
    import matplotlib.pyplot as plt
    prices=[r['cena'] for r in records if r['waluta']=='PLN' and r['cena'] is not None]
    fig,axes=plt.subplots(3,1,figsize=(7,8.5),gridspec_kw={'height_ratios':[1,1.3,0.65]})
    axes[0].hist(prices,bins=20,edgecolor='black')
    axes[0].set(title=f'Ceny w PLN (n={len(prices)})',xlabel='Cena (PLN)',ylabel='Liczba produktów')
    cheap=[price for price in prices if 0 <= price <= 200]
    counts,edges,bars=axes[1].hist(cheap,bins=list(range(0,201,20)),edgecolor='black')
    axes[1].set(title=f'Powiększenie 0–200 PLN: {len(cheap)} z {len(prices)} produktów',
                xlabel='Cena (PLN), przedziały co 20 zł',ylabel='Liczba produktów',
                xticks=list(range(0,201,20)),xlim=(0,200))
    axes[1].bar_label(bars,labels=[str(int(n)) if n else '' for n in counts],padding=3,fontsize=9)
    axes[1].set_ylim(0,max(counts)*1.18 if len(counts) and max(counts)>0 else 1)
    axes[2].boxplot(prices,orientation='horizontal')
    axes[2].set(xlabel='Cena (PLN), wszystkie produkty',yticks=[])
    fig.tight_layout()
    fig.savefig(directory/'wykresy-raport.png',dpi=150)
    plt.close(fig)
    print('Analiza i wykresy zapisane w',directory)


if __name__=='__main__':
    main()
