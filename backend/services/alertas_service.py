import logging
from backend.database import obtener_alertas_pendientes

logger = logging.getLogger(__name__)


def obtener_alertas():
    """
    Recupera las alertas pendientes de la BD.
    """
    try:
        pendientes = obtener_alertas_pendientes()
        return {'status': 'success', 'alertas': pendientes, 'count': len(pendientes)}
    except Exception as e:
        logger.error(f"Error en obtener_alertas: {e}", exc_info=True)
        return {'status': 'error', 'message': str(e)}
