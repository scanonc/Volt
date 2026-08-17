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
- Gestión de carritos.
- Gestión de elementos del carrito.
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
├── db.sqlite3
├── manage.py
├── prueba_pedido.py
└── requirements.txt
