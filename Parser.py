"""
╔══════════════════════════════════════════════════════════════════╗
║   SMART-HOME Parser PLY  —  Sintaxis y Semántica de Lenguajes   ║
║   UTN Facultad Regional Resistencia  |  Ciclo 2026              ║
╚══════════════════════════════════════════════════════════════════╝

Análisis léxico  : lexer_v4.py (implementación manual, sin re)
Análisis sintáctico: PLY LALR(1)

Nota sobre el adaptador:
  PLY llama a lexer.token() y espera un objeto con .type/.value/.lineno.
  Nuestro adaptador (_PLYToken) envuelve cada Token de lexer_v4 así:
      _PLYToken.type   = tok.tipo   (string, ej. "WHEN")
      _PLYToken.value  = tok        (Token completo de lexer_v4)
  Dentro de las reglas p_*, PLY ya extrae .value automáticamente,
  por lo tanto p[i] == Token de lexer_v4, con campos .tipo/.valor/.linea/.col
"""

import sys
import os
from collections import OrderedDict
from typing import Optional, List

sys.path.insert(0, os.path.dirname(__file__))
from Lexer import (
    SmartHomeLexer, Token, TT,
    ATRIBUTOS_CONOCIDOS,
)

import ply.yacc as yacc


# ======================================================================
#  1. ESPECIFICACIONES SEMÁNTICAS
# ======================================================================

ESPECIFICACION_ATRIBUTOS: dict = {
    (TT.ACT_FOCO,      TT.ATTR_ESTADO):      ({TT.ON, TT.OFF},               False, "BOOL (ON/OFF)"),
    (TT.ACT_FOCO,      TT.ATTR_BRILLO):      ({TT.PORCENTAJE},               False, "PERCENT (0%-100%)"),
    (TT.ACT_FOCO,      TT.ATTR_COLOR):       ({TT.BLANCO, TT.ROJO, TT.AZUL}, False, "NOMBRE (BLANCO/ROJO/AZUL)"),
    (TT.ACT_AIRE,      TT.ATTR_ESTADO):      ({TT.ON, TT.OFF},               False, "BOOL (ON/OFF)"),
    (TT.ACT_AIRE,      TT.ATTR_MODO):        ({TT.FRIO, TT.CALOR, TT.VENT},  False, "DISCRETO (FRIO/CALOR/VENT)"),
    (TT.ACT_AIRE,      TT.ATTR_TEMP_OBJ):    ({TT.TEMPERATURA},              False, "TEMP (16°C-30°C)"),
    (TT.ACT_AIRE,      TT.ATTR_TEMP_ACT):    ({TT.TEMPERATURA},              True,  "TEMP — Solo Lectura"),
    (TT.ACT_PERSIANA,  TT.ATTR_POSICION):    ({TT.PORCENTAJE},               False, "PERCENT (0%-100%)"),
    (TT.ACT_CERRADURA, TT.ATTR_ESTADO):      ({TT.ON, TT.OFF},               False, "BOOL (ON/OFF)"),
    (TT.ACT_RELOJ,     TT.ATTR_HORA):        ({TT.HORA},                     True,  "TIME — Solo Lectura"),
    (TT.ACT_RELOJ,     TT.ATTR_FECHA):       ({TT.FECHA},                    True,  "DATE — Solo Lectura"),
    (TT.ACT_ALTAVOZ,   TT.ATTR_VOLUMEN):     ({TT.PORCENTAJE},               False, "PERCENT (0%-100%)"),
    (TT.ACT_ALTAVOZ,   TT.ATTR_MUTE):        ({TT.ON, TT.OFF},               False, "BOOL (ON/OFF)"),
    (TT.ACT_ALTAVOZ,   TT.ATTR_MENSAJE):     ({TT.CADENA},                   False, "texto (cadena)"),
    (TT.ACT_ALTAVOZ,   TT.ATTR_EMAIL_NOTIF): ({TT.EMAIL},                    False, "email"),
    (TT.ACT_ALARMA,    TT.ATTR_ESTADO):      ({TT.ON, TT.OFF},               False, "BOOL (ON/OFF)"),
    (TT.ACT_ALARMA,    TT.ATTR_ACTIVADA):    ({TT.ON, TT.OFF},               False, "BOOL (ON/OFF)"),
}

TIPOS_VALOR_SENSOR: dict = {
    TT.SENSOR_TEMP:       {TT.TEMPERATURA},
    TT.SENSOR_HUMEDAD:    {TT.PORCENTAJE},
    TT.SENSOR_LUZ:        {TT.ILUMINANCIA},
    TT.SENSOR_MOVIMIENTO: {TT.TRUE, TT.FALSE},
    TT.SENSOR_HUMO:       {TT.TRUE, TT.FALSE},
}

_NOMBRE_TIPO_SENSOR: dict = {
    TT.SENSOR_TEMP:       "TEMPERATURA (ej. 26°C)",
    TT.SENSOR_HUMEDAD:    "PORCENTAJE (ej. 80%)",
    TT.SENSOR_LUZ:        "ILUMINANCIA (ej. 250lux)",
    TT.SENSOR_MOVIMIENTO: "TRUE o FALSE",
    TT.SENSOR_HUMO:       "TRUE o FALSE",
}


# ======================================================================
#  2. ESTILOS HTML
# ======================================================================

CSS_SENSOR   = "border:1px solid green; padding:20px; margin:10px 0;"
CSS_ACTUADOR = "border:1px solid gray;  padding:20px; margin:10px 0;"
CSS_SECCION  = ("margin:20px 0; padding:12px 16px; "
                "border-left:3px solid #4a90d9; background:#f8f9ff;")

_OP_TEXTO = {
    TT.OP_EQ: "==", TT.OP_NEQ: "!=",
    TT.OP_GT: ">",  TT.OP_LT:  "<",
    TT.OP_GTE: ">=", TT.OP_LTE: "<=",
}

_LABEL_SENSOR = {
    TT.SENSOR_TEMP:       "Temperatura",
    TT.SENSOR_HUMEDAD:    "Humedad",
    TT.SENSOR_LUZ:        "Iluminancia",
    TT.SENSOR_MOVIMIENTO: "Movimiento detectado",
    TT.SENSOR_HUMO:       "Humo detectado",
}

_UNIDAD_SENSOR = {
    TT.SENSOR_TEMP:    "°C",
    TT.SENSOR_HUMEDAD: "%",
    TT.SENSOR_LUZ:     "lux",
}


# ======================================================================
#  3. ESTADO GLOBAL (compartido entre reglas PLY)
# ======================================================================

class _Estado:
    def reset(self, titulo: str = ""):
        self.titulo       = titulo
        self.errores_sint: List[str] = []
        self.errores_sem:  List[str] = []
        self._out:         List[str] = []
        self._pila_acum:   List[OrderedDict] = []

    def emit(self, s: str):
        self._out.append(s)

    def html(self) -> str:
        return "\n".join(self._out)

    # ── Pila de acumuladores ──────────────────────────────────────
    def push_acum(self):
        self._pila_acum.append(OrderedDict())

    def pop_acum(self):
        if self._pila_acum:
            self._pila_acum.pop()

    def acum(self) -> OrderedDict:
        return self._pila_acum[-1] if self._pila_acum else OrderedDict()

    def anotar(self, nombre: str, li: str):
        a = self.acum()
        if nombre not in a:
            a[nombre] = []
        a[nombre].append(li)

    def volcar(self, ind: str):
        """Emite bloques grises de todos los actuadores acumulados."""
        a = self.acum()
        for nombre, items in a.items():
            self.emit(f'{ind}<div style="{CSS_ACTUADOR}">')
            self.emit(f"{ind}  <h1>{nombre}</h1>")
            self.emit(f"{ind}  <ul>")
            for li in items:
                self.emit(f"{ind}    {li}")
            self.emit(f"{ind}  </ul>")
            self.emit(f"{ind}</div>")
        a.clear()

    # ── Construcción HTML ─────────────────────────────────────────
    def bloque_sensor(self, tok_s: Token, tok_op: Token, tok_v: Token, ind: str):
        label  = _LABEL_SENSOR.get(tok_s.tipo, tok_s.valor)
        unidad = _UNIDAD_SENSOR.get(tok_s.tipo, "")
        op_txt = _OP_TEXTO.get(tok_op.tipo, tok_op.valor)
        texto  = f"{label}  {op_txt} {tok_v.valor}{unidad}".strip()
        self.emit(f'{ind}<div style="{CSS_SENSOR}">')
        self.emit(f"{ind}  <h2>{texto}</h2>")
        self.emit(f"{ind}</div>")

    def html_item(self, attr: Token, val: Token) -> str:
        label = attr.valor.replace("_", " ").capitalize()
        if val.tipo == TT.EMAIL:
            u = val.valor.split("@")[0]
            c = f'<a href="mailto:{val.valor}">Contactar a {u}</a>'
        elif val.tipo == TT.CADENA:
            c = val.valor.strip('"').strip('\u201c').strip('\u201d')
        else:
            c = val.valor
        return f"<li>{label}: {c}</li>"

    # ── Validaciones semánticas ───────────────────────────────────
    def chk_sensor(self, tok_s: Token, tok_v: Token):
        tipos = TIPOS_VALOR_SENSOR.get(tok_s.tipo)
        if tipos and tok_v.tipo not in tipos:
            desc = _NOMBRE_TIPO_SENSOR.get(tok_s.tipo, "valor compatible")
            self.errores_sem.append(
                f"Error semantico  | Linea {tok_v.linea:3d}, Col {tok_v.col:3d} "
                f"| '{tok_v.valor}' no es valido para '{tok_s.valor}' "
                f"-> se esperaba {desc}"
            )

    def chk_attr(self, tok_act: Token, tok_attr: Token,
                 tok_val: Token, es_lectura: bool = False):
        clave = (tok_act.tipo, tok_attr.tipo)
        espec = ESPECIFICACION_ATRIBUTOS.get(clave)
        if espec is None:
            if tok_attr.tipo != TT.ATTR_GENERICO:
                self.errores_sem.append(
                    f"Error semantico  | Linea {tok_attr.linea:3d}, Col {tok_attr.col:3d} "
                    f"| Atributo '.{tok_attr.valor}' no valido para '{tok_act.valor}'"
                )
            return
        tipos_val, solo_lect, desc = espec
        if solo_lect and not es_lectura:
            self.errores_sem.append(
                f"Error semantico  | Linea {tok_attr.linea:3d}, Col {tok_attr.col:3d} "
                f"| '{tok_act.valor}.{tok_attr.valor}' es de Solo Lectura"
            )
        elif tok_val.tipo not in tipos_val:
            self.errores_sem.append(
                f"Error semantico  | Linea {tok_val.linea:3d}, Col {tok_val.col:3d} "
                f"| '{tok_val.valor}' no es valido para "
                f"'{tok_act.valor}.{tok_attr.valor}' -> se esperaba {desc}"
            )


_st = _Estado()
_st.reset()


# ======================================================================
#  4. ADAPTADOR LEXER → PLY
# ======================================================================

class _PLYToken:
    """
    Objeto mínimo compatible con el protocolo de token de PLY.

    NOTA IMPORTANTE: no se usa __slots__ aquí porque PLY, al manejar
    un error sintáctico, intenta asignar dinámicamente el atributo
    `.lexer` sobre el token que causó el error (ply/yacc.py, método
    parseopt_notrack, línea "errtoken.lexer = lexer"). Si la clase
    tiene __slots__ sin incluir 'lexer', esa asignación lanza:
        AttributeError: '_PLYToken' object has no attribute 'lexer'
        and no __dict__ for setting new attributes
    Por eso se usa una clase normal (con __dict__), que permite a PLY
    agregar atributos extra sin que la aplicación se caiga.
    """
    pass


class LexerAdaptador:
    """
    Convierte List[Token] al protocolo de PLY.
    PLY llama a .token() y obtiene _PLYToken donde:
        .type  = tok.tipo   (string que PLY usa para las reglas)
        .value = tok        (Token completo; PLY lo pasa como p[i] en reglas)
    """
    def __init__(self, tokens: List[Token]):
        self._toks = [t for t in tokens if t.tipo not in (TT.EOF, TT.COMENTARIO, TT.DESCONOCIDO, TT.ERROR_LEX)]
        self._pos = 0

    def token(self):
        if self._pos >= len(self._toks):
            return None
        tok = self._toks[self._pos]
        self._pos += 1
        p = _PLYToken()
        p.type = tok.tipo
        p.value = tok          # p[i] en reglas PLY == tok
        p.lineno = tok.linea
        p.lexpos = tok.col
        return p


# ======================================================================
#  5. TOKENS PARA PLY
# ======================================================================

tokens = (
    'WHEN','IF','THEN','ELSE','DO','END','EVERY',
    'AND','OR','NOT',
    'TRUE','FALSE','ON','OFF',
    'FRIO','CALOR','VENT','BLANCO','ROJO','AZUL',
    'SENSOR_TEMP','SENSOR_HUMEDAD','SENSOR_LUZ',
    'SENSOR_MOVIMIENTO','SENSOR_HUMO',
    'ACT_FOCO','ACT_AIRE','ACT_PERSIANA','ACT_CERRADURA',
    'ACT_RELOJ','ACT_ALTAVOZ','ACT_ALARMA',
    'ATTR_ESTADO','ATTR_BRILLO','ATTR_COLOR','ATTR_MODO',
    'ATTR_TEMP_OBJ','ATTR_TEMP_ACT','ATTR_POSICION',
    'ATTR_HORA','ATTR_FECHA','ATTR_VOLUMEN','ATTR_MUTE',
    'ATTR_MENSAJE','ATTR_EMAIL_NOTIF','ATTR_ACTIVADA','ATTR_GENERICO',
    'TEMPERATURA','PORCENTAJE','ILUMINANCIA','TIEMPO',
    'HORA','FECHA','EMAIL','CADENA',
    'ENTERO','FLOTANTE','IDENTIFICADOR',
    'OP_EQ','OP_NEQ','OP_GTE','OP_LTE','OP_GT','OP_LT','OP_ASIG',
    'PUNTO',
)

precedence = (
    ('left',  'OR'),
    ('left',  'AND'),
    ('right', 'NOT'),
)


# ======================================================================
#  6. GRAMÁTICA PLY
#     Nota: p[i] ya es el Token de lexer_v4 (con .tipo/.valor/.linea/.col)
# ======================================================================

# ── programa ──────────────────────────────────────────────────────────

def p_programa(p):
    """programa : instruccion_lista"""
    pass

def p_instruccion_lista_multi(p):
    """instruccion_lista : instruccion_lista instruccion"""
    pass

def p_instruccion_lista_uno(p):
    """instruccion_lista : instruccion"""
    pass

def p_instruccion(p):
    """instruccion : bloque_when
                   | bloque_every
                   | condicional
                   | asignacion_suelta"""
    pass


# ── bloque WHEN ───────────────────────────────────────────────────────
# Se divide en _open + cuerpo + END para poder emitir la cabecera HTML
# ANTES de procesar las acciones del cuerpo (que generan actuadores).

def p_bloque_when_open(p):
    """bloque_when_open : WHEN condicion DO"""
    # p[1]=Token(WHEN), p[2]=(texto,sensores), p[3]=Token(DO)
    texto, sensores = p[2]
    ind = "  "
    _st.emit(f'{ind}<div style="{CSS_SECCION}">')
    _st.emit(f"{ind}  <h2>Cuando: {texto}</h2>")
    for tok_s, tok_op, tok_v in sensores:
        _st.bloque_sensor(tok_s, tok_op, tok_v, ind + "  ")
    _st.push_acum()
    p[0] = ind

def p_bloque_when(p):
    """bloque_when : bloque_when_open cuerpo END"""
    ind = p[1]
    _st.volcar(ind + "  ")
    _st.pop_acum()
    _st.emit(f"{ind}</div>")


# ── bloque EVERY ──────────────────────────────────────────────────────

def p_bloque_every_open(p):
    """bloque_every_open : EVERY TIEMPO DO"""
    # p[2] = Token(TIEMPO) con .valor = "30m"
    tiempo = p[2].valor
    ind    = "  "
    _st.emit(f'{ind}<div style="{CSS_SECCION}">')
    _st.emit(f"{ind}  <h2>Cada: {tiempo}</h2>")
    _st.push_acum()
    p[0] = ind

def p_bloque_every(p):
    """bloque_every : bloque_every_open cuerpo END"""
    ind = p[1]
    _st.volcar(ind + "  ")
    _st.pop_acum()
    _st.emit(f"{ind}</div>")


# ── cuerpo ────────────────────────────────────────────────────────────

def p_cuerpo_multi(p):
    """cuerpo : cuerpo accion"""
    pass

def p_cuerpo_uno(p):
    """cuerpo : accion"""
    pass

def p_accion_asig(p):
    """accion : asignacion"""
    pass

def p_accion_cond(p):
    """accion : condicional_inner"""
    pass


# ── condicional a nivel raíz ──────────────────────────────────────────

def p_if_open(p):
    """if_open : IF condicion THEN"""
    texto, sensores = p[2]
    ind = "  "
    _st.emit(f'{ind}<div style="{CSS_SECCION}">')
    _st.emit(f"{ind}  <h2>Si: {texto}</h2>")
    for tok_s, tok_op, tok_v in sensores:
        _st.bloque_sensor(tok_s, tok_op, tok_v, ind + "  ")
    _st.push_acum()
    p[0] = ind

def p_else_open(p):
    """else_open : ELSE"""
    _st.volcar("    ")
    _st.pop_acum()
    _st.emit("  </div>")
    _st.emit(f'  <div style="{CSS_SECCION}">')
    _st.emit("    <h2>En caso contrario:</h2>")
    _st.push_acum()

def p_condicional_then(p):
    """condicional : if_open cuerpo END"""
    ind = p[1]
    _st.volcar(ind + "  ")
    _st.pop_acum()
    _st.emit(f"{ind}</div>")

def p_condicional_then_else(p):
    """condicional : if_open cuerpo else_open cuerpo END"""
    _st.volcar("    ")
    _st.pop_acum()
    _st.emit("  </div>")


# ── condicional anidado (dentro de cuerpo) ────────────────────────────

def p_if_inner_open(p):
    """if_inner_open : IF condicion THEN"""
    texto, sensores = p[2]
    ind = "    "
    _st.volcar(ind)          # vaciar actuadores pendientes del nivel padre
    _st.emit(f'{ind}<div style="{CSS_SECCION}">')
    _st.emit(f"{ind}  <h3>Si: {texto}</h3>")
    for tok_s, tok_op, tok_v in sensores:
        _st.bloque_sensor(tok_s, tok_op, tok_v, ind + "  ")
    _st.push_acum()
    p[0] = ind

def p_else_inner_open(p):
    """else_inner_open : ELSE"""
    _st.volcar("      ")
    _st.pop_acum()
    _st.emit("    </div>")
    _st.emit(f'    <div style="{CSS_SECCION}">')
    _st.emit("      <h3>En caso contrario:</h3>")
    _st.push_acum()

def p_condicional_inner_then(p):
    """condicional_inner : if_inner_open cuerpo END"""
    ind = p[1]
    _st.volcar(ind + "  ")
    _st.pop_acum()
    _st.emit(f"{ind}</div>")

def p_condicional_inner_then_else(p):
    """condicional_inner : if_inner_open cuerpo else_inner_open cuerpo END"""
    _st.volcar("      ")
    _st.pop_acum()
    _st.emit("    </div>")


# ── asignacion dentro de cuerpo ───────────────────────────────────────

def p_asignacion(p):
    """asignacion : actuador PUNTO attr OP_ASIG valor_asig"""
    # p[1]=Token actuador, p[2]=Token PUNTO, p[3]=Token attr,
    # p[4]=Token OP_ASIG,  p[5]=Token valor
    tok_act, tok_attr, tok_val = p[1], p[3], p[5]
    _st.chk_attr(tok_act, tok_attr, tok_val, es_lectura=False)
    li = _st.html_item(tok_attr, tok_val)
    _st.anotar(tok_act.valor, li)


# ── asignacion a nivel raíz ───────────────────────────────────────────

def p_asignacion_suelta(p):
    """asignacion_suelta : actuador PUNTO attr OP_ASIG valor_asig"""
    tok_act, tok_attr, tok_val = p[1], p[3], p[5]
    _st.chk_attr(tok_act, tok_attr, tok_val, es_lectura=False)
    li = _st.html_item(tok_attr, tok_val)
    _st.emit(f'  <div style="{CSS_ACTUADOR}">')
    _st.emit(f"    <h1>{tok_act.valor}</h1>")
    _st.emit(f"    <ul>")
    _st.emit(f"      {li}")
    _st.emit(f"    </ul>")
    _st.emit(f"  </div>")


# ── condicion ─────────────────────────────────────────────────────────

def p_condicion_and(p):
    """condicion : condicion AND expr_cond"""
    t1, s1 = p[1]; t3, s3 = p[3]
    p[0] = (f"{t1} AND {t3}", s1 + s3)

def p_condicion_or(p):
    """condicion : condicion OR expr_cond"""
    t1, s1 = p[1]; t3, s3 = p[3]
    p[0] = (f"{t1} OR {t3}", s1 + s3)

def p_condicion_simple(p):
    """condicion : expr_cond"""
    p[0] = p[1]

def p_expr_not(p):
    """expr_cond : NOT expr_cond"""
    texto, sens = p[2]
    p[0] = (f"NOT {texto}", sens)

def p_expr_bool(p):
    """expr_cond : TRUE
                 | FALSE
                 | ON
                 | OFF"""
    p[0] = (p[1].valor, [])

def p_expr_sensor(p):
    """expr_cond : sensor op_cmp valor_literal"""
    tok_s, tok_op, tok_v = p[1], p[2], p[3]
    op_txt = _OP_TEXTO.get(tok_op.tipo, tok_op.valor)
    _st.chk_sensor(tok_s, tok_v)
    p[0] = (
        f"{tok_s.valor} {op_txt} {tok_v.valor}",
        [(tok_s, tok_op, tok_v)],   # tripla de Tokens para html_sensor
    )

def p_expr_actuador(p):
    """expr_cond : actuador PUNTO attr op_cmp valor_literal"""
    tok_act, tok_attr, tok_op, tok_val = p[1], p[3], p[4], p[5]
    op_txt = _OP_TEXTO.get(tok_op.tipo, tok_op.valor)
    _st.chk_attr(tok_act, tok_attr, tok_val, es_lectura=True)
    p[0] = (
        f"{tok_act.valor}.{tok_attr.valor} {op_txt} {tok_val.valor}",
        [],
    )


# ── grupos de terminales ──────────────────────────────────────────────

def p_sensor(p):
    """sensor : SENSOR_TEMP
              | SENSOR_HUMEDAD
              | SENSOR_LUZ
              | SENSOR_MOVIMIENTO
              | SENSOR_HUMO"""
    p[0] = p[1]   

def p_actuador(p):
    """actuador : ACT_FOCO
                | ACT_AIRE
                | ACT_PERSIANA
                | ACT_CERRADURA
                | ACT_RELOJ
                | ACT_ALTAVOZ
                | ACT_ALARMA"""
    p[0] = p[1]

def p_attr(p):
    """attr : ATTR_ESTADO
            | ATTR_BRILLO
            | ATTR_COLOR
            | ATTR_MODO
            | ATTR_TEMP_OBJ
            | ATTR_TEMP_ACT
            | ATTR_POSICION
            | ATTR_HORA
            | ATTR_FECHA
            | ATTR_VOLUMEN
            | ATTR_MUTE
            | ATTR_MENSAJE
            | ATTR_EMAIL_NOTIF
            | ATTR_ACTIVADA
            | ATTR_GENERICO"""
    p[0] = p[1]

def p_op_cmp(p):
    """op_cmp : OP_EQ
              | OP_NEQ
              | OP_GT
              | OP_LT
              | OP_GTE
              | OP_LTE"""
    p[0] = p[1]

def p_valor_asig(p):
    """valor_asig : TEMPERATURA
                  | PORCENTAJE
                  | ILUMINANCIA
                  | TIEMPO
                  | HORA
                  | FECHA
                  | EMAIL
                  | CADENA
                  | ON
                  | OFF
                  | TRUE
                  | FALSE
                  | FRIO
                  | CALOR
                  | VENT
                  | BLANCO
                  | ROJO
                  | AZUL
                  | ENTERO
                  | FLOTANTE
                  | IDENTIFICADOR"""
    p[0] = p[1]

def p_valor_literal(p):
    """valor_literal : TEMPERATURA
                     | PORCENTAJE
                     | ILUMINANCIA
                     | TIEMPO
                     | HORA
                     | FECHA
                     | ON
                     | OFF
                     | TRUE
                     | FALSE
                     | FRIO
                     | CALOR
                     | VENT
                     | BLANCO
                     | ROJO
                     | AZUL
                     | ENTERO
                     | FLOTANTE
                     | IDENTIFICADOR"""
    p[0] = p[1]


# ── error ─────────────────────────────────────────────────────────────

def p_error(p):
    """
    Manejador de errores sintácticos de PLY.

    IMPORTANTE: a diferencia de las reglas de gramática normales
    (donde PLY desempaqueta automáticamente .value y p[i] ya es el
    Token de lexer_v4), en p_error el parámetro `p` es el _PLYToken
    CRUDO tal como lo construyó el LexerAdaptador. Por eso acá hay
    que acceder explícitamente a `p.value` para llegar al Token real
    con sus campos .tipo/.valor/.linea/.col.
    """
    if p is None:
        _st.errores_sint.append(
            "Error sintactico | Fin de archivo inesperado"
        )
    else:
        tok = p.value   # .value es el Token completo de lexer_v4
        _st.errores_sint.append(
            f"Error sintactico | Linea {tok.linea:3d}, Col {tok.col:3d} "
            f"| Token inesperado: '{tok.valor}' [{tok.tipo}]"
        )


# ======================================================================
#  7. CONSTRUIR PARSER PLY
# ======================================================================

_parser = yacc.yacc(debug=False, write_tables=False)


# ======================================================================
#  8. CABECERA Y CIERRE HTML
# ======================================================================

def _cabecera(titulo: str):
    _st.emit("<!DOCTYPE html>")
    _st.emit('<html lang="es">')
    _st.emit("<head>")
    _st.emit('  <meta charset="UTF-8">')
    _st.emit('  <meta name="viewport" content="width=device-width,initial-scale=1.0">')
    _st.emit(f"  <title>Smart Home — {titulo}</title>")
    _st.emit("  <style>")
    _st.emit("    body{font-family:Arial,sans-serif;max-width:900px;"
             "margin:40px auto;padding:0 20px;background:#f9f9f9;color:#222}")
    _st.emit("    h1{color:#333} h2{color:#2a6496} h3{color:#555;font-style:italic}")
    _st.emit("    ul{margin:8px 0;padding-left:20px} li{margin:4px 0}")
    _st.emit("    a{color:#c0392b}")
    _st.emit("  </style>")
    _st.emit("</head>")
    _st.emit("<body>")
    _st.emit(f"  <h1>Dashboard Smart Home — {titulo}</h1>")

def _cierre():
    _st.emit("</body>")
    _st.emit("</html>")


# ======================================================================
#  9. FUNCIÓN PRINCIPAL DE COMPILACIÓN
# ======================================================================

def compilar(fuente: str, nombre_archivo: str):
    """
    Retorna (html, errores_lex, advertencias_lex, errores_sint, errores_sem)
    """
    global _st
    _st = _Estado()
    _st.reset(nombre_archivo)

    # Fase 1: léxico manual
    lexer  = SmartHomeLexer()
    tokens_lex = lexer.tokenizar(fuente)

    # Fase 2: cabecera HTML
    _cabecera(nombre_archivo)

    # Fase 3: parser PLY
    adaptador = LexerAdaptador(tokens_lex)
    _parser.parse(None, lexer=adaptador, tracking=False)

    # Cierre HTML
    _cierre()

    return (
        _st.html(),
        lexer.errores,
        lexer.advertencias,
        _st.errores_sint,
        _st.errores_sem,
    )


# ======================================================================
#  10. MODO ARCHIVO
# ======================================================================

def modo_archivo(ruta: str) -> None:
    if not os.path.exists(ruta):
        print(f"Error: '{ruta}' no existe."); sys.exit(1)
    _, ext = os.path.splitext(ruta)
    if ext.lower() != ".smart":
        print(f"Error: extension incorrecta '{ext}'."); sys.exit(1)

    with open(ruta, "r", encoding="utf-8") as f:
        fuente = f.read()

    nombre = os.path.splitext(os.path.basename(ruta))[0]
    ruta_html = os.path.splitext(ruta)[0] + ".html"
    sep = "=" * 67

    print(sep)
    print("  SMART-HOME Parser PLY + Lexer manual")
    print(f"  Entrada : {ruta}")
    print(f"  Salida  : {ruta_html}")
    print(sep)

    html, err_lex, adv_lex, err_sint, err_sem = compilar(fuente, nombre)

    hay_error = bool(err_lex or adv_lex or err_sint or err_sem)

    if err_lex:
        print(f"\n  [ERRORES LEXICOS: {len(err_lex)}]")
        for e in err_lex: print(f"    {e}")
    if adv_lex:
        print(f"\n  [ADVERTENCIAS DE RANGO: {len(adv_lex)}]")
        for a in adv_lex: print(f"    {a}")
    if err_sint:
        print(f"\n  [ERRORES SINTACTICOS: {len(err_sint)}]")
        for e in err_sint: print(f"    {e}")
    if err_sem:
        print(f"\n  [ERRORES SEMANTICOS: {len(err_sem)}]")
        for e in err_sem: print(f"    {e}")

    print()
    if hay_error:
        print("  ERROR  Analisis fallido — no se genero HTML.")
        sys.exit(2)

    with open(ruta_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  OK  HTML generado en: {ruta_html}")


# ======================================================================
#  11. MODO INTERACTIVO
# ======================================================================

def modo_interactivo():
    print("=" * 67)
    print("  SMART-HOME Parser PLY — Modo Interactivo")
    print("  Linea en blanco para compilar. 'salir' para terminar.")
    print("=" * 67)
    lineas, num = [], 1
    while True:
        try:
            linea = input(f"[{num:3d}] >>> ")
        except (EOFError, KeyboardInterrupt):
            break
        if linea.strip().lower() in ("salir", "exit"): break
        if linea.strip() == "" and lineas:
            fuente = "\n".join(lineas)
            html, el, al, es, esem = compilar(fuente, "interactivo")
            print("\n--- RESULTADO ---")
            for e in el:   print(f"  [LEX] {e}")
            for a in al:   print(f"  [AVS] {a}")
            for e in es:   print(f"  [SIN] {e}")
            for e in esem: print(f"  [SEM] {e}")
            if not el and not al and not es and not esem:
                print("  OK  Sin errores.\n--- HTML ---")
                print(html)
            lineas, num = [], 1; print()
        else:
            lineas.append(linea); num += 1


# ======================================================================
#  12. PUNTO DE ENTRADA
# ======================================================================

def seleccionar_archivo_gui() -> Optional[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None
    root = tk.Tk(); root.withdraw(); root.lift(); root.focus_force()
    ruta = filedialog.askopenfilename(
        title="SMART-HOME — Seleccionar archivo",
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
        print("Uso: python parser_ply.py [archivo.smart | --interactivo]")
        sys.exit(1)

if __name__ == "__main__":
    # ==================================================================
    #  13. EJECUCION COMO .EXE (doble clic)
    # ==================================================================
    # Cuando este script se empaqueta con PyInstaller y el usuario lo
    # ejecuta con doble clic, la consola se abre y se cierra sola apenas
    # termina, sin dar tiempo a leer los errores. Con sys.exit() ademas
    # se dispararia un traceback feo en una consola que ya se cerro.
    # Por eso envolvemos main() en un try/except y agregamos un input()
    # al final para que la ventana quede abierta hasta que el usuario
    # presione ENTER.
    try:
        main()
    except SystemExit:
        pass  # sys.exit(1) / sys.exit(2) ya imprimieron su mensaje
    except Exception as e:
        print(f"\n  ERROR INESPERADO: {e}")
    finally:
        input("\nPresione ENTER para salir...")