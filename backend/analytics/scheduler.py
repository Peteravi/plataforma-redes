from datetime import datetime

from backend.database import calcular_siguiente_fecha


def siguiente_ejecucion(fecha_actual: datetime, repeticion: str):
    return calcular_siguiente_fecha(fecha_actual, repeticion)


if __name__ == '__main__':
    ahora = datetime.now()
    for rep in ['una_vez', 'diario', 'semanal', 'mensual']:
        print(rep, '->', siguiente_ejecucion(ahora, rep))