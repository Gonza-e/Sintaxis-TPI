"""
╔══════════════════════════════════════════════════════════════════╗
║   SMART-HOME Lexer  v4.0  —  Sintaxis y Semántica de Lenguajes  ║
║   UTN Facultad Regional Resistencia  |  Ciclo 2026              ║
╚══════════════════════════════════════════════════════════════════╝

Cambios respecto a v3:
  • Tokens individuales por sensor y actuador:
      SENSOR_TEMP, SENSOR_HUMEDAD, SENSOR_LUZ,
      SENSOR_MOVIMIENTO, SENSOR_HUMO
      ACT_FOCO, ACT_AIRE, ACT_PERSIANA, ACT_CERRADURA,
      ACT_RELOJ, ACT_ALTAVOZ, ACT_ALARMA
  • Detección de literales inválidos con error específico:
      "500luxx"  → Error: iluminancia con sufijo inválido
      "80porcentaje" → Error: porcentaje con sufijo inválido
      "abc@..com" → Error: email con formato inválido
      "32/13/2026" → Error: fecha con mes inválido
      "25:99"    → Error: hora con minutos inválidos
      etc.
"""

import sys
import os
from dataclasses import dataclass
from typing import Optional


# ======================================================================
#  1. TIPOS DE TOKEN
# ======================================================================

class TT:
    # Palabras reservadas (case-insensitive, se normalizan a UPPER)
    WHEN     = "WHEN"
    IF       = "IF"
    THEN     = "THEN"
    ELSE     = "ELSE"
    DO       = "DO"
    END      = "END"
    EVERY    = "EVERY"
    AND      = "AND"
    OR       = "OR"
    NOT      = "NOT"
    TRUE     = "TRUE"
    FALSE    = "FALSE"
    ON       = "ON"
    OFF      = "OFF"
    FRIO     = "FRIO"
    CALOR    = "CALOR"
    VENT     = "VENT"
    BLANCO   = "BLANCO"
    ROJO     = "ROJO"
    AZUL     = "AZUL"

    # ── Sensores individuales ─────────────────────────────────────
    SENSOR_TEMP       = "SENSOR_TEMP"        # sensor_temp*
    SENSOR_HUMEDAD    = "SENSOR_HUMEDAD"     # sensor_humedad
    SENSOR_LUZ        = "SENSOR_LUZ"         # sensor_luz
    SENSOR_MOVIMIENTO = "SENSOR_MOVIMIENTO"  # sensor_movimiento
    SENSOR_HUMO       = "SENSOR_HUMO"        # sensor_humo

    # ── Actuadores individuales ───────────────────────────────────
    ACT_FOCO      = "ACT_FOCO"       # foco_*
    ACT_AIRE      = "ACT_AIRE"       # aire_*
    ACT_PERSIANA  = "ACT_PERSIANA"   # persiana_*
    ACT_CERRADURA = "ACT_CERRADURA"  # cerradura_*
    ACT_RELOJ     = "ACT_RELOJ"      # reloj_*
    ACT_ALTAVOZ   = "ACT_ALTAVOZ"    # altavoz_*
    ACT_ALARMA    = "ACT_ALARMA"     # alarma_*

    # ── Atributos tipados ─────────────────────────────────────────
    ATTR_ESTADO      = "ATTR_ESTADO"
    ATTR_BRILLO      = "ATTR_BRILLO"
    ATTR_COLOR       = "ATTR_COLOR"
    ATTR_MODO        = "ATTR_MODO"
    ATTR_TEMP_OBJ    = "ATTR_TEMP_OBJ"
    ATTR_TEMP_ACT    = "ATTR_TEMP_ACT"
    ATTR_POSICION    = "ATTR_POSICION"
    ATTR_HORA        = "ATTR_HORA"
    ATTR_FECHA       = "ATTR_FECHA"
    ATTR_VOLUMEN     = "ATTR_VOLUMEN"
    ATTR_MUTE        = "ATTR_MUTE"
    ATTR_MENSAJE     = "ATTR_MENSAJE"
    ATTR_EMAIL_NOTIF = "ATTR_EMAIL_NOTIF"
    ATTR_ACTIVADA    = "ATTR_ACTIVADA"
    ATTR_GENERICO    = "ATTR_GENERICO"

    # ── Literales con unidad ──────────────────────────────────────
    TEMPERATURA  = "TEMPERATURA"   # 25°C
    PORCENTAJE   = "PORCENTAJE"    # 80%
    ILUMINANCIA  = "ILUMINANCIA"   # 600lux
    TIEMPO       = "TIEMPO"        # 30m, 10s, 1h

    # ── Literales simples ─────────────────────────────────────────
    HORA          = "HORA"          # 22:00
    FECHA         = "FECHA"         # 21/04/2026
    EMAIL         = "EMAIL"
    CADENA        = "CADENA"
    ENTERO        = "ENTERO"
    FLOTANTE      = "FLOTANTE"
    IDENTIFICADOR = "IDENTIFICADOR"

    # ── Operadores ────────────────────────────────────────────────
    OP_EQ    = "OP_EQ"
    OP_NEQ   = "OP_NEQ"
    OP_GTE   = "OP_GTE"
    OP_LTE   = "OP_LTE"
    OP_GT    = "OP_GT"
    OP_LT    = "OP_LT"
    OP_ASIG  = "OP_ASIG"
    PUNTO    = "PUNTO"

    # ── Especiales ────────────────────────────────────────────────
    COMENTARIO  = "COMENTARIO"
    DESCONOCIDO = "DESCONOCIDO"
    ERROR_LEX   = "ERROR_LEX"    # literal inválido detectado explícitamente
    EOF         = "EOF"

    # ── Grupos útiles para el parser ──────────────────────────────
    # Todos los tipos de sensor
    SENSORES = {
        SENSOR_TEMP, SENSOR_HUMEDAD, SENSOR_LUZ,
        SENSOR_MOVIMIENTO, SENSOR_HUMO,
    }
    # Todos los tipos de actuador
    ACTUADORES = {
        ACT_FOCO, ACT_AIRE, ACT_PERSIANA, ACT_CERRADURA,
        ACT_RELOJ, ACT_ALTAVOZ, ACT_ALARMA,
    }


# ======================================================================
#  2. RANGOS NOMBRADOS
# ======================================================================

RANGO_TEMP_1  = (-10.0,  50.0,  "RANGO_TEMP_1: -10.0 a 50.0 grados C")
RANGO_TEMP_2  = ( 16.0,  30.0,  "RANGO_TEMP_2: 16.0 a 30.0 grados C")
RANGO_PERCENT = (  0.0, 100.0,  "RANGO_PERCENT: 0 a 100 %")
RANGO_LUX     = (  0.0,1000.0,  "RANGO_LUX: 0 a 1000 lux")

# ── Rangos ABSOLUTOS por tipo de unidad ─────────────────────────────
# Son los límites más amplios que CUALQUIER sensor/atributo del lenguaje
# puede aceptar. Se usan para validar literales TEMPERATURA/PORCENTAJE/
# ILUMINANCIA incluso cuando aparecen SUELTOS, sin contexto de
# dispositivo (ej. tokenizando una línea aislada, o un literal que no
# sigue a ningún sensor/atributo reconocido). Si un valor está fuera de
# este rango absoluto, es imposible que sea válido para NINGÚN
# sensor/atributo existente, así que se reporta como ERROR LÉXICO
# (no como advertencia, que es para casos "podría ser inválido según
# el contexto específico").
RANGO_ABSOLUTO_TEMP    = (-10.0,  50.0, "RANGO_ABSOLUTO_TEMP: -10.0 a 50.0 grados C")
RANGO_ABSOLUTO_PERCENT = (  0.0, 100.0, "RANGO_ABSOLUTO_PERCENT: 0 a 100 %")
RANGO_ABSOLUTO_LUX     = (  0.0,1000.0, "RANGO_ABSOLUTO_LUX: 0 a 1000 lux")

RANGOS_ABSOLUTOS_POR_TIPO: dict = {
    TT.TEMPERATURA:  RANGO_ABSOLUTO_TEMP,
    TT.PORCENTAJE:   RANGO_ABSOLUTO_PERCENT,
    TT.ILUMINANCIA:  RANGO_ABSOLUTO_LUX,
}


# ======================================================================
#  3. DATACLASS TOKEN
# ======================================================================

@dataclass
class Token:
    tipo:  str
    valor: str
    linea: int
    col:   int

    def __str__(self) -> str:
        return (f"[Linea {self.linea:3d}, Col {self.col:3d}]  "
                f"{self.tipo:<22} -> '{self.valor}'")


# ======================================================================
#  4. TABLAS DE CLASIFICACIÓN
# ======================================================================

PALABRAS_RESERVADAS: dict = {
    "WHEN": TT.WHEN, "IF": TT.IF, "THEN": TT.THEN, "ELSE": TT.ELSE,
    "DO": TT.DO, "END": TT.END, "EVERY": TT.EVERY,
    "AND": TT.AND, "OR": TT.OR, "NOT": TT.NOT,
    "TRUE": TT.TRUE, "FALSE": TT.FALSE,
    "ON": TT.ON, "OFF": TT.OFF,
    "FRIO": TT.FRIO, "CALOR": TT.CALOR, "VENT": TT.VENT,
    "BLANCO": TT.BLANCO, "ROJO": TT.ROJO, "AZUL": TT.AZUL,
}

# Sensor: (prefijo, tipo_TT)  — más largo primero para evitar
# que "sensor_temp" capture "sensor_temp_exterior" antes de terminar
PREFIJOS_SENSOR: tuple = (
    ("sensor_movimiento", TT.SENSOR_MOVIMIENTO),
    ("sensor_humedad",    TT.SENSOR_HUMEDAD),
    ("sensor_humo",       TT.SENSOR_HUMO),
    ("sensor_temp",       TT.SENSOR_TEMP),
    ("sensor_luz",        TT.SENSOR_LUZ),
)

# Actuador: (prefijo, tipo_TT)
PREFIJOS_ACTUADOR: tuple = (
    ("cerradura_", TT.ACT_CERRADURA),
    ("persiana_",  TT.ACT_PERSIANA),
    ("altavoz_",   TT.ACT_ALTAVOZ),
    ("alarma_",    TT.ACT_ALARMA),
    ("reloj_",     TT.ACT_RELOJ),
    ("foco_",      TT.ACT_FOCO),
    ("aire_",      TT.ACT_AIRE),
)

ATRIBUTOS_CONOCIDOS: dict = {
    "estado":      TT.ATTR_ESTADO,
    "brillo":      TT.ATTR_BRILLO,
    "color":       TT.ATTR_COLOR,
    "modo":        TT.ATTR_MODO,
    "temp_obj":    TT.ATTR_TEMP_OBJ,
    "temp_act":    TT.ATTR_TEMP_ACT,
    "posicion":    TT.ATTR_POSICION,
    "hora":        TT.ATTR_HORA,
    "fecha":       TT.ATTR_FECHA,
    "volumen":     TT.ATTR_VOLUMEN,
    "mute":        TT.ATTR_MUTE,
    "mensaje":     TT.ATTR_MENSAJE,
    "email_notif": TT.ATTR_EMAIL_NOTIF,
    "activada":    TT.ATTR_ACTIVADA,
}

TABLA_RANGOS: dict = {
    (TT.SENSOR_TEMP,    None): (TT.TEMPERATURA, RANGO_TEMP_1,  "sensor_temp"),
    (TT.SENSOR_HUMEDAD, None): (TT.PORCENTAJE,  RANGO_PERCENT, "sensor_humedad"),
    (TT.SENSOR_LUZ,     None): (TT.ILUMINANCIA, RANGO_LUX,     "sensor_luz"),
    (TT.ACT_FOCO,  TT.ATTR_BRILLO):   (TT.PORCENTAJE,  RANGO_PERCENT, "foco_.brillo"),
    (TT.ACT_AIRE,  TT.ATTR_TEMP_OBJ): (TT.TEMPERATURA, RANGO_TEMP_2,  "aire_.temp_obj"),
    (TT.ACT_AIRE,  TT.ATTR_TEMP_ACT): (TT.TEMPERATURA, RANGO_TEMP_1,  "aire_.temp_act"),
    (TT.ACT_PERSIANA, TT.ATTR_POSICION): (TT.PORCENTAJE, RANGO_PERCENT, "persiana_.posicion"),
    (TT.ACT_ALTAVOZ,  TT.ATTR_VOLUMEN): (TT.PORCENTAJE, RANGO_PERCENT, "altavoz_.volumen"),
}


# ======================================================================
#  5. HELPERS DE CARACTERES
# ======================================================================

def _es_letra(c):    return ('a' <= c <= 'z') or ('A' <= c <= 'Z')
def _es_digito(c):   return '0' <= c <= '9'
def _es_alfanum_o_guion(c): return _es_letra(c) or _es_digito(c) or c == '_'
def _es_email_char(c): return _es_letra(c) or _es_digito(c) or c in ('_','.', '+','-')
def _es_blanco(c):   return c in (' ', '\t', '\r', '\n')

def _distancia_edicion(a: str, b: str) -> int:
    n, m = len(a), len(b)
    if n == 0: return m
    if m == 0: return n
    fila_prev = list(range(m + 1))
    for i in range(1, n + 1):
        fila_act = [i] + [0] * m
        for j in range(1, m + 1):
            costo = 0 if a[i-1] == b[j-1] else 1
            fila_act[j] = min(
                fila_prev[j] + 1,      # eliminar
                fila_act[j-1] + 1,     # insertar
                fila_prev[j-1] + costo # sustituir
            )
        fila_prev = fila_act
    return fila_prev[m]


def _palabra_reservada_similar(palabra_upper: str) -> Optional[str]:
    """
    Si `palabra_upper` está muy cerca de alguna palabra reservada del
    lenguaje (pero no es exactamente igual a ninguna), devuelve esa
    palabra reservada como sugerencia. Si no se parece a ninguna,
    devuelve None.

    Umbral de similitud: distancia de edición de 1 carácter, y solo si
    la palabra candidata tiene una longitud razonablemente cercana
    (para no confundir "ON" con "ROJO" solo porque comparten letras).
    """
    mejor_match  = None
    mejor_dist   = None
    for reservada in PALABRAS_RESERVADAS:
        # Evitar comparar contra palabras de longitud muy distinta:
        # acelera y evita falsos positivos como "A" vs "AZUL"
        if abs(len(reservada) - len(palabra_upper)) > 2:
            continue
        dist = _distancia_edicion(palabra_upper, reservada)
        if dist == 0:
            return None   # es exactamente igual; no es un "parecido", ya se clasificó antes
        if dist <= 1 and (mejor_dist is None or dist < mejor_dist):
            mejor_match = reservada
            mejor_dist  = dist
    return mejor_match

_COMILLAS_APERTURA = ('"', '\u201c')
_COMILLAS_CIERRE   = ('"', '\u201d')


# ======================================================================
#  6. FUNCIONES DE RECONOCIMIENTO
#     Retornan (valor_str, nuevo_pos) o None.
# ======================================================================

def _leer_comentario(linea, pos):
    if pos + 1 < len(linea) and linea[pos] == '/' and linea[pos+1] == '/':
        return (linea[pos:], len(linea))
    return None

def _leer_cadena(linea, pos):
    if linea[pos] not in _COMILLAS_APERTURA:
        return None
    i = pos + 1
    while i < len(linea) and linea[i] not in _COMILLAS_CIERRE and linea[i] != '\n':
        i += 1
    if i < len(linea) and linea[i] in _COMILLAS_CIERRE:
        return (linea[pos:i+1], i+1)
    return None

def _leer_numero(linea, pos):
    """Lee número entero o decimal con signo negativo opcional."""
    i = pos
    if i < len(linea) and linea[i] == '-':
        i += 1
    if i >= len(linea) or not _es_digito(linea[i]):
        return None
    while i < len(linea) and _es_digito(linea[i]):
        i += 1
    if i < len(linea) and linea[i] == '.' and i+1 < len(linea) and _es_digito(linea[i+1]):
        i += 1
        while i < len(linea) and _es_digito(linea[i]):
            i += 1
    return (linea[pos:i], i)

def _extraer_numero(s):
    i = 0
    if i < len(s) and s[i] == '-': i += 1
    while i < len(s) and _es_digito(s[i]): i += 1
    if i < len(s) and s[i] == '.' and i+1 < len(s) and _es_digito(s[i+1]):
        i += 1
        while i < len(s) and _es_digito(s[i]): i += 1
    return float(s[:i])

def _leer_temperatura(linea, pos):
    res = _leer_numero(linea, pos)
    if res is None: return None
    num_str, i = res
    if i < len(linea) and linea[i] == '°':
        i += 1
        if i < len(linea) and linea[i] in ('C', 'c'):
            return (linea[pos:i+1], i+1)
    return None

def _leer_con_sufijo(linea, pos, sufijo):
    """Lee número positivo + sufijo exacto. Retorna None si hay más letras."""
    if pos < len(linea) and linea[pos] == '-': return None
    res = _leer_numero(linea, pos)
    if res is None: return None
    num_str, i = res
    if num_str.startswith('-'): return None
    if linea[i:i+len(sufijo)].lower() == sufijo.lower():
        j = i + len(sufijo)
        if j < len(linea) and _es_letra(linea[j]):
            return None   # hay más letras tras el sufijo
        return (linea[pos:j], j)
    return None

def _leer_tiempo(linea, pos):
    for u in ('s', 'm', 'h'):
        res = _leer_con_sufijo(linea, pos, u)
        if res: return res
    return None

def _leer_hora(linea, pos):
    if pos + 4 >= len(linea) + 1: return None
    s = linea[pos:pos+5]
    if len(s) < 5: return None
    if (s[2] != ':' or not all(_es_digito(s[k]) for k in (0,1,3,4))): return None
    hh, mm = int(s[0:2]), int(s[3:5])
    if hh > 23 or mm > 59: return None
    j = pos + 5
    if j < len(linea) and _es_digito(linea[j]): return None
    return (s, pos+5)

def _leer_fecha(linea, pos):
    i = pos
    if i >= len(linea) or not _es_digito(linea[i]): return None
    j = i
    while j < len(linea) and _es_digito(linea[j]): j += 1
    if j - i > 2 or j >= len(linea) or linea[j] != '/': return None
    dia = int(linea[i:j])
    if dia < 1 or dia > 31: return None
    i = j + 1
    if i >= len(linea) or not _es_digito(linea[i]): return None
    j = i
    while j < len(linea) and _es_digito(linea[j]): j += 1
    if j - i > 2 or j >= len(linea) or linea[j] != '/': return None
    mes = int(linea[i:j])
    if mes < 1 or mes > 12: return None
    i = j + 1
    if i + 3 >= len(linea): return None
    año_str = linea[i:i+4]
    if not all(_es_digito(c) for c in año_str): return None
    año = int(año_str)
    if año < 1900 or año > 2099: return None
    j = i + 4
    if j < len(linea) and _es_digito(linea[j]): return None
    return (linea[pos:j], j)

def _leer_email(linea, pos):
    i = pos
    if i >= len(linea) or not _es_email_char(linea[i]): return None
    while i < len(linea) and _es_email_char(linea[i]): i += 1
    if i >= len(linea) or linea[i] != '@': return None
    i += 1
    if i >= len(linea) or linea[i] == '.': return None
    segmentos, seg_start = [], i
    while i < len(linea) and _es_email_char(linea[i]):
        if linea[i] == '.':
            seg = linea[seg_start:i]
            if not seg: return None
            segmentos.append(seg)
            i += 1
            if i < len(linea) and linea[i] == '.': return None
            seg_start = i
        else:
            i += 1
    ultimo = linea[seg_start:i]
    if not ultimo: return None
    segmentos.append(ultimo)
    if len(segmentos) < 2: return None
    ext = segmentos[-1]
    if len(ext) < 2 or len(ext) > 4 or not all(_es_letra(c) for c in ext): return None
    return (linea[pos:i], i)

def _tiene_sufijo_sospechoso(linea: str, pos: int) -> bool:
    """
    Verifica si justo después de un número (ya leído) viene algo que
    sugiere un literal compuesto MAL FORMADO: una unidad incorrecta
    (letras pegadas, ° sin C), o el inicio de un patrón de FECHA u HORA
    que resultó inválido (':' o '/' después del número).
    Se usa para preferir un error específico de _detectar_invalido()
    en vez de aceptar el número suelto como ENTERO/FLOTANTE.
    """
    if pos >= len(linea):
        return False
    c = linea[pos]
    # Letras pegadas inmediatamente después del número: 500luxx, 80porciento
    if _es_letra(c):
        return True
    # Símbolo de grado sin "C" correcta detrás
    if c == '°':
        return True
    # '%' seguido de más texto: 80%basura
    if c == '%':
        j = pos + 1
        return j < len(linea) and _es_alfanum_o_guion(linea[j])
    # ':' sugiere intento de HORA que ya falló la validación de _leer_hora
    if c == ':':
        return True
    # '/' sugiere intento de FECHA que ya falló la validación de _leer_fecha
    if c == '/':
        return True
    return False


def _leer_identificador(linea, pos):
    if pos >= len(linea): return None
    c = linea[pos]
    if not (_es_letra(c) or c == '_'): return None
    i = pos + 1
    while i < len(linea) and _es_alfanum_o_guion(linea[i]): i += 1
    return (linea[pos:i], i)


# ======================================================================
#  7. HELPERS NUMÉRICOS PARA RANGOS
# ======================================================================

def _num_temperatura(v): return _extraer_numero(v)
def _num_porcentaje(v):  return _extraer_numero(v)
def _num_iluminancia(v): return _extraer_numero(v)

_EXTRACTOR = {
    TT.TEMPERATURA: _num_temperatura,
    TT.PORCENTAJE:  _num_porcentaje,
    TT.ILUMINANCIA: _num_iluminancia,
}


# ======================================================================
#  8. DETECCIÓN DE INVÁLIDOS ESPECÍFICOS
#     Intentan reconocer el patrón erróneo y retornan un mensaje descriptivo, o None si no aplica.
# ======================================================================

def _detectar_invalido(linea: str, pos: int) -> Optional[tuple]:

    c = linea[pos]

    # ── Número seguido de sufijo incorrecto ──────────────────────
    if _es_digito(c) or c == '-':
        res = _leer_numero(linea, pos)
        if res:
            num_str, i = res
            if num_str.startswith('-') and c == '-':
                pass  # número negativo, puede ser temperatura válida
            if i < len(linea):
                resto = linea[i]

                # Grado sin C: 25°F, 25°, 25°X
                if resto == '°':
                    j = i + 1
                    sufijo_real = linea[j] if j < len(linea) else ''
                    fin = j + 1 if sufijo_real else j
                    msg = (f"Temperatura invalida: '{linea[pos:fin]}' "
                           f"— se esperaba grados Celsius (°C), no '°{sufijo_real}'")
                    return (msg, fin)

                # Porcentaje con letras extra: 80porciento, 100por
                if _es_letra(resto):
                    j = i
                    while j < len(linea) and _es_alfanum_o_guion(linea[j]):
                        j += 1
                    sufijo_real = linea[i:j]
                    if sufijo_real.lower() in ('lux', 'luxx', 'luxes'):
                        msg = (f"Iluminancia invalida: '{linea[pos:j]}' "
                               f"— sufijo incorrecto '{sufijo_real}' (se esperaba 'lux')")
                    elif sufijo_real.lower() in ('m', 'min', 'minutos', 's', 'sec', 'h', 'hs', 'hr'):
                        msg = (f"Tiempo invalido: '{linea[pos:j]}' "
                               f"— sufijo incorrecto '{sufijo_real}' (se esperaba s/m/h)")
                    else:
                        msg = (f"Literal numerico invalido: '{linea[pos:j]}' "
                               f"— sufijo '{sufijo_real}' no reconocido")
                    return (msg, j)

                # % seguido de algo: 80%abc
                if resto == '%':
                    j = i + 1
                    if j < len(linea) and _es_alfanum_o_guion(linea[j]):
                        while j < len(linea) and _es_alfanum_o_guion(linea[j]):
                            j += 1
                        msg = (f"Porcentaje invalido: '{linea[pos:j]}' "
                               f"— no debe haber caracteres tras '%'")
                        return (msg, j)

                # Posible fecha con día o mes inválido
                if resto == '/':
                    # Intentar leer como fecha para dar error específico
                    dd_str = num_str.lstrip('-')
                    if dd_str.isdigit():
                        dia = int(dd_str)
                        if dia < 1 or dia > 31:
                            # leer hasta el final del patrón fecha
                            j = i
                            while j < len(linea) and (linea[j].isdigit() or linea[j] == '/'):
                                j += 1
                            msg = (f"Fecha invalida: '{linea[pos:j]}' "
                                   f"— dia {dia} fuera de rango (1-31)")
                            return (msg, j)
                        # intentar leer mes
                        k = i + 1
                        mes_start = k
                        while k < len(linea) and _es_digito(linea[k]):
                            k += 1
                        if k < len(linea) and linea[k] == '/':
                            mes_str = linea[mes_start:k]
                            if mes_str.isdigit():
                                mes = int(mes_str)
                                if mes < 1 or mes > 12:
                                    j = k
                                    while j < len(linea) and (linea[j].isdigit() or linea[j] == '/'):
                                        j += 1
                                    msg = (f"Fecha invalida: '{linea[pos:j]}' "
                                           f"— mes {mes} fuera de rango (1-12)")
                                    return (msg, j)
                                # año inválido
                                año_start = k + 1
                                año_str = linea[año_start:año_start+4]
                                if len(año_str) == 4 and año_str.isdigit():
                                    año = int(año_str)
                                    if año < 1900 or año > 2099:
                                        j = año_start + 4
                                        msg = (f"Fecha invalida: '{linea[pos:j]}' "
                                               f"— año {año} fuera de rango (1900-2099)")
                                        return (msg, j)

                # Posible hora con valores inválidos HH:MM
                if len(num_str) == 2 and resto == ':':
                    hh = int(num_str) if num_str.isdigit() else -1
                    j = i + 1
                    mm_str = linea[j:j+2]
                    if len(mm_str) == 2 and mm_str.isdigit():
                        mm = int(mm_str)
                        if hh > 23:
                            msg = (f"Hora invalida: '{num_str}:{mm_str}' "
                                   f"— hora {hh} fuera de rango (00-23)")
                            return (msg, j+2)
                        if mm > 59:
                            msg = (f"Hora invalida: '{num_str}:{mm_str}' "
                                   f"— minutos {mm} fuera de rango (00-59)")
                            return (msg, j+2)

    # ── Email mal formado: hay @ pero falla la validación ────────
    if _es_email_char(c) and '@' in linea[pos:]:
        # leer hasta el final del token "email-like"
        j = pos
        while j < len(linea) and (_es_email_char(linea[j]) or linea[j] == '@'):
            j += 1
        candidato = linea[pos:j]
        if '@' in candidato and len(candidato) > 3:
            # Solo reportar si tiene suficiente forma de email
            msg = (f"Email invalido: '{candidato}' "
                   f"— verifique que el formato sea usuario@dominio.ext "
                   f"sin puntos consecutivos y con extension de 2-4 letras")
            return (msg, j)

    return None


#  9. CLASE PRINCIPAL  SmartHomeLexer

class SmartHomeLexer:

    def __init__(self):
        self.errores:      list = []
        self.advertencias: list = []
        self._ctx_tipo:      Optional[str] = None   # tipo TT del dispositivo actual
        self._ctx_attr_tipo: Optional[str] = None   # en caso de detectarse un punto se guarda el atributo aca
        self._ultimo_tipo:   Optional[str] = None   # se guarda el ultimo tipo 

    # Toma el archivo .smart y lo va dividiendo en lineas. Por ejemplo:
    # IF | sensor_humo | == | TRUE | THEN
    def tokenizar(self, fuente: str, num_linea_base: int = 1) -> list:
        self.errores = []
        self.advertencias = []
        self._reset_ctx()
        tokens = []
        for i, linea in enumerate(fuente.splitlines(keepends=True)):
            self._procesar_linea(linea, num_linea_base + i, tokens)
        tokens.append(Token(TT.EOF, "", num_linea_base + len(fuente.splitlines()), 0))
        return tokens

    # Hace lo mismo pero para el modo interactivo (el modo al que se accede si se cierra la ventana de tkinter)
    def tokenizar_linea(self, linea: str, num_linea: int = 1) -> list:
        self.errores = []
        self.advertencias = []
        tokens = []
        self._procesar_linea(linea, num_linea, tokens)
        tokens.append(Token(TT.EOF, "", num_linea, len(linea)))
        return tokens

    def reset_contexto_interactivo(self):
        self._reset_ctx()

    def _reset_ctx(self):
        self._ctx_tipo      = None
        self._ctx_attr_tipo = None
        self._ultimo_tipo   = None

    def _procesar_linea(self, linea: str, num_linea: int, tokens: list) -> None:
        pos = 0
        n   = len(linea)
        while pos < n:
            if _es_blanco(linea[pos]):
                pos += 1
                continue

            col = pos + 1
            tok = self._siguiente_token(linea, pos, num_linea, col)

            if tok is None:
                # Intentar dar un error específico antes del genérico
                inv = _detectar_invalido(linea, pos)
                if inv:
                    msg, nuevo_pos = inv
                    err = (f"Error lexico   | Linea {num_linea:3d}, Col {col:3d} | {msg}")
                    self.errores.append(err)
                    tokens.append(Token(TT.ERROR_LEX, linea[pos:nuevo_pos], num_linea, col))
                    pos = nuevo_pos
                else:
                    self.errores.append(
                        f"Error lexico   | Linea {num_linea:3d}, Col {col:3d} "
                        f"| Caracter no reconocido: '{linea[pos]}'"
                    )
                    tokens.append(Token(TT.DESCONOCIDO, linea[pos], num_linea, col))
                    pos += 1
                continue

            tipo, valor, nuevo_pos = tok
            if tipo == TT.COMENTARIO:
                break

            # Caso especial: _clasificar() detectó una palabra reservada
            # mal escrita. Ejemplo: "OFFF" cerca de "OFF"), el "valor" ya trae
            # el mensaje de error armado, en vez de ser el texto del token.
            if tipo == TT.ERROR_LEX:
                self.errores.append(
                    f"Error lexico   | Linea {num_linea:3d}, Col {col:3d} | {valor}"
                )
                tokens.append(Token(TT.ERROR_LEX, linea[pos:nuevo_pos], num_linea, col))
                pos = nuevo_pos
                continue

            t = Token(tipo, valor, num_linea, col)
            tokens.append(t)
            self._actualizar_ctx(t)
            self._validar_rango(t)
            pos = nuevo_pos

    def _siguiente_token(self, linea: str, pos: int, num_linea: int, col: int):
        c = linea[pos]

        # 1. Comentario
        res = _leer_comentario(linea, pos)
        if res: return (TT.COMENTARIO, res[0], res[1])

        # 2. Cadena
        res = _leer_cadena(linea, pos)
        if res: return (TT.CADENA, res[0], res[1])

        # 3. Email
        if _es_email_char(c) and '@' in linea[pos:]:
            res = _leer_email(linea, pos)
            if res: return (TT.EMAIL, res[0], res[1])

        # 4. Temperatura
        if c == '-' or _es_digito(c):
            res = _leer_temperatura(linea, pos)
            if res: return (TT.TEMPERATURA, res[0], res[1])

        # 5. Iluminancia (nlux)
        if _es_digito(c):
            res = _leer_con_sufijo(linea, pos, 'lux')
            if res: return (TT.ILUMINANCIA, res[0], res[1])

        # 6. Porcentaje (n%)
        if _es_digito(c):
            res = _leer_con_sufijo(linea, pos, '%')
            if res: return (TT.PORCENTAJE, res[0], res[1])

        # 7. Tiempo (ns, nm, nh)
        if _es_digito(c):
            res = _leer_tiempo(linea, pos)
            if res: return (TT.TIEMPO, res[0], res[1])

        # 8. Fecha
        if _es_digito(c):
            res = _leer_fecha(linea, pos)
            if res: return (TT.FECHA, res[0], res[1])

        # 9. Hora
        if _es_digito(c):
            res = _leer_hora(linea, pos)
            if res: return (TT.HORA, res[0], res[1])

        # 10. Operadores dobles
        dos = linea[pos:pos+2]
        if dos == '==': return (TT.OP_EQ,  '==', pos+2)
        if dos == '!=': return (TT.OP_NEQ, '!=', pos+2)
        if dos == '>=': return (TT.OP_GTE, '>=', pos+2)
        if dos == '<=': return (TT.OP_LTE, '<=', pos+2)

        # 11. Operadores simples
        if c == '>': return (TT.OP_GT,   '>', pos+1)
        if c == '<': return (TT.OP_LT,   '<', pos+1)
        if c == '=': return (TT.OP_ASIG, '=', pos+1)

        # 12. Punto
        if c == '.': return (TT.PUNTO, '.', pos+1)

        # 13-14. Número (flotante o entero)
        # Antes de aceptar el número suelto, verificamos si
        # justo después viene un sufijo de unidad MAL ESCRITO (ej. "500luxx",
        # "25°F"). Si lo detectamos, no devolvemos el número: 
        # dejamos que el llamador reciba None y _detectar_invalido() genere
        # el error específico, en vez de partirlo en ENTERO + IDENTIFICADOR.
        if c == '-' or _es_digito(c):
            res = _leer_numero(linea, pos)
            if res:
                num_str, nuevo_pos = res
                if _tiene_sufijo_sospechoso(linea, nuevo_pos):
                    return None   # dejar que _detectar_invalido() lo explique
                return (TT.FLOTANTE if '.' in num_str else TT.ENTERO, num_str, nuevo_pos)

        # 15. Identificador / palabra reservada / sensor / actuador / atributo
        if _es_letra(c) or c == '_':
            res = _leer_identificador(linea, pos)
            if res:
                palabra, nuevo_pos = res

                # Si justo después del identificador hay un '@', esto en
                # realidad era un INTENTO de email que _leer_email() ya
                # rechazó por formato inválido (puntos consecutivos, etc).
                # No lo tratamos como identificador suelto: dejamos que
                # _detectar_invalido() construya el mensaje específico.
                if nuevo_pos < len(linea) and linea[nuevo_pos] == '@':
                    return None

                tipo, valor = self._clasificar(palabra)
                return (tipo, valor, nuevo_pos)

        return None

    # ── Clasificación ─────────────────────────────────────────────

    def _clasificar(self, palabra: str) -> tuple:
        """
        Clasifica un identificador crudo. Retorna SIEMPRE (tipo, valor).

        Caso especial: si la palabra no es ninguna palabra reservada,
        ni sensor, ni actuador, ni atributo conocido, pero está a 1
        carácter de distancia de alguna palabra reservada del lenguaje
        (ej. "OFFF" vs "OFF", "WHEM" vs "WHEN"), se devuelve el tipo
        especial TT.ERROR_LEX con un mensaje ya armado como valor.
        Esto se hace porque este lenguaje NUNCA usa identificadores
        sueltos en su gramática, así que una "casi palabra reservada"
        es casi siempre un error de tipeo, no algo intencional.
        """
        # 1. Palabras reservadas (case-insensitive)
        upper = palabra.upper()
        if upper in PALABRAS_RESERVADAS:
            return PALABRAS_RESERVADAS[upper], upper

        lower = palabra.lower()

        # 2. Sensores → tipo específico
        for pfx, tipo_tt in PREFIJOS_SENSOR:
            if lower == pfx or lower.startswith(pfx + "_"):
                return tipo_tt, lower

        # 3. Actuadores → tipo específico
        for pfx, tipo_tt in PREFIJOS_ACTUADOR:
            if lower.startswith(pfx):
                return tipo_tt, lower

        # 4. Atributo (solo si token anterior fue PUNTO)
        if self._ultimo_tipo == TT.PUNTO:
            attr_tipo = ATRIBUTOS_CONOCIDOS.get(lower, TT.ATTR_GENERICO)
            return attr_tipo, lower

        # 5. Palabra reservada MAL ESCRITA (ej. "OFFF", "WHEM", "Tehn")
        sugerencia = _palabra_reservada_similar(upper)
        if sugerencia is not None:
            msg = (f"Palabra invalida: '{palabra}' — ¿quiso decir "
                   f"'{sugerencia}'? (palabra reservada del lenguaje)")
            return TT.ERROR_LEX, msg

        # 6. Identificador genérico
        return TT.IDENTIFICADOR, palabra

    # ── Contexto para validación de rangos ───────────────────────

    def _actualizar_ctx(self, tok: Token) -> None:
        tt = tok.tipo
        if tt in TT.SENSORES:
            self._ctx_tipo      = tt
            self._ctx_attr_tipo = None
        elif tt in TT.ACTUADORES:
            self._ctx_tipo      = tt
            self._ctx_attr_tipo = None
        elif tt in ATRIBUTOS_CONOCIDOS.values():
            self._ctx_attr_tipo = tt
        elif tt == TT.ATTR_GENERICO:
            self._ctx_attr_tipo = None
        elif tt in (TT.WHEN, TT.IF, TT.THEN, TT.ELSE,
                    TT.DO, TT.END, TT.EVERY):
            self._ctx_tipo      = None
            self._ctx_attr_tipo = None
        self._ultimo_tipo = tt

    def _validar_rango(self, tok: Token) -> None:

        if tok.tipo not in _EXTRACTOR:
            return

        try:
            num = _EXTRACTOR[tok.tipo](tok.valor)
        except (ValueError, AttributeError):
            return

        # ── 1. Validación de rango ABSOLUTO (siempre se ejecuta) 
        rango_abs = RANGOS_ABSOLUTOS_POR_TIPO.get(tok.tipo)
        if rango_abs:
            abs_min, abs_max, abs_desc = rango_abs
            if not (abs_min <= num <= abs_max):
                self.errores.append(
                    f"Error lexico   | Linea {tok.linea:3d}, Col {tok.col:3d} "
                    f"| '{tok.valor}' fuera de rango absoluto -> {abs_desc}"
                )
                return   # ya es invalido en cualquier contexto, no seguir

        # ── 2. Validación de rango ESPECÍFICO (solo con contexto)
        if self._ctx_tipo is None:
            return
        es_sensor  = self._ctx_tipo in TT.SENSORES
        attr_clave = None if es_sensor else self._ctx_attr_tipo
        clave      = (self._ctx_tipo, attr_clave)
        if clave not in TABLA_RANGOS:
            return
        tipo_esp, rango, desc_ctx = TABLA_RANGOS[clave]
        rango_min, rango_max, desc_rango = rango
        if tok.tipo != tipo_esp:
            self.advertencias.append(
                f"Advertencia rango | Linea {tok.linea:3d}, Col {tok.col:3d} "
                f"| '{tok.valor}': tipo incorrecto para '{desc_ctx}' "
                f"-> se esperaba {tipo_esp}  ({desc_rango})"
            )
            return
        if not (rango_min <= num <= rango_max):
            self.advertencias.append(
                f"Advertencia rango | Linea {tok.linea:3d}, Col {tok.col:3d} "
                f"| '{tok.valor}' fuera de rango para '{desc_ctx}' "
                f"-> {desc_rango}"
            )


#  10. MODOS DE EJECUCIÓN

def modo_interactivo():
    lexer     = SmartHomeLexer()
    num_linea = 1
    print("=" * 67)
    print("  SMART-HOME Lexer  v4.0")
    print("  Comandos: 'reset' reinicia contexto | 'salir' termina")
    print("=" * 67)
    while True:
        try:
            linea = input(f"\n[{num_linea:3d}] >>> ")
        except (EOFError, KeyboardInterrupt):
            break
        cmd = linea.strip().lower()
        if cmd in ("salir", "exit", "quit"): break
        if cmd == "reset":
            lexer.reset_contexto_interactivo()
            print("  Contexto reseteado.")
            continue
        tokens = lexer.tokenizar_linea(linea, num_linea)
        for t in tokens:
            if t.tipo != TT.EOF: print(f"    {t}")
        for e in lexer.errores:   print(f"  [ERROR]  {e}")
        for a in lexer.advertencias: print(f"  [AVISO]  {a}")
        num_linea += 1

def modo_archivo(ruta: str) -> None:
    if not os.path.exists(ruta):
        print(f"Error: archivo '{ruta}' no existe.")
        sys.exit(1)
    _, ext = os.path.splitext(ruta)
    if ext.lower() != ".smart":
        print(f"Error: extension incorrecta '{ext}'. Se esperaba '.smart'.")
        sys.exit(1)
    with open(ruta, "r", encoding="utf-8") as f:
        fuente = f.read()
    lexer  = SmartHomeLexer()
    tokens = lexer.tokenizar(fuente)
    n      = sum(1 for t in tokens if t.tipo != TT.EOF)
    print("=" * 67)
    print(f"  SMART-HOME Lexer  v4.0  |  Archivo: {ruta}  |  Tokens: {n}")
    print("=" * 67)
    for t in tokens:
        if t.tipo != TT.EOF: print(t)
    print()
    if lexer.errores:
        print(f"  [ERRORES LEXICOS: {len(lexer.errores)}]")
        for e in lexer.errores: print(f"    {e}")
    if lexer.advertencias:
        print(f"  [ADVERTENCIAS DE RANGO: {len(lexer.advertencias)}]")
        for a in lexer.advertencias: print(f"    {a}")
    if not lexer.errores and not lexer.advertencias:
        print("  OK  Analisis lexico exitoso.")
    elif not lexer.errores:
        print("  OK  Analisis lexico exitoso (con advertencias).")
    if lexer.errores:
        sys.exit(2)

def seleccionar_archivo_gui() -> Optional[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None
    root = tk.Tk(); root.withdraw(); root.lift(); root.focus_force()
    ruta = filedialog.askopenfilename(
        title="Seleccionar archivo SMART-HOME",
        initialdir=os.getcwd(),
        filetypes=[("Archivos SMART-HOME", "*.smart"), ("Todos", "*.*")],
    )
    root.destroy()
    return ruta if ruta else None

def main():
    if len(sys.argv) == 1:
        ruta = seleccionar_archivo_gui()
        if ruta: modo_archivo(ruta)
        else: modo_interactivo()
    elif len(sys.argv) == 2:
        if sys.argv[1] == "--interactivo": modo_interactivo()
        else: modo_archivo(sys.argv[1])
    else:
        print("Uso: python lexer.py [archivo.smart | --interactivo]")
        sys.exit(1)

if __name__ == "__main__":
    main()