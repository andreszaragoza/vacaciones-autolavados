# Gestión de vacaciones para autolavados

Aplicación web para que los empleados de varios autolavados pidan sus vacaciones sin que coincidan con las de sus compañeros del mismo autolavado. El encargado de cada autolavado recibe un email para aprobar o rechazar cada solicitud.

Hecha con **Python + Flask + SQLite**. El calendario usa **flatpickr**.

---

## Índice

1. [Qué hace la aplicación](#1-qué-hace-la-aplicación)
2. [Estructura del proyecto](#2-estructura-del-proyecto)
3. [Instalación y arranque](#3-instalación-y-arranque)
4. [Configuración: correo y contraseña del panel](#4-configuración-correo-y-contraseña-del-panel)
5. [Cómo se usa](#5-cómo-se-usa)
6. [Historial de desarrollo paso a paso](#6-historial-de-desarrollo-paso-a-paso)
7. [Base de datos](#7-base-de-datos)
8. [API](#8-api)
9. [Reglas de negocio](#9-reglas-de-negocio)
10. [Problemas frecuentes](#10-problemas-frecuentes)


---

## 1. Qué hace la aplicación

| Quién | Qué puede hacer |
|---|---|
| **Administradora** (panel `/admin`, con contraseña) | Dar de alta autolavados con el email de su encargado, dar de alta o de baja empleados, fijar los días de vacaciones al año de cada uno y ver cuántos le quedan, ver todas las solicitudes, filtrarlas y aprobarlas o rechazarlas. |
| **Empleado** (página principal `/`) | Identificarse con su email, pedir vacaciones en un calendario que bloquea los días ocupados y ver su panel *Mis vacaciones*: días disponibles, calendario del año, sus solicitudes y los días no disponibles. |
| **Encargado** (enlace del email) | Recibir un email por cada solicitud nueva y aprobarla o rechazarla desde el enlace, sin entrar al panel. |
| **Web del negocio** (`/embed`) | Incrustar el formulario y el panel *Mis vacaciones* en otra web (por ejemplo en GoDaddy) con un `<iframe>`, sin menú ni enlace al panel. |

Además:
- Las fechas solo **chocan entre empleados del mismo autolavado**.
- El empleado recibe un **email con el resultado** cuando se aprueba o se rechaza su solicitud.
- El calendario **sombrea los días no disponibles**: en gris los de compañeros, en naranja los propios pendientes y en verde los propios aprobados.
- Cada empleado tiene unos **días de vacaciones al año** (28 por defecto) y **no puede pedir más de los que le quedan**.

---

## 2. Estructura del proyecto

```
Vacaciones/
├── venv/                     ← entorno virtual de Python (no se comparte)
└── Vacaciones/
    ├── app.py                ← servidor Flask: base de datos, API, emails
    ├── requirements.txt      ← dependencias (flask, python-dotenv)
    ├── .env.ejemplo          ← plantilla de configuración (correo y contraseña del panel)
    ├── .env                  ← configuración real (NO se comparte, tiene contraseñas)
    ├── .gitignore            ← evita subir .env, la base de datos y venv
    ├── vacaciones.db         ← base de datos SQLite (se crea sola)
    ├── README.md             ← este documento
    ├── Documentacion.ipynb   ← notebook con la documentación y ejemplos ejecutables
    ├── templates/
    │   ├── base.html         ← plantilla común (menú, estilos, flatpickr)
    │   ├── index.html        ← formulario del empleado (también la versión /embed)
    │   ├── admin.html        ← panel de gestión
    │   ├── login.html        ← pantalla de acceso al panel
    │   └── revisar.html      ← página de aprobación que abre el encargado
    └── static/
        └── estilos.css       ← estilos de toda la app
```

---

## 3. Instalación y arranque

### En este ordenador (el entorno ya está creado)

```powershell
cd C:\Users\anoni\Desktop\Vacaciones\Vacaciones
..\venv\Scripts\python.exe app.py
```

Cuando aparezca `Running on http://127.0.0.1:5000`, abre en el navegador:

- http://127.0.0.1:5000: formulario del empleado
- http://127.0.0.1:5000/embed: el mismo formulario sin menú, para incrustar en otra web
- http://127.0.0.1:5000/admin: panel de gestión (mientras no haya contraseña configurada, en local entra directamente)

**La terminal debe quedarse abierta** mientras uses la app. Para pararla, pulsa `Ctrl+C`.

### En otro ordenador desde cero

Hace falta tener **Python 3.10 o posterior** instalado.

```powershell
cd ruta\a\Vacaciones
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

---

## 4. Configuración: correo y contraseña del panel

Si no hay archivo `.env`, **los emails no se envían**: se escriben en la terminal del servidor. Así se puede probar todo sin una cuenta de correo.

Para enviarlos de verdad:

1. Copia `.env.ejemplo` y llama a la copia `.env`.
2. Si usas Gmail, crea una **contraseña de aplicación** en https://myaccount.google.com/apppasswords. Para eso necesitas tener activada la verificación en dos pasos. La contraseña normal de Gmail **no funciona**.
3. Rellena el archivo:

   ```ini
   BASE_URL=http://127.0.0.1:5000      # dirección de la app (se usa en el enlace del email)
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=tucorreo@gmail.com
   SMTP_PASSWORD=xxxx xxxx xxxx xxxx  # contraseña de aplicación
   MAIL_FROM=tucorreo@gmail.com
   ```

4. **Reinicia el servidor**, porque el `.env` solo se lee al arrancar.

> Mientras la app esté en `127.0.0.1`, el enlace del email **solo se puede abrir desde este ordenador**. Para que el encargado pueda abrirlo desde su móvil, la app tiene que estar publicada en internet y `BASE_URL` tiene que tener la dirección pública.

### Contraseña del panel de gestión

Añade estas dos líneas al `.env` y reinicia el servidor:

```ini
ADMIN_PASSWORD=una-contraseña-larga
SECRET_KEY=64-caracteres-aleatorios
```

- `SECRET_KEY` firma la sesión del panel. Se genera con:
  ```powershell
  ..\venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
  ```
  Si no se pone, la app crea una al arrancar. Funciona igual, pero hay que volver a entrar al panel cada vez que se reinicia el servidor.
- Con contraseña, `/admin` muestra una pantalla de acceso. La sesión dura 12 horas y en el menú aparece **Cerrar sesión**.

| Situación | Qué pasa con el panel |
|---|---|
| Sin `ADMIN_PASSWORD`, arrancada en local con `python app.py` | Abierto, para poder probar |
| Sin `ADMIN_PASSWORD`, publicada en internet | **Cerrado**, con un aviso de que falta configurar la contraseña |
| Con `ADMIN_PASSWORD` | Pide la contraseña, tanto en local como publicada |

El formulario de los empleados (`/` y `/embed`) y el enlace del email del encargado (`/revisar/...`) **no piden contraseña**.

---

## 5. Cómo se usa

### Administradora: configuración inicial (en `/admin`)

1. **Autolavados**: escribe el nombre y el email del encargado y pulsa **Añadir**. Se pueden editar después y pulsar **Guardar**.
2. **Empleados**: escribe el nombre y el email, elige el autolavado, indica los **días al año** (28 por defecto) y pulsa **Añadir**.
   - La columna **Disponibles** muestra cuántos días le quedan este año, por ejemplo *21 de 28*.
   - Los días al año se pueden cambiar en cualquier momento, por ejemplo para alguien a media jornada o que entró a mitad de año.
   - Si un empleado **cambia de autolavado**, elige el nuevo en la lista desplegable y pulsa **Guardar**.
   - Si un empleado **se va**, desmarca *Activo* y pulsa **Guardar**. Ya no podrá pedir vacaciones, pero su historial se conserva. Los empleados dados de baja aparecen en gris.

### Empleado: pedir vacaciones (en `/`)

1. Escribe su email y pulsa **Continuar** (o **Enter**).
2. Debajo del email aparecen su nombre y su autolavado, y el selector de fechas, que no deja elegir días ocupados.
3. Elige el rango de fechas y pulsa **Enviar solicitud**. Si solo elige un día, ese día cuenta como inicio y fin.
4. A la derecha (debajo en el móvil) ve el panel **Mis vacaciones**:
   - **Contadores:** días disponibles (el dato destacado), días al año, aprobados y pendientes.
   - **Barra de progreso:** *"Has usado 7 de 28 días · te quedan 21"*.
   - **Calendario del año**, con los 12 meses y estos colores:

     | Color | Significado |
     |---|---|
     | Verde | Sus vacaciones aprobadas |
     | Naranja | Sus vacaciones pendientes |
     | Rosa tachado | Sus solicitudes rechazadas |
     | Gris con rayas | **No disponible**: lo ha cogido un compañero de su autolavado |
     | Gris claro | Días ya pasados |
     | Recuadro azul | Hoy |

   - **Mis solicitudes:** lista con fechas, días, estado y comentario del encargado.
   - **Días no disponibles:** lista de las fechas que ya han cogido compañeros de su autolavado. No muestra nombres.
   - Las flechas **‹ 2026 ›** cambian de año.

### Encargado: aprobar o rechazar

1. Recibe un email *"Solicitud de vacaciones: Ana (Centro)"* con las fechas y un enlace.
2. Abre el enlace, añade un comentario si quiere y pulsa **Aprobar** o **Rechazar**.
3. El empleado recibe un email con el resultado.

También se puede aprobar o rechazar desde el panel `/admin`, en la sección **Solicitudes**.

### Incrustar el formulario en la web del negocio (GoDaddy)

La dirección `/embed` muestra solo el formulario y el panel *Mis vacaciones*, sin menú, sin enlace al panel de gestión y con fondo transparente.

**Requisito:** la app tiene que estar publicada en internet con **HTTPS**. Los navegadores bloquean un `<iframe>` que apunte a `http://` o a `127.0.0.1` dentro de una web `https://`.

Código para pegar en la web, sustituyendo la dirección por la de la app publicada:

```html
<iframe id="vacaciones" src="https://DIRECCION-DE-LA-APP/embed"
        style="width:100%; height:1100px; border:0" title="Solicitar vacaciones"></iframe>
<script>
  // Opcional: ajusta la altura del iframe al contenido
  window.addEventListener("message", function (e) {
    if (e.data && e.data.tipo === "vacaciones-altura") {
      document.getElementById("vacaciones").style.height = e.data.altura + "px";
    }
  });
</script>
```

Dónde pegarlo según el producto de GoDaddy:

| Producto | Dónde |
|---|---|
| **Websites + Marketing** (creador de páginas) | Añadir sección → **HTML** (*Insertar código*). Este editor mete el código dentro de su propio marco, así que el ajuste automático de altura puede no funcionar; en ese caso deja una altura fija generosa, por ejemplo `1400px`. |
| **WordPress** | Bloque **HTML personalizado** en una página, y añadir esa página al menú. |
| **Hosting con cPanel** | En cualquier página HTML. También se puede alojar la propia app ahí con *Setup Python App*. |

El panel de gestión (`/admin`) y la página del encargado (`/revisar/...`) **no se pueden incrustar**: envían la cabecera `X-Frame-Options: DENY`, que impide que otra web los meta en un iframe para engañar al usuario.

---

## 6. Historial de desarrollo paso a paso

### Paso 0: Código inicial

El punto de partida fue un `app.py` con Flask y SQLite. Tenía:
- una tabla `solicitudes`;
- un endpoint `GET /api/ocupadas` que devolvía las fechas ocupadas en el formato `{from, to}` de flatpickr.

### Paso 1: Revisión del código inicial

Problemas detectados:
1. `init_db()` solo se ejecutaba con `python app.py`. Con `flask run` la tabla no se creaba.
2. Las fechas pedidas por cualquier empleado bloqueaban a todos los demás.
3. No había forma de crear ni de gestionar solicitudes: faltaban el `POST`, el panel y el HTML.
4. El servidor no validaba nada.

### Paso 2: Primera versión completa

- Se instaló Flask en el `venv`.
- `init_db()` pasó a ejecutarse al importar el módulo, y la base de datos se guarda junto a `app.py`.
- Endpoints nuevos: `POST /api/solicitudes`, `GET /api/solicitudes` y `POST /api/solicitudes/<id>/estado`.
- Validaciones: email válido, formato de fecha, inicio ≤ fin, sin fechas pasadas y sin solapamientos.
- La comprobación de solapamiento se hace dentro de una transacción `BEGIN IMMEDIATE`, para que dos peticiones simultáneas no puedan reservar los mismos días.
- Páginas `index.html` (formulario con flatpickr en español, en modo rango) y `admin.html` (tabla con filtro y botones Aprobar/Rechazar).
- Se probó todo con el cliente de pruebas de Flask.

### Paso 3: Error `ERR_CONNECTION_REFUSED`

La página no cargaba porque **el servidor no estaba arrancado**. Se explicó que la terminal con `python app.py` tiene que quedarse abierta mientras se usa la app.

### Paso 4: Varios autolavados y emails

Requisito: la amiga tiene varios autolavados. Las vacaciones solo deben chocar dentro del mismo autolavado y el encargado debe recibir un email.

- Tabla nueva `autolavados` (nombre y email del encargado). La tabla `solicitudes` gana `autolavado_id` y `token`.
- **Migración automática**: si la base de datos es de la versión anterior, `init_db()` añade las columnas que faltan sin perder datos.
- La comprobación de solapamiento y `/api/ocupadas` filtran por autolavado.
- **Emails** con `smtplib`. La configuración se lee del `.env` con `python-dotenv`. Se envían en segundo plano para que el formulario no se quede esperando. Sin `.env`, se escriben en la consola.
- Cada solicitud tiene un **token aleatorio**. El email al encargado incluye el enlace `/revisar/<token>`, donde puede aprobar o rechazar.
  - La acción se hace con un formulario `POST`, no al abrir el enlace, para que los antivirus o las vistas previas del correo no aprueben solicitudes por accidente.
- Al resolver la solicitud se envía un email al empleado.
- Se añadieron `.env.ejemplo` y `.gitignore`.

### Paso 5: Gestión de empleados

Requisito: que la amiga pueda dar de alta autolavados **y empleados** desde la web.

- Tabla nueva `empleados` (nombre, email único en minúsculas, autolavado y activo). La tabla `solicitudes` gana `empleado_id`.
- Sección **Empleados** en el panel: alta, edición, cambio de autolavado y baja.
- El formulario del empleado ahora **solo pide el email**. El nombre y el autolavado salen de su ficha, así que no puede elegir otro autolavado. Si el email no está dado de alta, no puede pedir vacaciones.
- Endpoint nuevo `GET /api/identificar?email=...`.

### Paso 6: La solicitud no se enviaba

**Causa:** el recargador automático de Flask (modo debug) se reinició a mitad de los cambios de código y se quedó ejecutando una versión a medias. Esa versión daba `NameError` en cada envío.

**Solución:**
- Se reinició el servidor.
- El formulario ahora muestra *"Error del servidor. Inténtalo de nuevo."* si el servidor falla. Antes no mostraba nada.

### Paso 7: Días no disponibles sombreados

- `/api/ocupadas` acepta `email` y devuelve en cada rango `estado` y `propia`.
- El calendario usa `onDayCreate` de flatpickr para pintar cada día con rayas:
  - **gris tachado**: cogido por un compañero;
  - **naranja**: tuyo y pendiente;
  - **verde**: tuyo y aprobado.
- Se añadió una leyenda debajo del calendario y un aviso al pasar el ratón por encima.

### Paso 8: Los correos no llegaban

**Causa:** no existía el archivo `.env`, así que los emails solo se escribían en la consola. Se explicó cómo crear la contraseña de aplicación de Gmail y el `.env`. Ver [sección 4](#4-configuración-correo-y-contraseña-del-panel).

### Paso 9: Documentación

Se creó este `README.md` y el notebook `Documentacion.ipynb`.

### Paso 10: Repositorio propio en git

- La carpeta del proyecto estaba dentro del repositorio git del Escritorio, que tiene documentos personales y está conectado a GitHub. Se creó un **repositorio independiente** (`git init -b main`) solo para `Vacaciones/Vacaciones`.
- Se comprobó que el primer commit solo incluye los archivos del proyecto: ni `.env`, ni `vacaciones.db`, ni `__pycache__`.
- Para subirlo a GitHub: crear un repositorio **vacío** en https://github.com/new y después ejecutar:
  ```powershell
  git remote add origin https://github.com/USUARIO/REPO.git
  git push -u origin main
  ```

### Paso 11: Configuración real del correo

- **Problema 1:** los datos del correo se habían escrito en `.env.ejemplo`. La app no lee ese archivo, y además se sube a git, así que la contraseña se habría publicado. Se pasaron a `.env`, que está ignorado, y `.env.ejemplo` volvió a ser la plantilla.
- **Problema 2:** Gmail cortaba la conexión al iniciar sesión porque se usaba la contraseña normal de la cuenta. Se creó una **contraseña de aplicación** (16 letras).
- **Resultado:** se probó el inicio de sesión y se envió un correo de prueba. Después se reinició el servidor para que leyera el `.env`.

### Paso 12: Formulario de solicitud más profesional

- Una sola tarjeta: el título *Solicitar vacaciones* y el campo **Tu email** con el botón **Continuar** al lado.
- Al reconocer el email, aparecen debajo el nombre del empleado con su autolavado en una etiqueta y el selector de fechas.
- Se quitaron "Hola" y "¿No eres tú?". Si se cambia el email, el paso de fechas se oculta solo y vuelve a salir *Continuar*.
- Se corrigió un fallo: las reglas `display: flex` del CSS anulaban el atributo `hidden`. Se añadió `[hidden] { display: none !important; }`.

### Paso 13: Panel "Mis vacaciones" y días anuales

- Columna nueva `empleados.dias_anuales` (28 por defecto), añadida con migración automática. Se edita en el panel, donde también se ve la columna *Disponibles*.
- Funciones `dias_por_anio()`, que reparte un rango que cruza el fin de año, y `dias_usados()`, que suma los días aprobados y pendientes de un empleado en un año.
- Endpoint nuevo `GET /api/resumen?email=&anio=`.
- **Límite:** al crear una solicitud se comprueba, para cada año que toca, que no supere los días que quedan. La comprobación va dentro de la misma transacción que el solapamiento.
- Panel lateral con contadores, barra de progreso, calendario anual de 12 meses, leyenda, lista de solicitudes y selector de año.
- Se cuentan **días naturales**. Falta confirmar con la administradora si deben ser laborables.

### Paso 14: Días no disponibles en el panel

- El calendario anual pinta en **gris con rayas** los días cogidos por compañeros del mismo autolavado (pendientes o aprobados), y en gris claro los días pasados.
- Si un día es a la vez del empleado y de un compañero, se ve el estado propio.
- Sección nueva **Días no disponibles** con la lista de fechas futuras bloqueadas. No muestra nombres de compañeros, por privacidad.
- Se reutiliza `/api/ocupadas`, que ya marca con `propia` lo que es del propio empleado.

### Paso 15: Contraseña del panel de gestión

- Variables nuevas en `.env`: `ADMIN_PASSWORD` y `SECRET_KEY`. La contraseña no está en el código, así que la administradora la puede poner o cambiar sin tocarlo.
- Pantalla de acceso `/admin/login` y salida `/admin/logout`.
  - La contraseña se compara con `hmac.compare_digest`, que tarda lo mismo acierte o falle.
  - Cada intento fallido espera 1 segundo, para frenar a quien intente adivinarla.
- El decorador `@solo_admin` protege `/admin` y toda la API de gestión: autolavados, empleados, la lista de solicitudes y aprobar o rechazar. Sin sesión, las páginas redirigen al acceso y la API responde `401`.
- **Sin contraseña configurada**, el panel solo se abre en local con `python app.py` (modo debug y petición desde `127.0.0.1`). Publicada en internet, queda cerrada con un aviso.
- Cookie de sesión `HttpOnly` y `SameSite=Lax`, que pasa a `Secure` si `BASE_URL` empieza por `https://`. La sesión dura 12 horas.
- Si la sesión caduca mientras el panel está abierto, el panel vuelve solo a la pantalla de acceso.

### Paso 16: Versión para incrustar en la web del negocio

- La web de la administradora está en **GoDaddy**. Se creó la ruta `/embed`, que usa la misma plantilla que `/` con `embed=True`: sin menú, sin enlace al panel y con fondo transparente.
- La página avisa a la web contenedora de la altura que necesita, con `postMessage` y un `ResizeObserver`, para que el `<iframe>` crezca con el contenido.
- `/admin` y `/revisar` envían `X-Frame-Options: DENY` para que no se puedan incrustar. `/embed` sí se puede.
- El código para pegar y dónde hacerlo en cada producto de GoDaddy está en la [sección 5](#5-cómo-se-usa).

---

## 7. Base de datos

SQLite, en el archivo `vacaciones.db`. Se crea y se actualiza sola al arrancar.

```
autolavados                empleados                    solicitudes
───────────                ─────────                    ───────────
id  PK                     id  PK                       id  PK
nombre  (único)            nombre                       empleado        (copia del nombre)
email_encargado            email  (único, minúsculas)   email           (copia del email)
                           autolavado_id → autolavados  fecha_inicio    YYYY-MM-DD
                           activo  (1/0)                fecha_fin       YYYY-MM-DD
                           dias_anuales  (28)           estado          Pendiente | Aprobada | Rechazada
                                                        comentario
                                                        creada
                                                        autolavado_id → autolavados
                                                        empleado_id   → empleados
                                                        token           (enlace del email, único)
```

La solicitud guarda una copia del nombre, del email y del autolavado del momento en que se hizo. Así, si el empleado cambia de autolavado más adelante, sus solicitudes antiguas no cambian.

Para empezar con la base de datos vacía: para el servidor, borra `vacaciones.db` y vuelve a arrancar.

---

## 8. API

Las respuestas de `/api/...` son JSON. Los errores tienen la forma `{"error": "mensaje"}`. Las rutas marcadas con 🔒 necesitan haber iniciado sesión en el panel.

| Método | Ruta | Para qué |
|---|---|---|
| GET | `/` | Formulario del empleado |
| GET | `/embed` | Formulario sin menú, para incrustar con `<iframe>` |
| GET | `/admin` 🔒 | Panel de gestión |
| GET / POST | `/admin/login` | Pantalla de acceso al panel |
| GET | `/admin/logout` | Cerrar sesión |
| GET / POST | `/revisar/<token>` | Página de aprobación del encargado (protegida por el token) |
| GET | `/api/autolavados` 🔒 | Lista de autolavados |
| POST | `/api/autolavados` 🔒 | Crear `{nombre, email_encargado}` |
| PUT | `/api/autolavados/<id>` 🔒 | Editar `{nombre, email_encargado}` |
| GET | `/api/empleados` 🔒 | Lista de empleados con `dias_anuales` y `disponibles` del año actual |
| POST | `/api/empleados` 🔒 | Crear `{nombre, email, autolavado_id, dias_anuales?}` |
| PUT | `/api/empleados/<id>` 🔒 | Editar `{nombre, email, autolavado_id, activo, dias_anuales}` |
| GET | `/api/identificar?email=` | Reconoce a un empleado activo y devuelve `{nombre, autolavado_id, autolavado}` |
| GET | `/api/resumen?email=&anio=` | Panel *Mis vacaciones*: `{anio, dias_anuales, aprobados, pendientes, disponibles, solicitudes[]}` |
| GET | `/api/ocupadas?autolavado=&email=` | Rangos ocupados del autolavado `[{from, to, estado, propia}]` |
| GET | `/api/solicitudes` 🔒 | Todas las solicitudes (sin el token) |
| POST | `/api/solicitudes` | Crear `{email, fecha_inicio, fecha_fin}` |
| POST | `/api/solicitudes/<id>/estado` 🔒 | Resolver `{estado: "Aprobada" \| "Rechazada", comentario}` |

Códigos de respuesta: `400` dato no válido, `401` falta iniciar sesión en el panel, `403` email no dado de alta, `404` no encontrado, `409` solapamiento, días insuficientes, nombre o email duplicado, o solicitud que ya no está pendiente.

---

## 9. Reglas de negocio

- Solo pueden pedir vacaciones los **empleados activos** dados de alta.
- No se pueden pedir **fechas pasadas** ni rangos con el inicio posterior al fin.
- Una solicitud **choca** con otra si es del **mismo autolavado**, está *Pendiente* o *Aprobada* y comparte al menos un día.
- Las solicitudes *Rechazadas* **liberan** sus días, tanto en el calendario como en el contador de días disponibles.
- Cada empleado tiene `dias_anuales` días por año natural (28 por defecto). **Disponibles = días al año − aprobados − pendientes.** No se puede pedir más de lo disponible.
- Los días se cuentan como **días naturales**, incluidos fines de semana y festivos.
- Una solicitud que cruza el fin de año descuenta los días de cada año por separado. Por ejemplo, del 29/12 al 03/01 son 3 días de un año y 3 del siguiente.
- Solo se pueden resolver solicitudes *Pendientes*. Una vez aprobada o rechazada, no se puede cambiar.
- Los emails de empleados se guardan en minúsculas, así que da igual cómo se escriban.

---

## 10. Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `ERR_CONNECTION_REFUSED` | El servidor no está arrancado | Ejecuta `python app.py` y deja la terminal abierta |
| La solicitud no se envía o sale "Error del servidor" | El servidor quedó con código antiguo tras un cambio | `Ctrl+C` y vuelve a arrancar |
| No llegan los correos | Falta el `.env`, o la contraseña es la normal de Gmail | Ver [sección 4](#4-configuración-correo-y-contraseña-del-panel) y mira en la carpeta de spam |
| "Ese email no está dado de alta" | El empleado no existe o está inactivo | Dalo de alta o actívalo en `/admin` |
| "Pides N días… solo te quedan M" | El empleado ya ha gastado sus días del año | Revisa sus días al año en `/admin` o rechaza alguna solicitud pendiente |
| Gmail corta la conexión al iniciar sesión | Se está usando la contraseña normal de Gmail | Usa una contraseña de aplicación (ver sección 4) |
| El enlace del email no abre en el móvil | La app está en `127.0.0.1` | Publicar la app y poner la dirección pública en `BASE_URL` |
| El panel dice "está cerrado porque todavía no se ha configurado la contraseña" | La app está publicada (o sin modo debug) y falta `ADMIN_PASSWORD` | Añade `ADMIN_PASSWORD` al `.env` y reinicia |
| Hay que volver a entrar al panel tras cada reinicio | Falta `SECRET_KEY` en el `.env` | Genera una y añádela (ver sección 4) |
| El iframe en la web sale en blanco | La app no está publicada con `https://`, o se está incrustando `/admin` | Publica la app con HTTPS e incrusta `/embed` |
| Error `Address already in use` | Ya hay otro servidor en el puerto 5000 | Cierra el otro servidor |

---


