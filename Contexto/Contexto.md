# Proyecto Volt - Tienda Virtual & Asesor Virtual IA

## Descripción del proyecto

En un mundo donde las compras en línea hacen parte de la vida cotidiana, las personas buscan plataformas que les permitan adquirir ropa de forma rápida, sencilla y con una experiencia agradable. Nuestro proyecto consiste en el desarrollo de una tienda virtual para la marca de ropa **Volt**, diseñada para ofrecer un catálogo organizado de prendas, facilitar la búsqueda de productos y permitir a los usuarios encontrar fácilmente el estilo que mejor se adapte a sus gustos y necesidades.

Nuestra aplicación contará con funcionalidades como:
* Registro y autenticación de usuarios.
* Catálogo interactivo organizado por categorías.
* Carrito de compras y lista de favoritos.
* Seguimiento de pedidos.

Con este proyecto buscamos desarrollar una plataforma moderna, intuitiva y escalable que mejore la experiencia de compra y fortalezca la conexión entre la marca y sus clientes.

---

## Factor Diferencial: Asesor Virtual Inteligente

Como elemento innovador, implementaremos en **Volt** un *chatbot* que funcionará como un asesor virtual de moda. El usuario podrá conversar de manera natural y describir sus necesidades (estilo, ocasión, clima, etc.). El sistema interpretará la intención de la consulta y recomendará productos reales del catálogo que sean semánticamente relevantes.

La idea principal combina un **Modelo de Lenguaje (LLM)** para comprender las conversaciones y un sistema de **búsqueda semántica basada en embeddings** para encontrar las prendas ideales.

### Decisiones técnicas principales

* **Django:** Backend principal que gestionará el chatbot, catálogo de productos, historial de conversaciones, usuarios y lógica de recomendación.
* **Embeddings:** Cada producto tendrá un vector generado a partir de su nombre, descripción, categoría y atributos. Las consultas del usuario se convertirán a vectores usando el mismo modelo.
* **Búsqueda vectorial:** Comparación entre el embedding de la consulta y los embeddings del catálogo para medir similitud semántica.
* **LLM:** Encargado de interpretar la intención, mantener el contexto conversacional y redactar respuestas naturales. *No inventará ni seleccionará productos de forma arbitraria.*
* **Catálogo como fuente de verdad:** El chatbot solo recomendará productos existentes en la base de datos de Volt. Precios, stock, tallas e imágenes se obtendrán siempre de Django.
* **Filtros híbridos:** La búsqueda semántica se combinará con filtros estructurados para condiciones exactas (precio máximo, talla, color, disponibilidad).
* **Ranking:** Los resultados se ordenarán por relevancia semántica y se ajustarán según las restricciones explícitas del usuario.

### Arquitectura conceptual

La separación de responsabilidades se define de la siguiente manera:

* **LLM:** Comprende al usuario y redacta la respuesta final.
* **Embeddings:** Representan semánticamente las consultas y los productos.
* **Búsqueda vectorial:** Encuentra los productos más afines en espacio vectorial.
* **Filtros / Ranking:** Refinan y ordenan los resultados por criterios exactos.
* **Django + Base de datos:** Proporcionan los datos reales y consolidados del catálogo.
* **Frontend:** Despliega la interfaz de chat y las tarjetas de productos recomendados.

---

## Consideración Técnica: Evaluación de Base de Datos

Actualmente se plantea el uso de **SQLite** para la etapa inicial; sin embargo, dado que no está optimizada nativamente para búsqueda vectorial a gran escala, se evalúan dos caminos:

1. Conservar SQLite y realizar el cálculo/comparación de embeddings directamente en Python/Django (viable para catálogos pequeños/medianos).
2. Migrar a una base de datos relacional con soporte vectorial (ej. **PostgreSQL + extension `pgvector`**), lo cual facilitará la escalabilidad y las búsquedas híbridas (SQL + vectores) directamente en el motor de base de datos.

Tener cuenta que es un proyecto academico, por lo que el catalogo no tendra una cantidad muy grande de productos