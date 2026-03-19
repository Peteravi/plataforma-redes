import logging
import re
import traceback
from datetime import datetime

from flask import Blueprint, jsonify, request

from backend.database import (
    agregar_nota_dispositivo,
    cancelar_escaneo_programado as db_cancelar_escaneo,
    obtener_dispositivos as db_obtener_dispositivos,
    obtener_estadisticas,
    obtener_escaneos_programados as db_obtener_escaneos,
    programar_escaneo as db_programar_escaneo,
)
from backend.services.alertas_service import obtener_alertas
from backend.services.escaneo_service import marcar_confiabilidad_service, realizar_escaneo

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

escaneo_bp = Blueprint('escaneo', __name__, url_prefix='/api')

MAC_REGEX = re.compile(r'^([0-9A-F]{2}:){5}[0-9A-F]{2}$')
TIPOS_VALIDOS = {'completo', 'rapido', 'personalizado'}
REPETICIONES_VALIDAS = {'una_vez', 'diario', 'semanal', 'mensual'}
MAX_NOTA_LEN = 255


def response_ok(data=None, message='OK', status_code=200):
    body = {
        'status': 'success',
        'message': message,
    }
    if data:
        body.update(data)
    return jsonify(body), status_code


def response_error(message='Error', status_code=400, **extra):
    body = {
        'status': 'error',
        'message': message,
    }
    if extra:
        body.update(extra)
    return jsonify(body), status_code


def normalizar_mac(mac):
    if not isinstance(mac, str):
        return None
    mac = mac.strip().upper().replace('-', ':')
    if MAC_REGEX.fullmatch(mac):
        return mac
    return None


def normalizar_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {'true', '1', 'si', 'sí', 'yes'}:
            return True
        if v in {'false', '0', 'no'}:
            return False
    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False
    return None


def validar_nota(nota):
    if nota is None:
        return None, 'La nota es obligatoria'
    if not isinstance(nota, str):
        return None, 'La nota debe ser texto'

    nota = nota.strip()

    if not nota:
        return None, 'La nota no puede estar vacía'

    if len(nota) > MAX_NOTA_LEN:
        return None, f'La nota no puede superar {MAX_NOTA_LEN} caracteres'

    return nota, None


def validar_tipo(tipo):
    if not isinstance(tipo, str):
        return None
    tipo = tipo.strip().lower()
    return tipo if tipo in TIPOS_VALIDOS else None


def validar_repeticion(repeticion):
    if repeticion is None:
        return 'una_vez'
    if not isinstance(repeticion, str):
        return None
    repeticion = repeticion.strip().lower()
    return repeticion if repeticion in REPETICIONES_VALIDAS else None


def validar_fecha_programada(fecha_programada):
    if not fecha_programada:
        return None, 'fecha_programada es obligatoria'

    if not isinstance(fecha_programada, str):
        return None, 'fecha_programada debe ser texto en formato ISO'

    valor = fecha_programada.strip()
    if not valor:
        return None, 'fecha_programada es obligatoria'

    try:
        fecha_dt = datetime.fromisoformat(valor.replace('Z', ''))
    except Exception:
        return None, 'fecha_programada tiene formato inválido'

    if fecha_dt <= datetime.now():
        return None, 'La fecha programada debe estar en el futuro'

    return valor, None


@escaneo_bp.route('/escaneo', methods=['GET'])
def escaneo():
    try:
        logger.info('Endpoint /escaneo invocado')
        resultado = realizar_escaneo()

        if resultado.get('status') == 'busy':
            return jsonify(resultado), 409

        if resultado.get('status') in {'success', 'partial_success'}:
            return jsonify(resultado), 200

        return jsonify(resultado), 500
    except Exception as e:
        logger.critical('Error crítico en /escaneo', exc_info=True)
        return jsonify({
            'status': 'critical_error',
            'message': 'Error interno del servidor',
            'details': str(e),
            'stacktrace': traceback.format_exc().splitlines(),
        }), 500


@escaneo_bp.route('/estadisticas', methods=['GET'])
def estadisticas():
    try:
        logger.info('Endpoint /estadisticas invocado')
        stats = obtener_estadisticas()
        status_code = 200 if stats.get('status') == 'success' else 500
        return jsonify(stats), status_code
    except Exception as e:
        logger.error('Error obteniendo estadísticas', exc_info=True)
        return response_error(str(e), 500)


@escaneo_bp.route('/dispositivos', methods=['GET'])
def listar_dispositivos():
    try:
        dispositivos = db_obtener_dispositivos()
        return response_ok({'dispositivos': dispositivos}, 'Dispositivos obtenidos correctamente')
    except Exception as e:
        logger.error('Error obteniendo dispositivos', exc_info=True)
        return response_error(str(e), 500)


@escaneo_bp.route('/alertas', methods=['GET'])
def listar_alertas():
    try:
        alertas = obtener_alertas()
        return response_ok(
            {
                'alertas': alertas,
                'count': len(alertas),
            },
            'Alertas obtenidas correctamente'
        )
    except Exception as e:
        logger.error('Error obteniendo alertas', exc_info=True)
        return response_error(str(e), 500)


@escaneo_bp.route('/dispositivos/confiabilidad', methods=['POST'])
def marcar_confiabilidad():
    try:
        payload = request.get_json(silent=True) or {}

        mac = normalizar_mac(payload.get('mac'))
        es_confiable = normalizar_bool(payload.get('es_confiable'))

        if not mac:
            return response_error('MAC inválida. Usa formato AA:BB:CC:DD:EE:FF', 400)

        if es_confiable is None:
            return response_error('es_confiable debe ser booleano', 400)

        ok = marcar_confiabilidad_service(mac, es_confiable)
        if not ok:
            return response_error('No se pudo actualizar la confiabilidad', 400)

        return response_ok(message='Confiabilidad actualizada correctamente')
    except Exception as e:
        logger.error('Error marcando confiabilidad', exc_info=True)
        return response_error(str(e), 500)


@escaneo_bp.route('/dispositivos/nota', methods=['POST'])
def guardar_nota():
    try:
        payload = request.get_json(silent=True) or {}

        mac = normalizar_mac(payload.get('mac'))
        nota, error_nota = validar_nota(payload.get('nota'))

        if not mac:
            return response_error('MAC inválida. Usa formato AA:BB:CC:DD:EE:FF', 400)

        if error_nota:
            return response_error(error_nota, 400)

        ok = agregar_nota_dispositivo(mac, nota)
        if not ok:
            return response_error('No se pudo guardar la nota', 400)

        return response_ok(message='Nota actualizada correctamente')
    except Exception as e:
        logger.error('Error guardando nota', exc_info=True)
        return response_error(str(e), 500)


@escaneo_bp.route('/escaneos/programar', methods=['POST'])
def programar_escaneo():
    try:
        payload = request.get_json(silent=True) or {}

        tipo = validar_tipo(payload.get('tipo'))
        repeticion = validar_repeticion(payload.get('repeticion', 'una_vez'))
        fecha_programada, error_fecha = validar_fecha_programada(payload.get('fecha_programada'))

        if not tipo:
            return response_error(
                'Tipo inválido. Valores permitidos: completo, rapido, personalizado',
                400
            )

        if not repeticion:
            return response_error(
                'Repetición inválida. Valores permitidos: una_vez, diario, semanal, mensual',
                400
            )

        if error_fecha:
            return response_error(error_fecha, 400)

        escaneo_id = db_programar_escaneo(tipo, fecha_programada, repeticion)
        if not escaneo_id:
            return response_error('No se pudo programar el escaneo', 400)

        return response_ok(
            {
                'id': escaneo_id,
                'tipo': tipo,
                'fecha_programada': fecha_programada,
                'repeticion': repeticion,
            },
            'Escaneo programado correctamente'
        )
    except ValueError as e:
        return response_error(str(e), 400)
    except Exception as e:
        logger.error('Error programando escaneo', exc_info=True)
        return response_error(str(e), 500)


@escaneo_bp.route('/escaneos/programados', methods=['GET'])
def obtener_escaneos_programados():
    try:
        pendientes_raw = request.args.get('pendientes', 'true')
        pendientes = str(pendientes_raw).strip().lower() != 'false'

        escaneos = db_obtener_escaneos(pendientes=pendientes)
        return response_ok(
            {
                'escaneos': escaneos,
                'count': len(escaneos),
            },
            'Escaneos programados obtenidos correctamente'
        )
    except Exception as e:
        logger.error('Error obteniendo escaneos programados', exc_info=True)
        return response_error(str(e), 500)


@escaneo_bp.route('/escaneos/cancelar/<int:escaneo_id>', methods=['POST'])
def cancelar_escaneo(escaneo_id):
    try:
        if escaneo_id <= 0:
            return response_error('ID de escaneo inválido', 400)

        ok = db_cancelar_escaneo(escaneo_id)
        if not ok:
            return response_error('No se pudo cancelar el escaneo', 400)

        return response_ok({'id': escaneo_id}, 'Escaneo cancelado correctamente')
    except Exception as e:
        logger.error('Error cancelando escaneo programado', exc_info=True)
        return response_error(str(e), 500)