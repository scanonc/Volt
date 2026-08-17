# Patrones Creacionales

## Builder — `OrderBuilder` (`Volt/domain/builders.py`)

**Problema que resuelve:** `Order` es la entidad más compleja del sistema:
se construye a partir de múltiples `CartItem`, requiere calcular el total,
copiar el precio vigente de cada producto (para que cambios futuros de
precio no alteren pedidos históricos) y generar una lista de `OrderItem`
asociada. Construir esto directamente en el `Service` o en la `View`
mezclaría "cómo se arma un pedido" con "cuándo se dispara ese armado".

**Cómo se usa:**

```python
order, order_items = (
    OrderBuilder()
    .for_user(user)
    .with_items(cart_items)
    .build()
)
```

`build()` valida que exista un usuario y al menos un ítem antes de construir,
manteniendo la invariante de que no puede existir un `Order` sin dueño ni sin
productos.

## Factory — `NotificationFactory` (`Volt/infra/factory.py`)

**Problema que resuelve:** el mecanismo de notificación de confirmación de
pedido es una dependencia externa que varía según el entorno (consola en
desarrollo, correo en producción, y a futuro podría ser SMS o push). El
`OrderService` no debe saber *cuál* implementación usar ni *cómo*
construirla.

```python
notifier = NotificationFactory.create()
notifier.send_confirmation(order)
```

`NotificationFactory.create()` decide la implementación concreta
(`ConsoleNotification` o `EmailNotification`) según la configuración del
proyecto (`settings.DEBUG`), devolviendo siempre un objeto que cumple el
contrato `BaseNotification`. Agregar un nuevo canal (SMS, WhatsApp) solo
requiere una nueva subclase y un nuevo caso en la factory, sin tocar
`OrderService`.
