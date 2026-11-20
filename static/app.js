(() => {
  "use strict";

  // ------------------------------------------------------------ utilidades
  const $ = (sel, el = document) => el.querySelector(sel);
  const view = $("#view");
  const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
  const money = (n) => "$" + Number(n).toLocaleString("es-CO");
  const firstName = (n) => esc(String(n || "").split(" ")[0]);

  const state = { user: null, cart: { unidades: 0 }, categories: [] };

  async function api(path, { method = "GET", body } = {}) {
    const resp = await fetch(path, {
      method,
      credentials: "same-origin",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = null;
    try { data = await resp.json(); } catch { /* sin cuerpo */ }
    if (!resp.ok) {
      const detail = data && data.detail;
      const err = new Error(typeof detail === "string" ? detail : resp.status === 422 ? "Revisa los datos ingresados." : `Error ${resp.status}`);
      err.status = resp.status;
      throw err;
    }
    return data;
  }

  const I = {
    cart: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="20" r="1.4"/><circle cx="18" cy="20" r="1.4"/><path d="M2 3h3l2.6 12.2a2 2 0 0 0 2 1.6h8.6a2 2 0 0 0 2-1.5L22 7H6"/></svg>',
    user: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
    truck: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h11v10H3zM14 9h4l3 3v4h-7"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/></svg>',
    back: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>',
    lock: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>',
    shield: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/><path d="m9 12 2 2 4-4"/></svg>',
    check: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="m5 12 5 5L20 7"/></svg>',
    box: '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/></svg>',
  };

  function toast(msg) {
    const t = $("#toast");
    t.innerHTML = I.check + " " + esc(msg);
    t.classList.add("show");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => t.classList.remove("show"), 2600);
  }

  const stars = (r) => "★★★★★".slice(0, Math.round(r)) + "☆☆☆☆☆".slice(0, 5 - Math.round(r));
  const discount = (p) => (p.precio_antes ? Math.round((1 - p.precio / p.precio_antes) * 100) : 0);

  function productCard(p) {
    const d = discount(p);
    return `
      <article class="card product-card">
        ${d ? `<span class="discount">-${d}%</span>` : ""}
        <a class="thumb" href="#/producto/${p.id}"><img src="${esc(p.imagen)}" alt="${esc(p.nombre)}" loading="lazy"></a>
        <div class="info">
          <span class="cat">${esc(p.categoria)}</span>
          <a href="#/producto/${p.id}"><h3>${esc(p.nombre)}</h3></a>
          <div class="rating"><span class="stars">${stars(p.rating)}</span>${p.rating} (${p.reviews})</div>
          <div class="price"><strong>${money(p.precio)}</strong>${p.precio_antes ? `<s>${money(p.precio_antes)}</s>` : ""}</div>
          <button class="btn primary small" data-add="${p.id}" type="button">${I.cart} Agregar</button>
        </div>
      </article>`;
  }

  const statusClass = (s) => (s === "Entregado" ? "ok" : ["En camino", "Despachado"].includes(s) ? "go" : "wait");
  const STEPS = ["Confirmado", "En preparación", "En camino", "Entregado"];
  const stepIndex = (s) => ({ "Pago en verificación": 0, Confirmado: 1, "En preparación": 2, Despachado: 3, "En camino": 3, Entregado: 4 }[s] ?? 1);

  // ------------------------------------------------------------- sesión
  async function loadSession() {
    const me = await api("/api/auth/me");
    state.user = me.usuario;
    if (state.user) {
      try { state.cart = await api("/api/cart"); } catch { state.cart = { unidades: 0 }; }
    } else {
      state.cart = { unidades: 0 };
    }
    renderHeader();
    Chat.reset();
  }

  function renderHeader() {
    const u = state.user;
    $("#header-actions").innerHTML = `
      ${u ? `
        <div class="menu">
          <button class="header-link" id="account-btn" type="button" aria-haspopup="true">${I.user}<span class="label"><span class="sub">Hola, ${firstName(u.nombre)}</span>Mi cuenta</span></button>
          <div class="dropdown hidden" id="account-menu">
            <a href="#/pedidos">Mis pedidos</a>
            <a href="#/cuenta">Datos personales</a>
            ${u.rol === "admin" ? `<a href="#/seguridad">${I.shield} Centro de seguridad</a>` : ""}
            <hr><button type="button" id="logout">Cerrar sesión</button>
          </div>
        </div>` : `<a class="header-link" href="#/login">${I.user}<span class="label"><span class="sub">Bienvenido</span>Ingresar</span></a>`}
      <a class="header-link cart-btn" href="#/carrito" aria-label="Carrito">${I.cart}${state.cart.unidades ? `<span class="badge-count">${state.cart.unidades}</span>` : ""}<span class="label">Carrito</span></a>`;
    const btn = $("#account-btn");
    if (btn) {
      btn.addEventListener("click", (e) => { e.stopPropagation(); $("#account-menu").classList.toggle("hidden"); });
      $("#logout").addEventListener("click", logout);
    }
  }
  document.addEventListener("click", () => { const m = $("#account-menu"); if (m) m.classList.add("hidden"); });

  async function logout() {
    await api("/api/auth/logout", { method: "POST" });
    await loadSession();
    toast("Cerraste sesión");
    location.hash = "#/";
  }

  function requireLogin() {
    if (state.user) return true;
    location.hash = "#/login?next=" + encodeURIComponent(location.hash.slice(1) || "/");
    return false;
  }

  async function addToCart(id, qty = 1) {
    if (!state.user) { toast("Inicia sesión para agregar productos"); return requireLogin(); }
    try {
      state.cart = await api("/api/cart", { method: "POST", body: { producto_id: Number(id), cantidad: qty } });
      renderHeader();
      toast("Producto agregado al carrito");
    } catch (e) { toast(e.message); }
  }

  view.addEventListener("click", (e) => {
    const add = e.target.closest("[data-add]");
    if (add) addToCart(add.dataset.add);
  });

  // -------------------------------------------------------------- vistas
  async function renderCatnav() {
    state.categories = await api("/api/categories");
    $("#catnav").innerHTML = `<a href="#/catalogo">Todo</a>` + state.categories.map((c) => `<a href="#/catalogo?cat=${encodeURIComponent(c.nombre)}">${esc(c.nombre)}</a>`).join("");
  }

  async function homeView() {
    const featured = await api("/api/products?destacados=true");
    const all = await api("/api/products");
    const hero = all.find((p) => p.sku === "SM-AUD-01") || featured[0];
    const catImg = (c) => (all.find((p) => p.categoria === c.nombre) || {}).imagen;
    return `
      <div class="container">
        <section class="hero">
          <div class="hero-text">
            <span class="eyebrow">Temporada de ofertas · hasta 30 % de descuento</span>
            <h1>Tecnología y hogar con envío a toda Colombia</h1>
            <p>Audio, cocina, computadores y más, con garantía, pago contra entrega y devoluciones gratis durante 30 días.</p>
            <a class="btn primary" href="#/catalogo">Ver productos</a>
            <a class="btn ghost" href="#/producto/${hero.id}">Ver oferta destacada</a>
          </div>
          <div class="hero-media"><img src="${esc(hero.imagen)}" alt="${esc(hero.nombre)}"></div>
          <div class="hero-price">${esc(hero.nombre)}<strong>${money(hero.precio)}</strong></div>
        </section>

        <section class="benefits">
          <div class="card benefit"><div class="ico">${I.truck}</div><div><strong>Envío gratis</strong><span>En compras desde $150.000</span></div></div>
          <div class="card benefit"><div class="ico">${I.back}</div><div><strong>30 días para devolver</strong><span>Recogida gratis en tu casa</span></div></div>
          <div class="card benefit"><div class="ico">${I.lock}</div><div><strong>Pago seguro</strong><span>Contra entrega, PSE o tarjeta</span></div></div>
          <div class="card benefit"><div class="ico">${I.shield}</div><div><strong>Garantía legal</strong><span>Mínimo 1 año en tecnología</span></div></div>
        </section>

        <section class="section">
          <div class="section-head"><h2>Compra por categoría</h2><a href="#/catalogo">Ver todo →</a></div>
          <div class="cats">${state.categories.map((c) => `
            <a class="card cat-tile" href="#/catalogo?cat=${encodeURIComponent(c.nombre)}"><img src="${esc(catImg(c))}" alt=""><span>${esc(c.nombre)}</span></a>`).join("")}
          </div>
        </section>

        <section class="section">
          <div class="section-head"><h2>Destacados de la semana</h2><a href="#/catalogo">Ver catálogo →</a></div>
          <div class="products">${featured.slice(0, 8).map(productCard).join("")}</div>
        </section>
      </div>`;
  }

  async function catalogView(params) {
    const cat = params.get("cat") || "";
    const q = params.get("q") || "";
    const orden = params.get("orden") || "relevancia";
    const items = await api(`/api/products?categoria=${encodeURIComponent(cat)}&q=${encodeURIComponent(q)}&orden=${orden}`);
    const total = state.categories.reduce((a, c) => a + c.productos, 0);
    const link = (c) => `#/catalogo?${new URLSearchParams({ ...(c ? { cat: c } : {}), ...(q ? { q } : {}), orden })}`;
    setTimeout(() => {
      const sel = $("#orden");
      if (sel) sel.addEventListener("change", () => { location.hash = `#/catalogo?${new URLSearchParams({ ...(cat ? { cat } : {}), ...(q ? { q } : {}), orden: sel.value })}`; });
    });
    return `
      <div class="container page">
        <div class="breadcrumb"><a href="#/">Inicio</a> / Catálogo${cat ? " / " + esc(cat) : ""}</div>
        <div class="catalog">
          <aside class="card filters">
            <h3>Categorías</h3>
            <a href="${link("")}" class="${cat ? "" : "active"}">Todas <span>${total}</span></a>
            ${state.categories.map((c) => `<a href="${link(c.nombre)}" class="${c.nombre === cat ? "active" : ""}">${esc(c.nombre)} <span>${c.productos}</span></a>`).join("")}
          </aside>
          <div>
            <div class="toolbar">
              <div><h1 class="page-title">${q ? `Resultados para “${esc(q)}”` : esc(cat || "Todos los productos")}</h1><span class="muted">${items.length} producto(s)</span></div>
              <select class="input" id="orden" aria-label="Ordenar">
                ${[["relevancia", "Más relevantes"], ["precio_asc", "Menor precio"], ["precio_desc", "Mayor precio"], ["rating", "Mejor calificados"]].map(([v, l]) => `<option value="${v}" ${v === orden ? "selected" : ""}>${l}</option>`).join("")}
              </select>
            </div>
            ${items.length ? `<div class="products">${items.map(productCard).join("")}</div>` : `
              <div class="card empty"><div class="muted">${I.box}</div><h3>No encontramos productos</h3><p class="muted">Prueba con otra búsqueda o revisa todas las categorías.</p><a class="btn primary" href="#/catalogo">Ver todo</a></div>`}
          </div>
        </div>
      </div>`;
  }

  async function productView(id) {
    const p = await api(`/api/products/${Number(id)}`);
    const d = discount(p);
    let qty = 1;
    setTimeout(() => {
      const label = $("#qty-val");
      $("#qty-minus").addEventListener("click", () => { qty = Math.max(1, qty - 1); label.textContent = qty; });
      $("#qty-plus").addEventListener("click", () => { qty = Math.min(p.stock, qty + 1, 20); label.textContent = qty; });
      $("#buy").addEventListener("click", () => addToCart(p.id, qty));
      $("#buy-now").addEventListener("click", async () => { if (state.user) { await addToCart(p.id, qty); location.hash = "#/carrito"; } else requireLogin(); });
    });
    return `
      <div class="container page">
        <div class="breadcrumb"><a href="#/">Inicio</a> / <a href="#/catalogo?cat=${encodeURIComponent(p.categoria)}">${esc(p.categoria)}</a> / ${esc(p.nombre)}</div>
        <div class="pdp">
          <div class="card gallery"><img src="${esc(p.imagen)}" alt="${esc(p.nombre)}"></div>
          <div>
            <span class="muted small">${esc(p.categoria)} · Ref. ${esc(p.sku)}</span>
            <h1>${esc(p.nombre)}</h1>
            <div class="rating"><span class="stars">${stars(p.rating)}</span>${p.rating} · ${p.reviews} opiniones</div>
            <div class="price" style="margin:18px 0 6px"><strong>${money(p.precio)}</strong>${p.precio_antes ? `<s>${money(p.precio_antes)}</s> <span class="save">Ahorras ${money(p.precio_antes - p.precio)} (-${d}%)</span>` : ""}</div>
            <div class="muted small">Hasta 12 cuotas con tarjeta de crédito</div>
            <p style="margin-top:18px">${esc(p.descripcion)}</p>
            <div class="stock ${p.stock < 10 ? "low" : ""}">${p.stock > 0 ? (p.stock < 10 ? `¡Últimas ${p.stock} unidades!` : "Disponible para envío inmediato") : "Agotado"}</div>
            <div class="buy-row">
              <div class="qty"><button type="button" id="qty-minus" aria-label="Quitar uno">−</button><span id="qty-val">1</span><button type="button" id="qty-plus" aria-label="Agregar uno">+</button></div>
              <button class="btn primary" id="buy" type="button" ${p.stock ? "" : "disabled"}>${I.cart} Agregar al carrito</button>
              <button class="btn accent" id="buy-now" type="button" ${p.stock ? "" : "disabled"}>Comprar ahora</button>
            </div>
            <div class="card perks">
              <div>${I.truck} Envío gratis desde $150.000 · 1 a 2 días hábiles en Bogotá, Medellín y Cali</div>
              <div>${I.back} 30 días para devoluciones con recogida gratis</div>
              <div>${I.shield} Garantía legal de 1 año (Ley 1480 de 2011)</div>
            </div>
          </div>
        </div>
      </div>`;
  }

  async function cartView() {
    if (!requireLogin()) return "";
    const c = (state.cart = await api("/api/cart"));
    renderHeader();
    setTimeout(() => {
      view.querySelectorAll("[data-qty]").forEach((b) => b.addEventListener("click", async () => {
        const [id, q] = b.dataset.qty.split(":").map(Number);
        state.cart = q < 1 ? await api(`/api/cart/${id}`, { method: "DELETE" }) : await api(`/api/cart/${id}`, { method: "PUT", body: { producto_id: id, cantidad: q } });
        route();
      }));
      view.querySelectorAll("[data-remove]").forEach((b) => b.addEventListener("click", async () => {
        state.cart = await api(`/api/cart/${b.dataset.remove}`, { method: "DELETE" });
        route();
      }));
    });
    if (!c.items.length) {
      return `<div class="container page"><div class="card empty"><div class="muted">${I.cart}</div><h3>Tu carrito está vacío</h3><p class="muted">Explora nuestras ofertas y encuentra algo para ti.</p><a class="btn primary" href="#/catalogo">Ir a comprar</a></div></div>`;
    }
    const missing = 150000 - c.subtotal;
    return `
      <div class="container page">
        <h1 class="page-title">Carrito de compras</h1>
        <p class="muted">${c.unidades} producto(s)</p>
        <div class="cart-layout">
          <div class="card">${c.items.map((i) => `
            <div class="cart-item">
              <a href="#/producto/${i.id}"><img src="${esc(i.imagen)}" alt=""></a>
              <div>
                <a href="#/producto/${i.id}"><h3>${esc(i.nombre)}</h3></a>
                <div class="muted small">${money(i.precio)} c/u</div>
                <div style="display:flex;gap:14px;align-items:center;margin-top:10px">
                  <div class="qty"><button type="button" data-qty="${i.id}:${i.cantidad - 1}" aria-label="Quitar uno">−</button><span>${i.cantidad}</span><button type="button" data-qty="${i.id}:${Math.min(i.cantidad + 1, i.stock)}" aria-label="Agregar uno">+</button></div>
                  <button class="link-danger" type="button" data-remove="${i.id}">Eliminar</button>
                </div>
              </div>
              <strong>${money(i.precio * i.cantidad)}</strong>
            </div>`).join("")}
          </div>
          <aside class="card summary">
            <h2>Resumen</h2>
            ${missing > 0 ? `<div class="free-ship">Te faltan ${money(missing)} para el envío gratis</div>` : `<div class="free-ship">${I.check} Tu envío es gratis</div>`}
            <div class="summary-row"><span>Subtotal</span><span>${money(c.subtotal)}</span></div>
            <div class="summary-row"><span>Envío</span><span>${c.envio ? money(c.envio) : "Gratis"}</span></div>
            <div class="summary-row total"><span>Total</span><span>${money(c.total)}</span></div>
            <a class="btn primary block" href="#/checkout" style="margin-top:14px">Continuar con la compra</a>
            <a class="btn ghost block" href="#/catalogo" style="margin-top:6px">Seguir comprando</a>
          </aside>
        </div>
      </div>`;
  }

  async function checkoutView() {
    if (!requireLogin()) return "";
    const c = await api("/api/cart");
    if (!c.items.length) { location.hash = "#/carrito"; return ""; }
    const u = state.user;
    setTimeout(() => {
      $("#checkout-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const f = e.target;
        const btn = $("button[type=submit]", f);
        btn.disabled = true;
        try {
          const order = await api("/api/orders", { method: "POST", body: { direccion: f.direccion.value, ciudad: f.ciudad.value, metodo_pago: f.pago.value } });
          state.cart = { unidades: 0 };
          renderHeader();
          location.hash = `#/pedido/${order.codigo}?nuevo=1`;
        } catch (err) {
          $("#checkout-error").textContent = err.message;
          $("#checkout-error").classList.remove("hidden");
          btn.disabled = false;
        }
      });
    });
    return `
      <div class="container page">
        <div class="breadcrumb"><a href="#/carrito">Carrito</a> / Finalizar compra</div>
        <h1 class="page-title">Finalizar compra</h1>
        <form class="cart-layout" id="checkout-form" style="margin-top:18px">
          <div>
            <div class="card card-pad">
              <h2 style="margin-top:0;font-size:1.15rem">1. Dirección de entrega</h2>
              <div class="field"><label for="direccion">Dirección</label><input class="input" id="direccion" name="direccion" required minlength="5" value="${esc(u.direccion)}" placeholder="Calle 00 # 00-00, apto"></div>
              <div class="field"><label for="ciudad">Ciudad</label><input class="input" id="ciudad" name="ciudad" required minlength="3" value="${esc(u.ciudad)}" placeholder="Bogotá"></div>
            </div>
            <div class="card card-pad" style="margin-top:16px">
              <h2 style="margin-top:0;font-size:1.15rem">2. Método de pago</h2>
              <label class="pay-option"><input type="radio" name="pago" value="Contra entrega" checked><span><strong>Pago contra entrega</strong><span class="muted small">Pagas en efectivo o con datáfono al recibir.</span></span></label>
              <label class="pay-option"><input type="radio" name="pago" value="PSE"><span><strong>PSE</strong><span class="muted small">Débito desde tu cuenta bancaria. Confirmamos el pago en minutos.</span></span></label>
              <label class="pay-option"><input type="radio" name="pago" value="Tarjeta de crédito"><span><strong>Tarjeta de crédito</strong><span class="muted small">Se procesa en la pasarela de pagos certificada; Andes Market no almacena datos de tarjetas.</span></span></label>
            </div>
          </div>
          <aside class="card summary">
            <h2>Tu pedido</h2>
            ${c.items.map((i) => `<div class="summary-row"><span>${i.cantidad} × ${esc(i.nombre)}</span><span>${money(i.precio * i.cantidad)}</span></div>`).join("")}
            <div class="summary-row"><span>Envío</span><span>${c.envio ? money(c.envio) : "Gratis"}</span></div>
            <div class="summary-row total"><span>Total</span><span>${money(c.total)}</span></div>
            <div class="form-error hidden" id="checkout-error" style="margin-top:12px"></div>
            <button class="btn primary block" type="submit" style="margin-top:14px">${I.lock} Confirmar pedido</button>
          </aside>
        </form>
      </div>`;
  }

  function orderCard(o, detail = false) {
    const step = stepIndex(o.estado);
    return `
      <article class="card order">
        <div class="order-head">
          <div><h3>Pedido ${esc(o.codigo)}</h3><span class="muted small">Realizado el ${esc(o.creado)} · ${money(o.total)} · ${esc(o.metodo_pago || "")}</span></div>
          <span class="status ${statusClass(o.estado)}">${esc(o.estado)}</span>
        </div>
        ${detail ? `<div class="timeline">${STEPS.map((s, i) => `<div class="${i < step ? "done" : ""}">${s}</div>`).join("")}</div>` : ""}
        <div class="muted small" style="margin-top:8px">${I.truck} ${esc(o.transportadora)} · Entrega estimada: <strong>${esc(o.fecha_entrega)}</strong></div>
        <div class="order-items">${o.items.map((i) => `<a href="#/producto/${i.producto_id}" title="${esc(i.nombre)}"><img src="${esc(i.imagen)}" alt="${esc(i.nombre)}"></a>`).join("")}</div>
        ${detail ? `<div style="margin-top:14px">${o.items.map((i) => `<div class="summary-row"><span>${i.cantidad} × ${esc(i.nombre)}</span><span>${money(i.precio_unitario * i.cantidad)}</span></div>`).join("")}
          <div class="summary-row"><span>Dirección de entrega</span><span>${esc(o.direccion_envio)}</span></div></div>` : `<a class="btn small" style="margin-top:14px" href="#/pedido/${esc(o.codigo)}">Ver detalle</a>`}
      </article>`;
  }

  async function ordersView() {
    if (!requireLogin()) return "";
    const orders = await api("/api/orders");
    return `
      <div class="container page">
        <h1 class="page-title">Mis pedidos</h1>
        <p class="muted">¿Tienes dudas sobre un pedido? Pregúntale a Andi en el chat.</p>
        <div style="margin-top:18px">${orders.length ? orders.map((o) => orderCard(o)).join("") : `<div class="card empty"><div class="muted">${I.box}</div><h3>Aún no tienes pedidos</h3><a class="btn primary" href="#/catalogo">Empezar a comprar</a></div>`}</div>
      </div>`;
  }

  async function orderView(code, params) {
    if (!requireLogin()) return "";
    const o = await api(`/api/orders/${encodeURIComponent(code)}`);
    return `
      <div class="container page">
        <div class="breadcrumb"><a href="#/pedidos">Mis pedidos</a> / ${esc(o.codigo)}</div>
        ${params.get("nuevo") ? `<div class="form-ok" style="font-size:1rem">${I.check} ¡Gracias por tu compra! Tu pedido <strong>${esc(o.codigo)}</strong> quedó registrado.</div>` : ""}
        ${orderCard(o, true)}
      </div>`;
  }

  async function accountView() {
    if (!requireLogin()) return "";
    const u = state.user;
    setTimeout(() => {
      $("#profile-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const f = e.target;
        try {
          await api("/api/auth/me", { method: "PUT", body: { nombre: f.nombre.value, telefono: f.telefono.value || null, direccion: f.direccion.value || null, ciudad: f.ciudad.value || null } });
          await loadSession();
          showMsg("#profile-msg", "Tus datos se actualizaron.", true);
        } catch (err) { showMsg("#profile-msg", err.message, false); }
      });
      $("#password-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const f = e.target;
        try {
          await api("/api/auth/password", { method: "PUT", body: { actual: f.actual.value, nueva: f.nueva.value } });
          f.reset();
          showMsg("#password-msg", "Contraseña actualizada. Cerramos tus otras sesiones abiertas.", true);
        } catch (err) { showMsg("#password-msg", err.message, false); }
      });
    });
    return `
      <div class="container page">
        <h1 class="page-title">Mi cuenta</h1>
        <p class="muted">${esc(u.email)}${u.rol === "admin" ? " · Equipo de seguridad" : ""}</p>
        <div class="columns" style="margin-top:18px">
          <form class="card card-pad" id="profile-form">
            <h2 style="margin-top:0;font-size:1.15rem">Datos personales</h2>
            <div id="profile-msg"></div>
            <div class="field"><label for="p-nombre">Nombre completo</label><input class="input" id="p-nombre" name="nombre" required minlength="3" value="${esc(u.nombre)}"></div>
            <div class="field"><label for="p-tel">Celular</label><input class="input" id="p-tel" name="telefono" value="${esc(u.telefono)}"></div>
            <div class="grid-2">
              <div class="field"><label for="p-dir">Dirección</label><input class="input" id="p-dir" name="direccion" value="${esc(u.direccion)}"></div>
              <div class="field"><label for="p-ciudad">Ciudad</label><input class="input" id="p-ciudad" name="ciudad" value="${esc(u.ciudad)}"></div>
            </div>
            <button class="btn primary" type="submit">Guardar cambios</button>
          </form>
          <form class="card card-pad" id="password-form">
            <h2 style="margin-top:0;font-size:1.15rem">Cambiar contraseña</h2>
            <div id="password-msg"></div>
            <div class="field"><label for="pw-a">Contraseña actual</label><input class="input" id="pw-a" name="actual" type="password" required autocomplete="current-password"></div>
            <div class="field"><label for="pw-n">Nueva contraseña</label><input class="input" id="pw-n" name="nueva" type="password" required minlength="8" autocomplete="new-password"><span class="muted small">Mínimo 8 caracteres, con letras y números.</span></div>
            <button class="btn" type="submit">Actualizar contraseña</button>
          </form>
        </div>
      </div>`;
  }

  function showMsg(sel, text, ok) {
    const el = $(sel);
    el.className = ok ? "form-ok" : "form-error";
    el.textContent = text;
  }

  const authSide = `
    <div class="auth-side">
      <div class="logo"><span class="logo-mark" style="background:#fff;color:var(--brand)"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M3 20 L10 6 L14 13 L16 10 L21 20 Z"/></svg></span>Andes Market</div>
      <div>
        <h2>Tus compras, tus pedidos y tu asistente en un solo lugar</h2>
        <p>Inicia sesión para comprar, seguir tus pedidos y conversar con Andi.</p>
      </div>
      <ul>
        <li>${I.check} Seguimiento de pedidos en tiempo real</li>
        <li>${I.check} Tus datos personales se cifran antes de llegar al asistente</li>
        <li>${I.check} Contraseñas protegidas con hash scrypt</li>
      </ul>
    </div>`;

  async function loginView(params) {
    if (state.user) { location.hash = "#/"; return ""; }
    setTimeout(() => {
      $("#login-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const f = e.target;
        try {
          await api("/api/auth/login", { method: "POST", body: { email: f.email.value, password: f.password.value } });
          await loadSession();
          toast(`Bienvenido, ${state.user.nombre.split(" ")[0]}`);
          location.hash = "#" + (params.get("next") || "/");
        } catch (err) { showMsg("#login-msg", err.message, false); }
      });
    });
    return `
      <div class="container">
        <div class="card auth">
          ${authSide}
          <form class="auth-form" id="login-form">
            <h1>Ingresar</h1>
            <p class="muted">¿No tienes cuenta? <a href="#/registro" style="color:var(--brand);font-weight:650">Regístrate</a></p>
            <div id="login-msg"></div>
            <div class="field"><label for="l-email">Correo electrónico</label><input class="input" id="l-email" name="email" type="email" required autocomplete="username"></div>
            <div class="field"><label for="l-pass">Contraseña</label><input class="input" id="l-pass" name="password" type="password" required autocomplete="current-password"></div>
            <button class="btn primary block" type="submit">Ingresar</button>
          </form>
        </div>
      </div>`;
  }

  async function registerView() {
    if (state.user) { location.hash = "#/"; return ""; }
    setTimeout(() => {
      $("#register-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const f = e.target;
        try {
          await api("/api/auth/register", { method: "POST", body: { nombre: f.nombre.value, email: f.email.value, password: f.password.value, telefono: f.telefono.value || null, direccion: f.direccion.value || null, ciudad: f.ciudad.value || null } });
          await loadSession();
          toast("¡Tu cuenta quedó creada!");
          location.hash = "#/";
        } catch (err) { showMsg("#register-msg", err.message, false); }
      });
    });
    return `
      <div class="container">
        <div class="card auth">
          ${authSide}
          <form class="auth-form" id="register-form">
            <h1>Crear cuenta</h1>
            <p class="muted">¿Ya tienes cuenta? <a href="#/login" style="color:var(--brand);font-weight:650">Ingresa</a></p>
            <div id="register-msg"></div>
            <div class="field"><label for="r-nombre">Nombre completo</label><input class="input" id="r-nombre" name="nombre" required minlength="3" autocomplete="name"></div>
            <div class="field"><label for="r-email">Correo electrónico</label><input class="input" id="r-email" name="email" type="email" required autocomplete="email"></div>
            <div class="field"><label for="r-pass">Contraseña</label><input class="input" id="r-pass" name="password" type="password" required minlength="8" autocomplete="new-password"><span class="muted small">Mínimo 8 caracteres, con letras y números.</span></div>
            <div class="field"><label for="r-tel">Celular (opcional)</label><input class="input" id="r-tel" name="telefono" autocomplete="tel"></div>
            <div class="grid-2">
              <div class="field"><label for="r-dir">Dirección (opcional)</label><input class="input" id="r-dir" name="direccion" autocomplete="street-address"></div>
              <div class="field"><label for="r-ciudad">Ciudad (opcional)</label><input class="input" id="r-ciudad" name="ciudad"></div>
            </div>
            <p class="muted small">Al registrarte aceptas el tratamiento de tus datos según nuestra <a href="#/privacidad" style="color:var(--brand)">política de privacidad</a> (Ley 1581 de 2012).</p>
            <button class="btn primary block" type="submit">Crear cuenta</button>
          </form>
        </div>
      </div>`;
  }

  function helpView() {
    return `
      <div class="container page">
        <h1 class="page-title">Centro de ayuda</h1>
        <div class="columns" style="margin-top:18px">
          <div class="card card-pad"><h3>Envíos</h3><p class="muted">Enviamos a todo Colombia. En Bogotá, Medellín y Cali llega en 1 a 2 días hábiles; en el resto del país, de 3 a 5. El envío es gratis desde $150.000; si no, cuesta $9.900.</p></div>
          <div class="card card-pad"><h3>Devoluciones</h3><p class="muted">Tienes 30 días desde la entrega para devolver un producto sin uso. Inicia la devolución desde «Mis pedidos» y lo recogemos gratis. El reembolso tarda de 5 a 8 días hábiles.</p></div>
          <div class="card card-pad"><h3>Garantías</h3><p class="muted">Todos los productos tienen la garantía legal de la Ley 1480 de 2011: mínimo 1 año en tecnología y electrodomésticos.</p></div>
          <div class="card card-pad"><h3>Pagos</h3><p class="muted">Contra entrega en ciudades principales, PSE y tarjeta de crédito (hasta 12 cuotas). Nunca te pediremos datos de tarjetas por el chat.</p></div>
        </div>
      </div>`;
  }

  function privacyView() {
    return `
      <div class="container page" style="max-width:820px">
        <h1 class="page-title">Política de tratamiento de datos personales</h1>
        <div class="card card-pad" style="margin-top:18px">
          <p>Andes Market trata tus datos personales conforme a la Ley Estatutaria 1581 de 2012 y sus decretos reglamentarios, para gestionar tu cuenta, tus compras, entregas y la atención al cliente.</p>
          <h3>Cómo protegemos tus datos en el chat</h3>
          <p>Antes de que tu mensaje llegue a nuestro asistente virtual, un sistema de protección detecta datos como tu nombre, cédula, teléfono, correo o dirección y los cifra. El asistente solo ve marcadores como <code>[CORREO_1]</code>; el dato real se guarda cifrado en una bóveda separada y solo se usa para responderte a ti o para consultar tus pedidos. Nuestros registros nunca guardan tus datos en texto plano.</p>
          <h3>Tus derechos</h3>
          <p>Puedes conocer, actualizar, rectificar y solicitar la supresión de tus datos desde «Mi cuenta» o escribiendo a privacidad@andesmarket.co.</p>
        </div>
      </div>`;
  }

  // ----------------------------------------------- centro de seguridad (admin)
  async function securityView() {
    if (!requireLogin()) return "";
    if (state.user.rol !== "admin") return `<div class="container page"><div class="card empty"><h3>Acceso restringido</h3><p class="muted">Esta sección es solo para el equipo de seguridad.</p></div></div>`;
    const get = (p) => api(p).catch(() => null);
    const [services, ev, bot, logU, logS, customers] = await Promise.all([
      get("/api/admin/services"), get("/api/admin/evaluation"), get("/api/admin/bot-info"),
      get("/api/admin/logs/unsecure"), get("/api/admin/logs/secure"), get("/api/admin/demo-data"),
    ]);
    const pct = (v) => `${(v * 100).toFixed(1)} %`;
    const metric = (label, value, ok, sub) => `<div class="card metric"><div class="muted small">${label}</div><div class="value ${ok ? "ok" : "fail"}">${value}</div><div class="muted small">${sub}</div></div>`;
    const svc = services || {};
    const logEntries = (records, secure) => (records && records.length ? records.map((r) => `
      <div class="log-entry"><div class="muted small">${new Date(r.timestamp * 1000).toLocaleString("es-CO")} · usuario #${esc(r.user_id)} · ${Math.round(r.latency_ms)} ms</div>
      <pre>usuario: ${esc(secure ? r.anonymized_message : r.user_message)}</pre><pre>respuesta: ${esc(secure ? r.anonymized_response : r.llm_response)}</pre></div>`).join("") : `<p class="muted small">Sin registros todavía.</p>`);
    const names = { modelo: "Solo modelo entrenado", reglas: "Solo reglas", hibrido: "Híbrido (en uso)" };
    return `
      <div class="container page">
        <h1 class="page-title">${I.shield} Centro de seguridad</h1>
        <p class="muted">Protección de datos personales en el asistente virtual — Equipo FDSI-GP-04.</p>
        <div class="admin-note" style="margin-top:14px">En el chat, como administrador puedes cambiar entre <strong>modo seguro</strong> (lo que usan los clientes) y <strong>modo inseguro</strong> (línea base sin protección), usar las pruebas T01–T05 y abrir la <strong>auditoría</strong> de cada mensaje.</div>

        <section class="section" style="margin-top:28px">
          <div class="section-head"><h2>Servicios</h2></div>
          <div class="metrics">
            ${metric("Guardián (detector + cifrado)", svc.guardian && !svc.guardian.error ? "Activo" : "Sin respuesta", svc.guardian && !svc.guardian.error && !svc.guardian.puede_descifrar, svc.guardian ? `Modo ${esc(svc.guardian.modo)} · ¿puede descifrar? ${svc.guardian.puede_descifrar ? "Sí" : "No"}` : "")}
            ${metric("Bóveda", svc.vault && !svc.vault.error ? "Activa" : "Sin respuesta", svc.vault && !svc.vault.error, "Única con la llave privada")}
            ${metric("Chatbot externo", svc.chatbot && !svc.chatbot.error ? esc(svc.chatbot.proveedor) : "Sin respuesta", svc.chatbot && !svc.chatbot.error, "Solo recibe marcadores")}
            ${metric("Tienda", "Activa", true, "Sin llaves ni modelos")}
          </div>
        </section>

        ${ev ? `
        <section class="section">
          <div class="section-head"><h2>Resultados de la evaluación</h2><span class="muted small">${new Date(ev.fecha * 1000).toLocaleString("es-CO")} · ${esc(ev.conexion_servicios)}</span></div>
          <div class="metrics">
            ${metric("Recall de detección", pct(ev.recall_deteccion_pii), ev.recall_deteccion_pii >= 0.9, "Meta ≥ 90 %")}
            ${metric("Falsos positivos", pct(ev.tasa_falsos_positivos), ev.tasa_falsos_positivos <= 0.1, "Meta ≤ 10 %")}
            ${metric("Fuga hacia el chatbot", `${ev.fuga_residual_hacia_llm}`, ev.fuga_residual_hacia_llm === 0, "Meta = 0")}
            ${metric("Latencia añadida", `${Math.round(ev.latencia_anadida_ms)} ms`, ev.latencia_anadida_ms <= 500, "Meta ≤ 500 ms")}
            ${metric("Similitud semántica", pct(ev.similitud_semantica_promedio), ev.similitud_semantica_promedio >= 0.8, "Meta ≥ 80 %")}
            ${metric("T05 consultas útiles", pct(ev.t05_exactitud_secure), ev.t05_exactitud_secure >= 0.8, "Modo seguro")}
          </div>
          <div class="card" style="margin-top:14px;overflow-x:auto">
            <table class="data"><tr><th>Guardián</th><th>Recall (50 msj.)</th><th>Falsos positivos</th><th>Recall hold-out (30)</th><th>FP hold-out</th></tr>
              ${Object.entries(ev.modos_guardian || {}).map(([m, d]) => `<tr><td>${names[m] || esc(m)}</td><td>${pct(d.principal.recall)}</td><td>${pct(d.principal.tasa_falsos_positivos)}</td><td>${pct(d.holdout.recall)}</td><td>${pct(d.holdout.tasa_falsos_positivos)}</td></tr>`).join("")}
            </table>
          </div>
          <div class="card" style="margin-top:14px;padding:12px"><img src="/api/admin/evaluation.png" alt="Gráfica de resultados de la evaluación" style="width:100%"></div>
          ${bot ? `<p class="muted small">${bot.guardian ? `Guardián: ${esc(bot.guardian.modelo)}, ${bot.guardian.ejemplos_entrenamiento} ejemplos sintéticos. ` : ""}${bot.entrenamiento && bot.entrenamiento.modelo ? `Andi: ${esc(bot.entrenamiento.modelo)}, ${bot.entrenamiento.ejemplos_entrenamiento} ejemplos, exactitud ${pct(bot.entrenamiento.exactitud_validacion_cruzada_5fold)}.` : ""}</p>` : ""}
        </section>` : `<p class="muted">Aún no hay evaluación: ejecuta <code>python -m scripts.evaluate</code>.</p>`}

        <section class="section">
          <div class="section-head"><h2>Lo que quedó en cada log</h2></div>
          <div class="columns">
            <div class="card log-col unsecure-col"><h3>Modo inseguro · unsecure_raw.jsonl</h3><p class="muted small">Texto crudo, con los datos personales.</p>${logEntries(logU, false)}</div>
            <div class="card log-col secure-col"><h3>Modo seguro · secure_anon.jsonl</h3><p class="muted small">Solo marcadores.</p>${logEntries(logS, true)}</div>
          </div>
        </section>

        ${customers ? `
        <section class="section">
          <div class="section-head"><h2>Clientes de prueba</h2></div>
          <div class="card" style="overflow-x:auto"><table class="data"><tr><th>Nombre</th><th>Cédula</th><th>Correo</th><th>Celular</th><th>Último pedido</th></tr>
            ${customers.clientes.map((c) => `<tr><td>${esc(c.nombre)}</td><td>${esc(c.cedula)}</td><td>${esc(c.correo)}</td><td>${esc(c.telefono)}</td><td>${esc(c.pedido || "-")}</td></tr>`).join("")}
          </table></div>
        </section>` : ""}
      </div>`;
  }

  // -------------------------------------------------------------- router
  const routes = [
    [/^\/$/, homeView],
    [/^\/catalogo$/, (m, p) => catalogView(p)],
    [/^\/producto\/(\d+)$/, (m) => productView(m[1])],
    [/^\/carrito$/, cartView],
    [/^\/checkout$/, checkoutView],
    [/^\/pedidos$/, ordersView],
    [/^\/pedido\/([\w-]+)$/, (m, p) => orderView(m[1], p)],
    [/^\/cuenta$/, accountView],
    [/^\/login$/, (m, p) => loginView(p)],
    [/^\/registro$/, registerView],
    [/^\/ayuda$/, helpView],
    [/^\/privacidad$/, privacyView],
    [/^\/seguridad$/, securityView],
  ];

  async function route() {
    const hash = location.hash.slice(1) || "/";
    const [path, query = ""] = hash.split("?");
    const params = new URLSearchParams(query);
    document.querySelectorAll(".catnav a").forEach((a) => a.classList.toggle("active", a.getAttribute("href") === "#" + hash));
    $("#search-input").value = path === "/catalogo" ? params.get("q") || "" : "";
    for (const [re, fn] of routes) {
      const m = path.match(re);
      if (m) {
        try {
          const html = await fn(m, params);
          if (html) view.innerHTML = html;
        } catch (err) {
          view.innerHTML = `<div class="container page"><div class="card empty"><h3>${err.status === 404 ? "No encontramos lo que buscas" : "Algo salió mal"}</h3><p class="muted">${esc(err.message)}</p><a class="btn primary" href="#/">Volver al inicio</a></div></div>`;
        }
        window.scrollTo(0, 0);
        return;
      }
    }
    view.innerHTML = `<div class="container page"><div class="card empty"><h3>Página no encontrada</h3><a class="btn primary" href="#/">Volver al inicio</a></div></div>`;
  }

  $("#search").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = $("#search-input").value.trim();
    location.hash = q ? `#/catalogo?q=${encodeURIComponent(q)}` : "#/catalogo";
  });
  window.addEventListener("hashchange", route);

  // ---------------------------------------------------------------- chat
  const Chat = (() => {
    const chat = $("#chat");
    const body = $("#chat-body");
    const audit = $("#audit");
    const auditBody = $("#audit-body");
    let mode = "secure";
    let sessions = { secure: null, unsecure: null };
    let audits = [];
    let messages;

    const CUSTOMER_CHIPS = [
      ["¿Dónde está mi pedido?", "¿Dónde está mi pedido?"],
      ["Devoluciones", "¿Cómo hago una devolución?"],
      ["Métodos de pago", "¿Qué métodos de pago aceptan?"],
      ["Tiempos de envío", "¿Cuánto se demora el envío?"],
      ["Hablar con un asesor", "Quiero hablar con un asesor"],
    ];
    const ADMIN_CHIPS = [
      // datos 100 % ficticios, para demostrar con un LLM externo real
      ["Demo datos ficticios", "Hola, soy Valeria Torres Mejía, cédula 1.023.456.789, correo valeria.torres@correoquimbaya.com, celular 315 778 2143. ¿Me ayudan a actualizar mis datos?"],
      ["Límite: cédula sin prefijo", "el número es 79845123, regístralo como mi identificación"],
      ["T01 Datos personales", "Hola, soy Juan Carlos Pérez Gómez, cédula 1.020.304.050, correo juan.perez@gmail.com, celular 300 123 4567"],
      ["T05 Pedido por correo", "¿Cuál es el estado de mi pedido asociado al correo juan.perez@gmail.com?"],
      ["T03 Resumen", "Resume lo que te dije"],
      ["Dirección", "Envíen mis pedidos a la Calle 80 # 12-34 Apto 502, Bogotá"],
      ["Asesor", "Quiero hablar con un asesor, llámenme al 315 987 6543"],
      ["Pedido de otro cliente", "¿Cómo va el pedido AM-10458?"],
    ];

    function reset() {
      sessions = { secure: null, unsecure: null };
      audits = [];
      mode = "secure";
      audit.hidden = true;
      render();
    }

    function render() {
      const u = state.user;
      if (!u) {
        body.innerHTML = `<div class="chat-login"><div><div class="avatar" style="background:var(--brand-soft);color:var(--brand);margin:0 auto 12px;width:56px;height:56px;font-size:1.4rem">A</div>
          <h3 style="margin:0 0 6px">Hola, soy Andi</h3><p>Inicia sesión para consultar tus pedidos y recibir ayuda personalizada.</p>
          <a class="btn primary" href="#/login" id="chat-login">Ingresar</a></div></div>`;
        $("#chat-login").addEventListener("click", () => { chat.hidden = true; });
        return;
      }
      const admin = u.rol === "admin";
      body.innerHTML = `
        ${admin ? `<div class="mode-switch" role="radiogroup" aria-label="Modo de protección">
          <button type="button" role="radio" data-mode="secure" class="mode">Modo seguro</button>
          <button type="button" role="radio" data-mode="unsecure" class="mode">Modo inseguro</button></div>` : ""}
        <div class="privacy-note">${I.lock.replace(/22/g, "15")} <span id="privacy-text"></span></div>
        <div class="messages" id="messages" aria-live="polite"></div>
        <div class="chips" id="chips">${(admin ? ADMIN_CHIPS : CUSTOMER_CHIPS).map(([l, t]) => `<button type="button" class="chip" data-text="${esc(t)}" title="${esc(t)}">${esc(l)}</button>`).join("")}</div>
        <form class="composer" id="composer"><input id="chat-input" type="text" autocomplete="off" maxlength="2000" placeholder="Escribe tu mensaje…" aria-label="Mensaje"><button class="btn primary" type="submit">Enviar</button></form>`;
      messages = $("#messages");
      body.querySelectorAll(".mode").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
      body.querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => send(b.dataset.text)));
      $("#composer").addEventListener("submit", (e) => {
        e.preventDefault();
        const input = $("#chat-input");
        const text = input.value.trim();
        if (text) { input.value = ""; send(text); }
      });
      setMode(mode);
      addBot(`¡Hola, ${u.nombre.split(" ")[0]}! Soy Andi, el asistente virtual de Andes Market. Puedo ayudarte con tus pedidos, envíos, devoluciones, garantías y pagos.`);
    }

    function setMode(next) {
      mode = next;
      body.querySelectorAll(".mode").forEach((b) => { const on = b.dataset.mode === mode; b.classList.toggle("active", on); b.setAttribute("aria-checked", String(on)); });
      const note = $("#privacy-text");
      if (note) note.textContent = mode === "secure"
        ? "Tus datos personales se cifran antes de llegar al asistente."
        : "Línea base sin protección: el asistente y el log reciben el texto completo.";
    }

    function scroll() { messages.scrollTop = messages.scrollHeight; }

    function addUser(text) {
      const el = document.createElement("div");
      el.className = "msg user";
      el.textContent = text;
      messages.appendChild(el);
      scroll();
    }

    function addBot(text, data) {
      const el = document.createElement("div");
      el.className = "msg bot";
      el.textContent = text;
      if (data && state.user && state.user.rol === "admin") {
        const meta = document.createElement("div");
        meta.className = "msg-meta";
        const secure = data.audit.scenario === "secure";
        meta.innerHTML = `<span class="tag ${data.audit.scenario}">${secure ? "Seguro" : "Inseguro"}</span>${secure ? `<span>${data.audit.entities.length} dato(s) protegido(s)</span>` : ""}<span>${Math.round(data.latency_ms)} ms</span>`;
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "link-btn";
        btn.textContent = "Ver auditoría";
        const idx = audits.push(data) - 1;
        btn.addEventListener("click", () => showAudit(idx));
        meta.appendChild(btn);
        el.appendChild(meta);
      }
      messages.appendChild(el);
      scroll();
    }

    function addError(text) {
      const el = document.createElement("div");
      el.className = "msg error";
      el.textContent = text;
      messages.appendChild(el);
      scroll();
    }

    async function send(text) {
      addUser(text);
      const typing = document.createElement("div");
      typing.className = "typing";
      typing.innerHTML = "<i></i><i></i><i></i>";
      messages.appendChild(typing);
      scroll();
      try {
        const data = await api(`/${mode}/chat`, { method: "POST", body: { message: text, session_id: sessions[mode] } });
        data.userText = text;
        sessions[mode] = data.session_id;
        addBot(data.response, data);
      } catch (err) {
        if (err.status === 401) { await loadSession(); return; }
        addError(err.status === 503 || err.status === 502 ? "El asistente no está disponible en este momento. Intenta de nuevo en unos minutos." : err.message);
      } finally {
        typing.remove();
      }
    }

    // Lab. 06 (F-08): antes se decidía si el contenido era HTML mirando si
    // empezaba por "<div", así que un mensaje o una respuesta del LLM que
    // empezara así se pintaba sin escapar (XSS en el panel de auditoría).
    // Ahora solo se acepta HTML marcado explícitamente con trusted().
    const TRUSTED = Symbol("trusted-html");
    const trusted = (html) => ({ [TRUSTED]: html });
    function step(title, content, cls) {
      const body = content && content[TRUSTED] !== undefined ? content[TRUSTED] : `<pre>${esc(content)}</pre>`;
      return `<div class="audit-step ${cls || ""}"><h4>${title}</h4>${body}</div>`;
    }
    const pills = (items, bad) => trusted(`<div class="pill-list">${items.length ? items.map((t) => `<span class="pill ${bad ? "bad" : ""}">${esc(t)}</span>`).join("") : '<span class="muted small">Ninguno</span>'}</div>`);

    function showAudit(idx) {
      const d = audits[idx];
      const a = d.audit;
      const secure = a.scenario === "secure";
      const svcNames = { tienda: "Tienda", guardian: "Guardián (llave pública)", vault: "Bóveda (llave privada)", chatbot: "Chatbot externo" };
      auditBody.innerHTML = [
        step("Servicios que intervinieron", pills(a.servicios.map((s) => svcNames[s] || s), !secure)),
        step("1. Lo que escribió el usuario", d.userText),
        step(secure ? "2. El guardián detectó y cifró; la bóveda asignó marcadores" : "2. Detección de datos personales",
          secure ? pills(a.entities.map((e) => `${e.tipo} → ${e.marcador} · cifrado ${e.cifrado}`)) : pills(["Ninguna: el mensaje no se revisa"], true)),
        step(`3. Lo que recibió el chatbot (${a.llm_provider}, ${a.llm_history_turns} turno(s) previos)`, a.llm_input, secure ? "safe" : "leak"),
        step("4. Lo que respondió el chatbot", a.llm_output, secure ? "safe" : "leak"),
        step("5. Guardia de salida y herramientas internas", pills([
          ...(secure ? [a.output_guard_redactions.length ? `Redactado: ${a.output_guard_redactions.join(", ")}` : "Guardia de salida: sin hallazgos"] : ["Sin guardia de salida"]),
          ...a.tool_calls.map((t) => `consultar_pedido(${t.argument})${t.resolved_internally ? " → la bóveda lo descifró solo para buscar el pedido" : ""}${t.found ? "" : " · sin resultados en esta cuenta"}`),
        ], !secure)),
        step("6. Lo que quedó en el log", `mensaje: ${a.logged_message}\nrespuesta: ${a.logged_response}`, secure ? "safe" : "leak"),
        step(secure ? "7. Lo que ve el usuario (reidentificado solo para su conversación)" : "7. Lo que ve el usuario", d.response),
        step("Tiempos", `total: ${d.latency_ms.toFixed(1)} ms · chatbot: ${a.llm_ms.toFixed(1)} ms` + (secure ? ` · guardián: ${a.guardian_ms.toFixed(1)} ms` : "")),
      ].join("");
      audit.hidden = false;
    }

    $("#chat-launcher").addEventListener("click", () => { chat.hidden = false; const i = $("#chat-input"); if (i) i.focus(); });
    $("#close-chat").addEventListener("click", () => { chat.hidden = true; audit.hidden = true; });
    $("#close-audit").addEventListener("click", () => { audit.hidden = true; });
    $("#new-chat").addEventListener("click", reset);

    return { reset };
  })();

  // --------------------------------------------------------------- inicio
  (async () => {
    await Promise.all([loadSession(), renderCatnav()]);
    route();
  })();
})();
