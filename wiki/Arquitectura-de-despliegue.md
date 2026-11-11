# Arquitectura de despliegue de Volt

La instancia EC2 de AWS Academy ejecuta los servicios de Volt con Docker Compose. Nginx recibe las peticiones en el puerto 80 y distribuye el tráfico. PostgreSQL, Redis y los puertos de aplicación se usan dentro de la red de Compose.

```mermaid
flowchart LR
    browser["Navegador"]

    subgraph ec2["AWS Academy · EC2 · Docker Compose"]
        nginx["Nginx · API Gateway"]
        django["Django · Tienda y API REST"]
        notifications["Flask · Notificaciones"]
        chatbot["Flask · Chatbot"]
        postgres[("PostgreSQL")]
        redis[("Redis · Broker")]
        worker["Celery · Indexación"]
        chatDb[("SQLite · Volumen del chatbot")]
    end

    partner["FinanSmart · API del equipo aliado"]
    gemini["Gemini · API externa"]

    browser -->|"HTTP :80"| nginx
    nginx -->|"Tienda, /finansmart/ y /api/v1/"| django
    nginx -->|"/api/v2/notifications/"| notifications
    nginx -->|"/api/chatbot/"| chatbot
    django -->|"Catálogo, usuarios y pedidos"| postgres
    django -->|"Confirmación después del commit"| notifications
    django -->|"Eventos internos de productos"| chatbot
    chatbot -.->|"Encola indexación"| redis
    redis -.->|"Entrega tareas"| worker
    worker -->|"Consulta el catálogo"| django
    worker -->|"Guarda el índice"| chatDb
    chatbot -->|"Consulta índice y conversaciones"| chatDb
    django -.->|"Adapter · resumen financiero"| partner
    chatbot -.->|"Adapters · embeddings y texto"| gemini
    worker -.->|"Adapter · embeddings"| gemini
```

Django mantiene las operaciones de catálogo, carrito y pedidos. El patrón Strangler encamina las rutas de notificaciones y chatbot a sus servicios Flask. Nginx bloquea el acceso público a `/internal/`, que usa Django para comunicar cambios del catálogo al chatbot.

FinanSmart y Gemini requieren configuración en el entorno de ejecución. Para FinanSmart, configurar `FINANSMART_SUMMARY_URL` con una URL accesible desde EC2 y `FINANSMART_TOKEN` con un token de demostración, ya que la vista del resumen es pública. El modo `fake` muestra datos simulados. Para Gemini, configurar `GEMINI_API_KEY` y comprobar la indexación y una consulta desde el widget.
