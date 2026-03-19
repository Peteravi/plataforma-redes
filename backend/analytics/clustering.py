import pandas as pd
from sklearn.cluster import KMeans

from backend.database import get_connection


def compute_device_clusters(k=3):
    conn = get_connection()
    if not conn:
        return {
            'status': 'error',
            'message': 'No se pudo conectar a la base de datos',
            'clusters': [],
        }

    try:
        query = """
            SELECT
                d.dispositivo_id,
                COALESCE(d.nombre_dispositivo, d.mac) AS nombre,
                COUNT(ld.id) AS num_escaneos,
                SUM(CASE WHEN d.es_confiable = 1 THEN 1 ELSE 0 END) AS es_confiable_num,
                0 AS alertas_generadas
            FROM dispositivos d
            LEFT JOIN logs_dispositivos ld ON d.dispositivo_id = ld.dispositivo_id
            GROUP BY d.dispositivo_id, d.nombre_dispositivo, d.mac
        """

        df = pd.read_sql(query, conn)

        if df.empty:
            return {
                'status': 'success',
                'clusters': [],
                'message': 'No hay dispositivos suficientes para clusterizar',
            }

        n = min(max(1, k), len(df))
        features = df[['num_escaneos', 'es_confiable_num', 'alertas_generadas']].fillna(0)

        model = KMeans(n_clusters=n, random_state=42, n_init=10)
        df['cluster'] = model.fit_predict(features)

        return {
            'status': 'success',
            'clusters': df[['dispositivo_id', 'nombre', 'cluster']].to_dict(orient='records'),
        }
    finally:
        conn.close()