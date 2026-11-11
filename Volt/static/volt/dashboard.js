const form = document.querySelector('#notification-form');
const responseBody = document.querySelector('#response-body');
const responseTitle = document.querySelector('#response-title');
const responseCode = document.querySelector('#response-code');
const responseNote = document.querySelector('#response-note');
const statusText = document.querySelector('#service-status');
const statusDot = document.querySelector('#status-dot');
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

function showResponse(title, code, data, note) {
  responseTitle.textContent = title;
  responseCode.textContent = code;
  responseBody.textContent = JSON.stringify(data, null, 2);
  responseNote.textContent = note;
}

async function checkHealth() {
  statusText.textContent = gettext("Comprobando...");
  try {
    const response = await fetch('/api/notifications/health/');
    const data = await response.json();
    statusText.textContent = response.ok ? gettext("Operativo · Flask") : gettext("No disponible");
    statusDot.className = response.ok ? 'status-dot online' : 'status-dot offline';
    if (!response.ok) {
      showResponse(
        gettext("Servicio no disponible"), response.status, data,
        gettext("Revisa que el contenedor notifications esté levantado."),
      );
    }
  } catch (error) {
    statusText.textContent = gettext("Sin conexión");
    statusDot.className = 'status-dot offline';
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = form.querySelector('button[type=submit]');
  button.disabled = true;
  responseTitle.textContent = gettext("Enviando solicitud...");
  try {
    const response = await fetch('/api/notifications/send/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
      body: JSON.stringify({
        order_id: Number(form.order_id.value),
        username: form.username.value.trim(),
        channel: form.channel.value,
      }),
    });
    const data = await response.json();
    showResponse(
      response.ok ? gettext("Notificación simulada") : gettext("La solicitud fue rechazada"),
      response.status,
      data,
      response.ok
        ? gettext("Respuesta recibida desde el microservicio Flask.")
        : gettext("El servicio devolvió un error de validación."),
    );
  } catch (error) {
    showResponse(
      gettext("Error de conexión"), 'ERR',
      { error: gettext("No fue posible contactar el proxy de Django.") },
      gettext("Comprueba que el servidor esté ejecutándose."),
    );
  } finally {
    button.disabled = false;
  }
});

document.querySelector('#refresh-status').addEventListener('click', checkHealth);
document.querySelector('#clock').textContent = new Date().toLocaleTimeString(
  document.documentElement.lang, { hour: '2-digit', minute: '2-digit' },
);
checkHealth();
