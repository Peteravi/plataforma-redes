import logging
from datetime import datetime, timedelta
from typing import Any
from dotenv import load_dotenv
import os
import mysql.connector
from mysql.connector import Error

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
}

TIPOS_VALIDOS = {'completo', 'rapido', 'personalizado'}
REPETICIONES_VALIDAS = {'una_vez', 'diario', 'semanal', 'mensual'}


def get_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        logger.error(f'Error de conexión a BD: {e}')
        return None


def _normalizar_bool(value: Any):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        value = value.strip().lower()
        if value in {'true', '1', 'si', 'sí'}:
            return True
        if value in {'false', '0', 'no'}:
            return False
    return None


def _parse_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        value = value.strip().replace('Z', '')
        return datetime.fromisoformat(value)
    raise ValueError('Fecha inválida')


def guardar_escaneo(dispositivos: list, duracion_segundos: float) -> bool:
    conn = get_connection()
    if not conn:
        return False

    cursor = None
    try:
        cursor = conn.cursor(buffered=True)
        fecha = datetime.now()
        cursor.execute(
            'INSERT INTO escaneos (fecha, total_dispositivos, duracion_segundos) VALUES (%s, %s, %s)',
            (fecha, len(dispositivos), duracion_segundos),
        )
        escaneo_id = cursor.lastrowid

        for d in dispositivos:
            mac = (d.get('mac') or '').upper().replace('-', ':')
            ip = d.get('ip')
            nombre = d.get('nombre_dispositivo') or f'Desconocido-{ip}'
            estado = d.get('estado') or 'activo'
            tipo = d.get('tipo_dispositivo') or 'Desconocido'
            ultima = _parse_datetime(d.get('ultima_detectado') or datetime.now().isoformat())

            cursor.execute('SELECT dispositivo_id, es_confiable, notas FROM dispositivos WHERE mac=%s', (mac,))
            existente = cursor.fetchone()

            if existente:
                dispositivo_id = existente[0]
                cursor.execute(
                    '''
                    UPDATE dispositivos
                    SET nombre_dispositivo=%s,
                        ip=%s,
                        estado=%s,
                        ultima_detectado=%s,
                        tipo_dispositivo=%s
                    WHERE dispositivo_id=%s
                    ''',
                    (nombre, ip, estado, ultima, tipo, dispositivo_id),
                )
            else:
                cursor.execute(
                    '''
                    INSERT INTO dispositivos
                    (nombre_dispositivo, ip, mac, estado, ultima_detectado, tipo_dispositivo, es_known, es_confiable, notas)
                    VALUES (%s, %s, %s, %s, %s, %s, FALSE, FALSE, NULL)
                    ''',
                    (nombre, ip, mac, estado, ultima, tipo),
                )
                dispositivo_id = cursor.lastrowid

            cursor.execute(
                '''
                INSERT INTO logs_dispositivos (escaneo_id, dispositivo_id, ip_detectada, estado_dispositivo)
                VALUES (%s, %s, %s, %s)
                ''',
                (escaneo_id, dispositivo_id, ip, estado),
            )

        conn.commit()
        return True
    except Exception as e:
        logger.error(f'Error guardando escaneo: {e}', exc_info=True)
        conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        conn.close()


def obtener_estadisticas() -> dict:
    conn = get_connection()
    if not conn:
        return {'status': 'error', 'message': 'No se pudo conectar'}

    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        consultas = {
            'total_dispositivos': 'SELECT COUNT(*) AS total FROM dispositivos',
            'dispositivos_por_estado': 'SELECT estado, COUNT(*) AS cantidad FROM dispositivos GROUP BY estado',
            'ultimos_escaneos': (
                'SELECT fecha, total_dispositivos, duracion_segundos '
                'FROM escaneos ORDER BY fecha DESC LIMIT 5'
            ),
            'dispositivos_frecuentes': '''
                SELECT COALESCE(d.nombre_dispositivo, d.mac) AS nombre_dispositivo, COUNT(*) AS detecciones
                FROM logs_dispositivos ld
                JOIN dispositivos d ON ld.dispositivo_id = d.dispositivo_id
                GROUP BY d.dispositivo_id, d.nombre_dispositivo, d.mac
                ORDER BY detecciones DESC
                LIMIT 5
            ''',
        }
        resultado = {}
        for key, query in consultas.items():
            cursor.execute(query)
            resultado[key] = cursor.fetchall() or []

        return {
            'status': 'success',
            **resultado,
            'timestamp': datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f'Error obteniendo estadísticas: {e}', exc_info=True)
        return {'status': 'error', 'message': str(e)}
    finally:
        if cursor:
            cursor.close()
        conn.close()


def programar_escaneo(tipo: str, fecha_programada, repeticion: str = 'una_vez'):
    if tipo not in TIPOS_VALIDOS or repeticion not in REPETICIONES_VALIDAS:
        raise ValueError('Datos inválidos para programar el escaneo')

    fecha_dt = _parse_datetime(fecha_programada)
    if fecha_dt <= datetime.now():
        raise ValueError('La fecha programada debe estar en el futuro')

    conn = get_connection()
    if not conn:
        return None

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO escaneos_programados (tipo, fecha_programada, repeticion, estado)
            VALUES (%s, %s, %s, 'pendiente')
            ''',
            (tipo, fecha_dt, repeticion),
        )
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        logger.error(f'Error programando escaneo: {e}', exc_info=True)
        conn.rollback()
        return None
    finally:
        if cursor:
            cursor.close()
        conn.close()


def cancelar_escaneo_programado(escaneo_id: int) -> bool:
    conn = get_connection()
    if not conn:
        return False

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE escaneos_programados SET estado='cancelado' WHERE id=%s AND estado IN ('pendiente', 'ejecutando')",
            (escaneo_id,),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f'Error cancelando escaneo: {e}', exc_info=True)
        conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        conn.close()


def obtener_escaneos_programados(pendientes: bool = True):
    conn = get_connection()
    if not conn:
        return []

    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        if pendientes:
            query = """
                SELECT id, tipo, fecha_programada, repeticion, estado
                FROM escaneos_programados
                WHERE estado = 'pendiente'
                ORDER BY fecha_programada ASC
                """
            cursor.execute(query)
        else:
            query = """
                SELECT id, tipo, fecha_programada, repeticion, estado
                FROM escaneos_programados
                ORDER BY fecha_programada ASC
            """
            cursor.execute(query)

        resultados = cursor.fetchall() or []
        for item in resultados:
            fecha = item.get('fecha_programada')
            if isinstance(fecha, datetime):
                item['fecha_programada'] = fecha.isoformat()
        return resultados
    except Exception as e:
        logger.error(f'Error obteniendo escaneos programados: {e}', exc_info=True)
        return []
    finally:
        if cursor:
            cursor.close()
        conn.close()


def marcar_escaneo_programado_como_ejecutando(escaneo_id: int) -> bool:
    conn = get_connection()
    if not conn:
        return False

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE escaneos_programados SET estado='ejecutando' WHERE id=%s AND estado='pendiente'",
            (escaneo_id,),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f'Error marcando escaneo como ejecutando: {e}', exc_info=True)
        conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        conn.close()


def marcar_escaneo_programado_como_completado(escaneo_id: int, siguiente_fecha=None) -> bool:
    conn = get_connection()
    if not conn:
        return False

    cursor = None
    try:
        cursor = conn.cursor()
        if siguiente_fecha:
            cursor.execute(
                """
                UPDATE escaneos_programados
                SET estado='pendiente', fecha_programada=%s
                WHERE id=%s
                """,
                (siguiente_fecha, escaneo_id),
            )
        else:
            cursor.execute(
                "UPDATE escaneos_programados SET estado='completado' WHERE id=%s",
                (escaneo_id,),
            )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f'Error marcando escaneo como completado: {e}', exc_info=True)
        conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        conn.close()


def calcular_siguiente_fecha(fecha_actual: datetime, repeticion: str):
    if repeticion == 'diario':
        return fecha_actual + timedelta(days=1)
    if repeticion == 'semanal':
        return fecha_actual + timedelta(weeks=1)
    if repeticion == 'mensual':
        return fecha_actual + timedelta(days=30)
    return None


def obtener_dispositivos():
    conn = get_connection()
    if not conn:
        return []

    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            '''
            SELECT dispositivo_id, nombre_dispositivo, ip, mac, estado, ultima_detectado,
                   tipo_dispositivo, es_known, es_confiable, notas
            FROM dispositivos
            ORDER BY ultima_detectado DESC, nombre_dispositivo ASC
            '''
        )
        dispositivos = cursor.fetchall() or []

        for d in dispositivos:
            ultima = d.get('ultima_detectado')
            if isinstance(ultima, datetime):
                d['ultima_detectado'] = ultima.isoformat()
            d['es_known'] = bool(d.get('es_known'))
            d['es_confiable'] = bool(d.get('es_confiable'))

        return dispositivos
    except Exception as e:
        logger.error(f'Error obteniendo dispositivos: {e}', exc_info=True)
        return []
    finally:
        if cursor:
            cursor.close()
        conn.close()

def marcar_confiabilidad(mac: str, es_confiable: bool) -> bool:
    conn = get_connection()
    if not conn:
        return False

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE dispositivos SET es_confiable=%s WHERE mac=%s',
            (es_confiable, mac.upper().replace('-', ':')),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f'Error marcando confiabilidad: {e}', exc_info=True)
        conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        conn.close()


def agregar_nota_dispositivo(mac: str, nota: str) -> bool:
    conn = get_connection()
    if not conn:
        return False

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE dispositivos SET notas=%s WHERE mac=%s',
            (nota, mac.upper().replace('-', ':')),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f'Error agregando nota al dispositivo: {e}', exc_info=True)
        conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        conn.close()


def crear_alerta(tipo: str, mac: str, ip: str, mensaje: str) -> bool:
    conn = get_connection()
    if not conn:
        return False

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO alertas (tipo, mac, ip, mensaje, leida, fecha)
            VALUES (%s, %s, %s, %s, FALSE, %s)
            ''',
            (tipo, mac.upper().replace('-', ':'), ip, mensaje, datetime.now()),
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f'Error creando alerta: {e}', exc_info=True)
        conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        conn.close()

def obtener_alertas_no_leidas():
    conn = get_connection()
    if not conn:
        return []

    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            '''
            SELECT id, tipo, mac, ip, mensaje, fecha
            FROM alertas
            WHERE leida=FALSE
            ORDER BY fecha DESC
            '''
        )
        alertas = cursor.fetchall() or []
        for a in alertas:
            fecha = a.get('fecha')
            if isinstance(fecha, datetime):
                a['fecha'] = fecha.isoformat()
        return alertas
    except Exception as e:
        logger.error(f'Error obteniendo alertas: {e}', exc_info=True)
        return []
    finally:
        if cursor:
            cursor.close()
        conn.close()

def marcar_escaneo_programado_como_fallido(escaneo_id: int, error: str = None) -> bool:
    conn = get_connection()
    if not conn:
        return False

    cursor = None
    try:
        cursor = conn.cursor()

        # Si no tienes columna de error, deja solo estado='fallido'
        cursor.execute(
            "UPDATE escaneos_programados SET estado='fallido' WHERE id=%s",
            (escaneo_id,),
        )

        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f'Error marcando escaneo como fallido: {e}', exc_info=True)
        conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        conn.close()