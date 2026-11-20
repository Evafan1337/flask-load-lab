let catalog = [];
const items = new Map();
const money = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "RUB",
  maximumFractionDigits: 0,
});
const storageKey = "stationery-shop-v1";
const maxQuantity = 99;
const byId = (id) => document.getElementById(id);
const products = byId("products");
const cartItems = byId("cart-items");
const checkout = byId("checkout");
const dialog = byId("order-dialog");
const productTemplate = byId("product-template");
const cartTemplate = byId("cart-template");

function loadState() {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey));
    const cart = new Map(
      Object.entries(saved?.cart ?? {}).filter(
        ([id, quantity]) => items.has(id) &&
          Number.isInteger(quantity) && quantity > 0 && quantity <= maxQuantity
      )
    );
    const order = saved?.order;
    return {
      cart,
      order: order && /^(?:[0-9]{8}|[0-9A-F]{12})$/.test(order.number) && Number.isSafeInteger(order.total) &&
        order.total > 0 ? order : null,
    };
  } catch {
    return { cart: new Map(), order: null };
  }
}

let state = { cart: new Map(), order: null };
let orderPayload = null;
let orderPending = false;

async function requestJSON(path, payload) {
  const response = payload === undefined
    ? await fetch(path)
    : await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  const result = await response.json().catch(() => null);
  if (!response.ok || result === null) {
    throw new Error(result?.message || "Не удалось выполнить запрос.");
  }
  return result;
}

function currentBasket() {
  return { items: Array.from(state.cart, ([id, quantity]) => ({ id, quantity })) };
}

function saveState() {
  try {
    localStorage.setItem(storageKey, JSON.stringify({
      cart: Object.fromEntries(state.cart),
      order: state.order,
    }));
  } catch {
    // The cart remains usable when the browser blocks storage.
  }
}

function renderCatalog() {
  const query = byId("search").value.trim().toLocaleLowerCase("ru-RU");
  const category = byId("category").value;
  const sort = byId("sort").value;
  const visible = catalog.filter((product) =>
    (!category || product.category === category) &&
    product.name.toLocaleLowerCase("ru-RU").includes(query)
  );
  if (sort === "low") visible.sort((a, b) => a.price - b.price);
  if (sort === "high") visible.sort((a, b) => b.price - a.price);

  byId("results-count").classList.remove("message-error");
  byId("results-count").textContent = visible.length
    ? `Найдено товаров — ${visible.length}`
    : "Товары не найдены.";
  products.replaceChildren(...visible.map((product) => {
    const row = productTemplate.content.cloneNode(true);
    const name = row.querySelector("[data-detail]");
    name.textContent = product.name;
    name.dataset.detail = product.id;
    row.querySelector(".category").textContent = product.category;
    row.querySelector(".product-price").textContent = money.format(product.price);
    const button = row.querySelector(".primary");
    button.dataset.add = product.id;
    button.setAttribute("aria-label", `В корзину: ${product.name}`);
    button.disabled = state.cart.get(product.id) === maxQuantity;
    return row;
  }));
}

function cartTotals() {
  let quantity = 0;
  let total = 0;
  for (const [id, count] of state.cart) {
    quantity += count;
    total += count * items.get(id).price;
  }
  return { quantity, total };
}

function renderCart(focusAfterUpdate) {
  const { quantity, total } = cartTotals();
  const hasItems = quantity > 0;
  byId("cart-count").textContent = quantity;
  byId("cart-empty").hidden = hasItems;
  byId("cart-summary").hidden = !hasItems;
  byId("cart-total").textContent = money.format(total);
  checkout.hidden = !hasItems;

  const receipt = byId("receipt");
  receipt.hidden = !state.order;
  receipt.textContent = state.order
    ? `Демо-заказ №${state.order.number} оформлен на ${money.format(state.order.total)}.`
    : "";

  cartItems.replaceChildren(...Array.from(state.cart, ([id, count]) => {
    const product = items.get(id);
    const row = cartTemplate.content.cloneNode(true);
    row.querySelector("li").dataset.item = id;
    row.querySelector("h3").textContent = product.name;
    row.querySelector(".item-text p").textContent = `${money.format(product.price)} за шт.`;
    row.querySelector(".qty span").textContent = count;
    row.querySelector(".line-total").textContent = money.format(count * product.price);
    const decrease = row.querySelector('[data-change="-1"]');
    const increase = row.querySelector('[data-change="1"]');
    const remove = row.querySelector("[data-remove]");
    decrease.setAttribute("aria-label", `Уменьшить количество: ${product.name}`);
    increase.setAttribute("aria-label", `Увеличить количество: ${product.name}`);
    increase.disabled = count === maxQuantity;
    remove.setAttribute("aria-label", `Удалить: ${product.name}`);
    return row;
  }));

  for (const button of products.querySelectorAll("[data-add]")) {
    button.disabled = state.cart.get(button.dataset.add) === maxQuantity;
  }

  if (focusAfterUpdate) {
    const { id, control } = focusAfterUpdate;
    const button = cartItems.querySelector(`[data-item="${id}"] ${control}:enabled`);
    (button ?? cartItems.querySelector("button:enabled") ?? byId("cart-title")).focus();
  }
}

function changeQuantity(id, quantity, focusAfterUpdate) {
  byId("cart-error").textContent = "";
  if (quantity > maxQuantity) return;
  if (quantity > 0) {
    state.cart.set(id, quantity);
  } else {
    state.cart.delete(id);
  }
  state.order = null;
  saveState();
  renderCart(focusAfterUpdate);
  const product = items.get(id);
  byId("cart-status").textContent = quantity > 0
    ? `В корзине ${product.name}, ${quantity} шт.`
    : `Удалено из корзины: ${product.name}.`;
}

byId("filters").addEventListener("submit", (event) => event.preventDefault());
byId("search").addEventListener("input", renderCatalog);
byId("category").addEventListener("change", renderCatalog);
byId("sort").addEventListener("change", renderCatalog);
products.addEventListener("click", async (event) => {
  const add = event.target.closest("[data-add]");
  if (add) {
    const id = add.dataset.add;
    changeQuantity(id, (state.cart.get(id) ?? 0) + 1);
    return;
  }

  const details = event.target.closest("[data-detail]");
  if (!details) return;
  details.disabled = true;
  byId("results-count").classList.remove("message-error");
  try {
    const { product } = await requestJSON(`/api/products/${encodeURIComponent(details.dataset.detail)}`);
    byId("product-title").textContent = product.name;
    byId("product-description").textContent = product.description;
    byId("product-price").textContent = money.format(product.price);
    byId("product-dialog").showModal();
  } catch (error) {
    byId("results-count").classList.add("message-error");
    byId("results-count").textContent = error.message;
  } finally {
    details.disabled = false;
  }
});

cartItems.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  const id = button.closest("[data-item]").dataset.item;
  if (button.hasAttribute("data-remove")) {
    changeQuantity(id, 0, { id, control: "[data-remove]" });
    return;
  }
  const next = state.cart.get(id) + Number(button.dataset.change);
  changeQuantity(id, next, { id, control: `[data-change="${button.dataset.change}"]` });
});

checkout.addEventListener("click", async () => {
  if (!state.cart.size) return;
  checkout.disabled = true;
  byId("cart-error").textContent = "";
  const payload = currentBasket();
  try {
    const quote = await requestJSON("/api/cart", payload);
    if (JSON.stringify(payload) !== JSON.stringify(currentBasket())) return;

    const lines = quote.items.map((item) => {
      const row = document.createElement("li");
      const name = document.createElement("span");
      name.textContent = `${item.name} × ${item.quantity}`;
      const sum = document.createElement("strong");
      sum.textContent = money.format(item.subtotal);
      row.append(name, sum);
      return row;
    });
    byId("order-items").replaceChildren(...lines);
    byId("order-total").textContent = money.format(quote.total);
    byId("order-error").textContent = "";
    orderPayload = payload;
    dialog.showModal();
  } catch (error) {
    byId("cart-error").textContent = error.message;
  } finally {
    checkout.disabled = false;
  }
});

byId("order-form").addEventListener("submit", async (event) => {
  if (event.submitter?.value !== "confirm") return;
  event.preventDefault();
  if (!orderPayload || orderPending) return;

  orderPending = true;
  byId("order-confirm").disabled = true;
  byId("order-cancel").disabled = true;
  byId("order-error").textContent = "";
  try {
    const response = await requestJSON("/api/orders", orderPayload);
    state.order = { number: response.order_number, total: response.total };
    state.cart.clear();
    saveState();
    renderCart();
    dialog.close();
    byId("cart-title").focus();
  } catch (error) {
    byId("order-error").textContent = error.message;
  } finally {
    orderPending = false;
    byId("order-confirm").disabled = false;
    byId("order-cancel").disabled = false;
  }
});

dialog.addEventListener("cancel", (event) => {
  if (orderPending) event.preventDefault();
});

async function loadStore() {
  try {
    const [productsResponse, categoriesResponse] = await Promise.all([
      requestJSON("/api/products"), requestJSON("/api/categories"),
    ]);
    catalog = productsResponse.products;
    for (const product of catalog) items.set(product.id, product);
    for (const category of categoriesResponse.categories) {
      byId("category").append(new Option(category, category));
    }
    state = loadState();
    renderCatalog();
    renderCart();
  } catch (error) {
    byId("results-count").classList.add("message-error");
    byId("results-count").textContent = `Каталог недоступен. ${error.message}`;
  }
}

loadStore();
