# Proyecto de Curso: Arquitectura de Software 2026

**Entrega No. 1: Núcleo de Negocio y Exposición de API Profesional**  
Prof. Nicolás Ramírez Vélez

---

## 1. Objetivo de la Entrega

Consolidar el núcleo del sistema mediante la implementación del 50 % al 60 % de las clases de dominio propuestas en sus diagramas.  
Se evaluará la capacidad de exponer esta lógica mediante una capa de presentación moderna (Django Rest Framework), garantizando un desacoplamiento total mediante el uso de Service Layer y patrones creacionales.

---

## 2. Requerimientos Técnicos (Grado Empresarial)

### 2.1. Capa de Dominio e Implementación (Avance)
- Implementar entre el 50% y el 60% de las clases del modelo de datos.  
- El código debe reflejar el uso de tipos de datos adecuados y validaciones de negocio en el nivel de modelo/entidad.

### 2.2. Capa de Aplicación (Service Layer)
- **Prohibido:** Lógica de negocio en las Views o en los Serializers.  
- Cada flujo de negocio principal debe estar orquestado por una clase en `services.py`.  
- Se evaluará el cumplimiento de **SOLID**, especialmente el Principio de Responsabilidad Única (SRP).

### 2.3. Capa de Presentación (DRF)
- Implementación de **Serializers** para la entrada y salida de datos.  
- Uso de **APIView** para el control total de la petición.  
- Manejo correcto de códigos de estado HTTP (201, 400, 404, 409).

### 2.4. Patrones Creacionales
- **Builder:** Obligatorio para la creación de la entidad más compleja de su sistema.  
- **Factory:** Obligatorio para gestionar al menos una dependencia externa o variante de lógica (Notificaciones, pasarelas de pago, o generadores de reportes).

---

## 3. Entregables

La entrega se formaliza mediante un enlace al repositorio de GitHub que contenga:

1. **Código Fuente:** En la rama `main` o `develop`.  
2. **Wiki Técnica:** Documentación detallada que explique:  
   - Justificación de la estructura de carpetas elegida.  
   - Diagrama de secuencia de la funcionalidad más compleja implementada.  
   - Explicación de cómo el sistema está preparado para un **API Gateway** (visión de escalabilidad).

---

## 4. Rúbrica de Evaluación (Escala 0.0 - 5.0)

| Criterio                | Indicador de Logro                                                                 | Peso |
|--------------------------|------------------------------------------------------------------------------------|------|
| Dominio y Avance         | Se ha implementado el 50-60 % de las clases propuestas. Los modelos son coherentes | 1.0  |
| SOLID y Service Layer    | Desacoplamiento total. Lógica en servicios inyectables. No hay "Fat Views/Models". | 1.5  |
| DRF y API Gateway        | Uso profesional de Serializers y APIViews. Wiki explica estrategia de Gateway.     | 1.0  |
| Patrones Creacionales    | Implementación correcta y justificada de Factory y Builder. Código limpio.         | 1.0  |
| Documentación (Wiki)     | Wiki técnica valiosa. Incluye diagramas y justifica decisiones de diseño.          | 0.5  |

---

## Advertencia: Código de Calidad

Cualquier rastro de lógica de negocio (cálculos, validaciones de inventario, etc.) dentro de un archivo `views.py` o en métodos de un **Model** que no sean de persistencia, penalizará la nota de la sección **SOLID** en un 50 %.

---

## Nota: Evaluación de Front End

La capa de presentación será evaluada en la sustentación presencial, donde debe evidenciarse el funcionamiento del Back end desde el lado del usuario.

---

## 5. Instrucciones de Envío

El enlace del repositorio debe ser enviado a través de la plataforma institucional antes de la fecha límite.  
Asegúrese de que el repositorio sea público o de invitar al profesor como colaborador.
