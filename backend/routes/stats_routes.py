# backend/routes/stats_routes.py

from flask import Blueprint, jsonify, request
from backend.database import get_connection
from backend.analytics.clustering import compute_device_clusters

stats_bp = Blueprint('stats', __name__, url_prefix='/api/stats')

@stats_bp.route('/summary', methods=['GET'])
def stats_summary():
    """
    Devuelve un resumen estadístico con:
      - avg_por_escaneo: promedio de dispositivos detectados por escaneo
      - dist_os: distribución por sistema operativo
      - dist_estado: distribución por estado ('activo','inactivo','desconocido')
      - dist_confianza: conteo de dispositivos confiables vs no confiables
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Promedio de dispositivos por escaneo
    cursor.execute("SELECT AVG(total_dispositivos) AS avg_disp FROM escaneos")
    avg_disp = cursor.fetchone().get('avg_disp') or 0

    # Distribución por sistema operativo
    cursor.execute(
        "SELECT COALESCE(sistema_operativo, 'Desconocido') AS label, COUNT(*) AS count "
        "FROM dispositivos GROUP BY sistema_operativo"
    )
    dist_os = {row['label']: row['count'] for row in cursor.fetchall()}

    # Distribución por estado
    cursor.execute(
        "SELECT estado, COUNT(*) AS count "
        "FROM dispositivos GROUP BY estado"
    )
    dist_estado = {row['estado']: row['count'] for row in cursor.fetchall()}

    # Distribución por confiabilidad
    cursor.execute(
        "SELECT es_confiable, COUNT(*) AS count "
        "FROM dispositivos GROUP BY es_confiable"
    )
    dist_conf = {'confiables': 0, 'no_confiables': 0}
    for row in cursor.fetchall():
        key = 'confiables' if row['es_confiable'] else 'no_confiables'
        dist_conf[key] = row['count']

    cursor.close()
    conn.close()

    return jsonify({
        'avg_por_escaneo': avg_disp,
        'dist_os': dist_os,
        'dist_estado': dist_estado,
        'dist_confianza': dist_conf
    })


@stats_bp.route('/timeseries', methods=['GET'])
def stats_timeseries():
    """
    Devuelve serie de tiempo de dispositivos detectados agrupada por día o mes.
    Query param `period`: 'daily' (por defecto) o 'monthly'.
    """
    period = request.args.get('period', 'daily')
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if period == 'monthly':
        date_format = '%Y-%m'
    else:
        date_format = '%Y-%m-%d'

    # Agrupar por la misma expresión usada en SELECT
    query = (
        "SELECT DATE_FORMAT(fecha, %s) AS period, "
        "SUM(total_dispositivos) AS total "
        "FROM escaneos "
        "GROUP BY DATE_FORMAT(fecha, %s) "
        "ORDER BY DATE_FORMAT(fecha, %s)"
    )
    cursor.execute(query, (date_format, date_format, date_format))
    series = cursor.fetchall()

    cursor.close()
    conn.close()
    return jsonify(series)


@stats_bp.route('/alerts_per_day', methods=['GET'])
def alerts_per_day():
    """
    Devuelve número de alertas agrupadas por fecha (YYYY-MM-DD).
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT DATE(fecha) AS date, COUNT(*) AS count "
        "FROM alertas GROUP BY DATE(fecha) ORDER BY date"
    )
    data = cursor.fetchall()
    cursor.close(); conn.close()
    return jsonify(data)

@stats_bp.route('/alerts_by_type', methods=['GET'])
def alerts_by_type():
    """
    Devuelve número de alertas por tipo.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT tipo AS alert_type, COUNT(*) AS count "
        "FROM alertas GROUP BY tipo"
    )
    data = cursor.fetchall()
    cursor.close(); conn.close()
    return jsonify(data)

@stats_bp.route('/top_devices', methods=['GET'])
def top_devices():
    """
    Devuelve top N dispositivos más frecuentes en los logs (param ?limit). Por defecto 5.
    """
    limit = request.args.get('limit', 5, type=int)
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT d.nombre_dispositivo AS name, COUNT(ld.dispositivo_id) AS occurrences "
        "FROM logs_dispositivos ld "
        "JOIN dispositivos d ON ld.dispositivo_id=d.dispositivo_id "
        "GROUP BY ld.dispositivo_id "
        "ORDER BY occurrences DESC LIMIT %s", (limit,)
    )
    data = cursor.fetchall()
    cursor.close(); conn.close()
    return jsonify(data)

@stats_bp.route('/scan_duration_by_day', methods=['GET'])
def scan_duration_by_day():
    """
    Devuelve duración promedio de escaneo agrupada por fecha.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT DATE(fecha) AS date, AVG(duracion_segundos) AS avg_duration "
        "FROM escaneos GROUP BY DATE(fecha) ORDER BY date"
    )
    data = cursor.fetchall()
    cursor.close(); conn.close()
    return jsonify(data)

@stats_bp.route('/clusters', methods=['GET'])
def get_clusters():
    """
    Devuelve una lista de dispositivos con su cluster asignado,
    calculado al vuelo por compute_device_clusters().
    """
    # 1) Calcula los clusters en memoria
    df = compute_device_clusters(k=3)  # Ajusta k si quieres otro número de clusters

    # 2) Consulta el MAC para cada dispositivo_id
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT dispositivo_id, mac FROM dispositivos")
    mac_map = {row['dispositivo_id']: row['mac'] for row in cursor.fetchall()}
    cursor.close()
    conn.close()

    # 3) Fusiona y prepara la respuesta
    clusters = []
    for _, row in df.iterrows():
        did = int(row.dispositivo_id)
        clusters.append({
            'dispositivo_id': did,
            'mac': mac_map.get(did),
            'cluster': int(row.cluster)
        })

    return jsonify(clusters), 200