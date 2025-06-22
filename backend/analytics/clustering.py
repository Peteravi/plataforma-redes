# backend/analytics/clustering.py

import pandas as pd
from sqlalchemy import create_engine
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

# 1) Define aquí la conexión (igual que en database.py)
# Si cambias credenciales o host, hazlo solo en DB_URL
DB_URL = "mysql+mysqlconnector://root:piteravi07@localhost/PlataformaRedes"
ENGINE = create_engine(DB_URL, echo=False)

def compute_device_clusters(k: int = 3) -> pd.DataFrame:
    """
    Extrae métricas de cada dispositivo, aplica K-Means y devuelve
    un DataFrame con columnas [dispositivo_id, cluster].
    """
    # Métrica 1: frecuencia de logs
    freq = pd.read_sql("""
      SELECT d.dispositivo_id,
             COUNT(ld.log_id) AS frecuencia
      FROM logs_dispositivos ld
      JOIN dispositivos d ON ld.dispositivo_id=d.dispositivo_id
      GROUP BY d.dispositivo_id
    """, ENGINE)

    # Métrica 2: duración media de escaneos
    dur = pd.read_sql("""
      SELECT ld.dispositivo_id,
             AVG(e.duracion_segundos) AS duracion_media
      FROM logs_dispositivos ld
      JOIN escaneos e ON ld.escaneo_id=e.escaneo_id
      GROUP BY ld.dispositivo_id
    """, ENGINE)

    # Métrica 3: número de notas
    notas = pd.read_sql("""
      SELECT dispositivo_id,
             IFNULL(
               (LENGTH(notas) - LENGTH(REPLACE(notas, '\\n', ''))) + 1,
               0
             ) AS n_notas
      FROM dispositivos
    """, ENGINE)

    # Métrica 4: veces marcado confiable
    conf = pd.read_sql("""
      SELECT dispositivo_id,
             SUM(es_confiable) AS veces_confiable
      FROM dispositivos
      GROUP BY dispositivo_id
    """, ENGINE)

    # Métrica 5: alertas generadas
    alerts = pd.read_sql("""
      SELECT dispositivo_id,
             COUNT(*) AS alertas_generadas
      FROM alertas
      WHERE dispositivo_id IS NOT NULL
      GROUP BY dispositivo_id
    """, ENGINE)

    # 2) Combina todo en un DataFrame
    df = (freq
          .merge(dur,    on='dispositivo_id', how='left')
          .merge(notas,  on='dispositivo_id', how='left')
          .merge(conf,   on='dispositivo_id', how='left')
          .merge(alerts, on='dispositivo_id', how='left')
          .fillna(0))

    features = df[['frecuencia', 'duracion_media', 'n_notas', 'veces_confiable', 'alertas_generadas']]

    # 3) Normaliza
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(features)

    # 4) Aplica KMeans
    model = KMeans(n_clusters=k, random_state=42)
    df['cluster'] = model.fit_predict(X_scaled)

    # 5) Devuelve solo las columnas necesarias
    return df[['dispositivo_id', 'cluster']]
