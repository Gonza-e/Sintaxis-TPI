"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOKENS RECONOCIDOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Palabras reservadas: WHEN | IF | THEN | ELSE | DO | END | EVERY
Operadores lógicos: AND | OR | NOT
Booleanos sensor: TRUE | FALSE
Booleanos actuador: ON | OFF
Modos discretos: FRIO | CALOR | VENT
Colores: BLANCO | ROJO | AZUL

Sensores: SENSOR  (sensor_temp*, sensor_humedad, sensor_luz, sensor_movimiento, sensor_humo)

Actuadores: ACTUADOR  (foco_*, aire_*, persiana_*, cerradura_*, reloj_*, altavoz_*, alarma_*)

Atributos tipados    : ATTR_ESTADO      .estado
(emitidos al ver      ATTR_BRILLO       .brillo
PUNTO+nNombre)         ATTR_COLOR        .color
                      ATTR_MODO         .modo
                      ATTR_TEMP_OBJ     .temp_obj
                      ATTR_TEMP_ACT     .temp_act
                      ATTR_POSICION     .posicion / .posicion
                      ATTR_HORA         .hora
                      ATTR_FECHA        .fecha
                      ATTR_VOLUMEN      .volumen
                      ATTR_MUTE         .mute
                      ATTR_MENSAJE      .mensaje
                      ATTR_EMAIL_NOTIF  .email_notif
                      ATTR_ACTIVADA     .activada
                      ATTR_GENERICO     cualquier otro atributo

Literales con unidad : TEMPERATURA  25C  -5C
                       PORCENTAJE   80%
                       ILUMINANCIA  600lux
                       TIEMPO       10s  5m  1h

Literales simples    : HORA   06:00  (HH:MM 24h)
                       FECHA  21/04/2026  (DD/MM/AAAA)
                       EMAIL  user@dom.ext
                       CADENA "texto"
                       ENTERO  FLOTANTE

Operadores           : OP_EQ | OP_NEQ | OP_GTE | OP_LTE | OP_GT | OP_LT | OP_ASIG
Puntuacion           : PUNTO
Especiales           : COMENTARIO(descartado)  DESCONOCIDO  EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RANGOS NOMBRADOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RANGO_TEMP_1:  -10.0 a 50.0 C  (sensor_temp, aire_.temp_act)
RANGO_TEMP_2:  16.0 a 30.0 C  (aire_.temp_obj)
RANGO_PERCENT:   0.0 a 100.0 % (sensor_humedad, foco_.brillo, persiana_.posicion, altavoz_.volumen)
RANGO_LUX:       0.0 a 1000.0  (sensor_luz)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VALIDACION DE RANGOS  (advertencia semantica temprana)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
El lexer rastrea el contexto  dispositivo -> atributo -> valor
y emite ADVERTENCIAS cuando un literal cae fuera de rango.
Nota: la validacion de rangos pertenece al analisis semantico;
se incluye aqui como "early semantic check", practica habitual
en compiladores reales cuando el contexto esta disponible en la
fase lexica.
"""

import re
import sys
import os
from dataclasses import dataclass
from typing import Optional


# ======================================================================
#  1. TIPOS DE TOKEN
# ======================================================================

class TT:
    # Palabras reservadas
    WHEN     = "WHEN"
    IF       = "IF"
    THEN     = "THEN"
    ELSE     = "ELSE"
    DO       = "DO"
    END      = "END"
    EVERY    = "EVERY"
    # Operadores logicos
    AND      = "AND"
    OR       = "OR"
    NOT      = "NOT"
    # Booleanos
    TRUE     = "TRUE"
    FALSE    = "FALSE"
    ON       = "ON"
    OFF      = "OFF"
    # Valores discretos
    FRIO     = "FRIO"
    CALOR    = "CALOR"
    VENT     = "VENT"
    BLANCO   = "BLANCO"
    ROJO     = "ROJO"
    AZUL     = "AZUL"
    # Dispositivos
    SENSOR   = "SENSOR"
    ACTUADOR = "ACTUADOR"
    # ── Atributos tipados ──────────────────────────────────────────
    # El parser puede usarlos directamente en sus reglas de produccion
    # sin necesidad de inspeccionar el valor del token.
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
    ATTR_GENERICO    = "ATTR_GENERICO"   # cualquier otro .nombre
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
    # Generico
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
#     Cada constante: (min, max, descripcion)
#     Exportables al parser para sus propias validaciones semanticas.
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
#  4. TABLAS DE CLASIFICACION
# ======================================================================

# 4a. Palabras reservadas (clave en minusculas)
PALABRAS_RESERVADAS: dict = {
    "when":   TT.WHEN,
    "if":     TT.IF,
    "then":   TT.THEN,
    "else":   TT.ELSE,
    "do":     TT.DO,
    "end":    TT.END,
    "every":  TT.EVERY,
    "and":    TT.AND,
    "or":     TT.OR,
    "not":    TT.NOT,
    "true":   TT.TRUE,
    "false":  TT.FALSE,
    "on":     TT.ON,
    "off":    TT.OFF,
    "frio":   TT.FRIO,
    "calor":  TT.CALOR,
    "vent":   TT.VENT,
    "blanco": TT.BLANCO,
    "rojo":   TT.ROJO,
    "azul":   TT.AZUL,
}

# 4b. Prefijos de sensores (orden: mas largo primero para evitar que "sensor_temp" capture "sensor_temp_int" antes de tiempo)
PREFIJOS_SENSOR = (
    "sensor_movimiento",
    "sensor_humedad",
    "sensor_humo",
    "sensor_temp",
    "sensor_luz",
)

# 4c. Prefijos de actuadores (mas largo primero)
PREFIJOS_ACTUADOR = (
    "cerradura_",
    "persiana_",
    "altavoz_",
    "alarma_",
    "reloj_",
    "foco_",
    "aire_",
)

# 4d. Atributos conocidos -> tipo TT.ATTR_*
#     Clave: nombre del atributo en minusculas (sin el punto).
#     El lexer consulta esta tabla cuando ve  PUNTO + IDENTIFICADOR.
ATRIBUTOS_CONOCIDOS: dict = {
    # ── foco_ ───────────────────────────────
    "estado":      TT.ATTR_ESTADO,     # Booleano ON/OFF
    "brillo":      TT.ATTR_BRILLO,     # Porcentaje 0-100%
    "color":       TT.ATTR_COLOR,      # Nombre blanco/rojo/azul
    # ── aire_ ───────────────────────────────
    "modo":        TT.ATTR_MODO,       # Discreto FRIO/CALOR/VENT
    "temp_obj":    TT.ATTR_TEMP_OBJ,   # Temperatura 16-30 C  (RANGO_TEMP_2)
    "temp_act":    TT.ATTR_TEMP_ACT,   # Temperatura -10-50 C (RANGO_TEMP_1, solo lectura)
    # ── persiana_ ───────────────────────────
    "posicion":    TT.ATTR_POSICION,   # Porcentaje 0-100%
    "posicion":    TT.ATTR_POSICION,   # Alias sin tilde
    # ── reloj_ ──────────────────────────────
    "hora":        TT.ATTR_HORA,       # Tiempo 00:00-23:59 (solo lectura)
    "fecha":       TT.ATTR_FECHA,      # Fecha DD/MM/AAAA (solo lectura)
    # ── altavoz_ ────────────────────────────
    "volumen":     TT.ATTR_VOLUMEN,    # Porcentaje 0-100%
    "mute":        TT.ATTR_MUTE,       # Booleano ON/OFF
    "mensaje":     TT.ATTR_MENSAJE,    # Texto (cadena)
    "email_notif": TT.ATTR_EMAIL_NOTIF,# Email
    # ── alarma_ / cerradura_ ────────────────
    "activada":    TT.ATTR_ACTIVADA,   # Booleano ON/OFF
    # "estado" ya esta arriba y aplica a cerradura_, alarma_, etc.
}

# 4e. Tabla de validacion de rangos
#     Clave : (prefijo_canonico, TT.ATTR_* o None para sensores)
#     Valor : (TT_literal_esperado, rango_tupla, descripcion_contexto)
TABLA_RANGOS: dict = {
    # Sensores (atributo=None: el valor aparece en la condicion)
    ("sensor_temp",    None): (TT.TEMPERATURA, RANGO_TEMP_1,  "sensor_temp"),
    ("sensor_humedad", None): (TT.PORCENTAJE,  RANGO_PERCENT, "sensor_humedad"),
    ("sensor_luz",     None): (TT.ILUMINANCIA, RANGO_LUX,     "sensor_luz"),

    # foco_
    ("foco_",  TT.ATTR_BRILLO):   (TT.PORCENTAJE,  RANGO_PERCENT, "foco_.brillo"),

    # aire_
    ("aire_",  TT.ATTR_TEMP_OBJ): (TT.TEMPERATURA, RANGO_TEMP_2,  "aire_.temp_obj"),
    ("aire_",  TT.ATTR_TEMP_ACT): (TT.TEMPERATURA, RANGO_TEMP_1,  "aire_.temp_act [solo lectura]"),

    # persiana_
    ("persiana_", TT.ATTR_POSICION): (TT.PORCENTAJE, RANGO_PERCENT, "persiana_.posicion"),

    # altavoz_
    ("altavoz_", TT.ATTR_VOLUMEN):   (TT.PORCENTAJE, RANGO_PERCENT, "altavoz_.volumen"),
}


# ======================================================================
#  5. PATRONES REGEX  (orden critico: mas especifico primero)
# ======================================================================

PATRONES: list = [
    (TT.COMENTARIO,    r"//[^\n]*"),
    (TT.CADENA,        r'"[^"\n]*"'),
    (TT.EMAIL,         r"[A-Za-z0-9_.+\-]+@[A-Za-z0-9_.+\-]+\.[A-Za-z]{2,4}"),
    (TT.TEMPERATURA,   r"-?\d+(?:\.\d+)?°[Cc]"),
    (TT.ILUMINANCIA,   r"\d+(?:\.\d+)?lux"),
    (TT.PORCENTAJE,    r"\d+(?:\.\d+)?%"),
    (TT.TIEMPO,        r"\d+(?:\.\d+)?[smh]"),
    (TT.FECHA,
     r"(?:0?[1-9]|[12]\d|3[01])/(?:0?[1-9]|1[0-2])/(?:19\d{2}|20\d{2})"),
    (TT.HORA,          r"(?:[01]\d|2[0-3]):[0-5]\d"),
    (TT.OP_EQ,         r"=="),
    (TT.OP_NEQ,        r"!="),
    (TT.OP_GTE,        r">="),
    (TT.OP_LTE,        r"<="),
    (TT.OP_GT,         r">"),
    (TT.OP_LT,         r"<"),
    (TT.OP_ASIG,       r"="),
    (TT.PUNTO,         r"\."),
    (TT.FLOTANTE,      r"-?\d+\.\d+"),
    (TT.ENTERO,        r"-?\d+"),
    (TT.IDENTIFICADOR, r"[A-Za-z_][A-Za-z0-9_]*"),
]

_REGEX_MASTER = re.compile(
    "|".join(f"(?P<_{i}>{pat})" for i, (_, pat) in enumerate(PATRONES)),
    re.IGNORECASE,
)
_IDX_TO_TYPE: dict = {i: tt for i, (tt, _) in enumerate(PATRONES)}


# ======================================================================
#  6. HELPERS NUMERICOS
# ======================================================================

def _num_temperatura(v: str) -> float:
    return float(re.match(r"(-?\d+(?:\.\d+)?)", v).group(1))

def _num_porcentaje(v: str) -> float:
    return float(re.match(r"(\d+(?:\.\d+)?)", v).group(1))

def _num_iluminancia(v: str) -> float:
    return float(re.match(r"(\d+(?:\.\d+)?)", v).group(1))

_EXTRACTOR: dict = {
    TT.TEMPERATURA: _num_temperatura,
    TT.PORCENTAJE:  _num_porcentaje,
    TT.ILUMINANCIA: _num_iluminancia,
}


# ======================================================================
#  7. CLASE PRINCIPAL  SmartHomeLexer
# ======================================================================

class SmartHomeLexer:
    """
    Analizador lexico para SMART-HOME.

    Atributos despues de tokenizar():
        .errores       -- errores lexicos (caracter ilegal, etc.)
        .advertencias  -- advertencias de rango (semantica temprana)
    """

    def __init__(self):
        self.errores:      list = []
        self.advertencias: list = []
        self._ctx_prefijo:   Optional[str] = None
        self._ctx_attr_tipo: Optional[str] = None
        self._ultimo_tipo:   Optional[str] = None

    # ── API publica ───────────────────────────────────────────────

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

    # ── Tokenizacion interna ──────────────────────────────────────

    def _reset_ctx(self):
        self._ctx_prefijo   = None
        self._ctx_attr_tipo = None
        self._ultimo_tipo   = None

    def _procesar_linea(self, linea: str, num_linea: int, tokens: list) -> None:
        pos = 0
        while pos < len(linea):
            if linea[pos] in " \t\r\n":
                pos += 1
                continue

            m = _REGEX_MASTER.match(linea, pos)
            if not m:
                ch  = linea[pos]
                col = pos + 1
                self.errores.append(
                    f"Error lexico   | Linea {num_linea:3d}, Col {col:3d} "
                    f"| Caracter no reconocido: '{ch}'"
                )
                tokens.append(Token(TT.DESCONOCIDO, ch, num_linea, col))
                pos += 1
                continue

            idx   = int(m.lastgroup[1:])
            tipo  = _IDX_TO_TYPE[idx]
            valor = m.group()
            col   = pos + 1

            if tipo == TT.COMENTARIO:
                break

            if tipo == TT.IDENTIFICADOR:
                tipo, valor = self._clasificar(valor)

            tok = Token(tipo, valor, num_linea, col)
            tokens.append(tok)
            self._actualizar_ctx(tok)
            self._validar_rango(tok)
            pos = m.end()

    # ── Clasificacion de identificadores ─────────────────────────

    def _clasificar(self, palabra: str) -> tuple:
        lower = palabra.lower()

        # 1. Palabras reservadas / booleanos / discretos / colores
        if lower in PALABRAS_RESERVADAS:
            return PALABRAS_RESERVADAS[lower], palabra.upper()

        # 2. Sensores (prefijos ordenados por longitud desc.)
        for pfx in PREFIJOS_SENSOR:
            if lower == pfx or lower.startswith(pfx + "_"):
                return TT.SENSOR, lower

        # 3. Actuadores
        for pfx in PREFIJOS_ACTUADOR:
            if lower.startswith(pfx):
                return TT.ACTUADOR, lower

        # 4. Atributo (solo si el token anterior fue PUNTO)
        if self._ultimo_tipo == TT.PUNTO:
            attr_tipo = ATRIBUTOS_CONOCIDOS.get(lower, TT.ATTR_GENERICO)
            return attr_tipo, lower

        # 5. Identificador generico
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
            self._ctx_attr_tipo = tt           # ATTR_BRILLO, ATTR_TEMP_OBJ, etc.

        elif tt == TT.ATTR_GENERICO:
            self._ctx_attr_tipo = None         # sin rango definido

        elif tt in (TT.WHEN, TT.IF, TT.THEN, TT.ELSE,
                    TT.DO, TT.END, TT.EVERY):
            self._ctx_prefijo   = None
            self._ctx_attr_tipo = None

        self._ultimo_tipo = tt

    # ── Validacion de rangos ──────────────────────────────────────

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
#  8. MODO INTERACTIVO
# ======================================================================

def modo_interactivo():
    lexer     = SmartHomeLexer()
    num_linea = 1
    sep = "=" * 67

    print(sep)
    print("  SMART-HOME Lexer  v2.0  --  Modo Interactivo")
    print("  Escriba una instruccion y presione Enter.")
    print("  Comandos: 'reset' reinicia el contexto | 'salir' termina")
    print(sep)

    while True:
        try:
            linea = input(f"\n[{num_linea:3d}] >>> ")
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo.")
            break

        cmd = linea.strip().lower()
        if cmd in ("salir", "exit", "quit"):
            print("Hasta luego.")
            break
        if cmd == "reset":
            lexer.reset_contexto_interactivo()
            print("  Contexto reseteado.")
            continue

        tokens = lexer.tokenizar_linea(linea, num_linea)
        for tok in tokens:
            if tok.tipo != TT.EOF:
                print(f"    {tok}")
        for e in lexer.errores:
            print(f"  [ERROR]  {e}")
        for a in lexer.advertencias:
            print(f"  [AVISO]  {a}")

        num_linea += 1
    print()


# ======================================================================
#  9. MODO ARCHIVO
# ======================================================================

def modo_archivo(ruta: str) -> None:
    import os

    if not os.path.exists(ruta):
        print(f"Error de ejecucion | El archivo '{ruta}' no existe.")
        sys.exit(1)

    _, ext = os.path.splitext(ruta)
    if ext.lower() != ".smart":
        print(f"Error de ejecucion | Extension incorrecta '{ext}'. "
              f"Se esperaba '.smart'.")
        sys.exit(1)

    with open(ruta, "r", encoding="utf-8") as f:
        fuente = f.read()

    lexer  = SmartHomeLexer()
    tokens = lexer.tokenizar(fuente)
    n      = sum(1 for t in tokens if t.tipo != TT.EOF)
    sep    = "=" * 67

    print(sep)
    print(f"  SMART-HOME Lexer  v2.0")
    print(f"  Archivo : {ruta}")
    print(f"  Tokens  : {n}")
    print(sep)

    for tok in tokens:
        if tok.tipo != TT.EOF:
            print(tok)

    print()
    if lexer.errores:
        print(f"  [ERRORES LEXICOS: {len(lexer.errores)}]")
        for e in lexer.errores:
            print(f"    {e}")
        print()

    if lexer.advertencias:
        print(f"  [ADVERTENCIAS DE RANGO: {len(lexer.advertencias)}]")
        for a in lexer.advertencias:
            print(f"    {a}")
        print()

    if not lexer.errores and not lexer.advertencias:
        print("  OK  Analisis lexico exitoso -- sin errores ni advertencias.")
    elif not lexer.errores:
        print("  OK  Analisis lexico exitoso (con advertencias de rango).")

    if lexer.errores:
        sys.exit(2)


# ======================================================================
#  10. SELECTOR DE ARCHIVO (GUI — tkinter)
# ======================================================================

def seleccionar_archivo_gui() -> Optional[str]:
    """
    Abre un cuadro de diálogo nativo del sistema operativo para que
    el usuario seleccione un archivo .smart.

    Pasos:
      1. Importa tkinter y crea una ventana raíz oculta.
         (La ventana raíz es necesaria para que filedialog funcione,
          pero no la queremos visible — por eso se llama withdraw().)
      2. Lleva la ventana oculta al frente del escritorio con
         lift() + focus_force() para que el diálogo aparezca encima
         de otras ventanas y no quede detrás.
      3. Muestra el diálogo askopenfilename() filtrado a *.smart
         y al directorio de trabajo actual como punto de partida.
      4. Destruye la ventana raíz para liberar recursos de Tk.
      5. Retorna la ruta seleccionada, o None si el usuario canceló.

    Retorna:
        str  — ruta absoluta al archivo seleccionado
        None — si el usuario cerró el diálogo sin seleccionar nada
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        print("Error: tkinter no está disponible en este entorno.")
        print("       Instale python3-tk o use:  python lexer.py archivo.smart")
        return None

    # Crear ventana raíz invisible (obligatoria para filedialog)
    root = tk.Tk()
    root.withdraw()       # ocultarla — no queremos una ventana vacía
    root.lift()           # traerla al frente del stack de ventanas
    root.focus_force()    # darle el foco para que el diálogo no quede atrás

    ruta = filedialog.askopenfilename(
        title      = "Seleccionar archivo SMART-HOME",
        initialdir = os.getcwd(),
        filetypes  = [
            ("Archivos SMART-HOME", "*.smart"),
            ("Todos los archivos",  "*.*"),
        ],
    )

    root.destroy()   # liberar la ventana raíz de Tk

    # askopenfilename retorna "" si el usuario cancela
    return ruta if ruta else None


# ======================================================================
#  11. PUNTO DE ENTRADA
# ======================================================================

def main():
    """
    Lógica de inicio del programa.

    Casos posibles:
      • Sin argumentos       → abre el diálogo gráfico para elegir archivo.
                               Si el usuario cancela, cae al modo interactivo.
      • Un argumento (ruta)  → usa esa ruta directamente.
      • '--interactivo'      → fuerza el modo de consola sin GUI.
      • Más de un argumento  → muestra uso y termina.
    """
    if len(sys.argv) == 1:
        print("Abriendo selector de archivo...")
        ruta = seleccionar_archivo_gui()

        if ruta:
            modo_archivo(ruta)
        else:
            print("No se seleccionó archivo. Iniciando modo interactivo.\n")
            modo_interactivo()

    elif len(sys.argv) == 2:
        if sys.argv[1] == "--interactivo":
            modo_interactivo()
        else:
            modo_archivo(sys.argv[1])

    else:
        print("Uso:")
        print("  python lexer.py                    # selector gráfico de archivo")
        print("  python lexer.py archivo.smart      # ruta directa")
        print("  python lexer.py --interactivo      # modo consola sin GUI")
        sys.exit(1)

if __name__ == "__main__":
    main()