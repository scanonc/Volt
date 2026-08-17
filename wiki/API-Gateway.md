# Preparación para un API Gateway

## Estado actual

La API expone actualmente los siguientes recursos bajo el prefijo `/api/`
(definido en `config/urls.py` → `Volt/urls.py`):

- `GET/POST /api/orders/`
- `GET /api/categories/`
- `GET /api/products/`
- `GET /api/products/<id>/`

Todos los endpoints están implementados como `APIView` de Django REST
Framework, devuelven JSON y usan códigos de estado HTTP estándar
(`200`, `201`, `400`, `401`, `404`, `409`).

## Por qué el diseño actual ya está listo para un Gateway

1. **Un único punto de entrada versionable.** Toda la API cuelga de un
   prefijo (`/api/`) separado del resto del sitio (`/admin/`). Un API
   Gateway (Kong, AWS API Gateway, NGINX, Apigee, etc.) puede montarse
   delante de este prefijo sin reescribir rutas internas, y en el futuro se
   puede versionar como `/api/v1/` sin tocar la lógica de negocio.

2. **Autenticación desacoplada de la lógica de negocio.** La View solo
   verifica `request.user.is_authenticated`; no implementa el mecanismo de
   autenticación en sí. Esto permite que, detrás de un Gateway, la
   autenticación/autorización (API keys, OAuth2, JWT) se resuelva en el
   Gateway o en middleware de DRF, y la aplicación solo confíe en la
   identidad ya resuelta — sin cambiar `OrderService` ni los modelos.

3. **Contratos explícitos de entrada/salida (Serializers).** Cada endpoint
   tiene un Serializer de entrada y de salida bien definidos. Esto es
   justamente lo que un Gateway necesita para poder documentar (OpenAPI),
   validar payloads en el borde, o transformar/enrutar peticiones sin
   depender de la implementación interna.

4. **Errores de negocio traducidos a HTTP de forma consistente.** Como las
   excepciones de dominio (`CartNotFoundError`, `EmptyCartError`,
   `InsufficientStockError`) siempre se mapean a códigos HTTP estándar en la
   View, un Gateway puede aplicar políticas genéricas (reintentos, circuit
   breaker, rate limiting) basándose únicamente en el código de estado, sin
   conocer el dominio de Volt.

5. **Servicios internos independientes de HTTP.** `OrderService` no depende
   de `request`/`response` de Django; recibe un `user` y objetos de dominio.
   Esto significa que, si en el futuro la lógica de pedidos se extrae a un
   microservicio independiente detrás del Gateway, el `Service` se puede
   reutilizar casi sin cambios (solo cambia quién lo invoca).

## Responsabilidades que se centralizarían en el Gateway a futuro

- **Autenticación/autorización** de clientes (API keys por app cliente,
  OAuth2/JWT), en vez de manejarla ad-hoc en cada microservicio.
- **Rate limiting / throttling** por cliente o por IP.
- **Enrutamiento** hacia distintos microservicios a medida que el dominio
  crezca (por ejemplo, separar "catálogo", "pedidos" y el futuro "asesor
  virtual / chat" en servicios independientes).
- **Observabilidad transversal:** logging centralizado, trazabilidad
  (correlation IDs), métricas de latencia y tasa de error por endpoint.
- **Transformación de payloads y versionado de contratos** sin tocar el
  código de cada servicio interno.
- **TLS termination y CORS**, hoy manejados por Django/DRF, pasarían a
  resolverse en el borde de la infraestructura.

## Siguiente paso natural

Cuando el asesor virtual (chatbot) se implemente como un flujo con
necesidades distintas (latencia alta hacia el LLM, posible servicio
separado), el Gateway permitiría enrutar `/api/chat/*` hacia ese servicio
mientras `/api/orders/*`, `/api/products/*` y `/api/categories/*` siguen
sirviéndose desde este monolito Django, sin que el cliente note la
diferencia.
