const productListContainers = [
	document.querySelector('#noweProdukty'),
	document.querySelector('#polecane'),
	document.querySelector('#listaProduktow')
].filter(Boolean);
const productDetailContainer = document.querySelector('#szczegolyProduktu');
const topPicksContainer = document.querySelector('#topPicksProducts');
const loadMoreDiv = document.querySelector('#pokazWiecej');

var displayProducts = 30;

function shuffleArray(array) {
  let currentIndex = array.length;

  while (currentIndex != 0) {

    let randomIndex = Math.floor(Math.random() * currentIndex);
    currentIndex--;

    [array[currentIndex], array[randomIndex]] = [
      array[randomIndex], array[currentIndex]];
  }
}

function createElement(tagName, className, text) {
	const element = document.createElement(tagName);
	if (className) element.className = className;
	if (text !== undefined && text !== null) element.textContent = text;
	return element;
}

function formatPrice(product) {
	if (typeof product.cena === 'string') return product.cena;
	return new Intl.NumberFormat('pl-PL', {
		style: 'currency',
		currency: product.waluta || 'PLN'
	}).format(product.cena);
}

function parseAddedDate(date) {
	if (typeof date !== 'string') return 0;
	const polishDate = date.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
	const parsed = polishDate
		? new Date(Number(polishDate[3]), Number(polishDate[2]) - 1, Number(polishDate[1]))
		: new Date(date);
	return Number.isNaN(parsed.getTime()) ? 0 : parsed.getTime();
}

function productUrl(product) {
	return `./product.html?id=${encodeURIComponent(product.id)}`;
}

function createProductCard(product, columnClass) {
	const column = createElement('div', columnClass);
	const card = createElement('article', 'card h-100 shadow-sm');
	const body = createElement('div', 'card-body');
	const title = createElement('h3', 'h5 card-title', product.nazwa);
	const category = createElement('p', 'small text-muted mb-2', product.kategoria);
	const description = createElement('p', 'card-text', product.opis);
	const price = createElement('p', 'fw-bold text-success', formatPrice(product));
	const link = createElement('a', 'btn btn-outline-success', 'Zobacz produkt');

	link.href = productUrl(product);
	body.append(title, category, description, price, link);
	card.append(body);
	column.append(card);
	return column;
}

function renderCards(container, products, columnClass = 'col-md-4') {
	container.replaceChildren();
	if (products.length === 0) {
		container.append(createElement('p', 'text-muted', 'Brak produktów do wyświetlenia.'));
		return;
	}
	products.forEach(product => container.append(createProductCard(product, columnClass)));
}

function renderProductDetails(product) {
	const container = productDetailContainer;
	container.replaceChildren();

	if (!product) {
		container.append(
			createElement('h1', 'h2', 'Nie znaleziono produktu'),
			createElement('p', 'text-muted', 'Sprawdź, czy link zawiera prawidłowy identyfikator produktu.')
		);
		return;
	}

	const row = createElement('div', 'row g-4');
	const mainColumn = createElement('div', 'col-lg-8');
	const title = createElement('h1', 'mb-3', product.nazwa);
	const category = createElement('p', 'text-muted', `${product.kategoria} · ${product.marka}`);
	const description = createElement('p', 'lead', product.opis);
	const price = createElement('p', 'h3 text-success fw-bold', formatPrice(product));
	const available = createElement('p', 'mb-1', `${Boolean(product.aktywny) ? 'Dostępny' : 'Niedostępny'}`);
	const stock = createElement('p', 'mb-4', `Na stanie: ${product.stan_magazynowy} ${product.jednostka || 'szt.'}`);
	const backLink = createElement('a', 'btn btn-outline-success', 'Wróć do produktów');
	backLink.href = './catalogue.html';

	mainColumn.append(title, category, description, price, available, stock, backLink);

	const specsColumn = createElement('div', 'col-lg-4');
	const specsCard = createElement('section', 'card');
	const specsBody = createElement('div', 'card-body');
	specsBody.append(createElement('h2', 'h5', 'Szczegóły produktu'));
	const specs = [
		['Podkategoria', product.podkategoria ?? 'brak informacji'],
		['Ocena', product.ocena_srednia == null ? 'brak informacji' : `${product.ocena_srednia} / 5 (${product.liczba_opinii} opinii)`],
		['Waga', product.waga_g == null ? 'brak informacji' : `${product.waga_g} g`],
		['Długość', product.dlugosc_cm == null ? 'brak informacji' : `${product.dlugosc_cm} cm`],
		['Kolor', product.kolor ?? 'brak informacji'],
		['Materiał', product.material ?? 'brak informacji'],
		['Data dodania', product.data_dodania ?? 'brak informacji']
	];

	shuffleArray(specs);
	
	const specsList = createElement('dl', 'row mb-2');
	specs.forEach(([label, value]) => {
		specsList.append(
			createElement('dt', 'col-5', label),
			createElement('dd', 'col-7', String(value))
		);
	});

	const additionalSpecs = [
		['SKU', product.sku ?? 'brak informacji'],
		['EAN', product.ean ?? 'brak informacji'],
		['Dostawca', product.dostawca ?? 'brak informacji'],
		['VAT', product.stawka_vat ?? 'brak informacji'],
		['Id', product.id ?? 'brak informacji']
	]

	shuffleArray(additionalSpecs);

	const additionalSpecsDiv = createElement('div','collapse');
	additionalSpecsDiv.setAttribute('id', 'demo');
	const additionalSpecsList = createElement('dl', 'row mb-0');
	additionalSpecsDiv.append(additionalSpecsList);
	additionalSpecs.forEach(([label, value]) => {
		additionalSpecsList.append(
			createElement('dt', 'col-5', label),
			createElement('dd', 'col-7', String(value))
		);
	});

	specsBody.append(specsList);
	const showDetailsButton = createElement('button', 'btn btn-primary mb-2', 'Dodatkowe informacje');
	showDetailsButton.setAttribute('type', 'button');
	showDetailsButton.setAttribute('data-bs-toggle', 'collapse');
	showDetailsButton.setAttribute('data-bs-target', '#demo');
	specsBody.append(showDetailsButton);
	specsBody.append(additionalSpecsDiv);
	specsCard.append(specsBody);
	specsColumn.append(specsCard);
	row.append(mainColumn, specsColumn);
	container.append(row);

	document.title = `${product.nazwa} — Wędkarski Raj`;
}

function showError(error) {
	console.error('Nie udało się załadować produktów:', error);
	const message = createElement('div', 'alert alert-danger', 'Nie udało się pobrać produktów. Spróbuj odświeżyć stronę.');
	[...productListContainers, productDetailContainer, topPicksContainer].filter(Boolean)
		.forEach(container => container.replaceChildren(message.cloneNode(true)));
}

async function loadProducts() {
	const response = await fetch('./products.json');
	if (!response.ok) {
		throw new Error(`Pobranie products.json nie powiodło się (HTTP ${response.status}).`);
	}

	const products = await response.json();
	if (!Array.isArray(products)) {
		throw new Error('products.json powinien zawierać tablicę produktów.');
	}

	const newestContainer = document.querySelector('#noweProdukty');
	if (newestContainer) {
		const newestProducts = [...products]
			.sort((a, b) => parseAddedDate(b.data_dodania) - parseAddedDate(a.data_dodania))
			.slice(0, 2);
		renderCards(newestContainer, newestProducts, 'col-md-6');
	}

	const recommendedContainer = document.querySelector('#polecane');
	if (recommendedContainer) {
		const recommendedProducts = [...products]
			.sort((a, b) => (b.ocena_srednia || 0) - (a.ocena_srednia || 0))
			.slice(0, 3);
		renderCards(recommendedContainer, recommendedProducts);
	}

	if (document.querySelector('#listaProduktow')) {
		const loadMoreButton = createElement("button","btn btn-primary bg-success border-success","Załaduj więcej");
		loadMoreButton.setAttribute("onclick","loadMoreButtonClicked()")
		if (displayProducts < products.length) 
			{
				loadMoreDiv.append(loadMoreButton);
				//show button
			} else {
				loadMoreDiv.replaceChildren();
				//hide button
			}
		renderCards(document.querySelector('#listaProduktow'), products.slice(0,displayProducts));
	}

	if (productDetailContainer) {
		const productId = new URLSearchParams(window.location.search).get('id');
		const product = products.find(item => String(item.id) === productId);
		renderProductDetails(product);
	}

	if (topPicksContainer) {
		const topProducts = [...products]
			.sort((a, b) => (b.ocena_srednia || 0) - (a.ocena_srednia || 0))
			.slice(0, 3);
		renderCards(topPicksContainer, topProducts);
	}
}

if (productListContainers.length || productDetailContainer || topPicksContainer) {
	loadProducts().catch(showError);
}

async function loadMoreButtonClicked() {
	const loadingSpinner = createElement("span","spinner-border text-success");
	loadMoreDiv.replaceChildren(loadingSpinner);

	displayProducts += 30;

	const response = await fetch('./products.json');
	if (!response.ok) {
		throw new Error(`Pobranie products.json nie powiodło się (HTTP ${response.status}).`);
	}

	const products = await response.json();
	if (!Array.isArray(products)) {
		throw new Error('products.json powinien zawierać tablicę produktów.');
	}

	const randomSleepTime = Math.floor(1701 * Math.random());
	await new Promise(r => setTimeout(r, 300 + randomSleepTime));
	
	const loadMoreButton = createElement("button","btn btn-primary bg-success border-success","Załaduj więcej");
	loadMoreButton.setAttribute("onclick","loadMoreButtonClicked()")
	if (displayProducts < products.length) 
		{
			loadMoreDiv.replaceChildren(loadMoreButton);
			//show button
		} else {
			loadMoreDiv.replaceChildren();
			//hide button
		}
	renderCards(document.querySelector('#listaProduktow'), products.slice(0,displayProducts));
}
