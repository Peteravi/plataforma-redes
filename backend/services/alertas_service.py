from backend.database import obtener_alertas_no_leidas


def obtener_alertas():
    alertas = obtener_alertas_no_leidas()
    return [
        {
            'id': a.get('id'),
            'tipo': a.get('tipo'),
            'mac': a.get('mac'),
            'ip': a.get('ip'),
            'mensaje': a.get('mensaje'),
            'fecha': a.get('fecha'),
        }
        for a in alertas
    ]