# Wiki Técnica — Volt

Documentación técnica del proyecto **Volt** para la Entrega No. 1 del curso de
Arquitectura de Software 2026 (Núcleo de Negocio y Exposición de API Profesional).

## Índice

- [[Estructura de Carpetas|Estructura-de-Carpetas]]
- [[Diagrama de Secuencia|Diagrama-de-Secuencia]]
- [[Patrones Creacionales|Patrones-Creacionales]]
- [[Preparación para API Gateway|API-Gateway]]

## Resumen del avance (Entrega 1)

- **Capa de dominio:** `Category`, `Product`, `Cart`, `CartItem`, `Order`,
  `OrderItem`, `Address` (7 clases implementadas), con validaciones de negocio
  a nivel de modelo (`Product.has_stock`, `Product.reduce_stock`).
- **Service Layer:** `OrderService` orquesta la creación de pedidos a partir
  del carrito, validando existencia de carrito, carrito vacío e inventario.
  `CartService` orquesta agregar/quitar productos del carrito, validando
  existencia del producto y disponibilidad de stock.
- **Capa de presentación (DRF):** `APIView` + `Serializers` para pedidos,
  carrito y catálogo (`/api/orders/`, `/api/cart/`, `/api/cart/items/`,
  `/api/categories/`, `/api/products/`).
- **Patrones creacionales:** `OrderBuilder` (Builder) y `NotificationFactory`
  (Factory).
- **Pendiente (ver PlanDeTrabajo.md):** reseñas, favoritos y las entidades del
  asesor virtual (chat), a cargo de la siguiente iteración del equipo.
<<<<<<< HEAD

- [Migración a Microservicios (Strangler Pattern)](Migracion-a-Microservicios-Strangler-Pattern)
=======
>>>>>>> 616e6e1ef9f72e30884912055310c7b01b399cc3
