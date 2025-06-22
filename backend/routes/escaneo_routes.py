# backend/routes/escaneo_routes.py

import logging
import traceback
from datetime import datetime

from flask import Blueprint, jsonify, request

from backend.services.escaneo_service import (
    realizar_escaneo,
    marcar_confiabilidad_service
)
from backend.services.alertas_service import obtener_alertas
from backend.database import (
    obtener_estadisticas,
    programar_escaneo as db_programar_escaneo,
    obtener_escaneos_programados as db_obtener_escaneos,
    cancelar_escaneo_programado as db_cancelar_escaneo
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

escaneo_bp = Blueprint('escaneo', __name__, url_prefix='/api')


@escaneo_bp.route('/escaneo', methods=['GET'])
def escaneo():
    try:
        logger.info("Endpoint /escaneo invocado")
        resultado = realizar_escaneo()
        status_code = 200 if resultado['status'] in ['success', 'partial_success'] else 500
        return jsonify(resultado), status_code

    except Exception as e:
        logger.critical("Error crítico en /escaneo", exc_info=True)
        return jsonify({
            'status': 'critical_error',
            'message': 'Error interno del servidor',
            'details': str(e),
            'stacktrace': traceback.format_exc().splitlines()
        }), 500


@escaneo_bp.route('/estadisticas', methods=['GET'])
def estadisticas():
    try:
        logger.info("Endpoint /estadisticas invocado")
        stats = obtener_estadisticas()
        status_code = 200 if stats.get('status') == 'success' else 500
        return jsonify(stats), status_code

    except Exception as e:
        logger.critical("Error crítico en /estadisticas", exc_info=True)
        return jsonify({
            'status': 'critical_error',
            'message': 'Error interno al procesar estadísticas',
            'error': str(e)
        }), 500


@escaneo_bp.route('/alertas', methods=['GET'])
def alertas():
    try:
        return jsonify(obtener_alertas()), 200
    except Exception as e:
        logger.error("Error en /alertas", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Error al obtener alertas'}), 500


@escaneo_bp.route('/escaneos/programar', methods=['POST'])
def programar_escaneo():
    """
    Programa un nuevo escaneo y devuelve la fecha_programada en formato ISO
    para que el frontend la muestre correctamente.
    """
    data = request.get_json() or {}
    tipo = data.get('tipo')
    fecha = data.get('fecha_programada')
    repeticion = data.get('repeticion')

    # Validaciones básicas
    if tipo not in ['completo', 'rapido', 'personalizado'] \
       or repeticion not in ['una_vez', 'diario', 'semanal', 'mensual'] \
       or not fecha:
        return jsonify({'status': 'error', 'message': 'Datos inválidos'}), 400

    nuevo_id = db_programar_escaneo(tipo, fecha, repeticion)
    if not nuevo_id:
        return jsonify({'status': 'error', 'message': 'No se pudo programar'}), 500

    # Devolvemos la misma fecha ISO que recibió el frontend
    return jsonify({
        'status': 'success',
        'id': nuevo_id,
        'fecha_programada': fecha
    }), 201


@escaneo_bp.route('/escaneos/programados', methods=['GET'])
def obtener_escaneos_programados():
    """
    Recupera los escaneos pendientes, convierte datetime a ISO y los devuelve.
    """
    escaneos = db_obtener_escaneos(pendientes=True)

    for e in escaneos:
        fp = e.get('fecha_programada')
        if isinstance(fp, datetime):
            # Convertir a 'YYYY-MM-DDTHH:MM'
            e['fecha_programada'] = fp.isoformat(sep='T', timespec='minutes')

    return jsonify({'status': 'success', 'escaneos': escaneos}), 200


@escaneo_bp.route('/escaneos/cancelar/<int:escaneo_id>', methods=['POST'])
def cancelar_escaneo(escaneo_id):
    """
    Cancela un escaneo pendiente dado su ID.
    """
    ok = db_cancelar_escaneo(escaneo_id)
    if ok:
        return jsonify({'status': 'success'}), 200
    return jsonify({'status': 'error', 'message': 'No cancelable o inexistente'}), 404


@escaneo_bp.route('/dispositivos/marcar-confiable', methods=['POST'])
def marcar_confiable():
    data = request.get_json() or {}
    mac = data.get('mac')
    es_confiable = data.get('es_confiable')

    if not mac or es_confiable is None:
        return jsonify({'status': 'error', 'message': 'Faltan parámetros'}), 400

    success = marcar_confiabilidad_service(mac, es_confiable)
    code = 200 if success else 500
    return jsonify({'status': 'success' if success else 'error'}), code


@escaneo_bp.route('/dispositivos/agregar-nota', methods=['POST'])
def agregar_nota():
    from backend.database import agregar_nota_dispositivo

    data = request.get_json() or {}
    mac = data.get('mac')
    nota = data.get('nota')

    if not mac or not nota:
        return jsonify({'status': 'error', 'message': 'Faltan parámetros'}), 400

    success = agregar_nota_dispositivo(mac, nota)
    code = 200 if success else 500
    return jsonify({'status': 'success' if success else 'error'}), code


@escaneo_bp.route('/dispositivos', methods=['GET'])
def obtener_dispositivos():
    filtros = {
        'confiable': request.args.get('confiable', type=lambda v: v.lower() == 'true'),
        'tipo': request.args.get('tipo'),
        'busqueda': request.args.get('busqueda')
    }
    from backend.database import obtener_dispositivos as db_obtener
    dispositivos = db_obtener(filtros)
    return jsonify({'status': 'success', 'dispositivos': dispositivos, 'total': len(dispositivos)}), 200
