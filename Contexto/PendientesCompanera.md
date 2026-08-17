# Pendientes para la Entrega No. 1

Este documento resume qué quedó listo en este avance y qué falta para
terminar de cumplir el checklist de `Contexto/Entrega.md`. La idea es que
cada quien pueda tomar un bloque sin pisarse con el otro.

## ✅ Ya implementado (esta iteración)

- **Dominio (7 clases):** `Category`, `Product`, `Cart`, `CartItem`, `Order`,
  `OrderItem`, `Address`.
  - Validaciones de negocio en el modelo: `Product.has_stock()`,
    `Product.reduce_stock()` (nunca deja stock negativo), `price` con
    `MinValueValidator`, `Category.name` único.
- **Service Layer:** `OrderService.create_order()` sigue siendo el único
  orquestador del flujo de pedidos (carrito → validación de stock → Order →
  descuento de stock → notificación), dentro de una transacción atómica.
- **DRF:**
  - `POST/GET /api/orders/` (ya existía).
  - `GET /api/categories/` y `GET /api/products/` (+ filtro `?category=`) y
    `GET /api/products/<id>/` (nuevos, de solo lectura).
- **Patrones creacionales:** `OrderBuilder` (Builder) y `NotificationFactory`
  (Factory), documentados en la Wiki (`wiki/Patrones-Creacionales.md`).
- **Tests:** se agregaron pruebas de dominio (`ProductDomainTests`) y de la
  API de catálogo (`CatalogApiTests`). Los tests existentes de `OrderService`
  y de la API de pedidos siguen pasando.
- **Wiki técnica** (carpeta `wiki/`, lista para copiar a la Wiki de GitHub):
  estructura de carpetas, diagrama de secuencia, patrones creacionales y
  preparación para API Gateway.
- **Admin de Django** con inlines para `Cart`/`Order` (útil para poblar datos
  de prueba antes de la sustentación).

## 🟡 Pendiente (para completar el 50-60 % con margen y reforzar la nota)

Elige uno o dos bloques, no hace falta hacerlos todos para esta entrega:

1. **Endpoint de `Address`** (`AddressSerializer` ya existe en
   `Volt/serializers.py`, falta la `View`/`url` para crear/listar
   direcciones del usuario autenticado, p. ej. `GET/POST /api/addresses/`).
2. **Una clase de dominio adicional** para subir el porcentaje con margen,
   por ejemplo `Wishlist`/`FavoriteItem` (mencionado en `Contexto.md` como
   feature) o `Review` (reseña de producto). Debe seguir el mismo patrón:
   modelo con sus validaciones propias + (si aplica) un Service +
   Serializer + APIView + tests.
3. **Más pruebas de borde** en `CreateOrderApiTests`: usuario no
   autenticado contra endpoints de catálogo (si se decide protegerlos),
   productos de otra categoría, paginación si el catálogo crece.
4. **README.md** en la raíz del repo con instrucciones de instalación
   (`pip install -r requirements.txt`, migraciones, `createsuperuser`,
   cómo correr los tests) — hoy no existe y ayuda mucho en la sustentación.
5. **Revisar y ampliar la Wiki** una vez se agregue lo del punto 2 (nueva
   entidad → agregar su justificación y, si aplica, su propio diagrama).

## Cómo evitar choques de trabajo

- Los archivos que vas a tocar para el punto 1 y 2 (`models.py`,
  `serializers.py`, `views.py`, `urls.py`, `tests.py`, `admin.py`) son los
  mismos que se tocaron en este avance. Haz `git pull` de la rama antes de
  empezar para partir del último estado.
- Si agregas un modelo nuevo, genera tú misma la migración con
  `python manage.py makemigrations Volt` (no la escribas a mano) y súbela
  en el mismo commit que el modelo.
