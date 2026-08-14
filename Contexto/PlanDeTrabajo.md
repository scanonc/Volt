# Plan de Trabajo — Entrega No. 1

## 1. Objetivo

Consolidar el núcleo de negocio del proyecto Volt y exponer sus funcionalidades mediante una API profesional utilizando Django REST Framework (DRF), manteniendo una separación clara de responsabilidades mediante una capa de servicios (Service Layer) y aplicando los patrones creacionales Builder y Factory.

El objetivo de esta entrega será alcanzar la implementación de aproximadamente el 50 % al 60 % de las clases de dominio definidas para el proyecto, junto con una API funcional, pruebas y documentación de las principales decisiones arquitectónicas.

## 2. Estado inicial

Actualmente el proyecto cuenta con una implementación inicial del flujo de creación de pedidos a partir del carrito de un usuario.

Se encuentran implementados:

- Modelos de Category, Product, Cart, CartItem, Order y OrderItem.
- Servicio `OrderService` para la creación de pedidos.
- Patrón Builder mediante `OrderBuilder`.
- Patrón Factory mediante `NotificationFactory`.
- Endpoint inicial para la creación de pedidos.
- Pruebas automatizadas básicas.
- Base de datos SQLite.
- Separación inicial entre Views, Services, Domain e Infrastructure.

Sin embargo, la API todavía no utiliza Django REST Framework y existen funcionalidades y validaciones que deben ser fortalecidas para cumplir con los requisitos de la entrega.

## 3. Plan de trabajo

### Fase 1 — Revisión y ajuste del modelo de dominio

**Objetivo:** verificar que las entidades implementadas representen correctamente el dominio y que se alcance el porcentaje de clases requerido.

**Actividades:**

- Revisar las clases de dominio existentes.
- Comparar los modelos implementados con los diagramas definidos para el proyecto.
- Determinar qué clases adicionales son necesarias para alcanzar el 50 % - 60 % requerido.
- Revisar tipos de datos y relaciones entre entidades.
- Identificar validaciones de negocio que deban existir en el dominio.
- Definir restricciones necesarias en la base de datos.

**Validación:**

- Los modelos deben representar correctamente las entidades y relaciones del sistema.
- Las validaciones de negocio no deben depender de las Views.
- El porcentaje de clases implementadas debe encontrarse dentro del rango solicitado.

### Fase 2 — Consolidación de la Service Layer

**Objetivo:** garantizar que los flujos de negocio estén desacoplados de la capa de presentación.

**Actividades:**

- Revisar `OrderService` y su responsabilidad dentro del sistema.
- Identificar lógica de negocio que actualmente pueda estar ubicada en Views.
- Crear servicios adicionales para los nuevos flujos de negocio.
- Mantener las Views enfocadas exclusivamente en recibir peticiones, invocar servicios y construir respuestas.
- Aplicar el principio de responsabilidad única (SRP).
- Evitar lógica de negocio dentro de Serializers.
- Analizar dependencias para mantener un bajo acoplamiento.

**Validación:**

- Cada flujo principal debe estar orquestado por un Service.
- Las Views no deben contener cálculos ni reglas de negocio.
- Los Serializers deben encargarse principalmente de la validación y transformación de datos de entrada/salida.
- Las responsabilidades de cada componente deben estar claramente definidas.

### Fase 3 — Migración y construcción de la API con DRF

**Objetivo:** reemplazar la exposición HTTP inicial por una API basada en Django REST Framework.

**Actividades:**

- Incorporar Django REST Framework al proyecto.
- Definir Serializers para entrada y salida de información.
- Implementar APIViews para los endpoints principales.
- Definir correctamente las URLs de la API.
- Implementar respuestas HTTP apropiadas.
- Manejar casos de éxito y error.
- Implementar códigos de estado como 201, 400, 404 y 409 cuando correspondan.
- Mantener la lógica de negocio dentro de los Services.

**Validación:**

- Los endpoints deben poder probarse de manera independiente.
- Las respuestas deben tener una estructura consistente.
- Los errores deben retornar códigos HTTP apropiados.
- Las Views deben mantenerse delgadas y desacopladas.

### Fase 4 — Consolidación de patrones creacionales

**Objetivo:** cumplir y justificar correctamente el uso de Builder y Factory.

**Builder:**

- Mantener `OrderBuilder` como mecanismo para construir la entidad compleja Order.
- Revisar que la construcción del pedido esté separada de la lógica de presentación.
- Validar que el Builder tenga una responsabilidad clara.

**Factory:**

- Mantener `NotificationFactory` para seleccionar el mecanismo de notificación.
- Evaluar posibles mejoras en la abstracción de las notificaciones.
- Mantener la posibilidad de agregar nuevos mecanismos sin modificar la lógica principal del pedido.

**Validación:**

- Los patrones deben solucionar problemas reales del diseño.
- El código debe demostrar por qué Builder y Factory son apropiados para estos casos.
- Las decisiones deben quedar justificadas en la documentación técnica.

### Fase 5 — Validaciones y consistencia del negocio

**Objetivo:** asegurar que los flujos implementados mantengan la consistencia del sistema.

**Actividades:**

- Implementar validación de inventario al crear pedidos.
- Revisar el comportamiento de las transacciones.
- Evitar creación de pedidos con productos inexistentes o cantidades inválidas.
- Revisar el comportamiento cuando un usuario no tiene carrito.
- Revisar el comportamiento cuando el carrito está vacío.
- Analizar posibles conflictos de concurrencia relacionados con el inventario.
- Definir correctamente los casos que deben generar errores 400, 404 o 409.

**Validación:**

- Un pedido no debe poder crearse si no cumple las reglas de negocio.
- La información persistida debe mantenerse consistente.
- Los errores de negocio deben ser manejados por la capa correspondiente y no directamente por la View.

### Fase 6 — Pruebas automatizadas

**Objetivo:** comprobar el comportamiento de los servicios y de la API.

**Actividades:**

- Mantener las pruebas actuales del `OrderService`.
- Agregar pruebas para los nuevos Services.
- Agregar pruebas de los Serializers.
- Agregar pruebas de los APIViews.
- Probar usuarios no autenticados.
- Probar carritos vacíos.
- Probar usuarios sin carrito.
- Probar productos sin stock.
- Probar errores de validación.
- Probar respuestas HTTP y códigos de estado.

**Validación:**

- Todos los tests existentes deben continuar funcionando.
- Los nuevos casos principales deben estar cubiertos.
- Los errores esperados deben producir respuestas controladas.

### Fase 7 — Preparación para API Gateway

**Objetivo:** diseñar la API de manera que pueda evolucionar hacia una arquitectura escalable.

**Actividades:**

- Definir una estructura clara de URLs.
- Mantener una separación entre la API y la lógica de negocio.
- Analizar cómo un API Gateway podría ubicarse delante de la aplicación.
- Documentar responsabilidades que podrían centralizarse posteriormente en un Gateway, como autenticación, routing, rate limiting o control de acceso.
- Evitar acoplar la lógica de negocio directamente a una infraestructura específica.

**Validación:**

- La documentación debe explicar cómo la API actual podría integrarse posteriormente detrás de un API Gateway.
- La arquitectura debe permitir agregar nuevos servicios sin modificar innecesariamente el núcleo de negocio.

### Fase 8 — Documentación técnica y Wiki

**Objetivo:** documentar las decisiones arquitectónicas tomadas durante la implementación.

La Wiki deberá incluir:

- Justificación de la estructura de carpetas.
- Descripción de la arquitectura utilizada.
- Explicación de la Service Layer.
- Explicación y justificación del patrón Builder.
- Explicación y justificación del patrón Factory.
- Diagrama de secuencia de la funcionalidad más compleja implementada.
- Explicación de la preparación del sistema para un futuro API Gateway.
- Principales decisiones técnicas y sus razones.

### Fase 9 — Integración y entrega

**Objetivo:** dejar el repositorio preparado para la evaluación.

**Actividades:**

- Ejecutar todas las pruebas.
- Verificar que no existan errores de Django.
- Revisar estructura y calidad del código.
- Revisar que no exista lógica de negocio en Views o Serializers.
- Verificar el funcionamiento de los endpoints.
- Actualizar la documentación.
- Revisar el README y la Wiki.
- Realizar commits organizados.
- Integrar los cambios a `main` o `develop`.
- Verificar que el repositorio pueda ser ejecutado por otra persona.

## 4. Orden de prioridades

La implementación se realizará priorizando:

1. Modelo de dominio.
2. Service Layer.
3. Django REST Framework.
4. Serializers.
5. APIViews.
6. Validaciones y manejo de errores.
7. Builder y Factory.
8. Pruebas.
9. Documentación.
10. Preparación para la entrega.

## 5. Criterios de finalización

La Entrega No. 1 estará lista cuando:

- Se haya implementado entre el 50 % y 60 % de las clases de dominio.
- Los modelos sean coherentes con el dominio.
- Los principales flujos de negocio estén implementados mediante Services.
- No exista lógica de negocio en las Views.
- No exista lógica de negocio en los Serializers.
- La API utilice Django REST Framework.
- Se utilicen Serializers y APIViews.
- Los códigos HTTP sean manejados correctamente.
- Builder y Factory estén implementados y justificados.
- Existan pruebas automatizadas de los principales casos.
- La Wiki contenga la documentación técnica solicitada.
- El repositorio se encuentre funcional y organizado para la entrega.
