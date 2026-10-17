Strona WWW - Wędkarski Raj
- Zawiera 6 podstron:
    - `index.html` który jest główną witryną sklepu, zawiera wyróżnione produkty, header z nazwą sklepu, menu oraz footer.
    - `catalogue.html` zawiera pełny katalog produktów oferowanych w sklepie, w sumie jest 400 produktów. Wyświetlane na początku pierwsze 30, resztę można doczytać klikając przycisk na dole strony który symuluje pobieranie informacji robiąc sleepa w losowym przedziale czasu od 300 do 2000 ms.
    - `contact.html` - podstrona zawierające "informacje kontaktowe"
    - `product.html` - strona dynamicznie dostosowywana do produktu których chcemy przeglądać. Zamienia zawartość strony czytając `URLSearchParams` z `id` i wyświetla szczegóły o żądanym produkcie, część dodatkowych informacji jest schowana pod collapsiblem który możemy rozwinąć klikając w przycisk. Kolejność właściwości  produktu jest losowa po każdym przeładowaniu.
    - `top_picks.html` - top 3 najwyżej oceniane produkty na stronie :)
    - `404.html` - nieużywana strona błędu żądania

- Wszystkie informacje o produktach są trzyane w jednym pliku `products.json`
- Skrypty używane na stronie znajdują się w `products.js` - wykrywamy elementy na stronie z odpowiednimi `id` i manipulująć DOM zastępujemy je dynamiczną zawartością. Fetchujemy dane z jsona za pomocą fetcha.
- Wybrane utrudnienia:
    - ceny zapisane w różny sposób i różnych walutach
    - braki wartości w dwóch różnych polach
    - niespójne formaty dat
    - atrybuty produktu widoczne dopiero po kliknęciu przycisku na stronie
    - losowa kolejność atrybutów w karcie produktu