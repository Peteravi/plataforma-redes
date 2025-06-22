# backend/analytics/scheduler.py
from clustering import compute_device_clusters
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from backend.analytics import ENGINE  

def update_clusters_in_db():
    df = compute_device_clusters(k=3)
    Session = sessionmaker(bind=ENGINE)
    session = Session()
    # Ejecutar un UPDATE por cada fila
    for _, row in df.iterrows():
        session.execute(
            text("UPDATE dispositivos SET cluster = :c WHERE dispositivo_id = :id"),
            {'c': int(row.cluster), 'id': int(row.dispositivo_id)}
        )
    session.commit()
