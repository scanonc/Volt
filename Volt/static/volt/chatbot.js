(function () {
  'use strict';
  const root = document.getElementById('vc-root');
  if (!root) return;

  const ENDPOINT = root.dataset.endpoint || '/api/chatbot/message/';
  const language = document.documentElement.lang;
  const K_CONV = 'volt_chat_conversation_id_' + language;
  const K_HIST = 'volt_chat_history_' + language;
  const K_OPEN = 'volt_chat_open';
  const TIMEOUT_MS = 35000;
  const MAX_LEN = 1000;
  const MAX_TA_HEIGHT = 132;
  const MAX_HISTORY = 40;
  const GREETING = gettext("¡Hola! ⚡ Soy el asesor virtual de Volt. Cuéntame qué buscas: prenda, color, talla, estilo o presupuesto.");
  const SUGGESTIONS = [
    gettext("Camisetas casuales"),
    gettext("Algo elegante para una cita"),
    gettext("Jeans para hombre"),
    gettext("Ropa deportiva"),
    gettext("Un regalo para ella"),
  ];

  const toggle = document.getElementById('vc-toggle');
  const closeBtn = document.getElementById('vc-close');
  const resetBtn = document.getElementById('vc-reset');
  const panel = document.getElementById('vc-panel');
  const list = document.getElementById('vc-messages');
  const suggest = document.getElementById('vc-suggest');
  const form = document.getElementById('vc-form');
  const input = document.getElementById('vc-input');
  const sendBtn = document.getElementById('vc-send');
  const counter = document.getElementById('vc-count');
  let busy = false;
  let history = [];

  /* ---------- Almacenamiento (sessionStorage, tolerante a fallos) ---------- */
  const ss = {
    get(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { sessionStorage.setItem(k, v); } catch (e) { /* ignorar */ } },
    del(k) { try { sessionStorage.removeItem(k); } catch (e) { /* ignorar */ } },
  };

  function saveHistory() {
    if (history.length > MAX_HISTORY) history = history.slice(-MAX_HISTORY);
    ss.set(K_HIST, JSON.stringify(history));
  }

  function loadHistory() {
    try {
      const raw = ss.get(K_HIST);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) { return []; }
  }

  /* ---------- Utilidades ---------- */
  const cleanName = (n) => String(n || '').replace(/\s*\[DEMO\]\s*/g, '').trim();
  const cleanText = (t) => String(t || '').replace(/\*/g, '');

  function money(v) {
    const n = Number(v);
    if (isNaN(n)) return '';
    return '$' + n.toLocaleString(document.documentElement.lang, { maximumFractionDigits: 0 }) + ' COP';
  }

  function scrollBottom() { list.scrollTop = list.scrollHeight; }

  // Tras una respuesta larga, deja visible su inicio en vez de saltar al final.
  function scrollToReplyStart(el) {
    if (!el) return scrollBottom();
    const top = el.offsetTop - 8;
    list.scrollTop = Math.min(list.scrollHeight, Math.max(0, top));
  }

  /* ---------- Render de mensajes ---------- */
  function createMsg(text, kind) {
    const d = document.createElement('div');
    d.className = 'vc-msg ' + kind;
    d.textContent = kind === 'bot' ? cleanText(text) : text;
    return d;
  }

  function addMsg(text, kind, persist) {
    const d = createMsg(text, kind);
    list.appendChild(d);
    if (persist !== false && kind !== 'error') {
      history.push({ t: 'msg', kind: kind, text: text });
      saveHistory();
    }
    return d;
  }

  function addError(text, retryText) {
    const d = createMsg(text, 'error');
    if (retryText) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'vc-retry';
      b.textContent = gettext("Reintentar");
      b.addEventListener('click', () => {
        if (busy) return;
        d.remove();
        send(retryText, true);
      });
      d.appendChild(b);
    }
    list.appendChild(d);
    return d;
  }

  function setTyping(on) {
    const existing = document.getElementById('vc-typing');
    if (on && !existing) {
      const t = document.createElement('div');
      t.id = 'vc-typing';
      t.className = 'vc-msg bot vc-typing';
      t.setAttribute('role', 'status');
      t.setAttribute('aria-label', gettext("El asesor está escribiendo"));
      t.innerHTML = '<i></i><i></i><i></i>';
      list.appendChild(t);
      scrollBottom();
    } else if (!on && existing) {
      existing.remove();
    }
  }

  // Abre el producto en el catálogo real (modal) si la página lo muestra; si no, va al catálogo.
  function openProduct(id) {
    const card = document.querySelector('.card[data-id="' + id + '"]');
    if (window.innerWidth <= 480) setOpen(false);
    if (card) { card.click(); return; }
    window.location.href = '/#catalogo';
  }

  function buildProducts(products) {
    const wrap = document.createElement('div');
    wrap.className = 'vc-products';
    products.forEach((p) => {
      const stock = Number(p.stock);
      const soldOut = !isNaN(stock) && stock <= 0;
      const low = !isNaN(stock) && stock > 0 && stock <= 5;

      const row = document.createElement('div');
      row.className = 'vc-prod' + (soldOut ? ' soldout' : '');

      const thumb = document.createElement('div');
      thumb.className = 'vc-thumb';
      if (p.image) {
        const img = document.createElement('img');
        img.src = p.image;
        img.alt = cleanName(p.name);
        img.loading = 'lazy';
        thumb.appendChild(img);
      } else {
        thumb.textContent = cleanName(p.name).charAt(0).toUpperCase();
      }

      const info = document.createElement('div');
      info.className = 'vc-info';

      const name = document.createElement('div');
      name.className = 'vc-name';
      name.title = cleanName(p.name);
      name.textContent = cleanName(p.name);

      const price = document.createElement('div');
      price.className = 'vc-price';
      price.textContent = money(p.price);
      if (soldOut || low) {
        const badge = document.createElement('span');
        badge.className = 'vc-badge' + (low ? ' low' : '');
        badge.textContent = soldOut ? gettext("Agotado") : interpolate(gettext("Últimas %(count)s"), { count: stock }, true);
        price.appendChild(badge);
      }

      info.append(name, price);

      const sizes = Array.isArray(p.available_sizes) ? p.available_sizes.join(', ') : '';
      const metaParts = [];
      if (sizes) metaParts.push('Tallas: ' + sizes);
      if (p.color) metaParts.push(p.color);
      if (metaParts.length) {
        const meta = document.createElement('div');
        meta.className = 'vc-meta';
        meta.textContent = metaParts.join(' · ');
        info.appendChild(meta);
      }

      const link = document.createElement('button');
      link.type = 'button';
      link.className = 'vc-link';
      link.textContent = gettext("Ver producto");
      link.addEventListener('click', () => openProduct(p.id));
      info.appendChild(link);

      row.append(thumb, info);
      wrap.appendChild(row);
    });
    return wrap;
  }

  function addProducts(products, persist) {
    if (!Array.isArray(products) || !products.length) return null;
    const slim = products.map((p) => ({
      id: p.id, name: p.name, price: p.price, stock: p.stock,
      available_sizes: p.available_sizes, color: p.color, image: p.image,
    }));
    const el = buildProducts(slim);
    list.appendChild(el);
    if (persist !== false) {
      history.push({ t: 'products', items: slim });
      saveHistory();
    }
    return el;
  }

  /* ---------- Sugerencias rápidas ---------- */
  function renderSuggestions() {
    suggest.innerHTML = '';
    SUGGESTIONS.forEach((s) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'vc-chip';
      b.textContent = s;
      b.addEventListener('click', () => { if (!busy) send(s); });
      suggest.appendChild(b);
    });
  }

  function updateSuggestions() {
    const hasUser = history.some((h) => h.t === 'msg' && h.kind === 'user');
    suggest.hidden = hasUser;
  }

  /* ---------- Textarea: auto-altura, contador y estado del botón ---------- */
  function autosize() {
    input.style.height = 'auto';
    const h = Math.min(input.scrollHeight, MAX_TA_HEIGHT);
    input.style.height = h + 'px';
    input.style.overflowY = input.scrollHeight > MAX_TA_HEIGHT ? 'auto' : 'hidden';
  }

  function refreshInputState() {
    const len = input.value.length;
    sendBtn.disabled = busy || input.value.trim().length === 0;
    if (len >= MAX_LEN - 200) {
      counter.hidden = false;
      counter.textContent = len + '/' + MAX_LEN;
      counter.classList.toggle('max', len >= MAX_LEN);
    } else {
      counter.hidden = true;
    }
  }

  function onInput() { autosize(); refreshInputState(); }

  /* ---------- Errores amigables ---------- */
  function friendlyError(status) {
    if (status === 400) return interpolate(gettext("No pude entender tu mensaje. Intenta escribirlo de otra forma (máximo %(count)s caracteres)."), { count: MAX_LEN }, true);
    if (status === 404) return gettext("Reiniciamos la conversación. Por favor, envía tu mensaje de nuevo.");
    if (status === 502 || status === 503) return gettext("El asesor no está disponible en este momento. Inténtalo de nuevo en unos minutos.");
    if (status === 'timeout') return gettext("La respuesta está tardando más de lo normal. Inténtalo de nuevo.");
    if (status === 'offline') return gettext("Parece que no tienes conexión a internet. Revísala e inténtalo de nuevo.");
    return gettext("Ocurrió un problema al contactar al asesor. Inténtalo de nuevo.");
  }

  /* ---------- Envío ---------- */
  function setBusy(v) {
    busy = v;
    input.readOnly = v;
    root.setAttribute('aria-busy', String(v));
    refreshInputState();
  }

  async function send(text, isRetry) {
    setBusy(true);
    if (!isRetry) {
      addMsg(text, 'user');
      updateSuggestions();
    }
    scrollBottom();
    setTyping(true);

    if (navigator.onLine === false) {
      setTyping(false);
      addError(friendlyError('offline'), text);
      scrollBottom();
      setBusy(false);
      return;
    }

    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    try {
      const body = { message: text };
      const cid = ss.get(K_CONV);
      if (cid) body.conversation_id = cid;

      const res = await fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept-Language': language },
        body: JSON.stringify(body),
        signal: ctrl.signal,
      });

      let data = null;
      try { data = await res.json(); } catch (e) { /* respuesta no JSON */ }

      setTyping(false);
      if (!res.ok || !data) {
        if (res.status === 404) ss.del(K_CONV);
        addError(friendlyError(res.status), res.status === 400 ? null : text);
        scrollBottom();
        return;
      }
      if (data.conversation_id) ss.set(K_CONV, data.conversation_id);
      const botEl = addMsg(data.reply || gettext("No tengo una respuesta en este momento."), 'bot');
      addProducts(data.products);
      scrollToReplyStart(botEl);
    } catch (err) {
      setTyping(false);
      addError(friendlyError(err && err.name === 'AbortError' ? 'timeout' : 'network'), text);
      scrollBottom();
    } finally {
      clearTimeout(timer);
      setBusy(false);
      if (!panel.hidden) input.focus();
    }
  }

  /* ---------- Conversación: restaurar / reiniciar ---------- */
  function renderHistory() {
    list.innerHTML = '';
    history.forEach((h) => {
      if (h.t === 'msg') list.appendChild(createMsg(h.text, h.kind));
      else if (h.t === 'products') list.appendChild(buildProducts(h.items || []));
    });
    scrollBottom();
  }

  function startFresh() {
    history = [];
    ss.del(K_HIST);
    ss.del(K_CONV);
    list.innerHTML = '';
    addMsg(GREETING, 'bot');
    updateSuggestions();
    scrollBottom();
  }

  function resetConversation() {
    if (busy) return;
    startFresh();
    input.value = '';
    onInput();
    input.focus();
  }

  /* ---------- Abrir / cerrar ---------- */
  function setOpen(open) {
    panel.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? gettext("Cerrar asesor virtual") : gettext("Abrir asesor virtual"));
    ss.set(K_OPEN, open ? '1' : '0');
    if (open) {
      scrollBottom();
      autosize();
      input.focus();
    }
  }

  /* ---------- Eventos ---------- */
  toggle.addEventListener('click', () => setOpen(panel.hidden));
  closeBtn.addEventListener('click', () => { setOpen(false); toggle.focus(); });
  resetBtn.addEventListener('click', resetConversation);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !panel.hidden) { setOpen(false); toggle.focus(); }
  });

  input.addEventListener('input', onInput);
  input.addEventListener('keydown', (e) => {
    // Enter envía; Shift+Enter inserta salto de línea (sin interferir con el teclado IME).
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      form.requestSubmit();
    }
  });
  input.addEventListener('paste', () => setTimeout(onInput, 0));

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text || busy) return;
    input.value = '';
    onInput();
    send(text);
  });

  /* ---------- Inicio ---------- */
  renderSuggestions();
  history = loadHistory();
  if (history.length) {
    renderHistory();
  } else {
    addMsg(GREETING, 'bot');
  }
  updateSuggestions();
  refreshInputState();
  if (ss.get(K_OPEN) === '1') setOpen(true);
})();
