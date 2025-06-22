import mysql.connector
from mysql.connector import Error
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'piteravi07',
    'database': 'PlataformaRedes'
}

def get_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        logger.error(f"Error de conexión a BD: {e}")
        return None

def guardar_escaneo(dispositivos: list, duracion_segundos: float) -> bool:
    conn = get_connection()
    if not conn:
        return False
    try:
        # Usamos cursor buffered para evitar 'Unread result found'
        cursor = conn.cursor(buffered=True)
        fecha = datetime.now()
        cursor.execute(
            "INSERT INTO escaneos (fecha, total_dispositivos, duracion_segundos) VALUES (%s, %s, %s)",
            (fecha, len(dispositivos), duracion_segundos)
        )
        esc_id = cursor.lastrowid

        for d in dispositivos:
            cursor.execute("SELECT dispositivo_id FROM dispositivos WHERE mac=%s", (d['mac'],))
            res = cursor.fetchone()
            if res:
                did = res[0]
                cursor.execute(
                    "UPDATE dispositivos SET ip=%s, estado=%s, ultima_detectado=%s WHERE dispositivo_id=%s",
                    (d['ip'], d['estado'], d['ultima_detectado'], did)
                )
            else:
                cursor.execute(
                    "INSERT INTO dispositivos (nombre_dispositivo, ip, mac, estado, ultima_detectado) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (d['nombre_dispositivo'], d['ip'], d['mac'], d['estado'], d['ultima_detectado'])
                )
                did = cursor.lastrowid

            cursor.execute(
                "INSERT INTO logs_dispositivos (escaneo_id, dispositivo_id, ip_detectada, estado_dispositivo) "
                "VALUES (%s, %s, %s, %s)",
                (esc_id, did, d['ip'], d['estado'])
            )

        conn.commit()
        return True

    except Error as e:
        logger.error(f"Error guardando escaneo: {e}", exc_info=True)
        conn.rollback()
        return False

    finally:
        cursor.close()
        conn.close()
        
def obtener_estadisticas() -> dict:
    conn = get_connection()
    if not conn:
        return {'status': 'error', 'message': 'No se pudo conectar'}
    try:
        cursor = conn.cursor(dictionary=True)
        consultas = {
            'total_dispositivos': "SELECT COUNT(*) as total FROM dispositivos",
            'dispositivos_por_estado': "SELECT estado, COUNT(*) cantidad FROM dispositivos GROUP BY estado",
            'ultimos_escaneos': "SELECT fecha, total_dispositivos, duracion_segundos "
                                "FROM escaneos ORDER BY fecha DESC LIMIT 5",
            'dispositivos_frecuentes': """
                SELECT d.nombre_dispositivo, COUNT(*) detecciones
                FROM logs_dispositivos ld
                JOIN dispositivos d ON ld.dispositivo_id=d.dispositivo_id
                GROUP BY d.nombre_dispositivo
                ORDER BY detecciones DESC LIMIT 5
            """
        }
        resultado = {}
        for key, q in consultas.items():
            cursor.execute(q)
            resultado[key] = cursor.fetchall() or []
        return {'status': 'success', **resultado, 'timestamp': datetime.now().isoformat()}
    except Error as e:
        logger.error(f"Error obteniendo estadísticas: {e}", exc_info=True)
        return {'status': 'error', 'message': str(e)}
    finally:
        cursor.close()
        conn.close()


def programar_escaneo(tipo: str, fecha_programada, repeticion: str = 'una_vez'):
    conn = get_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        if isinstance(fecha_programada, str):
            fecha_programada = datetime.fromisoformat(fecha_programada)
        cursor.execute(
            "INSERT INTO escaneos_programados (tipo, fecha_programada, repeticion, estado) "
            "VALUES (%s,%s,%s,'pendiente')",
            (tipo, fecha_programada, repeticion)
        )
        conn.commit()
        return cursor.lastrowid
    except Error as e:
        logger.error(f"Error programando escaneo: {e}", exc_info=True)
        return None
    finally:
        cursor.close()
        conn.close()


def cancelar_escaneo_programado(e_id: int) -> bool:
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE escaneos_programados SET estado='cancelado' "
            "WHERE id=%s AND estado='pendiente'",
            (e_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        logger.error(f"Error cancelando escaneo: {e}", exc_info=True)
        return False
    finally:
        cursor.close()
        conn.close()


def obtener_escaneos_programados(pendientes: bool = True):
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        estado_clause = "IN ('pendiente','ejecutando')" if pendientes else ""
        query = f"SELECT * FROM escaneos_programados WHERE estado {estado_clause} ORDER BY fecha_programada"
        cursor.execute(query)
        return cursor.fetchall()
    except Error as e:
        logger.error(f"Error obteniendo escaneos programados: {e}", exc_info=True)
        return []
    finally:
        cursor.close()
        conn.close()


def reprogramar_escaneo_periodico(e_id: int) -> bool:
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM escaneos_programados WHERE id=%s", (e_id,))
        esc = cursor.fetchone()
        if not esc:
            return False
        from datetime import timedelta
        delta = {
            'diario': timedelta(days=1),
            'semanal': timedelta(weeks=1),
            'mensual': timedelta(days=30)
        }.get(esc['repeticion'])
        if not delta:
            return False
        nueva = esc['fecha_programada'] + delta
        cursor.execute(
            "UPDATE escaneos_programados SET fecha_programada=%s, estado='pendiente' WHERE id=%s",
            (nueva, e_id)
        )
        conn.commit()
        return True
    except Error as e:
        logger.error(f"Error reprogramando periódico: {e}", exc_info=True)
        return False
    finally:
        cursor.close()
        conn.close()


def detectar_nuevos_dispositivos(dispositivos_escaneados: list) -> list:
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT mac, es_known FROM dispositivos")
        known = {d['mac']: d['es_known'] for d in cursor.fetchall()}
        nuevos = []
        for d in dispositivos_escaneados:
            if not known.get(d['mac'], False):
                nuevos.append(d)
                cursor.execute(
                    "INSERT INTO alertas (tipo, mac, ip, mensaje) VALUES (%s,%s,%s,%s)",
                    (
                        'nuevo_dispositivo',
                        d['mac'],
                        d['ip'],
                        f"Nuevo dispositivo detectado: MAC {d['mac']}, IP {d['ip']}"
                    )
                )
                cursor.execute(
                    """INSERT INTO dispositivos
                       (nombre_dispositivo, ip, mac, estado, ultima_detectado, es_known)
                       VALUES (%s,%s,%s,%s,%s,TRUE)
                       ON DUPLICATE KEY UPDATE
                         ip=VALUES(ip),
                         estado=VALUES(estado),
                         ultima_detectado=VALUES(ultima_detectado),
                         es_known=TRUE
                    """,
                    (
                        d.get('nombre_dispositivo', 'Desconocido'),
                        d['ip'],
                        d['mac'],
                        'activo',
                        d['ultima_detectado']
                    )
                )
        conn.commit()
        return nuevos
    except Error as e:
        logger.error(f"Error detectando nuevos: {e}", exc_info=True)
        conn.rollback()
        return []
    finally:
        cursor.close()
        conn.close()


def obtener_alertas_pendientes() -> list:
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT a.*, d.nombre_dispositivo
               FROM alertas a
               LEFT JOIN dispositivos d ON a.mac=d.mac
               WHERE a.leida=FALSE
               ORDER BY a.fecha DESC
               LIMIT 50"""
        )
        return cursor.fetchall()
    except Error as e:
        logger.error(f"Error obteniendo alertas pendientes: {e}", exc_info=True)
        return []
    finally:
        cursor.close()
        conn.close()


def agregar_nota_dispositivo(mac: str, nota: str) -> bool:
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE dispositivos SET notas=%s WHERE mac=%s",
            (nota, mac)
        )
        conn.commit()
        return True
    except Error as e:
        logger.error(f"Error agregando nota: {e}", exc_info=True)
        return False
    finally:
        cursor.close()
        conn.close()


def obtener_dispositivos(filtros: dict = None) -> list:
    conn = get_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        base = "SELECT * FROM dispositivos WHERE 1=1"
        params = []
        if filtros:
            if filtros.get('confiable') is not None:
                base += " AND es_confiable=%s"
                params.append(filtros['confiable'])
            if filtros.get('tipo'):
                base += " AND tipo_dispositivo=%s"
                params.append(filtros['tipo'])
            if filtros.get('busqueda'):
                term = f"%{filtros['busqueda']}%"
                base += " AND (nombre_dispositivo LIKE %s OR mac LIKE %s OR ip LIKE %s)"
                params.extend([term] * 3)
        cursor.execute(base, params)
        return cursor.fetchall()
    except Error as e:
        logger.error(f"Error obteniendo dispositivos: {e}", exc_info=True)
        return []
    finally:
        cursor.close()
        conn.close()


# === Nueva función para marcar confiabilidad ===
def marcar_confiabilidad(mac: str, es_confiable: bool) -> bool:
    """
    Actualiza el campo es_confiable de un dispositivo dado su MAC.
    """
    conn = get_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE dispositivos SET es_confiable=%s WHERE mac=%s",
            (es_confiable, mac)
        )
        conn.commit()
        return True
    except Error as e:
        logger.error(f"Error marcando confiabilidad: {e}", exc_info=True)
        return False
    finally:
        cursor.close()
        conn.close()
