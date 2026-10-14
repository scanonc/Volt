(() => {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const COP = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });
  const money = (v) => COP.format(Number(v));
  const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const ICONS = { camiseta: '👕', camisa: '👔', pantalon: '👖', vestido: '👗', chaqueta: '🧥', buzo: '🧶', deport: '🏃', accesorio: '🧢', zapato: '👟' };
  const icon = (cat) => { const n = cat.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''); const k = Object.keys(ICONS).find((k) => n.includes(k)); return ICONS[k] || '🛍️'; };
  const bg = (id) => { const hue = (id * 47) % 360; return `linear-gradient(135deg,hsl(${hue} 60% 88%),hsl(${(hue + 40) % 360} 65% 78%))`; };

  const state = { products: [], categories: [], category: 'all', query: '', sort: 'default', onlyStock: false, cart: null, addresses: [], view: 'cart', lastOrder: null };

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      credentials: 'same-origin',
      ...opts,
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, ...(opts.headers || {}) },
    });
    let data = null;
    if (res.status !== 204) { try { data = await res.json(); } catch (_) { /* sin cuerpo */ } }
    return { ok: res.ok, status: res.status, data };
  }
  const errMsg = (r) => {
    if (r.status === 401 || r.status === 403) return 'Debes iniciar sesión para continuar.';
    const d = r.data || {};
    if (d.error) return d.error;
    if (d.errors) return Object.entries(d.errors).map(([k, v]) => `${k}: ${[].concat(v).join(' ')}`).join(' · ');
    return 'Ocurrió un error inesperado.';
  };
  function toast(msg, error = false) {
    const el = document.createElement('div');
    el.className = 'toast' + (error ? ' error' : '');
    el.textContent = msg;
    $('#toasts').appendChild(el);
    setTimeout(() => el.remove(), 3200);
  }

  /* ---------- Catálogo ---------- */
  function renderChips() {
    const items = [{ id: 'all', name: 'Todo' }, ...state.categories];
    $('#chips').innerHTML = items.map((c) => `<button class="chip ${String(c.id) === String(state.category) ? 'active' : ''}" data-cat="${c.id}">${esc(c.name)}</button>`).join('');
  }
  function filtered() {
    let list = state.products.filter((p) =>
      (state.category === 'all' || String(p.category.id) === String(state.category)) &&
      (!state.onlyStock || p.stock > 0) &&
      (!state.query || (p.name + ' ' + p.description + ' ' + p.category.name).toLowerCase().includes(state.query)));
    const by = { 'price-asc': (a, b) => a.price - b.price, 'price-desc': (a, b) => b.price - a.price, name: (a, b) => a.name.localeCompare(b.name) }[state.sort];
    return by ? [...list].sort(by) : list;
  }
  function badge(p) {
    if (p.stock === 0) return '<span class="badge out">AGOTADO</span>';
    if (p.stock <= 5) return `<span class="badge low">QUEDAN ${p.stock}</span>`;
    return '';
  }
  const cleanName = (n) => n.replace(/\s*\[DEMO\]\s*/g, '').trim();
  function renderGrid() {
    const list = filtered();
    $('#empty').hidden = list.length > 0;
    $('#grid').innerHTML = list.map((p) => `
      <article class="card" data-id="${p.id}">
        <div class="thumb" style="background:${bg(p.id)}">${badge(p)}${icon(p.category.name)}</div>
        <div class="card-body">
          <span class="card-cat">${esc(p.category.name)}</span>
          <h3>${esc(cleanName(p.name))}</h3>
          <p class="card-desc">${esc(p.description)}</p>
          <div class="card-foot"><span class="price">${money(p.price)}</span>
            <button class="add" data-add="${p.id}" ${p.stock === 0 ? 'disabled' : ''} aria-label="Agregar al carrito">+</button></div>
        </div>
      </article>`).join('');
  }
  async function loadCatalog() {
    $('#grid').innerHTML = '<div class="skeleton"></div>'.repeat(4);
    const [c, p] = await Promise.all([api('/api/categories/'), api('/api/products/')]);
    if (!c.ok || !p.ok) { $('#grid').innerHTML = ''; toast('No se pudo cargar el catálogo.', true); return; }
    state.categories = c.data; state.products = p.data.map((x) => ({ ...x, price: Number(x.price) }));
    renderChips(); renderGrid();
  }

  /* ---------- Modal de producto ---------- */
  let modalQty = 1;
  function openModal(id) {
    const p = state.products.find((x) => x.id === id); if (!p) return;
    modalQty = 1;
    const m = $('#product-modal');
    m.innerHTML = `
      <button class="icon-btn modal-close" id="modal-close" aria-label="Cerrar">✕</button>
      <div class="thumb" style="background:${bg(p.id)}">${badge(p)}${icon(p.category.name)}</div>
      <div class="modal-info">
        <span class="card-cat">${esc(p.category.name)}</span>
        <h2>${esc(cleanName(p.name))}</h2>
        <p class="muted">${esc(p.description) || 'Sin descripción.'}</p>
        <span class="price" style="font-size:26px">${money(p.price)}</span>
        <small class="muted">${p.stock > 0 ? p.stock + ' unidades disponibles' : 'Sin stock por ahora'}</small>
        <div class="qty"><button data-q="-1" aria-label="Menos">−</button><span id="mq">1</span><button data-q="1" aria-label="Más">+</button></div>
        <button class="btn btn-primary" id="modal-add" ${p.stock === 0 ? 'disabled' : ''}>Agregar al carrito</button>
      </div>`;
    m.hidden = false; $('#modal-overlay').hidden = false;
    m.onclick = async (e) => {
      const q = e.target.closest('[data-q]');
      if (q) { modalQty = Math.min(Math.max(1, modalQty + Number(q.dataset.q)), p.stock || 1); $('#mq').textContent = modalQty; }
      if (e.target.closest('#modal-close')) closeModal();
      if (e.target.closest('#modal-add')) { if (await addToCart(p.id, modalQty)) closeModal(); }
    };
  }
  function closeModal() { $('#product-modal').hidden = true; $('#modal-overlay').hidden = true; }

  /* ---------- Carrito ---------- */
  function requireLogin() {
    if (window.VOLT.authenticated) return true;
    toast('Inicia sesión para usar el carrito.', true);
    setTimeout(() => { location.href = window.VOLT.loginUrl + '?next=/'; }, 900);
    return false;
  }
  async function loadCart() {
    if (!window.VOLT.authenticated) return;
    const r = await api('/api/cart/');
    if (r.ok) { state.cart = r.data; updateCount(); }
  }
  function updateCount() {
    const n = (state.cart?.items || []).reduce((s, i) => s + i.quantity, 0);
    $('#cart-count').textContent = n;
  }
  async function addToCart(productId, quantity = 1) {
    if (!requireLogin()) return false;
    const r = await api('/api/cart/items/', { method: 'POST', body: JSON.stringify({ product_id: productId, quantity }) });
    if (!r.ok) { toast(errMsg(r), true); return false; }
    state.cart = r.data; updateCount(); toast('Agregado al carrito ✓');
    if (!$('#drawer').hidden) renderDrawer();
    return true;
  }
  async function removeItem(id) {
    const r = await api(`/api/cart/items/${id}/`, { method: 'DELETE' });
    if (!r.ok) return toast(errMsg(r), true);
    await loadCart(); renderDrawer();
  }
  async function loadAddresses() {
    const r = await api('/api/addresses/');
    state.addresses = r.ok ? r.data : [];
  }
  async function openCart() {
    if (!requireLogin()) return;
    const d = $('#drawer'); d.hidden = false; requestAnimationFrame(() => d.classList.add('open'));
    state.view = 'cart';
    await Promise.all([loadCart(), loadAddresses()]);
    renderDrawer();
  }
  function closeCart() { const d = $('#drawer'); d.classList.remove('open'); setTimeout(() => { d.hidden = true; }, 280); }

  function renderDrawer() {
    const body = $('#drawer-body'), foot = $('#drawer-foot');
    if (state.view === 'success') {
      const o = state.lastOrder;
      body.innerHTML = `<div class="success"><div class="big">🎉</div><h3>¡Pedido #${o.id} confirmado!</h3>
        <p class="muted">Total pagado: <b>${money(o.total)}</b>.<br>Te enviamos la confirmación de tu compra.</p></div>`;
      foot.innerHTML = '<button class="btn btn-primary btn-block" id="keep-shopping">Seguir comprando</button>';
      return;
    }
    if (state.view === 'address') {
      body.innerHTML = `<h3 style="margin-top:0">Nueva dirección</h3>
        <form class="addr-form" id="addr-form">
          <input class="full" name="street" placeholder="Calle / carrera y número" required>
          <input name="city" placeholder="Ciudad" required><input name="state" placeholder="Departamento" required>
          <input name="zip_code" placeholder="Código postal" required><input name="country" placeholder="País" value="Colombia" required>
          <label class="check full" style="grid-column:1/-1"><input type="checkbox" name="is_default"> Usar como principal</label>
        </form>`;
      foot.innerHTML = '<button class="btn btn-primary btn-block" id="save-addr">Guardar dirección</button><button class="btn btn-block" id="back-cart">Volver al carrito</button>';
      return;
    }
    const items = state.cart?.items || [];
    if (!items.length) {
      body.innerHTML = '<div class="empty-cart"><div class="big">🛒</div><p>Tu carrito está vacío.</p></div>';
      foot.innerHTML = '<button class="btn btn-block" id="keep-shopping">Explorar catálogo</button>';
      return;
    }
    body.innerHTML = items.map((i) => `
      <div class="line">
        <div class="mini" style="background:${bg(i.product.id)}">${icon(i.product.category.name)}</div>
        <div class="line-info"><b>${esc(cleanName(i.product.name))}</b><small>${i.quantity} × ${money(i.product.price)}</small></div>
        <div style="text-align:right"><b>${money(i.subtotal)}</b><br><button class="remove" data-remove="${i.id}">Quitar</button></div>
      </div>`).join('');
    const def = state.addresses.find((a) => a.is_default) || state.addresses[0];
    const opts = state.addresses.map((a) => `<option value="${a.id}" ${def && a.id === def.id ? 'selected' : ''}>${esc(a.street)}, ${esc(a.city)}</option>`).join('');
    foot.innerHTML = `
      <div class="total-row"><span>Total</span><span>${money(state.cart.total)}</span></div>
      <label>DIRECCIÓN DE ENVÍO</label>
      ${state.addresses.length ? `<select id="addr-select">${opts}</select>` : '<small class="muted">Aún no tienes direcciones guardadas.</small>'}
      <button class="btn" id="new-addr">+ Agregar dirección</button>
      <button class="btn btn-primary btn-block" id="checkout" ${state.addresses.length ? '' : 'disabled'}>Finalizar compra</button>`;
  }
  async function saveAddress() {
    const f = $('#addr-form');
    if (!f.reportValidity()) return;
    const fd = new FormData(f);
    const body = Object.fromEntries(fd.entries()); body.is_default = fd.get('is_default') === 'on';
    const r = await api('/api/addresses/', { method: 'POST', body: JSON.stringify(body) });
    if (!r.ok) return toast(errMsg(r), true);
    toast('Dirección guardada ✓'); await loadAddresses(); state.view = 'cart'; renderDrawer();
  }
  async function checkout() {
    const btn = $('#checkout'); btn.disabled = true; btn.textContent = 'Procesando…';
    const sel = $('#addr-select');
    const r = await api('/api/orders/', { method: 'POST', body: JSON.stringify({ shipping_address_id: sel ? Number(sel.value) : null }) });
    if (!r.ok) { toast(errMsg(r), true); btn.disabled = false; btn.textContent = 'Finalizar compra'; return; }
    state.lastOrder = r.data.order; state.view = 'success';
    await loadCart(); renderDrawer();
    loadCatalog(); // refresca el stock descontado
  }

  /* ---------- Eventos ---------- */
  document.addEventListener('click', (e) => {
    const t = e.target;
    const chip = t.closest('.chip'); if (chip) { state.category = chip.dataset.cat; renderChips(); renderGrid(); return; }
    const add = t.closest('[data-add]'); if (add) { e.stopPropagation(); addToCart(Number(add.dataset.add)); return; }
    const card = t.closest('.card'); if (card) { openModal(Number(card.dataset.id)); return; }
    if (t.closest('#open-cart')) return openCart();
    if (t.closest('#close-cart')) return closeCart();
    if (t === $('#modal-overlay')) return closeModal();
    const rm = t.closest('[data-remove]'); if (rm) return removeItem(rm.dataset.remove);
    if (t.closest('#new-addr')) { state.view = 'address'; return renderDrawer(); }
    if (t.closest('#back-cart')) { state.view = 'cart'; return renderDrawer(); }
    if (t.closest('#save-addr')) return saveAddress();
    if (t.closest('#checkout')) return checkout();
    if (t.closest('#keep-shopping')) { closeCart(); location.hash = '#catalogo'; }
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { closeModal(); if (!$('#drawer').hidden) closeCart(); } });
  $('#search').addEventListener('input', (e) => { state.query = e.target.value.trim().toLowerCase(); renderGrid(); });
  $('#sort').addEventListener('change', (e) => { state.sort = e.target.value; renderGrid(); });
  $('#only-stock').addEventListener('change', (e) => { state.onlyStock = e.target.checked; renderGrid(); });

  loadCatalog();
  loadCart();
})();
