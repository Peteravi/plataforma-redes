import os
from threading import Thread, Event
from datetime import datetime

from flask import Flask, render_template, send_from_directory
from flask_cors import CORS

from backend.routes.escaneo_routes import escaneo_bp
from backend.routes.stats_routes import stats_bp
from backend.services.escaneo_service import ejecutar_escaneo_automatico
from backend.socketio_app import socketio

# =========================
# RUTAS BASE
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# =========================
# APP
# =========================
app = Flask(
    __name__,
    template_folder=FRONTEND_DIR,
    static_folder=FRONTEND_DIR
)

CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio.init_app(app)

# =========================
# BLUEPRINTS
# =========================
app.register_blueprint(escaneo_bp)
app.register_blueprint(stats_bp)

# =========================
# RUTAS FRONTEND
# =========================
@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/historial")
def historial():
    return render_template("historial.html")


@app.route("/escaneo_automatico")
def escaneo_automatico():
    return render_template("escaneo_automatico.html")


# =========================
# ARCHIVOS ESTÁTICOS
# =========================
@app.route("/css/<path:filename>")
def css_files(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, "css"), filename)


@app.route("/js/<path:filename>")
def js_files(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, "js"), filename)


@app.route("/img/<path:filename>")
def img_files(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, "img"), filename)


# =========================
# SCHEDULER
# =========================
scheduler_stop_event = Event()


def iniciar_scheduler():
    print("🟡 Iniciando scheduler automático...")

    hilo_scheduler = Thread(
        target=ejecutar_escaneo_automatico,
        kwargs={
            "stop_event": scheduler_stop_event,
            "intervalo_segundos": 10
        },
        daemon=True
    )
    hilo_scheduler.start()

    print("🟢 Scheduler iniciado correctamente")
    return hilo_scheduler


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    print("\n==============================")
    print("🚀 SERVIDOR INICIANDO")
    print("==============================")

    print("📂 BASE_DIR:", BASE_DIR)
    print("📁 FRONTEND_DIR:", FRONTEND_DIR)

    print("✔ dashboard:", os.path.exists(os.path.join(FRONTEND_DIR, "dashboard.html")))
    print("✔ historial:", os.path.exists(os.path.join(FRONTEND_DIR, "historial.html")))
    print("✔ escaneo automático:", os.path.exists(os.path.join(FRONTEND_DIR, "escaneo_automatico.html")))

    iniciar_scheduler()

    print("\n🌐 Servidor disponible en:")
    print("👉 http://127.0.0.1:5000")
    print("👉 http://localhost:5000")
    print("==============================\n")

    socketio.run(app, debug=False, host="0.0.0.0", port=5000)