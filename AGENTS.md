### AGENTS.md

### Propósito y alcance

Estas instrucciones aplican únicamente a **Mayu Bodega** y a sus subdirectorios. El proyecto administra de forma integral el inventario, las ventas y el crédito de una bodega o tienda. 

El sistema está diseñado para cumplir con los siguientes objetivos core: 

* **Catálogo Comercial:** Registrar productos con su información comercial detallada, soportando ingresos tanto por artículo individual como por paquete o bulto.
* **Gestión Multimedia:** Asociar y administrar imágenes para cada artículo del catálogo, facilitando su identificación visual rápida en la interfaz de ventas.
* **Control de Stock:** Registrar entradas de mercancía, gestionar existencias y permitir salidas de inventario justificadas mediante notas de salida físicas o administrativas.
* **Multimoneda:** Operar de forma nativa con Bolívares (VES) y Dólares Estadounidenses (USD), mostrando importes en ambas monedas cuando corresponda.
* **Gestión de Crédito (Fiado):** Registrar ventas pagadas y ventas fiadas. Cuando un cliente liquide una deuda en bolívares, el sistema debe calcular el monto exacto basado en la tasa del dólar vigente al momento del pago.
* **Auditoría de Clientes:** Identificar clientes, saldos pendientes y registros históricos de abonos a crédito.
* **Flexibilidad en Facturación:** Permitir la configuración global (habilitar/deshabilitar) para facturar artículos cuya existencia sea igual a cero (0).
* **Configuración de Recargos:** El recargo se resuelve por línea con la precedencia `Artículo > Categoría > Tienda`. El porcentaje por defecto de la tienda (inicialmente 0%) actúa como último nivel. Las categorías agrupan artículos y pueden tener un porcentaje compartido; un artículo con valor propio lo reemplaza. El cajero puede ajustar el porcentaje de cada línea en el carrito.

*No amplíes el alcance sin confirmación del usuario.* 

### Decisiones pendientes

Antes de implementar una regla que no esté definida, pregunta de forma concreta. No inventes decisiones comerciales. Deben acordarse, entre otras: 

* Política de almacenamiento de imágenes (uso de almacenamiento local en el servidor, servicios en la nube como AWS S3 o Cloudinary, etc.).
* Límites de tamaño máximo y formatos permitidos para la carga de imágenes de productos.
* Política definitiva para cambiar precios expresados en VES o USD.
* Momento exacto de captura de la tasa oficial y reglas de redondeo monetario.
* Si una venta fiada admite abonos parciales, múltiples deudas acumuladas o únicamente pago total.
* Tratamiento de anulaciones, devoluciones de mercancía y productos con fecha de vencimiento.

**Convención Inicial:** Se usa el **USD** como moneda base de precios. El cálculo a **VES** se realiza mediante la tasa vigente publicada por el Banco Central de Venezuela (https://www.bcv.org.ve/) expresada como “VES por 1 USD”. El backend guardará por separado la fecha de vigencia publicada por el BCV y la fecha de consulta de la API. 

### Reglas del dominio

### Productos e Imágenes

* **Definición de Artículo:** Representa un artículo comercial con campos estrictos: Nombre del artículo, código generado por el sistema, código de barra, unidad de medida, marca, etc. Ejemplo de nomenclatura estándar: "Tostones picantes con limón TOM 270G".
* **Imágenes de Artículos:** Cada producto puede tener imágenes asociadas para su identificación visual en el punto de venta móvil. El sistema debe optimizar estas imágenes automáticamente para evitar el consumo excesivo de datos móviles y almacenamiento.
* **Unidades de Entrada:** El sistema debe permitir el ingreso de mercancía bajo dos modalidades: artículo individual o empaque/paquete/bulto (asociando la equivalencia de unidades internas por bulto).
* **Integridad del Catálogo:** No dupliques productos por cambiar únicamente su presentación o código. Define la clave mínima y las restricciones según el catálogo real. Usa siempre una clave única estable en lugar del nombre para identificadores y relaciones.

### Entradas, Salidas e Inventario

* **Flujo de Entrada:** La recepción de mercancía registra producto, cantidad, fecha, costo de compra, proveedor y usuario responsable.
* **Notas de Salida:** Para rebajar stock por mermas, consumo interno o pérdidas, se debe emitir una "Nota de Salida" explícita que descuente las unidades del inventario de forma justificada y auditable.
* **Facturación con Stock Cero:** El sistema debe contar con un *toggle* o parámetro de configuración. Si está habilitado, permitirá vender y facturar artículos con existencia cero (0); si está deshabilitado, bloqueará la venta por falta de stock.
* **Persistencia:** Mantén un historial inmutable de movimientos de inventario (StockMovement). No borres movimientos para corregir stock; usa transacciones de base de datos para asegurar que las ventas/entradas se apliquen por completo o se reviertan.

### Moneda y tasa de cambio

* **Precisión Financiera:** Representa VES y USD mediante códigos ISO de moneda. Guarda los importes con precisión decimal estricta; **está prohibido usar punto flotante (float/double) para dinero**.
* **Sincronización:** El backend automatiza la consulta de la tasa del BCV cada hora. React consume la tasa validada mediante la API. Si la sincronización falla, un administrador puede registrar una tasa MANUAL de fallback sin sobreescribir el historial oficial.
* **Inmutabilidad Histórica:** En ventas y créditos se guarda la tasa aplicada en ese instante. Las fluctuaciones de tasa futuras no recalculan transacciones pasadas, excepto al momento de liquidar saldos de deudas fiadas en bolívares.

### Ventas y crédito

* **Tipificación:** Separa una venta pagada de una venta fiada mediante un estado o tipo explícito.
* **Venta Fiada:** Asocia obligatoriamente un cliente, productos, cantidades, precios unitarios, total, moneda, el porcentaje de recargo aplicado y la tasa del momento.
* **Cálculo de Deuda al Cobro:** Cuando el cliente paga su deuda fiada en bolívares (VES), el sistema debe tomar el saldo pendiente en USD y multiplicarlo por la **tasa actual del dólar** del día del pago, garantizando el valor real del dinero.
* **Abonos:** Registra los pagos como operaciones independientes vinculadas a la deuda. Las correcciones se hacen mediante anulaciones o reversos auditables; nunca borrando registros.

### Backend: Django

* **API y Multimedia:** Usa Django con Django REST Framework (DRF). El backend debe encargarse de recibir las imágenes de los productos, validarlas, procesar su redimensión y compresión (por ejemplo, convirtiéndolas a formatos eficientes como WebP) y almacenar las rutas de acceso de manera segura.
* **Arquitectura:** Aloja la lógica de negocio en servicios, modelos o funciones de dominio; evita separar validaciones críticas en vistas o serializers.
* **Seguridad y Permisos:** Define permisos explícitos basados en roles para consultar, crear, modificar imágenes, emitir notas de salida y procesar pagos.
* **Restricciones de BD:** Usa restricciones nativas (CheckConstraints, UniqueConstraints) para evitar stocks negativos inválidos, importes corruptos o estados inexistentes.
* **Logs Seguros:** Configura la zona horaria explícita y nunca registres credenciales, tokens o datos sensibles de clientes en los logs del sistema.

### Frontend: React (Mobile-First Architecture)

### 1. Enfoque Mobile-First y Diseño de Experiencia

* **Diseño e Interfaz:** Desarrolla la aplicación con un enfoque estrictamente **Mobile-First**. Las interfaces de venta deben optimizarse para pantallas pequeñas, navegación táctil y zonas de alcance del pulgar, desplegando las imágenes de los productos en cuadrículas o listas compactas y visuales.
* **Aprovechamiento del Espacio:** Utiliza componentes compactos pero legibles. Las imágenes de los artículos deben tener dimensiones fijas y proporcionales para evitar saltos de diseño (*Layout Shifts*) mientras se cargan.
* **Robustez de UI:** Incluye obligatoriamente estados de carga (*skeletons* para las listas de productos e imágenes), estados vacíos (*empty states*) descriptivos, mensajes de error accesibles y soporte para imágenes de marcador de posición (*placeholders*) si un artículo no tiene foto.

### 2. Stack Tecnológico y Tipado

* **Consistencia del Stack:** Usa **React** y el stack tecnológico ya existente en el proyecto. Está prohibido introducir frameworks alternativos, routers, gestores de estado o librerías de datos adicionales sin una justificación técnica aprobada.
* **TypeScript por Defecto:** Prefiere **TypeScript** para todo el código nuevo, incluyendo los tipados para archivos multimedia e inputs de formularios de carga de imágenes.

### 3. Arquitectura de Componentes y Lógica

* **Separación de Conceptos:** Mantén los componentes visuales enfocados exclusivamente en la presentación y la interacción del usuario. Extrae toda la lógica de compresión del lado del cliente (si aplica) o peticiones multipart hacia hooks personalizados o utilidades.
* **Hooks Personalizados:** Diseña *custom hooks* que sigan la convención de nombres useX. Cada hook debe tener una única responsabilidad clara, un alcance delimitado y una API (*inputs/outputs*) lo más pequeña posible.
* **Rendimiento Multimedia:** Implementa técnicas de carga diferida (*lazy loading*) para las imágenes de los artículos que no estén inmediatamente en pantalla, reduciendo el consumo de memoria y CPU en dispositivos móviles de gama baja o conexiones lentas.

### 4. Gestión de Datos, API y Finanzas

* **Consumo de API:** Centraliza todas las llamadas HTTP en un cliente de API unificado. Las cargas de imágenes deben realizarse utilizando el formato adecuado (FormData/multipart/form-data) de forma explícita y controlando los estados de progreso de carga si es necesario.
* **Caché y Estado Remoto:** Reutiliza las librerías de caché de estado remoto existentes en el proyecto (como React Query o RTK Query) para almacenar en caché las listas de productos e imágenes, evitando peticiones repetitivas al servidor.

### 5. Comportamiento predeterminado: herramientas y scripts reutilizables

Este proyecto **acumula** sus scripts de diagnóstico y prueba. No los borres al terminar una tarea.

* **No borres scripts de prueba ni de diagnóstico.** Aunque parezcan obsoletos, forman parte del conocimiento acumulado del proyecto. Reutilízalos antes de escribir algo nuevo.
* **Ubicación única:** todo script de diagnóstico, verificación o reparación vive en `backend/tools/`. Nunca dejes scripts sueltos en la raíz de `backend/`, junto a `manage.py`, ni en el sistema de archivos temporal del equipo.
* **Reutilizar antes de crear:** antes de escribir un script, lee `backend/tools/README.md` y el `--help` de las herramientas existentes. Si falta una variación, **añade un argumento** al script más cercano en lugar de duplicarlo.
* **Indexado:** toda herramienta nueva debe quedar documentada en la tabla de `backend/tools/README.md` con su propósito y si escribe o no en la base de datos.
* **Solo lectura por defecto:** cualquier script que modifique la base de datos o borre archivos debe usar `--apply`, imprimir primero el plan de cambios y abortar sin ese flag. Apóyate en `require_apply()` de `backend/tools/_common.py`.
* **Sin credenciales en el código:** las contraseñas se leen de variables de entorno (`MAYU_API_URL`, `MAYU_USERNAME`, `MAYU_PASSWORD`) o de un prompt interactivo. Nunca las escribas en un archivo, en el `README` ni en los logs.
* **No destructivo por accidente:** antes de ejecutar un script contra la base de datos real, confirma si el modelo lo protege. Los `PROTECT` de las claves foráneas son deliberados: si un script los dispara, el script está mal, no los datos.
* **Pruebas reales aparte:** el código que debe permanecer en el repositorio como regresión va en los archivos de tests de cada app (`tests.py`, `test_*.py`), no en `backend/tools/`. `backend/tools/` es para investigaciones manuales y reparadoras.