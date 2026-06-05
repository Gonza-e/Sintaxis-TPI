"""
╔══════════════════════════════════════════════════════════════════╗
║   SMART-HOME Lexer  v3.0  —  Sintaxis y Semántica de Lenguajes  ║
║   UTN Facultad Regional Resistencia  |  Ciclo 2026              ║
╚══════════════════════════════════════════════════════════════════╝

Implementación manual SIN el módulo `re`.
Todo el análisis léxico se realiza con índices, comparaciones de
caracteres y funciones auxiliares puras de Python.

Cambios respecto a v2:
  • Se eliminó completamente el módulo `re`.
  • Las palabras reservadas (WHEN, IF, THEN, ELSE, DO, END, EVERY,
    AND, OR, NOT, TRUE, FALSE, ON, OFF, FRIO, CALOR, VENT, BLANCO,
    ROJO, AZUL) SOLO se reconocen en MAYÚSCULAS.
  • Sensores y actuadores siguen siendo case-insensitive porque son
    nombres de dispositivos, no palabras del lenguaje.
  • Los tokens compuestos (TEMPERATURA, PORCENTAJE, ILUMINANCIA,
    TIEMPO, HORA, FECHA, EMAIL) se reconocen con funciones
    específicas que avanzan carácter a carácter.
"""

import sys
import os
from dataclasses import dataclass
from typing import Optional


# ======================================================================
#  1. TIPOS DE TOKEN
# ======================================================================

class TT:
    # Palabras reservadas (solo MAYÚSCULAS)
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
    # Dispositivos
    SENSOR   = "SENSOR"
    ACTUADOR = "ACTUADOR"
    # Atributos tipados
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
    # Literales con unidad
    TEMPERATURA  = "TEMPERATURA"
    PORCENTAJE   = "PORCENTAJE"
    ILUMINANCIA  = "ILUMINANCIA"
    TIEMPO       = "TIEMPO"
    # Literales simples
    HORA         = "HORA"
    FECHA        = "FECHA"
    EMAIL        = "EMAIL"
    CADENA       = "CADENA"
    ENTERO       = "ENTERO"
    FLOTANTE     = "FLOTANTE"
    IDENTIFICADOR = "IDENTIFICADOR"
    # Operadores
    OP_EQ    = "OP_EQ"
    OP_NEQ   = "OP_NEQ"
    OP_GTE   = "OP_GTE"
    OP_LTE   = "OP_LTE"
    OP_GT    = "OP_GT"
    OP_LT    = "OP_LT"
    OP_ASIG  = "OP_ASIG"
    PUNTO    = "PUNTO"
    # Especiales
    COMENTARIO  = "COMENTARIO"
    DESCONOCIDO = "DESCONOCIDO"
    EOF         = "EOF"


# ======================================================================
#  2. RANGOS NOMBRADOS
# ======================================================================

RANGO_TEMP_1  = (-10.0,  50.0,  "RANGO_TEMP_1: -10.0 a 50.0 grados C")
RANGO_TEMP_2  = ( 16.0,  30.0,  "RANGO_TEMP_2: 16.0 a 30.0 grados C")
RANGO_PERCENT = (  0.0, 100.0,  "RANGO_PERCENT: 0 a 100 %")
RANGO_LUX     = (  0.0,1000.0,  "RANGO_LUX: 0 a 1000 lux")


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
                f"{self.tipo:<20} -> '{self.valor}'")


# ======================================================================
#  4. TABLAS DE CLASIFICACIÓN
# ======================================================================

# Solo MAYÚSCULAS: palabras reservadas case-SENSITIVE
PALABRAS_RESERVADAS: dict = {
    "WHEN":   TT.WHEN,
    "IF":     TT.IF,
    "THEN":   TT.THEN,
    "ELSE":   TT.ELSE,
    "DO":     TT.DO,
    "END":    TT.END,
    "EVERY":  TT.EVERY,
    "AND":    TT.AND,
    "OR":     TT.OR,
    "NOT":    TT.NOT,
    "TRUE":   TT.TRUE,
    "FALSE":  TT.FALSE,
    "ON":     TT.ON,
    "OFF":    TT.OFF,
    "FRIO":   TT.FRIO,
    "CALOR":  TT.CALOR,
    "VENT":   TT.VENT,
    "BLANCO": TT.BLANCO,
    "ROJO":   TT.ROJO,
    "AZUL":   TT.AZUL,
}

# Prefijos de sensores (más largo primero)
PREFIJOS_SENSOR = (
    "sensor_movimiento",
    "sensor_humedad",
    "sensor_humo",
    "sensor_temp",
    "sensor_luz",
)

# Prefijos de actuadores (más largo primero)
PREFIJOS_ACTUADOR = (
    "cerradura_",
    "persiana_",
    "altavoz_",
    "alarma_",
    "reloj_",
    "foco_",
    "aire_",
)

# Atributos conocidos (case-insensitive en el nombre del atributo)
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

# Tabla de rangos para validación semántica temprana
TABLA_RANGOS: dict = {
    ("sensor_temp",    None): (TT.TEMPERATURA, RANGO_TEMP_1,  "sensor_temp"),
    ("sensor_humedad", None): (TT.PORCENTAJE,  RANGO_PERCENT, "sensor_humedad"),
    ("sensor_luz",     None): (TT.ILUMINANCIA, RANGO_LUX,     "sensor_luz"),
    ("foco_",  TT.ATTR_BRILLO):   (TT.PORCENTAJE,  RANGO_PERCENT, "foco_.brillo"),
    ("aire_",  TT.ATTR_TEMP_OBJ): (TT.TEMPERATURA, RANGO_TEMP_2,  "aire_.temp_obj"),
    ("aire_",  TT.ATTR_TEMP_ACT): (TT.TEMPERATURA, RANGO_TEMP_1,  "aire_.temp_act"),
    ("persiana_", TT.ATTR_POSICION): (TT.PORCENTAJE, RANGO_PERCENT, "persiana_.posicion"),
    ("altavoz_", TT.ATTR_VOLUMEN):   (TT.PORCENTAJE, RANGO_PERCENT, "altavoz_.volumen"),
}


# ======================================================================
#  5. FUNCIONES AUXILIARES DE CARACTERES  (reemplazan a `re`)
# ======================================================================

def _es_letra(c: str) -> bool:
    return ('a' <= c <= 'z') or ('A' <= c <= 'Z')

def _es_digito(c: str) -> bool:
    return '0' <= c <= '9'

def _es_alfanum_o_guion(c: str) -> bool:
    return _es_letra(c) or _es_digito(c) or c == '_'

def _es_email_char(c: str) -> bool:
    """Caracteres válidos en nombre de usuario o dominio de email."""
    return _es_letra(c) or _es_digito(c) or c in ('_', '.', '+', '-')

def _es_blanco(c: str) -> bool:
    return c in (' ', '\t', '\r', '\n')


# ======================================================================
#  6. FUNCIONES DE RECONOCIMIENTO MANUAL  (sin re)
#     Cada función recibe (linea, pos) y retorna (valor, nuevo_pos)
#     o None si no hay coincidencia en esa posición.
# ======================================================================

def _leer_comentario(linea: str, pos: int) -> Optional[tuple]:
    """// hasta fin de línea"""
    if pos + 1 < len(linea) and linea[pos] == '/' and linea[pos+1] == '/':
        return (linea[pos:], len(linea))
    return None

def _leer_cadena(linea: str, pos: int) -> Optional[tuple]:
    """Cadena entre comillas dobles: "..." sin saltos de línea"""
    if linea[pos] != '"':
        return None
    i = pos + 1
    while i < len(linea) and linea[i] != '"' and linea[i] != '\n':
        i += 1
    if i < len(linea) and linea[i] == '"':
        return (linea[pos:i+1], i+1)
    return None  # comilla sin cerrar → error léxico

def _leer_numero(linea: str, pos: int) -> Optional[tuple]:
    """
    Lee un número entero o decimal, con signo negativo opcional.
    Retorna (valor_str, nuevo_pos).
    """
    i = pos
    if i < len(linea) and linea[i] == '-':
        i += 1
    if i >= len(linea) or not _es_digito(linea[i]):
        return None
    while i < len(linea) and _es_digito(linea[i]):
        i += 1
    # parte decimal
    if i < len(linea) and linea[i] == '.' and i+1 < len(linea) and _es_digito(linea[i+1]):
        i += 1
        while i < len(linea) and _es_digito(linea[i]):
            i += 1
    return (linea[pos:i], i)

def _extraer_numero(s: str) -> float:
    """
    Extrae el valor numérico del inicio de un string que puede
    comenzar con '-' y dígitos (para tokens como '25°C', '-5°C',
    '80%', '600lux').
    Reemplaza re.match en la extraccion numerica.
    """
    i = 0
    if i < len(s) and s[i] == '-':
        i += 1
    while i < len(s) and _es_digito(s[i]):
        i += 1
    if i < len(s) and s[i] == '.' and i+1 < len(s) and _es_digito(s[i+1]):
        i += 1
        while i < len(s) and _es_digito(s[i]):
            i += 1
    return float(s[:i])

def _leer_temperatura(linea: str, pos: int) -> Optional[tuple]:
    """
    Reconoce: [-]dígitos[.dígitos]°C
    El carácter ° es Unicode U+00B0 (puede ser multibyte en UTF-8,
    pero Python str es Unicode, así que lo comparamos directamente).
    """
    res = _leer_numero(linea, pos)
    if res is None:
        return None
    num_str, i = res
    if i < len(linea) and linea[i] == '°':
        i += 1
        if i < len(linea) and linea[i] in ('C', 'c'):
            return (linea[pos:i+1], i+1)
    return None

def _leer_con_sufijo(linea: str, pos: int, sufijo: str) -> Optional[tuple]:
    """
    Lee un número positivo seguido exactamente por `sufijo`.
    Para PORCENTAJE (%), ILUMINANCIA (lux), TIEMPO (s, m, h).
    No acepta signo negativo.
    """
    if linea[pos] == '-':
        return None  # no se admite negativo
    res = _leer_numero(linea, pos)
    if res is None:
        return None
    num_str, i = res
    if num_str.startswith('-'):
        return None
    if linea[i:i+len(sufijo)].lower() == sufijo.lower():
        # Verificar que después del sufijo no haya más letras
        # (para no confundir "5min" con "5m" + "in")
        j = i + len(sufijo)
        if j < len(linea) and _es_letra(linea[j]):
            return None
        return (linea[pos:j], j)
    return None

def _leer_tiempo(linea: str, pos: int) -> Optional[tuple]:
    """Número seguido de s, m, o h (solo si no hay más letras tras)"""
    for unidad in ('s', 'm', 'h'):
        res = _leer_con_sufijo(linea, pos, unidad)
        if res is not None:
            return res
    return None

def _leer_hora(linea: str, pos: int) -> Optional[tuple]:
    """
    HH:MM  en formato 24 horas.
    HH: 00-23, MM: 00-59.
    """
    # Necesitamos exactamente 5 caracteres: DD:DD
    if pos + 4 >= len(linea) + 1:
        return None
    s = linea[pos:pos+5]
    if len(s) < 5:
        return None
    if (s[2] != ':' or
        not _es_digito(s[0]) or not _es_digito(s[1]) or
        not _es_digito(s[3]) or not _es_digito(s[4])):
        return None
    hh = int(s[0:2])
    mm = int(s[3:5])
    if hh > 23 or mm > 59:
        return None
    # Verificar que justo después no haya más dígitos (evitar 12:345)
    j = pos + 5
    if j < len(linea) and _es_digito(linea[j]):
        return None
    return (s, pos+5)

def _leer_fecha(linea: str, pos: int) -> Optional[tuple]:
    """
    DD/MM/AAAA.
    Día 1-31, Mes 1-12, Año 1900-2099.
    """
    i = pos
    # Leer día (1 o 2 dígitos)
    if i >= len(linea) or not _es_digito(linea[i]):
        return None
    j = i
    while j < len(linea) and _es_digito(linea[j]):
        j += 1
    if j - i > 2 or j >= len(linea) or linea[j] != '/':
        return None
    dia = int(linea[i:j])
    if dia < 1 or dia > 31:
        return None
    i = j + 1  # saltar '/'

    # Leer mes (1 o 2 dígitos)
    if i >= len(linea) or not _es_digito(linea[i]):
        return None
    j = i
    while j < len(linea) and _es_digito(linea[j]):
        j += 1
    if j - i > 2 or j >= len(linea) or linea[j] != '/':
        return None
    mes = int(linea[i:j])
    if mes < 1 or mes > 12:
        return None
    i = j + 1  # saltar '/'

    # Leer año (exactamente 4 dígitos)
    if i + 3 >= len(linea):
        return None
    año_str = linea[i:i+4]
    if not all(_es_digito(c) for c in año_str):
        return None
    año = int(año_str)
    if año < 1900 or año > 2099:
        return None
    # Verificar que tras el año no haya más dígitos
    j = i + 4
    if j < len(linea) and _es_digito(linea[j]):
        return None
    return (linea[pos:j], j)

def _leer_email(linea: str, pos: int) -> Optional[tuple]:
    """
    usuario@dominio.ext
    usuario/dominio: letras, dígitos, _ . + -
    extensión: 2-4 letras
    """
    i = pos
    # nombre de usuario (al menos un char válido)
    if i >= len(linea) or not _es_email_char(linea[i]):
        return None
    while i < len(linea) and _es_email_char(linea[i]):
        i += 1
    # @
    if i >= len(linea) or linea[i] != '@':
        return None
    i += 1
    # dominio (al menos un char antes del último punto)
    dom_start = i
    while i < len(linea) and _es_email_char(linea[i]):
        i += 1
    if i == dom_start:
        return None
    # extensión: debe haber un punto y 2-4 letras al final
    # Buscar el último punto en lo que llevamos
    dominio_completo = linea[dom_start:i]
    ultimo_punto = dominio_completo.rfind('.')
    if ultimo_punto == -1:
        return None
    ext = dominio_completo[ultimo_punto+1:]
    if len(ext) < 2 or len(ext) > 4 or not all(_es_letra(c) for c in ext):
        return None
    return (linea[pos:i], i)

def _leer_identificador(linea: str, pos: int) -> Optional[tuple]:
    """
    Letra o _ seguido de letras, dígitos o _.
    """
    if pos >= len(linea):
        return None
    c = linea[pos]
    if not (_es_letra(c) or c == '_'):
        return None
    i = pos + 1
    while i < len(linea) and _es_alfanum_o_guion(linea[i]):
        i += 1
    return (linea[pos:i], i)


# ======================================================================
#  7. HELPERS NUMÉRICOS PARA VALIDACIÓN DE RANGOS  (sin re)
# ======================================================================

def _num_temperatura(v: str) -> float:
    """'25°C' → 25.0  |  '-5°C' → -5.0"""
    return _extraer_numero(v)

def _num_porcentaje(v: str) -> float:
    """'80%' → 80.0"""
    return _extraer_numero(v)

def _num_iluminancia(v: str) -> float:
    """'600lux' → 600.0"""
    return _extraer_numero(v)

_EXTRACTOR: dict = {
    TT.TEMPERATURA: _num_temperatura,
    TT.PORCENTAJE:  _num_porcentaje,
    TT.ILUMINANCIA: _num_iluminancia,
}


# ======================================================================
#  8. CLASE PRINCIPAL  SmartHomeLexer
# ======================================================================

class SmartHomeLexer:
    """
    Analizador léxico para SMART-HOME.
    No usa el módulo `re` en ninguna parte.
    Las palabras reservadas son CASE-SENSITIVE (solo MAYÚSCULAS).
    """

    def __init__(self):
        self.errores:      list = []
        self.advertencias: list = []
        self._ctx_prefijo:   Optional[str] = None
        self._ctx_attr_tipo: Optional[str] = None
        self._ultimo_tipo:   Optional[str] = None

    # ── API pública ───────────────────────────────────────────────

    def tokenizar(self, fuente: str, num_linea_base: int = 1) -> list:
        self.errores = []
        self.advertencias = []
        self._reset_ctx()
        tokens = []
        lineas = fuente.splitlines(keepends=True)
        for i, linea in enumerate(lineas):
            self._procesar_linea(linea, num_linea_base + i, tokens)
        tokens.append(Token(TT.EOF, "", num_linea_base + len(lineas), 0))
        return tokens

    def tokenizar_linea(self, linea: str, num_linea: int = 1) -> list:
        self.errores = []
        self.advertencias = []
        tokens = []
        self._procesar_linea(linea, num_linea, tokens)
        tokens.append(Token(TT.EOF, "", num_linea, len(linea)))
        return tokens

    def reset_contexto_interactivo(self):
        self._reset_ctx()

    # ── Internos ──────────────────────────────────────────────────

    def _reset_ctx(self):
        self._ctx_prefijo   = None
        self._ctx_attr_tipo = None
        self._ultimo_tipo   = None

    def _procesar_linea(self, linea: str, num_linea: int, tokens: list) -> None:
        pos = 0
        n   = len(linea)

        while pos < n:
            # Saltar blancos
            if _es_blanco(linea[pos]):
                pos += 1
                continue

            col = pos + 1   # columna 1-based
            tok = self._siguiente_token(linea, pos, num_linea, col)

            if tok is None:
                # Carácter no reconocido
                self.errores.append(
                    f"Error lexico   | Linea {num_linea:3d}, Col {col:3d} "
                    f"| Caracter no reconocido: '{linea[pos]}'"
                )
                tokens.append(Token(TT.DESCONOCIDO, linea[pos], num_linea, col))
                pos += 1
                continue

            tipo, valor, nuevo_pos = tok

            if tipo == TT.COMENTARIO:
                break   # resto de la línea es comentario

            t = Token(tipo, valor, num_linea, col)
            tokens.append(t)
            self._actualizar_ctx(t)
            self._validar_rango(t)
            pos = nuevo_pos

    def _siguiente_token(self, linea: str, pos: int, num_linea: int, col: int):
        """
        Intenta reconocer el próximo token en linea[pos:].
        Retorna (tipo, valor, nuevo_pos) o None.

        Orden de precedencia:
          1. Comentario //
          2. Cadena "..."
          3. Email  (antes que identificador porque contiene @)
          4. Temperatura  -?n°C
          5. Iluminancia  nlux
          6. Porcentaje   n%
          7. Tiempo       n[smh]
          8. Fecha        DD/MM/AAAA
          9. Hora         HH:MM
         10. Operadores dobles  == != >= <=
         11. Operadores simples > < =
         12. Punto .
         13. Flotante  -?n.n
         14. Entero    -?n
         15. Identificador → palabra reservada / sensor / actuador / atributo
        """
        c = linea[pos]

        # 1. Comentario
        res = _leer_comentario(linea, pos)
        if res:
            return (TT.COMENTARIO, res[0], res[1])

        # 2. Cadena
        res = _leer_cadena(linea, pos)
        if res:
            return (TT.CADENA, res[0], res[1])

        # 3. Email  (solo si el primer char es letra/dígito/etc.,
        #    y hay un '@' más adelante antes de un espacio)
        if _es_email_char(c) and '@' in linea[pos:]:
            res = _leer_email(linea, pos)
            if res:
                return (TT.EMAIL, res[0], res[1])

        # 4. Temperatura  (puede empezar con '-')
        if c == '-' or _es_digito(c):
            res = _leer_temperatura(linea, pos)
            if res:
                return (TT.TEMPERATURA, res[0], res[1])

        # 5. Iluminancia  nlux  (positivo)
        if _es_digito(c):
            res = _leer_con_sufijo(linea, pos, 'lux')
            if res:
                return (TT.ILUMINANCIA, res[0], res[1])

        # 6. Porcentaje  n%  (positivo)
        if _es_digito(c):
            res = _leer_con_sufijo(linea, pos, '%')
            if res:
                return (TT.PORCENTAJE, res[0], res[1])

        # 7. Tiempo  n[smh]  (positivo)
        if _es_digito(c):
            res = _leer_tiempo(linea, pos)
            if res:
                return (TT.TIEMPO, res[0], res[1])

        # 8. Fecha DD/MM/AAAA
        if _es_digito(c):
            res = _leer_fecha(linea, pos)
            if res:
                return (TT.FECHA, res[0], res[1])

        # 9. Hora HH:MM
        if _es_digito(c):
            res = _leer_hora(linea, pos)
            if res:
                return (TT.HORA, res[0], res[1])

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

        # 13. Flotante  -?n.n   (el '.' decimal no es un PUNTO)
        if c == '-' or _es_digito(c):
            res = _leer_numero(linea, pos)
            if res:
                num_str, nuevo_pos = res
                tipo = TT.FLOTANTE if '.' in num_str else TT.ENTERO
                return (tipo, num_str, nuevo_pos)

        # 14. Identificador (letra o _)
        if _es_letra(c) or c == '_':
            res = _leer_identificador(linea, pos)
            if res:
                palabra, nuevo_pos = res
                tipo, valor = self._clasificar(palabra)
                return (tipo, valor, nuevo_pos)

        return None   # carácter desconocido

    # ── Clasificación de identificadores ─────────────────────────

    def _clasificar(self, palabra: str) -> tuple:
        """
        Clasifica un identificador en su categoría real.

        Cambio respecto a v2: las palabras reservadas son CASE-SENSITIVE.
        Solo se reconocen en MAYÚSCULAS exactas.
        Sensores y actuadores siguen siendo case-insensitive porque
        son nombres de dispositivos dados por el usuario.
        """
        # 1. Palabras reservadas: CASE-SENSITIVE (solo MAYÚSCULAS)
        if palabra in PALABRAS_RESERVADAS:
            return PALABRAS_RESERVADAS[palabra], palabra

        # 2. Sensores (case-insensitive en el nombre)
        lower = palabra.lower()
        for pfx in PREFIJOS_SENSOR:
            if lower == pfx or lower.startswith(pfx + "_"):
                return TT.SENSOR, lower

        # 3. Actuadores (case-insensitive)
        for pfx in PREFIJOS_ACTUADOR:
            if lower.startswith(pfx):
                return TT.ACTUADOR, lower

        # 4. Atributo (solo si el token anterior fue PUNTO)
        if self._ultimo_tipo == TT.PUNTO:
            attr_tipo = ATRIBUTOS_CONOCIDOS.get(lower, TT.ATTR_GENERICO)
            return attr_tipo, lower

        # 5. Identificador genérico
        return TT.IDENTIFICADOR, palabra

    # ── Autómata de contexto ──────────────────────────────────────

    def _prefijo_canonico(self, nombre: str) -> Optional[str]:
        lower = nombre.lower()
        for pfx in PREFIJOS_SENSOR:
            if lower == pfx or lower.startswith(pfx + "_"):
                return pfx
        for pfx in PREFIJOS_ACTUADOR:
            if lower.startswith(pfx):
                return pfx
        return None

    def _actualizar_ctx(self, tok: Token) -> None:
        tt = tok.tipo
        if tt in (TT.SENSOR, TT.ACTUADOR):
            self._ctx_prefijo   = self._prefijo_canonico(tok.valor)
            self._ctx_attr_tipo = None
        elif tt in ATRIBUTOS_CONOCIDOS.values():
            self._ctx_attr_tipo = tt
        elif tt == TT.ATTR_GENERICO:
            self._ctx_attr_tipo = None
        elif tt in (TT.WHEN, TT.IF, TT.THEN, TT.ELSE,
                    TT.DO, TT.END, TT.EVERY):
            self._ctx_prefijo   = None
            self._ctx_attr_tipo = None
        self._ultimo_tipo = tt

    # ── Validación de rangos ──────────────────────────────────────

    def _validar_rango(self, tok: Token) -> None:
        if tok.tipo not in _EXTRACTOR or self._ctx_prefijo is None:
            return
        es_sensor  = self._ctx_prefijo in PREFIJOS_SENSOR
        attr_clave = None if es_sensor else self._ctx_attr_tipo
        clave      = (self._ctx_prefijo, attr_clave)
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
        try:
            num = _EXTRACTOR[tok.tipo](tok.valor)
        except (ValueError, AttributeError):
            return
        if not (rango_min <= num <= rango_max):
            self.advertencias.append(
                f"Advertencia rango | Linea {tok.linea:3d}, Col {tok.col:3d} "
                f"| '{tok.valor}' fuera de rango para '{desc_ctx}' "
                f"-> {desc_rango}"
            )


# ======================================================================
#  9. MODO INTERACTIVO
# ======================================================================

def modo_interactivo():
    lexer     = SmartHomeLexer()
    num_linea = 1
    sep = "=" * 67
    print(sep)
    print("  SMART-HOME Lexer  v3.0  --  Modo Interactivo  (sin re)")
    print("  Palabras reservadas solo en MAYUSCULAS.")
    print("  Comandos: 'reset' reinicia contexto | 'salir' termina")
    print(sep)
    while True:
        try:
            linea = input(f"\n[{num_linea:3d}] >>> ")
        except (EOFError, KeyboardInterrupt):
            break
        cmd = linea.strip().lower()
        if cmd in ("salir", "exit", "quit"):
            break
        if cmd == "reset":
            lexer.reset_contexto_interactivo()
            print("  Contexto reseteado.")
            continue
        tokens = lexer.tokenizar_linea(linea, num_linea)
        for t in tokens:
            if t.tipo != TT.EOF:
                print(f"    {t}")
        for e in lexer.errores:
            print(f"  [ERROR]  {e}")
        for a in lexer.advertencias:
            print(f"  [AVISO]  {a}")
        num_linea += 1
    print()


# ======================================================================
#  10. MODO ARCHIVO
# ======================================================================

def modo_archivo(ruta: str) -> None:
    if not os.path.exists(ruta):
        print(f"Error de ejecucion | El archivo '{ruta}' no existe.")
        sys.exit(1)
    _, ext = os.path.splitext(ruta)
    if ext.lower() != ".smart":
        print(f"Error de ejecucion | Extension incorrecta '{ext}'.")
        sys.exit(1)
    with open(ruta, "r", encoding="utf-8") as f:
        fuente = f.read()
    lexer  = SmartHomeLexer()
    tokens = lexer.tokenizar(fuente)
    n      = sum(1 for t in tokens if t.tipo != TT.EOF)
    sep    = "=" * 67
    print(sep)
    print(f"  SMART-HOME Lexer  v3.0  (sin re)")
    print(f"  Archivo : {ruta}")
    print(f"  Tokens  : {n}")
    print(sep)
    for t in tokens:
        if t.tipo != TT.EOF:
            print(t)
    print()
    if lexer.errores:
        print(f"  [ERRORES LEXICOS: {len(lexer.errores)}]")
        for e in lexer.errores:
            print(f"    {e}")
    if lexer.advertencias:
        print(f"  [ADVERTENCIAS DE RANGO: {len(lexer.advertencias)}]")
        for a in lexer.advertencias:
            print(f"    {a}")
    if not lexer.errores and not lexer.advertencias:
        print("  OK  Analisis lexico exitoso.")
    elif not lexer.errores:
        print("  OK  Analisis lexico exitoso (con advertencias).")
    if lexer.errores:
        sys.exit(2)


# ======================================================================
#  11. SELECTOR DE ARCHIVO (tkinter)
# ======================================================================

def seleccionar_archivo_gui() -> Optional[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        print("tkinter no disponible. Use: python lexer.py archivo.smart")
        return None
    root = tk.Tk()
    root.withdraw()
    root.lift()
    root.focus_force()
    ruta = filedialog.askopenfilename(
        title="Seleccionar archivo SMART-HOME",
        initialdir=os.getcwd(),
        filetypes=[("Archivos SMART-HOME", "*.smart"), ("Todos", "*.*")],
    )
    root.destroy()
    return ruta if ruta else None


# ======================================================================
#  12. PUNTO DE ENTRADA
# ======================================================================

def main():
    if len(sys.argv) == 1:
        print("Abriendo selector de archivo...")
        ruta = seleccionar_archivo_gui()
        if ruta:
            modo_archivo(ruta)
        else:
            print("No se selecciono archivo. Iniciando modo interactivo.\n")
            modo_interactivo()
    elif len(sys.argv) == 2:
        if sys.argv[1] == "--interactivo":
            modo_interactivo()
        else:
            modo_archivo(sys.argv[1])
    else:
        print("Uso:")
        print("  python lexer.py                   # selector grafico")
        print("  python lexer.py archivo.smart     # ruta directa")
        print("  python lexer.py --interactivo     # modo consola")
        sys.exit(1)

if __name__ == "__main__":
    main()