# backend/socket.py
from flask_socketio import SocketIO

# Instancia única de SocketIO para evitar importaciones circulares
socketio = SocketIO(cors_allowed_origins="*")
