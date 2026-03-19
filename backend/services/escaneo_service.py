import logging
import threading
import time
from datetime import datetime

from backend.database import (
    calcular_siguiente_fecha,
    crear_alerta,
    get_connection,
    guardar_escaneo,
    marcar_confiabilidad,
    marcar_escaneo_programado_como_completado,
    marcar_escaneo_programado_como_ejecutando,
    marcar_escaneo_programado_como_fallido,
    obtener_escaneos_programados,
)
from backend.utils.escaneo_red import escanear_red_local

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Evita escaneos simultáneos dentro del mismo proceso
_scan_lock = threading.Lock()


def _obtener_dispositivo_id_por_mac(mac: str):
    conn = get_connection()
    if not conn:
        return None

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT dispositivo_id FROM dispositivos WHERE mac=%s',
            (mac.upper().replace('-', ':'),)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception:
        return None
    finally:
        if cursor:
            cursor.close()
        conn.close()


def _hacer_escaneo_real():
    inicio = time.time()
    dispositivos = escanear_red_local()
    duracion = round(time.time() - inicio, 2)

    guardado_ok = guardar_escaneo(dispositivos, duracion)
    if not guardado_ok:
        return {
            'status': 'error',
            'message': 'No se pudo guardar el escaneo en la base de datos',
            'duracion_segundos': duracion,
            'dispositivos': dispositivos,
        }

    for dispositivo in dispositivos:
        mac = (dispositivo.get('mac') or '').upper().replace('-', ':')
        ip = dispositivo.get('ip')
        nombre = dispositivo.get('nombre_dispositivo') or mac

        if dispositivo.get('nuevo'):
            crear_alerta(
                tipo='nuevo_dispositivo',
                mac=mac,
                ip=ip,
                mensaje=f'Se detectó un nuevo dispositivo: {nombre}',
            )

    return {
        'status': 'success',
        'message': 'Escaneo completado correctamente',
        'duracion_segundos': duracion,
        'total_dispositivos': len(dispositivos),
        'dispositivos': dispositivos,
        'timestamp': datetime.now().isoformat(),
    }


def realizar_escaneo(forzar=False):
    """
    Si ya hay un escaneo en curso:
    - forzar=False: devuelve busy
    - forzar=True: espera al lock
    """
    acquired = _scan_lock.acquire(blocking=forzar)
    if not acquired:
        logger.warning('Se intentó iniciar un escaneo mientras otro sigue en ejecución')
        return {
            'status': 'busy',
            'message': 'Ya hay un escaneo en ejecución'
        }

    try:
        logger.info('Iniciando escaneo')
        resultado = _hacer_escaneo_real()
        logger.info('Escaneo finalizado con estado: %s', resultado.get('status'))
        return resultado
    except Exception as e:
        logger.error(f'Error ejecutando escaneo: {e}', exc_info=True)
        return {
            'status': 'error',
            'message': f'Error ejecutando escaneo: {e}'
        }
    finally:
        _scan_lock.release()


def marcar_confiabilidad_service(mac: str, es_confiable):
    return marcar_confiabilidad(mac, bool(es_confiable))


def procesar_escaneos_pendientes():
    """
    Procesa todos los escaneos vencidos.
    Devuelve cuántos procesó.
    """
    ahora = datetime.now()
    procesados = 0
    programados = obtener_escaneos_programados(pendientes=True)

    for item in programados:
        fecha = datetime.fromisoformat(item['fecha_programada'])
        if fecha > ahora:
            continue

        escaneo_id = item['id']
        repeticion = item.get('repeticion', 'una_vez')

        # Reclama el trabajo de forma atómica por BD
        if not marcar_escaneo_programado_como_ejecutando(escaneo_id):
            continue

        try:
            logger.info('Ejecutando escaneo programado id=%s', escaneo_id)

            # No permitas solapamiento con escaneo manual
            resultado = realizar_escaneo(forzar=True)

            if resultado.get('status') != 'success':
                raise RuntimeError(resultado.get('message', 'El escaneo no terminó correctamente'))

            siguiente_fecha = calcular_siguiente_fecha(fecha, repeticion)
            marcar_escaneo_programado_como_completado(
                escaneo_id,
                siguiente_fecha=siguiente_fecha
            )
            procesados += 1

        except Exception as e:
            logger.error(
                'Error procesando escaneo programado id=%s: %s',
                escaneo_id,
                e,
                exc_info=True
            )
            marcar_escaneo_programado_como_fallido(escaneo_id, str(e))

    return procesados


def ejecutar_escaneo_automatico(stop_event=None, intervalo_segundos=10):
    """
    Bucle del scheduler.
    - stop_event permite apagarlo ordenadamente.
    - intervalo_segundos corto para reaccionar mejor.
    """
    logger.info('Scheduler automático iniciado')

    if stop_event is None:
        stop_event = threading.Event()

    while not stop_event.is_set():
        try:
            procesados = procesar_escaneos_pendientes()
            if procesados:
                logger.info('Scheduler procesó %s escaneo(s)', procesados)
        except Exception as e:
            logger.error(f'Error en scheduler automático: {e}', exc_info=True)

        stop_event.wait(intervalo_segundos)

    logger.info('Scheduler automático detenido')