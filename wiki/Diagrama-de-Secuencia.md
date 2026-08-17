# Diagrama de Secuencia — Creación de Pedido

La funcionalidad más compleja implementada en esta entrega es la **creación
de un pedido a partir del carrito de compras** (`POST /api/orders/`), porque
involucra validaciones de negocio, concurrencia (bloqueo de filas), dos
patrones creacionales (Builder y Factory) y una transacción atómica.

```mermaid
sequenceDiagram
    actor Cliente
    participant View as CreateOrderView (DRF)
    participant Serializer as CreateOrderInputSerializer
    participant Service as OrderService
    participant DB as Base de Datos
    participant Builder as OrderBuilder
    participant Product as Product (modelo)
    participant Factory as NotificationFactory
    participant Notifier as BaseNotification

    Cliente->>View: POST /api/orders/
    View->>View: ¿usuario autenticado?
    alt no autenticado
        View-->>Cliente: 401 Unauthorized
    end
    View->>Serializer: validar payload
    alt payload inválido
        Serializer-->>View: errores
        View-->>Cliente: 400 Bad Request
    end
    View->>Service: create_order(user)
    activate Service
    Service->>DB: BEGIN (transaction.atomic)
    Service->>DB: SELECT ... FOR UPDATE (Cart del usuario)
    alt sin carrito
        DB-->>Service: None
        Service-->>View: CartNotFoundError
        View-->>Cliente: 404 Not Found
    end
    Service->>DB: SELECT items del carrito FOR UPDATE
    alt carrito vacío
        Service-->>View: EmptyCartError
        View-->>Cliente: 400 Bad Request
    end
    Service->>DB: SELECT productos FOR UPDATE
    Service->>Service: validar stock por producto
    alt stock insuficiente
        Service-->>View: InsufficientStockError
        View-->>Cliente: 409 Conflict
    end
    Service->>Builder: for_user(user).with_items(items).build()
    Builder-->>Service: (order, order_items)
    Service->>DB: guardar Order y OrderItems
    Service->>Product: reduce_stock(cantidad) por cada producto
    Product-->>Service: stock actualizado (o ValidationError)
    Service->>DB: vaciar carrito
    Service->>DB: COMMIT
    Service->>Factory: NotificationFactory.create()
    Factory-->>Service: instancia de BaseNotification
    Service->>Notifier: send_confirmation(order)
    deactivate Service
    Service-->>View: order
    View-->>Cliente: 201 Created + OrderSerializer(order)
```

## Puntos clave que ilustra el diagrama

- **Service Layer como orquestador único:** `OrderService` es el único punto
  que coordina modelo, builder, factory y transacción; la `View` no conoce
  ninguna de estas reglas.
- **Builder** encapsula el ensamblaje de la entidad compleja `Order` (con sus
  `OrderItem` derivados de los ítems del carrito), separando "cómo se
  construye" de "cuándo se construye".
- **Factory** desacopla `OrderService` de la implementación concreta de
  notificación (consola en desarrollo, correo en producción), cumpliendo el
  principio de inversión de dependencias.
- **Manejo de errores por capas:** las excepciones de negocio
  (`CartNotFoundError`, `EmptyCartError`, `InsufficientStockError`) se
  originan en el Service/Domain y se traducen a códigos HTTP únicamente en
  la View.
