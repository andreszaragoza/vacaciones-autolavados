# Gestión de vacaciones para autolavados

Aplicación web para que los empleados de varios autolavados pidan sus vacaciones sin que coincidan con las de sus compañeros del mismo autolavado. El encargado de cada autolavado recibe un email para aprobar o rechazar cada solicitud.

Hecha con **Python + Flask + SQLite**. El calendario usa **flatpickr**.

---

## Índice

1. [Qué hace la aplicación](#1-qué-hace-la-aplicación)
2. [Estructura del proyecto](#2-estructura-del-proyecto)
3. [Instalación y arranque](#3-instalación-y-arranque)
4. [Configurar el envío de correos](#4-configurar-el-envío-de-correos)
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
| **Administradora** (panel `/admin`) | Dar de alta autolavados con el email de su encargado, dar de alta o de baja empleados, ver todas las solicitudes, filtrarlas y aprobarlas o rechazarlas. |
| **Empleado** (página principal `/`) | Identificarse con su email, ver el calendario de su autolavado con los días ocupados y pedir vacaciones. |
| **Encargado** (enlace del email) | Recibir un email por cada solicitud nueva y aprobarla o rechazarla desde el enlace, sin entrar al panel. |

Además:
- Las fechas solo **chocan entre empleados del mismo autolavado**.
- El empleado recibe un **email con el resultado** cuando se aprueba o se rechaza su solicitud.
- El calendario **sombrea los días no disponibles**: en gris los de compañeros, en naranja los propios pendientes y en verde los propios aprobados.

---

## 2. Estructura del proyecto

```
Vacaciones/
├── venv/                     ← entorno virtual de Python (no se comparte)
└── Vacaciones/
    ├── app.py                ← servidor Flask: base de datos, API, emails
    ├── requirements.txt      ← dependencias (flask, python-dotenv)
    ├── .env.ejemplo          ← plantilla de configuración del correo
    ├── .env                  ← configuración real (NO se comparte, tiene contraseñas)
    ├── .gitignore            ← evita subir .env, la base de datos y venv
    ├── vacaciones.db         ← base de datos SQLite (se crea sola)
    ├── README.md             ← este documento
    ├── Documentacion.ipynb   ← notebook con la documentación y ejemplos ejecutables
    ├── templates/
    │   ├── base.html         ← plantilla común (menú, estilos, flatpickr)
    │   ├── index.html        ← formulario del empleado
    │   ├── admin.html        ← panel de gestión
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
- http://127.0.0.1:5000/admin: panel de gestión

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

## 4. Configurar el envío de correos

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

> Mientras la app esté en `127.0.0.1`, el enlace del email **solo se puede abrir desde este ordenador**. Para que el encargado pueda abrirlo desde su móvil, la app tiene que estar publicada en internet y `BASE_URL` tiene que tener la dirección pública. Ver [Pendiente](#11-pendiente).

---

## 5. Cómo se usa

### Administradora: configuración inicial (en `/admin`)

1. **Autolavados**: escribe el nombre y el email del encargado y pulsa **Añadir**. Se pueden editar después y pulsar **Guardar**.
2. **Empleados**: escribe el nombre y el email, elige el autolavado y pulsa **Añadir**.
   - Si un empleado **cambia de autolavado**, elige el nuevo en la lista desplegable y pulsa **Guardar**.
   - Si un empleado **se va**, desmarca *Activo* y pulsa **Guardar**. Ya no podrá pedir vacaciones, pero su historial se conserva. Los empleados dados de baja aparecen en gris.

### Empleado: pedir vacaciones (en `/`)

1. Escribe su email y pulsa **Continuar**.
2. Ve *"Hola Ana · Centro"* y el calendario de su autolavado con los días ocupados sombreados.
3. Elige el rango de fechas y pulsa **Enviar solicitud**. Si solo elige un día, ese día cuenta como inicio y fin.

### Encargado: aprobar o rechazar

1. Recibe un email *"Solicitud de vacaciones: Ana (Centro)"* con las fechas y un enlace.
2. Abre el enlace, añade un comentario si quiere y pulsa **Aprobar** o **Rechazar**.
3. El empleado recibe un email con el resultado.

También se puede aprobar o rechazar desde el panel `/admin`, en la sección **Solicitudes**.

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

**Causa:** no existía el archivo `.env`, así que los emails solo se escribían en la consola. Se explicó cómo crear la contraseña de aplicación de Gmail y el `.env`. Ver [sección 4](#4-configurar-el-envío-de-correos).

### Paso 9: Documentación

Se creó este `README.md` y el notebook `Documentacion.ipynb`.

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
                                                        estado          Pendiente | Aprobada | Rechazada
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

Todas las respuestas son JSON. Los errores tienen la forma `{"error": "mensaje"}`.

| Método | Ruta | Para qué |
|---|---|---|
| GET | `/` | Formulario del empleado |
| GET | `/admin` | Panel de gestión |
| GET / POST | `/revisar/<token>` | Página de aprobación del encargado |
| GET | `/api/autolavados` | Lista de autolavados |
| POST | `/api/autolavados` | Crear `{nombre, email_encargado}` |
| PUT | `/api/autolavados/<id>` | Editar `{nombre, email_encargado}` |
| GET | `/api/empleados` | Lista de empleados |
| POST | `/api/empleados` | Crear `{nombre, email, autolavado_id}` |
| PUT | `/api/empleados/<id>` | Editar `{nombre, email, autolavado_id, activo}` |
| GET | `/api/identificar?email=` | Reconoce a un empleado activo y devuelve `{nombre, autolavado_id, autolavado}` |
| GET | `/api/ocupadas?autolavado=&email=` | Rangos ocupados del autolavado `[{from, to, estado, propia}]` |
| GET | `/api/solicitudes` | Todas las solicitudes (sin el token) |
| POST | `/api/solicitudes` | Crear `{email, fecha_inicio, fecha_fin}` |
| POST | `/api/solicitudes/<id>/estado` | Resolver `{estado: "Aprobada" \| "Rechazada", comentario}` |

Códigos de respuesta: `400` dato no válido, `403` email no dado de alta, `404` no encontrado, `409` solapamiento, nombre o email duplicado, o solicitud que ya no está pendiente.

---

## 9. Reglas de negocio

- Solo pueden pedir vacaciones los **empleados activos** dados de alta.
- No se pueden pedir **fechas pasadas** ni rangos con el inicio posterior al fin.
- Una solicitud **choca** con otra si es del **mismo autolavado**, está *Pendiente* o *Aprobada* y comparte al menos un día.
- Las solicitudes *Rechazadas* **liberan** sus días.
- Solo se pueden resolver solicitudes *Pendientes*. Una vez aprobada o rechazada, no se puede cambiar.
- Los emails de empleados se guardan en minúsculas, así que da igual cómo se escriban.

---

## 10. Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `ERR_CONNECTION_REFUSED` | El servidor no está arrancado | Ejecuta `python app.py` y deja la terminal abierta |
| La solicitud no se envía o sale "Error del servidor" | El servidor quedó con código antiguo tras un cambio | `Ctrl+C` y vuelve a arrancar |
| No llegan los correos | Falta el `.env`, o la contraseña es la normal de Gmail | Ver [sección 4](#4-configurar-el-envío-de-correos) y mira en la carpeta de spam |
| "Ese email no está dado de alta" | El empleado no existe o está inactivo | Dalo de alta o actívalo en `/admin` |
| El enlace del email no abre en el móvil | La app está en `127.0.0.1` | Publicar la app y poner la dirección pública en `BASE_URL` |
| Error `Address already in use` | Ya hay otro servidor en el puerto 5000 | Cierra el otro servidor |

---


