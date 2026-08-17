# Justificación de la Estructura de Carpetas

```
Volt/
├── config/                # Proyecto Django: settings, urls raíz, wsgi/asgi.
│                           # Solo configuración de infraestructura del sitio.
└── Volt/                  # App de dominio ("bounded context" de la tienda).
    ├── models.py           # Capa de Dominio: entidades y reglas de negocio
    │                        # que son invariantes de la propia entidad
    │                        # (p. ej. Product.reduce_stock).
    ├── domain/
    │   └── builders.py      # Patrones creacionales que ensamblan entidades
    │                        # complejas del dominio (OrderBuilder).
    ├── infra/
    │   ├── notifications.py # Implementaciones concretas de un puerto de
    │   │                     # infraestructura (envío de confirmaciones).
    │   └── factory.py       # Factory que decide qué implementación de
    │                        # infraestructura usar (Console vs Email).
    ├── services.py         # Capa de Aplicación (Service Layer): orquesta
    │                        # flujos de negocio completos (OrderService),
    │                        # coordinando dominio + infraestructura dentro
    │                        # de una transacción.
    ├── serializers.py      # Capa de Presentación: contratos de entrada y
    │                        # salida de la API (DRF Serializers).
    ├── views.py             # Capa de Presentación: APIViews. Solo reciben
    │                        # la petición, delegan al Service y traducen el
    │                        # resultado/errores a códigos HTTP.
    ├── urls.py              # Enrutamiento de la app, montado en config/urls.py
    │                        # bajo el prefijo /api/.
    ├── admin.py             # Panel administrativo (soporte operativo, no
    │                        # es parte del núcleo de negocio).
    ├── migrations/          # Historial versionado del esquema de datos.
    └── tests.py             # Pruebas de dominio, servicios y API.
```

## Por qué esta separación

Elegimos separar `domain/`, `infra/` y `services.py` como carpetas/módulos
distintos (en vez de mezclar todo en `models.py` o en `views.py`) porque cada
uno tiene una razón de cambio diferente (Principio de Responsabilidad Única
a nivel de módulo):

- **`models.py`** cambia cuando cambian las reglas *intrínsecas* de una
  entidad (por ejemplo, que el stock nunca sea negativo).
- **`domain/builders.py`** cambia cuando cambia la forma de *construir* una
  entidad compleja (por ejemplo, si `Order` empieza a requerir cupones o
  impuestos).
- **`infra/`** cambia cuando cambia un proveedor externo (por ejemplo, pasar
  de imprimir en consola a usar un proveedor real de correo/SMS). Al estar
  aislado, ese cambio no toca `services.py` ni `views.py`.
- **`services.py`** cambia cuando cambia el *flujo* de negocio (pasos,
  validaciones de orquestación, transacciones), sin acoplarse a HTTP ni a la
  base de datos directamente.
- **`serializers.py` / `views.py`** cambian cuando cambia el *contrato* de la
  API (forma de la petición/respuesta, códigos HTTP), sin necesidad de tocar
  reglas de negocio.

Esta separación es también lo que permite cumplir el requisito de la entrega:
**cero lógica de negocio en `views.py` o en `serializers.py`**, y **cero
lógica de orquestación en `models.py`** (los modelos solo validan sus propias
invariantes, no coordinan múltiples entidades).
