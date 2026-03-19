from flask import Blueprint, jsonify, request

from backend.analytics.clustering import compute_device_clusters
from backend.database import get_connection

stats_bp = Blueprint('stats', __name__, url_prefix='/api/stats')


@stats_bp.route('/summary', methods=['GET'])
def summary():
    conn = get_connection()
    if not conn:
        return jsonify({'message': 'No se pudo conectar a la base de datos'}), 500

    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute('SELECT COALESCE(AVG(total_dispositivos), 0) AS avg_por_escaneo FROM escaneos')
        avg_row = cursor.fetchone() or {}
        avg_por_escaneo = float(avg_row.get('avg_por_escaneo') or 0)

        cursor.execute("""
            SELECT COALESCE(tipo_dispositivo, 'Desconocido') AS tipo, COUNT(*) AS total
            FROM dispositivos
            GROUP BY COALESCE(tipo_dispositivo, 'Desconocido')
        """)
        dist_tipo = {row['tipo']: row['total'] for row in cursor.fetchall()}

        cursor.execute("""
            SELECT
                CASE
                    WHEN es_confiable = 1 THEN 'Confiable'
                    ELSE 'No confiable'
                END AS categoria,
                COUNT(*) AS total
            FROM dispositivos
            GROUP BY CASE WHEN es_confiable = 1 THEN 'Confiable' ELSE 'No confiable' END
        """)
        dist_confianza = {row['categoria']: row['total'] for row in cursor.fetchall()}

        return jsonify({
            'avg_por_escaneo': avg_por_escaneo,
            'dist_tipo': dist_tipo,
            'dist_confianza': dist_confianza,
        })
    finally:
        if cursor:
            cursor.close()
        conn.close()


@stats_bp.route('/alerts_per_day', methods=['GET'])
def alerts_per_day():
    conn = get_connection()
    if not conn:
        return jsonify([])

    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT DATE(fecha) AS date, COUNT(*) AS count
            FROM alertas
            GROUP BY DATE(fecha)
            ORDER BY DATE(fecha)
        """)
        rows = cursor.fetchall() or []
        return jsonify([
            {'date': str(row['date']), 'count': row['count']}
            for row in rows
        ])
    finally:
        if cursor:
            cursor.close()
        conn.close()


@stats_bp.route('/alerts_by_type', methods=['GET'])
def alerts_by_type():
    conn = get_connection()
    if not conn:
        return jsonify([])

    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT COALESCE(tipo, 'Desconocido') AS alert_type, COUNT(*) AS count
            FROM alertas
            GROUP BY COALESCE(tipo, 'Desconocido')
            ORDER BY count DESC
        """)
        return jsonify(cursor.fetchall() or [])
    finally:
        if cursor:
            cursor.close()
        conn.close()


@stats_bp.route('/top_devices', methods=['GET'])
def top_devices():
    limit = request.args.get('limit', default=5, type=int)
    if limit <= 0:
        limit = 5

    conn = get_connection()
    if not conn:
        return jsonify([])

    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT COALESCE(d.nombre_dispositivo, d.mac) AS name, COUNT(*) AS occurrences
            FROM logs_dispositivos ld
            JOIN dispositivos d ON d.dispositivo_id = ld.dispositivo_id
            GROUP BY d.dispositivo_id, d.nombre_dispositivo, d.mac
            ORDER BY occurrences DESC
            LIMIT %s
        """, (limit,))
        return jsonify(cursor.fetchall() or [])
    finally:
        if cursor:
            cursor.close()
        conn.close()


@stats_bp.route('/scan_duration_by_day', methods=['GET'])
def scan_duration_by_day():
    conn = get_connection()
    if not conn:
        return jsonify([])

    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT DATE(fecha) AS date, AVG(duracion_segundos) AS avg_duration
            FROM escaneos
            GROUP BY DATE(fecha)
            ORDER BY DATE(fecha)
        """)
        rows = cursor.fetchall() or []
        return jsonify([
            {'date': str(row['date']), 'avg_duration': float(row['avg_duration'] or 0)}
            for row in rows
        ])
    finally:
        if cursor:
            cursor.close()
        conn.close()


@stats_bp.route('/timeseries', methods=['GET'])
def timeseries():
    period = request.args.get('period', 'day').lower()

    format_map = {
        'day': '%Y-%m-%d',
        'week': '%x-%v',
        'month': '%Y-%m',
    }
    sql_format = format_map.get(period, '%Y-%m-%d')

    conn = get_connection()
    if not conn:
        return jsonify([])

    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"""
            SELECT DATE_FORMAT(fecha, %s) AS period, COUNT(*) AS total
            FROM escaneos
            GROUP BY DATE_FORMAT(fecha, %s)
            ORDER BY MIN(fecha)
        """, (sql_format, sql_format))
        return jsonify(cursor.fetchall() or [])
    finally:
        if cursor:
            cursor.close()
        conn.close()


@stats_bp.route('/clusters', methods=['GET'])
def clusters():
    data = compute_device_clusters(k=3)
    return jsonify(data)