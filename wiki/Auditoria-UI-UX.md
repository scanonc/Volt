# Auditoría de UI/UX de Volt

La revisión cubrió la navegación de la tienda, los formularios y los estados de error mediante inspección del código, pruebas de Django y solicitudes HTTP locales. La navegación móvil se revisó en las reglas CSS. El alcance incluyó español e inglés y respuestas simuladas para FinanSmart.

| Flujo | Evidencia | Resultado |
|---|---|---|
| Navegación a FinanSmart en móvil | La regla para anchos de hasta 760 px ocultaba los enlaces simples del encabezado, incluidos FinanSmart, Notificaciones e Ingresar. | Se eliminó esa regla y se permite que los controles del menú se distribuyan en varias filas. |
| Cambio de idioma | Solicitudes con protección CSRF al selector y navegación posterior entre la tienda y FinanSmart. | Español e inglés muestran sus etiquetas correspondientes y el idioma persiste al navegar. |
| Cuenta y acceso | Pruebas de renderizado de inicio de sesión y creación de usuario mediante el formulario de registro. | El registro válido crea la cuenta e inicia sesión. La plantilla de acceso muestra un aviso ante credenciales incorrectas. |
| Carrito, direcciones y compra | Pruebas de acceso sin sesión, datos inválidos, aislamiento de direcciones, carrito vacío y stock insuficiente. | El servidor rechaza las solicitudes inválidas y el flujo válido crea el pedido. |
| Caída del servicio aliado | Pruebas con timeout, respuesta inválida y errores HTTP. Solicitud local del resumen sin token en inglés. | FinanSmart muestra un aviso traducido y la tienda permanece accesible. |
| Caída de notificaciones | Prueba del pedido con el servicio de notificaciones fuera de línea. | El pedido confirmado se conserva y la aplicación registra el fallo. |
