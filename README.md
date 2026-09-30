# Volt - Tienda Virtual de Moda

## Integrantes

- Fabiola Valencia Barrios
- Sebastian Cañon Cuartas
- Mariana Patiño Arboleda

## Descripción

Volt es una plataforma web de comercio electrónico enfocada en la venta de ropa. El proyecto permite gestionar productos, categorías, carritos de compra, direcciones y pedidos mediante una API REST desarrollada con Django y Django REST Framework.

Como propuesta de mejora, el proyecto contempla la integración de un asesor virtual basado en Inteligencia Artificial. Este componente permitirá que los usuarios realicen consultas utilizando lenguaje natural y reciban recomendaciones de productos existentes en el catálogo.

La propuesta de IA combina un modelo de lenguaje (LLM), embeddings, búsqueda semántica, filtros y ranking de productos.

## Objetivos

### Objetivo general

Desarrollar una plataforma de comercio electrónico para la gestión de productos y pedidos, con una arquitectura que permita integrar un asesor virtual basado en Inteligencia Artificial.

### Objetivos específicos

- Gestionar productos y categorías.
- Administrar carritos de compra.
- Crear y gestionar pedidos.
- Controlar el inventario disponible.
- Exponer las funcionalidades mediante una API REST.
- Aplicar patrones de diseño y separación de responsabilidades.
- Diseñar la arquitectura necesaria para integrar funcionalidades de Inteligencia Artificial.

## Funcionalidades

### Implementadas

- Gestión de categorías.
- Gestión de productos.
- Gestión de carritos y sus elementos vía API (`/api/cart/`).
- Gestión de direcciones.
- Creación de pedidos.
- Validación de disponibilidad de productos.
- Actualización del inventario al realizar pedidos.
- Sistema básico de notificaciones.
- API REST.
- Pruebas automatizadas.

### Futuras

- Asesor virtual de moda.
- Chat con el usuario.
- Integración con un LLM.
- Embeddings de productos.
- Búsqueda semántica.
- Sistema de recomendaciones.
- Favoritos y reseñas.

## Tecnologías

- Python
- Django 6.0.8
- Django REST Framework 3.18.0
- SQLite
- Git
- GitHub

### Tecnologías proyectadas para IA

- LLM
- Embeddings
- Búsqueda semántica
- Ranking de productos

## Instalación y ejecución

Requisitos: Python 3.12 o superior (Django 6.0.8 no funciona con versiones
anteriores).

```bash
# 1. Clonar el repositorio y entrar a la carpeta
git clone <url-del-repo>
cd Volt

# 2. Crear y activar un entorno virtual
python -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Aplicar migraciones
python manage.py migrate

# 5. Crear un superusuario (para entrar a /admin/ y cargar datos de prueba)
python manage.py createsuperuser

# 6. Levantar el servidor de desarrollo
python manage.py runserver
```

La API queda disponible en `http://localhost:8000/api/` y el panel de
administración en `http://localhost:8000/admin/`.

### Correr las pruebas automatizadas

```bash
python manage.py test Volt
```

### Variables de entorno (opcional)

Por defecto el proyecto corre con una `SECRET_KEY` de desarrollo y
`DEBUG=True`. Para otro entorno, exportar:

```bash
export DJANGO_SECRET_KEY="una-clave-secreta-real"
export DJANGO_DEBUG=False
export DJANGO_ALLOWED_HOSTS="midominio.com"
```

### Endpoints principales

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/categories/` | Listar categorías |
| GET | `/api/products/` | Listar productos (filtro `?category=<id>`) |
| GET | `/api/products/<id>/` | Detalle de producto |
| GET | `/api/cart/` | Ver el carrito del usuario autenticado |
| POST | `/api/cart/items/` | Agregar un producto al carrito (`product_id`, `quantity`) |
| DELETE | `/api/cart/items/<id>/` | Quitar un producto del carrito |
| GET/POST | `/api/addresses/` | Listar/crear direcciones del usuario |
| GET | `/api/addresses/<id>/` | Detalle de una dirección |
| GET/POST | `/api/orders/` | Crear un pedido a partir del carrito |

Los endpoints que requieren usuario autenticado aceptan sesión de Django
(`/admin/` login) o HTTP Basic Auth, por ejemplo:

```bash
curl -u usuario:contraseña -X POST http://localhost:8000/api/cart/items/ \
  -H "Content-Type: application/json" \
  -d '{"product_id": 1, "quantity": 2}'
```

## Estructura del proyecto

```text
Volt-main/
│
├── .gitignore
│
├── Contexto/
│   ├── Contexto.md
│   ├── Entrega.md
│   ├── PendientesCompanera.md
│   └── PlanDeTrabajo.md
│
├── Volt/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   │
│   ├── domain/
│   │   └── builders.py
│   │
│   ├── infra/
│   │   ├── __init__.py
│   │   ├── factory.py
│   │   └── notifications.py
│   │
│   ├── migrations/
│   │   ├── __init__.py
│   │   ├── 0001_initial.py
│   │   └── 0002_add_address_and_domain_validations.py
│   │
│   ├── models.py
│   ├── serializers.py
│   ├── services.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
│
├── config/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── wiki/
│   ├── API-Gateway.md
│   ├── Diagrama-de-Secuencia.md
│   ├── Estructura-de-Carpetas.md
│   ├── Home.md
│   └── Patrones-Creacionales.md
│
├── scripts/
│   └── prueba_pedido.py
│
├── db.sqlite3
├── manage.py
└── requirements.txt
<<<<<<< HEAD

## Taller 02: extracción de notificaciones

La implementación del patrón Strangler incorpora un servicio Flask de notificaciones,
Django, PostgreSQL y Nginx. Los canales conservan el comportamiento simulado del avance
original; no se envían correos reales.

```bash
cp .env.example .env
# Configurar las claves en .env.
docker compose up --build -d
```

Entrada: `http://localhost:8080`. Las rutas `/api/` y `/api/v1/` llegan a Django;
`/api/v2/notifications/` llega a Flask y exige `X-API-Key`.

Consulta [Migración a Microservicios (Strangler Pattern)](wiki/Migracion-a-Microservicios-Strangler-Pattern.md)
para la matriz de decisión, arquitectura, contrato, pruebas, límites y publicación de la Wiki.
=======
>>>>>>> 616e6e1ef9f72e30884912055310c7b01b399cc3
