# Parser laboratorium 1

Zmiany dotyczą wyłącznie folderu parser. Etapy 3.0 i 4.0 są sprawdzane na kontrolowanych katalogach, a etap 5.0 działa na dynamicznej stronie autora. Instrukcja uruchomienia etapu 5.0 znajduje się poniżej.

## Instalacja (z głównego folderu projektu)

```powershell
python -m venv parser/.venv
parser/.venv/Scripts/python.exe -m pip install -r parser/requirements.txt
```

## Testy

```powershell
parser/.venv/Scripts/python.exe -m unittest discover -s parser/tests -v
```

## Uruchomienie etapu 3.0

W pierwszym terminalu uruchom lokalny katalog testowy:

```powershell
parser/.venv/Scripts/python.exe -m http.server 8001 --bind 127.0.0.1 --directory parser/tests/fixtures
```

W drugim terminalu:

```powershell
parser/.venv/Scripts/python.exe parser/parser.py http://127.0.0.1:8001/catalogue.html --output parser/output/etap3.csv
```

Wynik: 60 rekordów (30 z tabeli, 30 z kart), 12 kolumn, UTF-8 z BOM. Cena jest liczbą Decimal, a w CSV ma zapis liczbowy bez waluty. CSV nie przechowuje metadanych typów; przy imporcie w polskim Excelu należy ustawić kropkę jako separator dziesiętny.

Selektory tabel opierają się na nagłówkach. Karty: article, div.produkt lub div.product; pola identyfikowane przez data-field, klasy semantyczne albo data-* na kontenerze. Nazwy i aliasy są w FIELDS i ALIASES. Gdy autor ukończy stronę, dostosujemy te selektory do jej rzeczywistego DOM. Nie jest to uniwersalny parser dowolnej strony.

Brak wartości daje puste pole. Niepoprawna niepusta cena przerywa etap 3.0 z komunikatem. Pusta strona, mniej niż 60 rekordów, brak jednej struktury lub błąd HTTP nie nadpisują poprzedniego CSV. Żądania mają timeout 30 s i minimum 0,5 s przerwy.

## Kolejność prac

1. 3.0: ukończona implementacja i testy na danych kontrolowanych; test z gotową stroną autora pozostaje otwarty.
2. 4.0: ukończone na danych kontrolowanych — paginacja, szczegóły, 200 rekordów i 24 atrybuty, normalizacja, braki, deduplikacja i analiza. Rozszerzenia: CSV + JSON oraz testy funkcji czyszczących. Instrukcja poniżej.
3. 5.0: Playwright + Edge, jawne oczekiwania, doładowywanie do końca, retry 1/2/4 s z limitem, 400 rekordów i 23 kolumny. Rozszerzenia: screenshot + HTML przy błędach oraz wykrycie i wykorzystanie źródła JSON. JSON służy niezależnej kontroli, nie zastępuje parsera DOM.
4. Analiza 4.0 dotyczy danych testowych, a analiza 5.0 danych strony autora. Sprawozdanie PDF zawiera wyniki oraz porównanie HTML/DOM.


## Etap 4.0

Implementacja: `stage4.py`. Etap 3.0 nadal działa osobno.

W pierwszym terminalu uruchom kontrolowany serwis (nie zmienia plików www):

```powershell
parser/.venv/Scripts/python.exe parser/tests/site4.py --port 8002
```

W drugim terminalu wykonaj pobranie, a potem analizę:

```powershell
parser/.venv/Scripts/python.exe parser/stage4.py http://127.0.0.1:8002/katalog/1 --today 2026-10-17 --output-dir parser/output/etap4
parser/.venv/Scripts/python.exe parser/analysis4.py parser/output/etap4
```

Pobieranie trwa około 105 sekund, ponieważ wykonuje 205 żądań z przerwami co najmniej 0,5 s. Test z prawdziwym HTTP można powtórzyć jednym poleceniem (sam uruchamia i zamyka serwer):

```powershell
parser/.venv/Scripts/python.exe parser/tests/verify_stage4_http.py
```

### Działanie

- Paginacja: kolejka adresów z `a[rel~=next]`, `.pagination a[href]` i `nav[aria-label=Paginacja] a[href]`. Zbiór odwiedzonych adresów zapobiega zapętleniu. Fragmenty `#...` są usuwane. Linki poza serwisem są odrzucane. Przekroczenie limitu stron jest błędem, nie cichym zakończeniem z częściowymi danymi.
- Wszystkie odnośniki szczegółów są odwiedzane. Ten sam adres pobierany jest tylko raz. Szczegóły czytane są z pól semantycznych, list `dt/dd` i tabel dwukolumnowych. Dane listy mają pierwszeństwo; szczegóły uzupełniają braki.
- 24 kolumny: 12 z etapu 3.0 oraz SKU, podkategoria, opis, waga, długość, kolor, materiał, EAN, dostawca, VAT, stan magazynowy i jednostka. W próbie połączone rekordy mają co najmniej 22 niepuste pola. Przed eksportem wymagane jest minimum 200 unikalnych rekordów i 18 kolumn z rzeczywistymi danymi oraz obie struktury list.
- Deduplikacja używa id, a przy jego braku SKU, a następnie adresu URL. Nazwa nie jest identyfikatorem. Pierwsza niepusta wartość wygrywa; późniejsze rekordy uzupełniają braki. Konflikty są wypisywane w podsumowaniu. Ten konserwatywny klucz wymaga spójnych identyfikatorów autora; nie rozpoznaje automatycznie tego samego produktu pod różnymi id.
- Ceny pozostają w oryginalnej walucie; nie mieszamy PLN z EUR w statystykach. Znak `$` bez kodu waluty nie jest automatycznie uznawany za USD.
- Daty ISO, DD.MM.RRRR, DD/MM/RRRR i „wczoraj” stają się YYYY-MM-DD. `--today` ustala datę odniesienia; domyślnie jest to lokalna data uruchomienia.
- Brakujące i nieprawidłowe liczby lub daty stają się pustymi wartościami (CSV) albo null (JSON); nieprawidłowe niepuste wartości trafiają do raportu. EAN, SKU i id pozostają tekstami, aby zachować początkowe zera. Jednostki obsługiwane obecnie: g, cm, procent.
- Nieudane pobranie strony lub nierozpoznane szczegóły przerywa pracę przed eksportem. Retry będzie w 5.0. Żądania i przekierowania respektują przerwę 0,5 s.

### Rozszerzenia i wyniki

Wybrane rozszerzenia 4.0: równoczesny eksport CSV + JSON oraz testy funkcji czyszczących. Liczby w JSON mają typ number, brakujące wartości null; w CSV typ ustala program importujący.

Próba HTTP: 5 stron katalogu, 200 stron szczegółów, 208 wpisów wejściowych, 8 usuniętych duplikatów, 200 produktów wyjściowych, 24 kolumny. Czas 103,5 s, najmniejszy odstęp między żądaniami 0,5 s. Dane pochodzą z generatora testowego, a nie z witryny kolegi. Integracja z jego dynamiczną stroną pozostaje na 5.0.

Pliki: `produkty.csv`, `produkty.json`, `podsumowanie.json`, `analiza.json`, `histogram.png`, `boxplot.png` w `parser/output/etap4`. Wyniki są pomijane przez Git; generator i testy umożliwiają ich odtworzenie.

Analiza: po 40 braków (20%) w wadze i kolorze, pozostałe pola bez braków; 8 duplikatów przed i 0 po deduplikacji; brak odrzuconych wartości. Cena 1299,90 PLN dla id 199 jest odstająca według 1,5 IQR, ale zgodna z wejściowym HTML — jest celowo wprowadzoną anomalią danych testowych, nie błędem przecinka. Korelacja stanu magazynowego z liczbą opinii wynosi 1, ponieważ generator ustawia opinie jako dwukrotność stanu. Nie stanowi to wniosku o rzeczywistym sklepie.

Statystyki obejmują wszystkie 7 cech liczbowych; ceny rozdzielono według waluty. Kwartyle: metoda inclusive. Jeśli każda wartość występuje raz, moda ma pustą listę. Histogram i boxplot pokazują ceny osobno dla PLN i EUR.

Wniosek: porównanie wszystkich 200 cen, dat, stanów i długości ze znanym generatorem potwierdza poprawność ekstrakcji na tym zestawie. Dodano odrzucanie niepoprawnego grupowania separatorów ceny, aby np. `1.2,00` nie stawało się po cichu liczbą 12. Odporność na końcowy DOM autora trzeba sprawdzić po ukończeniu strony. Kolory i układ CSS mogą się zmieniać bez wpływu na parser, ale zmiana nazw pól, klas semantycznych lub struktury paginacji wymaga dostosowania selektorów.

Etapy 3.0 i 4.0 zachowujemy jako testy kontrolowane. Integrację z gotową stroną autora realizuje opisany poniżej etap 5.0.

## Etap 5.0 na stronie autora

Implementacja: `stage5.py`, Playwright z przeglądarką Microsoft Edge. Zależności są w `requirements.txt`. Domyślny tryb headless nie otwiera okna; `--headed` pokazuje przeglądarkę. Inna zainstalowana przeglądarka Chromium może zostać wskazana przez `--channel chrome`. Nie deklarujemy rozszerzenia z porównaniem headless/headed: wybrano diagnostykę i źródło JSON.

Zainstaluj zaktualizowane biblioteki:

```powershell
parser/.venv/Scripts/python.exe -m pip install -r parser/requirements.txt
```

Uruchom stronę kolegi w pierwszym terminalu:

```powershell
parser/.venv/Scripts/python.exe -m http.server 8003 --bind 127.0.0.1 --directory www
```

W drugim terminalu:

```powershell
parser/.venv/Scripts/python.exe -X utf8 parser/stage5.py http://127.0.0.1:8003/catalogue.html --output-dir parser/output/etap5
parser/.venv/Scripts/python.exe -X utf8 parser/analysis5.py parser/output/etap5
```

Opcja `--today 2026-10-18` pozwala odtworzyć datę odniesienia bieżącego testu. Przy zwykłym użyciu należy pozostawić lokalną datę uruchomienia. Po uruchomieniu zobaczysz postęp co 25 produktów. Strona potrzebuje internetu do załadowania Bootstrap z CDN; bez niego nie działa rozwijanie dodatkowych informacji.

### Wymagania 5.0

- `wait_for_selector` i `wait_for_function` oczekują na elementy, wzrost liczby kart i zniknięcie spinnera. Nie używamy sztywnego czasu oczekiwania na gotowość strony. `sleep` występuje tylko w limiterze ruchu oraz w wymaganym backoff.
- Katalog jest doładowywany do zniknięcia przycisku. W bieżącej stronie startuje od 30 produktów; 13 kliknięć daje 400. Po kliknięciu odczytujemy aktualny DOM, ponieważ poprzednie karty są usuwane i tworzone ponownie.
- Każdy link do szczegółów jest odwiedzany. Parser klika „Dodatkowe informacje” i czeka na widoczny `#demo.show`. Pola `dt/dd` są rozpoznawane po etykietach, więc ich losowanie nie zmienia wyniku.
- Retry ma domyślnie 4 próby i przerwy 1, 2, 4 s. Całe pobranie katalogu lub pojedynczej strony szczegółów jest powtarzane od nawigacji, co usuwa skutki nieudanego kliknięcia. `--attempts` przyjmuje 1–4. Po wyczerpaniu prób parser kończy się kodem 1.
- Każda nieudana próba zapisuje HTML, PNG i wpis w `diagnostics/bledy.json`. Gdy sama przeglądarka jest już niedostępna, błąd zapisu diagnostyki trafia do tego samego raportu. Błędy końcowej walidacji także mają diagnostykę.
- Limit 0,5 s obejmuje wszystkie rzeczywiste żądania przeglądarki do lokalnego serwisu, w tym JSON. Skrypty, style i obrazy są po pierwszym pobraniu obsługiwane z pamięciowego cache; treść produktów nie jest podstawiana z cache ani z pliku lokalnego. Zasoby CDN nie są objęte limitem serwisu autora.
- Surowy HTML pobieramy bez przeglądarki i zapisujemy osobno. Zapisujemy też DOM katalogu po doładowaniu oraz przykładowe szczegóły po interakcji. Konkretne liczby trafiają do podsumowania.
- Minimum 400 rekordów jest sprawdzane przed eksportem i ponownie po deduplikacji. Eksport ma 23 kolumny: 22 atrybuty źródłowe (z aliasami marka→producent, ocena_srednia→ocena, aktywny→dostepnosc) i URL. Nie tworzymy nieistniejącej na stronie gwarancji. Brak wagi lub koloru nie eliminuje produktu.

### Wybrane rozszerzenia

1. Automatyczny screenshot i HTML przy błędach. Test wymuszonego HTTP 503 sprawdza zapis obu plików oraz odzyskanie działania przez retry.
2. Wykrycie źródła JSON: adres pochodzi z zaobserwowanych odpowiedzi fetch/XHR. Po zakończeniu parsowania DOM parser niezależnie pobiera JSON przez requests, normalizuje go i porównuje wszystkie pola wszystkich produktów. JSON nie uzupełnia braków DOM i nie zastępuje wizyt na stronach szczegółów. Niezerowe różnice lub odrzucone wartości powodują błąd przed eksportem produktów.

Pliki w `parser/output/etap5`: `produkty.csv`, `produkty.json`, `podsumowanie.json`, `zrodlo.json`, `porownanie.json`, `katalog-surowy.html`, `katalog-dom-1.html`, `szczegoly-dom.html`, `analiza.json`, `histogram.png`, `boxplot.png` oraz ewentualny folder `diagnostics`.

Czas JSON obejmuje pojedynczy odczyt i normalizację 400 rekordów; czas DOM obejmuje doładowywanie i wizyty na stronach szczegółów. To porównanie sposobów pozyskania tej samej treści, a nie test samej szybkości silnika HTML. JSON jest szybszy, bo nie wykonuje skryptów, animacji ani setek nawigacji. Nie mierzymy pamięci, ponieważ nie wybrano tego rozszerzenia.

### Dodatkowy test przeglądarkowy

Po uruchomieniu serwera na porcie 8003 (test wykonuj osobno, nie jednocześnie z pełnym pobieraniem):

```powershell
parser/.venv/Scripts/python.exe -X utf8 parser/tests/verify_stage5_browser.py
```

Wymusza jedno HTTP 503 dla JSON-u, sprawdza retry, pliki PNG/HTML i zgodność wyników po ponownym losowaniu kolejności atrybutów. Wymaga Edge i internetu do CDN.

### Granice zgodności

Na aktualnej stronie autora jest jeden katalog z doładowywaniem i karty, bez tabeli oraz bez pięciu stron paginacji katalogu. Parser odwiedza cały istniejący katalog i wszystkie strony produktów; nie wytwarza fikcyjnych podstron. Obsługę tabel i pięciu stron wykazują testy 3.0/4.0. Pozostają to różnice strony autora wobec dziedziczonych wymagań zadania, a nie pominięte produkty. Pliki www nie są zmieniane.

Selektory pól na stronie autora częściowo opierają się na klasach Bootstrap (np. `p.lead`, `p.h3`). Zmiana układu lub tych klas wymaga aktualizacji. Losowanie kolejności `dt/dd`, zmiana kolorów i wartości produktów nie wpływają na odczyt. Nowe etykiety lub inny format złożonej oceny wymagają dopasowania ekstrakcji.

### Odtworzenie dokumentacji

Po pełnym przebiegu parsera, analizie i teście przeglądarkowym:

```powershell
parser/.venv/Scripts/python.exe -m pip install -r parser/docs/requirements.txt
parser/.venv/Scripts/python.exe parser/docs/build_documentation5.py
./parser/docs/export_documentation.ps1
```

Eksport PDF wymaga zainstalowanego Microsoft Word. Dokumenty końcowe: `parser/docs/dokumentacja.docx` i `parser/docs/sprawozdanie.pdf`. Skrypt `build_documentation.py` dotyczy historycznej dokumentacji 4.0; dla wyniku końcowego używaj `build_documentation5.py`.

### Wynik pełnej weryfikacji 18.10.2026

- Strona autora: commit `7556ccc`; pliki www niezmienione.
- Surowy HTML: 0 rekordów; pierwszy DOM: 30; po 13 doładowaniach: 400.
- Odwiedzone szczegóły i rozwinięte panele: 400.
- Wynik: 400 produktów, 23 kolumny, 0 duplikatów i 0 odrzuconych wartości.
- Porównanie z niezależnym JSON-em: 9200 pól, 0 różnic.
- Czas DOM: 707,766 s; JSON (pobranie i normalizacja): 0,031 s; całość: 708,453 s.
- 816 rzeczywistych żądań przeglądarki do serwisu; minimalna przerwa: 0,5 s. Pełny przebieg bez błędów sieciowych i bez retry.
- 20 testów zakończonych powodzeniem; osobny test przeglądarkowy potwierdził retry po HTTP 503, zapis HTML/PNG i niezależność od kolejności etykiet.
- Braki: waga i kolor po 80 rekordów (20%); pozostałe kolumny bez braków.
- Korelacja stanu z opiniami: r≈0,079, bardzo słaba. Reguła IQR wskazuje m.in. 99 stawek VAT 8% jako odstające względem większości 23%; nie są usuwane jako błędy.
- Dokumentacja Word i PDF: 5 stron, sprawdzone wizualnie po eksporcie przez Word.
