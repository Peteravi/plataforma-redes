import ipaddress
import platform
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from backend.database import get_connection


def _obtener_mac_existentes():
    conn = get_connection()
    if not conn:
        return set()

    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT mac FROM dispositivos')
        return {
            str(row[0]).upper().replace('-', ':').strip()
            for row in cursor.fetchall()
            if row and row[0]
        }
    except Exception:
        return set()
    finally:
        if cursor:
            cursor.close()
        conn.close()


def _resolver_hostname(ip: str):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return None


def _inferir_tipo(nombre: str | None):
    if not nombre:
        return 'Desconocido'

    valor = nombre.lower()

    if any(k in valor for k in [
        'iphone', 'android', 'samsung', 'xiaomi', 'huawei',
        'motorola', 'redmi', 'galaxy', 'pixel'
    ]):
        return 'Móvil'

    if any(k in valor for k in [
        'printer', 'epson', 'hp', 'canon', 'brother', 'xerox'
    ]):
        return 'Impresora'

    if any(k in valor for k in [
        'tv', 'roku', 'chromecast', 'firetv', 'smarttv', 'bravia', 'lgwebos'
    ]):
        return 'TV / Streaming'

    if any(k in valor for k in [
        'pc', 'desktop', 'laptop', 'lenovo', 'dell', 'asus',
        'acer', 'msi', 'thinkpad', 'macbook', 'imac', 'notebook'
    ]):
        return 'Computadora'

    if any(k in valor for k in [
        'router', 'mikrotik', 'tplink', 'tp-link', 'ubiquiti', 'huawei-router'
    ]):
        return 'Router / Red'

    return 'Desconocido'


def _ejecutar_comando(comando):
    try:
        return subprocess.check_output(
            comando,
            shell=isinstance(comando, str),
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
    except Exception:
        return ''


def _obtener_info_red_windows():
    salida = _ejecutar_comando('ipconfig')

    ip = None
    mascara = None
    gateway = None

    lineas = salida.splitlines()

    for i, linea in enumerate(lineas):
        if not ip:
            match_ip = re.search(r'IPv4[^:]*:\s*(\d+\.\d+\.\d+\.\d+)', linea)
            if match_ip:
                ip = match_ip.group(1)

        if not mascara:
            match_mask = re.search(r'M[aá]scara de subred[ .:]*\s*(\d+\.\d+\.\d+\.\d+)', linea, re.IGNORECASE)
            if match_mask:
                mascara = match_mask.group(1)
            else:
                match_mask_en = re.search(r'Subnet Mask[ .:]*\s*(\d+\.\d+\.\d+\.\d+)', linea, re.IGNORECASE)
                if match_mask_en:
                    mascara = match_mask_en.group(1)

        if not gateway:
            match_gw = re.search(r'Puerta de enlace predeterminada[ .:]*\s*(\d+\.\d+\.\d+\.\d+)', linea, re.IGNORECASE)
            if match_gw:
                gateway = match_gw.group(1)
            else:
                match_gw_en = re.search(r'Default Gateway[ .:]*\s*(\d+\.\d+\.\d+\.\d+)', linea, re.IGNORECASE)
                if match_gw_en:
                    gateway = match_gw_en.group(1)

    return ip, mascara, gateway


def _obtener_info_red_linux():
    salida_ip = _ejecutar_comando("ip -4 addr")
    salida_route = _ejecutar_comando("ip route")

    ip = None
    mascara = None
    gateway = None

    match_ip = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)', salida_ip)
    if match_ip:
        ip = match_ip.group(1)
        prefijo = int(match_ip.group(2))
        try:
            red = ipaddress.IPv4Network(f'0.0.0.0/{prefijo}')
            mascara = str(red.netmask)
        except Exception:
            mascara = None

    match_gw = re.search(r'default via\s+(\d+\.\d+\.\d+\.\d+)', salida_route)
    if match_gw:
        gateway = match_gw.group(1)

    return ip, mascara, gateway


def _obtener_info_red():
    sistema = platform.system().lower()

    if 'windows' in sistema:
        return _obtener_info_red_windows()

    if 'linux' in sistema:
        return _obtener_info_red_linux()

    return None, None, None


def _obtener_subred_objetivo():
    ip_local, mascara, gateway = _obtener_info_red()
    base_ip = ip_local or gateway

    if not base_ip:
        return None

    try:
        if ip_local and mascara:
            return ipaddress.ip_network(f'{ip_local}/{mascara}', strict=False)

        # fallback si no pudo obtener máscara
        return ipaddress.ip_network(f'{base_ip}/24', strict=False)
    except Exception:
        return None


def _ping_host(ip: str, timeout_ms: int = 250):
    sistema = platform.system().lower()

    try:
        if 'windows' in sistema:
            comando = ['ping', '-n', '1', '-w', str(timeout_ms), ip]
        else:
            # Linux/macOS
            timeout_seg = max(1, round(timeout_ms / 1000))
            comando = ['ping', '-c', '1', '-W', str(timeout_seg), ip]

        resultado = subprocess.run(
            comando,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False
        )
        return resultado.returncode == 0
    except Exception:
        return False


def _ping_rango_concurrente(network, max_hosts=None, workers=64, timeout_ms=250):
    if not network:
        return []

    hosts = [str(ip) for ip in network.hosts()]

    if max_hosts is not None and max_hosts > 0:
        hosts = hosts[:max_hosts]

    activos = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futuros = {
            executor.submit(_ping_host, ip, timeout_ms): ip
            for ip in hosts
        }

        for futuro in as_completed(futuros):
            ip = futuros[futuro]
            try:
                if futuro.result():
                    activos.append(ip)
            except Exception:
                pass

    return activos


def _leer_arp():
    sistema = platform.system().lower()

    if 'windows' in sistema:
        salida = _ejecutar_comando('arp -a')
    else:
        salida = _ejecutar_comando('ip neigh')
        if not salida.strip():
            salida = _ejecutar_comando('arp -a')

    encontrados = []

    patron_windows = re.compile(
        r'(\d+\.\d+\.\d+\.\d+)\s+([a-fA-F0-9-]{17}|[a-fA-F0-9:]{17})\s+(\w+)',
        re.IGNORECASE
    )

    patron_linux_ip_neigh = re.compile(
        r'(\d+\.\d+\.\d+\.\d+).*?lladdr\s+([a-fA-F0-9:]{17})',
        re.IGNORECASE
    )

    patron_linux_arp = re.compile(
        r'\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([a-fA-F0-9:]{17}|[a-fA-F0-9-]{17})',
        re.IGNORECASE
    )

    for match in patron_windows.finditer(salida):
        ip, mac, _tipo = match.groups()
        encontrados.append((ip, mac.upper().replace('-', ':')))

    for match in patron_linux_ip_neigh.finditer(salida):
        ip, mac = match.groups()
        encontrados.append((ip, mac.upper().replace('-', ':')))

    for match in patron_linux_arp.finditer(salida):
        ip, mac = match.groups()
        encontrados.append((ip, mac.upper().replace('-', ':')))

    # quitar duplicados
    unicos = []
    vistos = set()
    for ip, mac in encontrados:
        clave = (ip, mac)
        if clave in vistos:
            continue
        vistos.add(clave)
        unicos.append((ip, mac))

    return unicos


def _ip_valida(ip: str):
    try:
        ip_obj = ipaddress.ip_address(ip)

        if ip_obj.is_multicast:
            return False
        if ip_obj.is_loopback:
            return False
        if ip_obj.is_unspecified:
            return False
        if str(ip_obj) == '255.255.255.255':
            return False

        return True
    except Exception:
        return False


def _mac_valida(mac: str):
    if not mac:
        return False

    mac = mac.upper().replace('-', ':').strip()

    if mac == 'FF:FF:FF:FF:FF:FF':
        return False

    if mac == '00:00:00:00:00:00':
        return False

    if not re.fullmatch(r'([A-F0-9]{2}:){5}[A-F0-9]{2}', mac):
        return False

    return True


def _construir_dispositivo(ip: str, mac: str, existentes: set):
    nombre = _resolver_hostname(ip) or f'Dispositivo-{ip}'
    tipo = _inferir_tipo(nombre)

    return {
        'ip': ip,
        'mac': mac,
        'nombre_dispositivo': nombre,
        'estado': 'activo',
        'tipo_dispositivo': tipo,
        'ultima_detectado': datetime.now().isoformat(),
        'nuevo': mac not in existentes,
    }


def escanear_red_local(max_hosts=None, workers=64, timeout_ms=250):
    """
    Escanea la red local intentando detectar hosts activos y enriquecerlos con ARP.

    Parámetros:
    - max_hosts: limita cantidad de hosts a recorrer. None = toda la subred detectada.
    - workers: cantidad de hilos para ping concurrente.
    - timeout_ms: timeout del ping en milisegundos.
    """
    existentes = _obtener_mac_existentes()
    dispositivos = []
    vistos = set()

    network = _obtener_subred_objetivo()
    if not network:
        return []

    # 1) "Despertar" hosts de la red de forma concurrente
    _ping_rango_concurrente(
        network=network,
        max_hosts=max_hosts,
        workers=workers,
        timeout_ms=timeout_ms
    )

    # 2) Leer tabla ARP después del barrido
    entradas_arp = _leer_arp()

    # 3) Filtrar y construir dispositivos
    for ip, mac in entradas_arp:
        if not _ip_valida(ip):
            continue

        if not _mac_valida(mac):
            continue

        # si se limitó el rango, evita meter IPs fuera del subconjunto esperado
        try:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj not in network:
                continue
        except Exception:
            continue

        clave = (ip, mac)
        if clave in vistos:
            continue
        vistos.add(clave)

        dispositivos.append(_construir_dispositivo(ip, mac, existentes))

    # ordenar por IP
    def ip_sort_key(d):
        try:
            return tuple(int(x) for x in d['ip'].split('.'))
        except Exception:
            return (999, 999, 999, 999)

    dispositivos.sort(key=ip_sort_key)
    return dispositivos