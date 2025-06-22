import platform
import subprocess
import re
import socket
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def detectar_tipo_dispositivo(mac: str, nombre: str) -> str:
    nombre = (nombre or '').lower()
    # Normalizar MAC a mayúsculas y dos puntos
    mac_norm = mac.upper().replace('-', ':')
    mac_raw = mac_norm.replace(':', '')

    # Keywords para móvil y PC
    movil_keys = ['iphone', 'ipad', 'android', 'galaxy', 'samsung', 'pixel', 'móvil', 'smartphone']
    pc_keys    = ['pc', 'windows', 'desktop', 'laptop', 'notebook', 'hp', 'dell', 'microsoft']

    if any(k in nombre for k in movil_keys):
        return 'Móvil'
    if any(k in nombre for k in pc_keys):
        return 'PC'

    # Detección OUI simplificada
    oui = mac_raw[:6].lower()
    prefijosois = {
        'apple':    ['001CB3', '000393', '001B63'],
        'samsung':  ['0007AB', '000FE4'],
        'dell':     ['001422', '001C23'],
        'hp':       ['002264', '001A4B'],
    }
    for fab, lst in prefijosois.items():
        if oui in lst:
            return 'Móvil' if fab in ['apple','samsung'] else 'PC'

    # Heurística U/L bit
    try:
        primer = int(mac_raw[:2], 16)
        return 'PC' if (primer & 2) == 0 else 'Móvil'
    except:
        return 'Desconocido'


def obtener_dispositivos_arp() -> str:
    sistema = platform.system().lower()
    cmd = ['arp', '-a']  # Mismo comando en Win/Linux/Mac
    try:
        if sistema == 'windows':
            return subprocess.check_output(cmd, creationflags=subprocess.CREATE_NO_WINDOW).decode('latin-1', errors='ignore')
        else:
            return subprocess.check_output(cmd).decode('utf-8', errors='ignore')
    except Exception as e:
        logger.error(f"Error ejecutando ARP: {e}", exc_info=True)
        return ''


def escanear_red() -> list:
    """
    Ejecuta ARP y devuelve una lista de dispositivos con IP y MAC.
    Ahora reconoce tanto MAC con ':' como con '-'.
    """
    salida = obtener_dispositivos_arp()
    dispositivos = []

    # Regex que captura IPv4 y MAC en formato XX:XX:XX:XX:XX:XX o XX-XX-XX-XX-XX-XX
    patron = re.compile(r'(\d+\.\d+\.\d+\.\d+).+?([0-9A-Fa-f:-]{17})')

    for linea in salida.splitlines():
        m = patron.search(linea)
        if not m:
            continue
        ip, mac = m.groups()
        mac = mac.upper().replace('-', ':')
        try:
            nombre = socket.gethostbyaddr(ip)[0]
        except (socket.herror, socket.gaierror):
            nombre = f"Desconocido-{ip}"
        tipo = detectar_tipo_dispositivo(mac, nombre)
        dispositivos.append({
            'ip': ip,
            'mac': mac,
            'estado': 'activo',
            'ultima_detectado': datetime.now().isoformat(),
            'nombre_dispositivo': nombre,
            'tipo_dispositivo': tipo
        })

    logger.info(f"Escaneo ARP encontró {len(dispositivos)} dispositivos")
    return dispositivos
