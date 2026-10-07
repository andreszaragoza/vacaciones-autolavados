import hmac
import os
import re
import secrets
import smtplib
import sqlite3
import threading
import time
from datetime import date, timedelta
from email.message import EmailMessage
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, g, redirect, render_template, request, session, url_for

load_dotenv(Path(__file__).with_name(".env"))

app = Flask(__name__)
DB = str(Path(__file__).with_name("vacaciones.db"))

# Configuración del correo (se lee del archivo .env)
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5000").rstrip("/")
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
MAIL_FROM = os.environ.get("MAIL_FROM") or SMTP_USER

# Acceso al panel de gestión (también en .env)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or None
# Sin SECRET_KEY se genera una al arrancar: funciona, pero las sesiones se pierden al reiniciar
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=BASE_URL.startswith("https://"),
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)

ESTADOS_ACTIVOS = ("Pendiente", "Aprobada")
DIAS_ANUALES_DEFECTO = 28
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    con = sqlite3.connect(DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS autolavados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            email_encargado TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS empleados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,   -- siempre en minúsculas
            autolavado_id INTEGER NOT NULL REFERENCES autolavados(id),
            activo INTEGER NOT NULL DEFAULT 1,
            dias_anuales INTEGER NOT NULL DEFAULT 28   -- días de vacaciones por año
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS solicitudes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empleado TEXT NOT NULL,
            email TEXT NOT NULL,
            fecha_inicio TEXT NOT NULL,   -- formato YYYY-MM-DD
            fecha_fin TEXT NOT NULL,      -- formato YYYY-MM-DD
            estado TEXT NOT NULL DEFAULT 'Pendiente',
            comentario TEXT,
            creada TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            autolavado_id INTEGER REFERENCES autolavados(id),
            token TEXT,                   -- para el enlace de aprobación del email
            empleado_id INTEGER REFERENCES empleados(id)
        )
    """)
    # Bases de datos creadas con la versión anterior: añadir las columnas nuevas
    columnas = {r[1] for r in con.execute("PRAGMA table_info(solicitudes)")}
    if "autolavado_id" not in columnas:
        con.execute("ALTER TABLE solicitudes ADD COLUMN autolavado_id INTEGER REFERENCES autolavados(id)")
    if "token" not in columnas:
        con.execute("ALTER TABLE solicitudes ADD COLUMN token TEXT")
    if "empleado_id" not in columnas:
        con.execute("ALTER TABLE solicitudes ADD COLUMN empleado_id INTEGER REFERENCES empleados(id)")
    columnas = {r[1] for r in con.execute("PRAGMA table_info(empleados)")}
    if "dias_anuales" not in columnas:
        con.execute(f"ALTER TABLE empleados ADD COLUMN dias_anuales INTEGER NOT NULL DEFAULT {DIAS_ANUALES_DEFECTO}")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_solicitudes_token ON solicitudes(token)")
    con.commit()
    con.close()


# Se ejecuta al importar, así funciona tanto con `python app.py` como con `flask run`
init_db()


def error(msg, code=400):
    return jsonify({"error": msg}), code


def parse_fecha(valor):
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        return None


def fmt_fecha(iso):
    return "/".join(reversed(iso.split("-")))


def dias(inicio, fin):
    return (date.fromisoformat(fin) - date.fromisoformat(inicio)).days + 1


def dias_por_anio(inicio, fin):
    """{año: días} de un rango. Un rango puede cruzar el fin de año."""
    res = {}
    a, b = date.fromisoformat(inicio), date.fromisoformat(fin)
    while a <= b:
        tope = min(b, date(a.year, 12, 31))
        res[a.year] = res.get(a.year, 0) + (tope - a).days + 1
        a = tope + timedelta(days=1)
    return res


def dias_usados(empleado_id, anio):
    """Días aprobados y pendientes de un empleado en un año."""
    rows = get_db().execute(
        "SELECT fecha_inicio, fecha_fin, estado FROM solicitudes "
        "WHERE empleado_id = ? AND estado IN (?, ?) AND fecha_inicio <= ? AND fecha_fin >= ?",
        (empleado_id, *ESTADOS_ACTIVOS, f"{anio}-12-31", f"{anio}-01-01"),
    ).fetchall()
    usados = {"Aprobada": 0, "Pendiente": 0}
    for r in rows:
        usados[r["estado"]] += dias_por_anio(r["fecha_inicio"], r["fecha_fin"]).get(anio, 0)
    return usados


# ---------- Email ----------

def _enviar(msg):
    try:
        if SMTP_PORT == 465:
            smtp = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15)
        else:
            smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
            smtp.starttls()
        with smtp:
            if SMTP_USER:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(msg)
    except Exception:
        app.logger.exception("No se pudo enviar el email a %s", msg["To"])


def enviar_email(destino, asunto, cuerpo):
    msg = EmailMessage()
    msg["From"] = MAIL_FROM or "vacaciones@localhost"
    msg["To"] = destino
    msg["Subject"] = asunto
    msg.set_content(cuerpo)

    if not SMTP_HOST:
        # Sin correo configurado: se muestra en la consola para poder probar
        print(f"\n===== EMAIL (no enviado, falta configurar .env) =====\n"
              f"Para: {destino}\nAsunto: {asunto}\n\n{cuerpo}\n"
              f"=====================================================\n", flush=True)
        return
    # En segundo plano para que el formulario no espere al servidor de correo
    threading.Thread(target=_enviar, args=(msg,), daemon=True).start()


def avisar_encargado(s):
    enviar_email(
        s["email_encargado"],
        f"Solicitud de vacaciones: {s['empleado']} ({s['autolavado']})",
        f"Hola,\n\n"
        f"{s['empleado']} ({s['email']}) ha solicitado vacaciones en {s['autolavado']}:\n\n"
        f"  Desde: {fmt_fecha(s['fecha_inicio'])}\n"
        f"  Hasta: {fmt_fecha(s['fecha_fin'])}\n"
        f"  Días:  {dias(s['fecha_inicio'], s['fecha_fin'])}\n\n"
        f"Para aprobarla o rechazarla entra aquí:\n{BASE_URL}/revisar/{s['token']}\n",
    )


def avisar_empleado(s):
    enviar_email(
        s["email"],
        f"Tu solicitud de vacaciones ha sido {s['estado'].lower()}",
        f"Hola {s['empleado']},\n\n"
        f"Tu solicitud de vacaciones en {s['autolavado'] or 'tu autolavado'} del "
        f"{fmt_fecha(s['fecha_inicio'])} al {fmt_fecha(s['fecha_fin'])} "
        f"ha sido {s['estado'].upper()}.\n"
        + (f"\nComentario del encargado: {s['comentario']}\n" if s["comentario"] else ""),
    )


# ---------- Lógica compartida ----------

SELECT_SOLICITUD = (
    "SELECT s.*, a.nombre AS autolavado, a.email_encargado "
    "FROM solicitudes s LEFT JOIN autolavados a ON a.id = s.autolavado_id "
)


def obtener_solicitud(campo, valor):
    return get_db().execute(SELECT_SOLICITUD + f"WHERE s.{campo} = ?", (valor,)).fetchone()


def resolver_solicitud(sid, nuevo, comentario):
    """Aprueba o rechaza una solicitud pendiente. Devuelve un mensaje de error o None."""
    if nuevo not in ("Aprobada", "Rechazada"):
        return "Estado no válido."
    db = get_db()
    cur = db.execute(
        "UPDATE solicitudes SET estado = ?, comentario = ? WHERE id = ? AND estado = 'Pendiente'",
        (nuevo, comentario, sid),
    )
    db.commit()
    if cur.rowcount == 0:
        return "Esta solicitud ya no está pendiente."
    avisar_empleado(obtener_solicitud("id", sid))
    return None


# ---------- Acceso al panel ----------

def admin_autorizado():
    if ADMIN_PASSWORD:
        return session.get("admin") is True
    # Sin contraseña configurada: solo en local arrancando con `python app.py` (modo debug)
    return app.debug and request.remote_addr in ("127.0.0.1", "::1")


def solo_admin(f):
    """Protege una página o endpoint del panel de gestión."""
    @wraps(f)
    def envoltura(*args, **kwargs):
        if admin_autorizado():
            return f(*args, **kwargs)
        if request.path.startswith("/api/"):
            return error("Inicia sesión en el panel de gestión.", 401)
        return redirect(url_for("login"))
    return envoltura


@app.context_processor
def datos_plantillas():
    return {"sesion_admin": bool(ADMIN_PASSWORD) and session.get("admin") is True}


@app.after_request
def no_incrustar_panel(resp):
    # El panel y la página del encargado no se pueden meter en un iframe ajeno
    if request.path.startswith(("/admin", "/revisar")):
        resp.headers["X-Frame-Options"] = "DENY"
    return resp


@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if admin_autorizado():
        return redirect(url_for("admin"))
    if not ADMIN_PASSWORD:
        return render_template("login.html", sin_configurar=True), 503

    fallo = False
    if request.method == "POST":
        escrita = (request.form.get("password") or "").encode()
        if hmac.compare_digest(escrita, ADMIN_PASSWORD.encode()):
            session.clear()
            session["admin"] = True
            session.permanent = True
            return redirect(url_for("admin"))
        time.sleep(1)   # frena los intentos de adivinar la contraseña
        fallo = True
    return render_template("login.html", fallo=fallo)


@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- Páginas ----------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/embed")
def embed():
    """Formulario sin menú, para incrustar con un <iframe> en otra web."""
    return render_template("index.html", embed=True)


@app.route("/admin")
@solo_admin
def admin():
    return render_template("admin.html")


@app.route("/revisar/<token>", methods=["GET", "POST"])
def revisar(token):
    s = obtener_solicitud("token", token)
    if not s:
        return render_template("revisar.html", s=None), 404

    mensaje = None
    if request.method == "POST":
        comentario = (request.form.get("comentario") or "").strip() or None
        mensaje = resolver_solicitud(s["id"], request.form.get("estado"), comentario)
        s = obtener_solicitud("token", token)
    return render_template("revisar.html", s=s, mensaje=mensaje,
                           fmt=fmt_fecha, dias=dias(s["fecha_inicio"], s["fecha_fin"]))


# ---------- API: autolavados ----------

def datos_autolavado():
    datos = request.get_json(silent=True) or {}
    nombre = (datos.get("nombre") or "").strip()
    email = (datos.get("email_encargado") or "").strip()
    if not nombre:
        return None, "El nombre del autolavado es obligatorio."
    if not EMAIL_RE.match(email):
        return None, "El email del encargado no es válido."
    return (nombre, email), None


@app.route("/api/autolavados", methods=["GET"])
@solo_admin
def listar_autolavados():
    rows = get_db().execute("SELECT * FROM autolavados ORDER BY nombre").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/autolavados", methods=["POST"])
@solo_admin
def crear_autolavado():
    valores, msg = datos_autolavado()
    if msg:
        return error(msg)
    db = get_db()
    try:
        cur = db.execute("INSERT INTO autolavados (nombre, email_encargado) VALUES (?, ?)", valores)
        db.commit()
    except sqlite3.IntegrityError:
        return error("Ya existe un autolavado con ese nombre.", 409)
    return jsonify({"id": cur.lastrowid}), 201


@app.route("/api/autolavados/<int:aid>", methods=["PUT"])
@solo_admin
def editar_autolavado(aid):
    valores, msg = datos_autolavado()
    if msg:
        return error(msg)
    db = get_db()
    try:
        cur = db.execute("UPDATE autolavados SET nombre = ?, email_encargado = ? WHERE id = ?",
                         (*valores, aid))
        db.commit()
    except sqlite3.IntegrityError:
        return error("Ya existe un autolavado con ese nombre.", 409)
    if cur.rowcount == 0:
        return error("Autolavado no encontrado.", 404)
    return jsonify({"id": aid})


# ---------- API: empleados ----------

def buscar_empleado(email):
    """Empleado activo con ese email (o None), con el nombre de su autolavado."""
    return get_db().execute(
        "SELECT e.*, a.nombre AS autolavado FROM empleados e "
        "JOIN autolavados a ON a.id = e.autolavado_id "
        "WHERE e.email = ? AND e.activo = 1",
        ((email or "").strip().lower(),),
    ).fetchone()


def datos_empleado():
    datos = request.get_json(silent=True) or {}
    nombre = (datos.get("nombre") or "").strip()
    email = (datos.get("email") or "").strip().lower()
    activo = 0 if datos.get("activo") is False else 1
    try:
        aid = int(datos.get("autolavado_id"))
    except (TypeError, ValueError):
        aid = None
    try:
        dias_anuales = int(datos.get("dias_anuales", DIAS_ANUALES_DEFECTO))
    except (TypeError, ValueError):
        dias_anuales = -1

    if not nombre:
        return None, "El nombre del empleado es obligatorio."
    if not EMAIL_RE.match(email):
        return None, "El email del empleado no es válido."
    if aid is None or not get_db().execute("SELECT 1 FROM autolavados WHERE id = ?", (aid,)).fetchone():
        return None, "Elige un autolavado válido."
    if not 0 <= dias_anuales <= 366:
        return None, "Los días de vacaciones al año deben estar entre 0 y 366."
    return (nombre, email, aid, activo, dias_anuales), None


@app.route("/api/empleados", methods=["GET"])
@solo_admin
def listar_empleados():
    rows = get_db().execute(
        "SELECT e.*, a.nombre AS autolavado FROM empleados e "
        "JOIN autolavados a ON a.id = e.autolavado_id "
        "ORDER BY e.activo DESC, a.nombre, e.nombre"
    ).fetchall()
    anio = date.today().year
    lista = []
    for r in rows:
        u = dias_usados(r["id"], anio)
        lista.append({**dict(r), "disponibles": max(r["dias_anuales"] - u["Aprobada"] - u["Pendiente"], 0)})
    return jsonify(lista)


@app.route("/api/empleados", methods=["POST"])
@solo_admin
def crear_empleado():
    valores, msg = datos_empleado()
    if msg:
        return error(msg)
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO empleados (nombre, email, autolavado_id, activo, dias_anuales) "
            "VALUES (?, ?, ?, ?, ?)", valores)
        db.commit()
    except sqlite3.IntegrityError:
        return error("Ya existe un empleado con ese email.", 409)
    return jsonify({"id": cur.lastrowid}), 201


@app.route("/api/empleados/<int:eid>", methods=["PUT"])
@solo_admin
def editar_empleado(eid):
    valores, msg = datos_empleado()
    if msg:
        return error(msg)
    db = get_db()
    try:
        cur = db.execute(
            "UPDATE empleados SET nombre = ?, email = ?, autolavado_id = ?, activo = ?, dias_anuales = ? "
            "WHERE id = ?",
            (*valores, eid))
        db.commit()
    except sqlite3.IntegrityError:
        return error("Ya existe un empleado con ese email.", 409)
    if cur.rowcount == 0:
        return error("Empleado no encontrado.", 404)
    return jsonify({"id": eid})


@app.route("/api/identificar")
def identificar():
    """El formulario lo usa para reconocer al empleado por su email."""
    e = buscar_empleado(request.args.get("email"))
    if not e:
        return error("Ese email no está dado de alta. Pide a tu encargado que te añada.", 404)
    return jsonify({"nombre": e["nombre"], "autolavado_id": e["autolavado_id"],
                    "autolavado": e["autolavado"]})


@app.route("/api/resumen")
def resumen():
    """Panel "Mis vacaciones": contadores y solicitudes del empleado en un año."""
    e = buscar_empleado(request.args.get("email"))
    if not e:
        return error("Ese email no está dado de alta.", 404)
    anio = request.args.get("anio", type=int) or date.today().year

    rows = get_db().execute(
        "SELECT id, fecha_inicio, fecha_fin, estado, comentario FROM solicitudes "
        "WHERE empleado_id = ? AND fecha_inicio <= ? AND fecha_fin >= ? ORDER BY fecha_inicio",
        (e["id"], f"{anio}-12-31", f"{anio}-01-01"),
    ).fetchall()
    u = dias_usados(e["id"], anio)
    return jsonify({
        "anio": anio,
        "dias_anuales": e["dias_anuales"],
        "aprobados": u["Aprobada"],
        "pendientes": u["Pendiente"],
        "disponibles": max(e["dias_anuales"] - u["Aprobada"] - u["Pendiente"], 0),
        "solicitudes": [{
            "id": r["id"], "from": r["fecha_inicio"], "to": r["fecha_fin"],
            "estado": r["estado"], "comentario": r["comentario"],
            "dias": dias_por_anio(r["fecha_inicio"], r["fecha_fin"]).get(anio, 0),
        } for r in rows],
    })


# ---------- API: solicitudes ----------

@app.route("/api/ocupadas")
def ocupadas():
    aid = request.args.get("autolavado", type=int)
    if aid is None:
        return error("Falta el parámetro autolavado.")
    email = (request.args.get("email") or "").strip().lower()
    rows = get_db().execute(
        "SELECT fecha_inicio, fecha_fin, email, estado FROM solicitudes "
        "WHERE autolavado_id = ? AND estado IN (?, ?)", (aid, *ESTADOS_ACTIVOS)
    ).fetchall()
    # from/to es el formato que entiende flatpickr en su opción `disable`;
    # `propia` marca las del propio empleado para pintarlas de otro color
    return jsonify([{"from": r["fecha_inicio"], "to": r["fecha_fin"], "estado": r["estado"],
                     "propia": bool(email) and r["email"].lower() == email} for r in rows])


@app.route("/api/solicitudes", methods=["GET"])
@solo_admin
def listar_solicitudes():
    rows = get_db().execute(SELECT_SOLICITUD + "ORDER BY s.fecha_inicio DESC").fetchall()
    # El token no se expone: es la "llave" del enlace de aprobación
    return jsonify([{k: r[k] for k in r.keys() if k != "token"} for r in rows])


@app.route("/api/solicitudes", methods=["POST"])
def crear_solicitud():
    datos = request.get_json(silent=True) or {}
    inicio = parse_fecha(datos.get("fecha_inicio"))
    fin = parse_fecha(datos.get("fecha_fin"))

    # El nombre y el autolavado salen de la ficha del empleado, no del formulario
    emp = buscar_empleado(datos.get("email"))
    if not emp:
        return error("Ese email no está dado de alta. Pide a tu encargado que te añada.", 403)
    aid = emp["autolavado_id"]

    if not inicio or not fin:
        return error("Las fechas deben tener formato YYYY-MM-DD.")
    if inicio > fin:
        return error("La fecha de inicio no puede ser posterior a la de fin.")
    if inicio < date.today():
        return error("No se pueden pedir vacaciones en fechas pasadas.")

    db = get_db()
    token = secrets.token_urlsafe(24)
    # BEGIN IMMEDIATE bloquea la escritura: evita que dos peticiones simultáneas
    # pasen la comprobación de solapamiento a la vez.
    db.execute("BEGIN IMMEDIATE")
    try:
        # Solo choca con solicitudes del mismo autolavado
        choque = db.execute(
            "SELECT id FROM solicitudes WHERE autolavado_id = ? AND estado IN (?, ?) "
            "AND fecha_inicio <= ? AND fecha_fin >= ?",
            (aid, *ESTADOS_ACTIVOS, fin.isoformat(), inicio.isoformat()),
        ).fetchone()
        if choque:
            db.rollback()
            return error("Esas fechas se solapan con otro compañero de tu autolavado.", 409)

        # No puede pasarse de sus días anuales (las pendientes ya cuentan)
        for anio, n in dias_por_anio(inicio.isoformat(), fin.isoformat()).items():
            u = dias_usados(emp["id"], anio)
            quedan = max(emp["dias_anuales"] - u["Aprobada"] - u["Pendiente"], 0)
            if n > quedan:
                db.rollback()
                return error(f"Pides {n} días en {anio}, pero solo te quedan {quedan}.", 409)

        cur = db.execute(
            "INSERT INTO solicitudes "
            "(empleado, email, fecha_inicio, fecha_fin, autolavado_id, token, empleado_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (emp["nombre"], emp["email"], inicio.isoformat(), fin.isoformat(), aid, token, emp["id"]),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    avisar_encargado(obtener_solicitud("id", cur.lastrowid))
    return jsonify({"id": cur.lastrowid, "estado": "Pendiente"}), 201


@app.route("/api/solicitudes/<int:sid>/estado", methods=["POST"])
@solo_admin
def cambiar_estado(sid):
    datos = request.get_json(silent=True) or {}
    comentario = (datos.get("comentario") or "").strip() or None
    if not obtener_solicitud("id", sid):
        return error("Solicitud no encontrada.", 404)
    msg = resolver_solicitud(sid, datos.get("estado"), comentario)
    if msg:
        return error(msg, 409)
    return jsonify({"id": sid, "estado": datos.get("estado")})


if __name__ == "__main__":
    app.run(debug=True)
