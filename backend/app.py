# backend/app.py
import os
from flask import Flask, render_template
from flask_cors import CORS
from threading import Thread
from backend.routes.stats_routes import stats_bp

# Importamos la instancia de socketio desde nuestro módulo central
from backend.socketio_app import socketio
from backend.routes.escaneo_routes import escaneo_bp
from backend.services.escaneo_service import ejecutar_escaneo_automatico

# Directorio del frontend (templates y estáticos)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'frontend'))

app = Flask(
    __name__,
    template_folder=FRONTEND_DIR,
    static_folder=FRONTEND_DIR
)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Inicializar SocketIO con la app Flask
socketio.init_app(app)

# Registrar blueprint de rutas API
app.register_blueprint(escaneo_bp)
app.register_blueprint(stats_bp)

@app.route('/')
def index():
    return render_template("dashboard.html")

@app.route('/historial')
def historial():
    return render_template("historial.html")

@app.route('/escaneo_automatico')
def escaneo_automatico():
    return render_template("escaneo_automatico.html")

if __name__ == '__main__':
    # Arrancar hilo de escaneos programados
    hilo = Thread(target=ejecutar_escaneo_automatico, daemon=True)
    hilo.start()
    # Ejecutar servidor con Socket.IO
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
