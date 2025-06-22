# backend/services/escaneo_service.py

import time
import logging
from datetime import datetime
from backend.utils.escaneo_red import escanear_red
from backend.database import (
    guardar_escaneo,
    get_connection,
    reprogramar_escaneo_periodico,
    detectar_nuevos_dispositivos,
    marcar_confiabilidad,
)
from backend.socketio_app import socketio  # instancia centralizada


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def realizar_escaneo():
    inicio = time.time()
    logger.info("Iniciando escaneo de red...")
    dispositivos = escanear_red()
    if not isinstance(dispositivos, list):
        dispositivos = []

    duracion = round(time.time() - inicio, 2)
    success = guardar_escaneo(dispositivos, duracion)
    status = 'success' if success else 'partial_success'
    message = f"Escaneo completado en {duracion}s" + (" y guardado" if success else "")

    nuevos = detectar_nuevos_dispositivos(dispositivos)
    if nuevos:
        logger.warning(f"{len(nuevos)} nuevos dispositivos detectados")

    resultado = {
        'status': status,
        'dispositivos': dispositivos,
        'total': len(dispositivos),
        'duracion_segundos': duracion,
        'message': message
    }

    # Emitimos el evento al frontend
    socketio.emit('scan_complete', resultado)
    return resultado

def ejecutar_escaneo_automatico():
    while True:
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM escaneos_programados WHERE estado='pendiente' "
                "ORDER BY fecha_programada ASC LIMIT 1"
            )
            esc = cursor.fetchone()

            if esc:
                ahora = datetime.now(esc['fecha_programada'].tzinfo) \
                        if hasattr(esc['fecha_programada'], 'tzinfo') else datetime.now()
                espera = (esc['fecha_programada'] - ahora).total_seconds()
                if espera > 0:
                    time.sleep(min(espera, 60))
                    continue

                logger.info(f"Ejecutando escaneo programado ID={esc['id']}")
                cursor.execute(
                    "UPDATE escaneos_programados SET estado='ejecutando' WHERE id=%s",
                    (esc['id'],)
                )
                conn.commit()

                resultado = realizar_escaneo()

                # Cambiamos 'error' por 'cancelado' para no truncar el ENUM
                nuevo_estado = 'completado' if resultado['status'] == 'success' else 'cancelado'
                cursor.execute(
                    "UPDATE escaneos_programados SET estado=%s WHERE id=%s",
                    (nuevo_estado, esc['id'])
                )

                if esc['repeticion'] != 'una_vez':
                    reprogramar_escaneo_periodico(esc['id'])

                conn.commit()
            else:
                time.sleep(60)

        except Exception as e:
            logger.error(f"Error en escaneo automático: {e}", exc_info=True)
            time.sleep(60)

        finally:
            if conn:
                conn.close()

def marcar_confiabilidad_service(mac: str, es_confiable: bool) -> bool:
    return marcar_confiabilidad(mac, es_confiable)
