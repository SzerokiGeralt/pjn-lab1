const productListContainers = [
	document.querySelector('#noweProdukty'),
	document.querySelector('#polecane'),
	document.querySelector('#listaProduktow')
].filter(Boolean);
const productDetailContainer = document.querySelector('#szczegolyProduktu');
const topPicksContainer = document.querySelector('#topPicksProducts');

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
		['SKU', product.sku],
		['Podkategoria', product.podkategoria],
		['Ocena', product.ocena_srednia == null ? null : `${product.ocena_srednia} / 5 (${product.liczba_opinii} opinii)`],
		['Waga', product.waga_g == null ? null : `${product.waga_g} g`],
		['Długość', product.dlugosc_cm == null ? null : `${product.dlugosc_cm} cm`],
		['Kolor', product.kolor],
		['Materiał', product.material],
		['Data dodania', product.data_dodania],
		['EAN', product.ean],
		['Dostawca', product.dostawca],
		['VAT', product.stawka_vat]
	];
	const list = createElement('dl', 'row mb-0');
	specs.forEach(([label, value]) => {
		list.append(
			createElement('dt', 'col-5', label),
			createElement('dd', 'col-7', String(value))
		);
	});
	specsBody.append(list);
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
		renderCards(document.querySelector('#listaProduktow'), products);
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
