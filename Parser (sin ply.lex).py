"""
╔══════════════════════════════════════════════════════════════════╗
║   SMART-HOME Parser + Traductor HTML                            ║
║   Sintaxis y Semántica de Lenguajes  —  UTN FRRe  |  2026      ║
╚══════════════════════════════════════════════════════════════════╝

Parser descendente recursivo (LL(1)) construido a mano.
No usa PLY, ANTLR ni ninguna herramienta de análisis sintáctico.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GRAMÁTICA (BNF simplificada)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

programa       ::= instruccion+  EOF

instruccion    ::= bloque_when
               |   bloque_every
               |   condicional
               |   asignacion

bloque_when    ::= WHEN condicion DO cuerpo END

bloque_every   ::= EVERY TIEMPO DO cuerpo END

cuerpo         ::= accion+

accion         ::= asignacion
               |   condicional

condicional    ::= IF condicion THEN cuerpo
                   [ ELSE cuerpo ]
                   END

condicion      ::= expr_cond  ( (AND | OR)  expr_cond )*

expr_cond      ::= NOT expr_cond
               |   SENSOR  op_cmp  valor_literal
               |   ACTUADOR PUNTO ATTR_*  op_cmp  valor_literal
               |   TRUE | FALSE | ON | OFF

op_cmp         ::= OP_EQ | OP_NEQ | OP_GT | OP_LT | OP_GTE | OP_LTE

asignacion     ::= ACTUADOR PUNTO ATTR_*  OP_ASIG  valor_asig

valor_asig     ::= valor_literal
               |   CADENA
               |   EMAIL

valor_literal  ::= TEMPERATURA | PORCENTAJE | ILUMINANCIA
               |   TIEMPO | HORA | FECHA
               |   ON | OFF | TRUE | FALSE
               |   FRIO | CALOR | VENT
               |   BLANCO | ROJO | AZUL
               |   ENTERO | FLOTANTE
               |   IDENTIFICADOR

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRADUCCIÓN A HTML  (sección 5 de la consigna)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

El parser no genera HTML durante el parseo sino que primero
construye un AST liviano (dataclasses) y luego un segundo
pasaje (HtmlEmitter) lo recorre y genera el HTML.

Reglas de traducción:
  • Sensores que aparecen en condiciones → bloque verde
        <div style="border:1px solid green; padding:20px">
          <h2>sensor_luz  250lux</h2>
        </div>

  • Actuadores con sus asignaciones → bloque gris
        <div style="border:1px solid gray; padding:20px">
          <h1>foco_entrada</h1>
          <ul>
            <li>estado: ON</li>
            <li>brillo: 80%</li>
          </ul>
        </div>

  • email_notif → tag <a>
        <a href="mailto:user@dom.ext">Contactar a user</a>

  Los bloques WHEN / EVERY / IF se representan como secciones
  <section> con un <h3> que describe la condición disparadora,
  y dentro se anidan los bloques de sensores y actuadores.
"""

import sys
import os
from dataclasses import dataclass, field
from typing import Optional, List

# Importar el lexer del mismo directorio
sys.path.insert(0, os.path.dirname(__file__))
from LexerFunciona import SmartHomeLexer, Token, TT


# ======================================================================
#  1. NODOS DEL AST
# ======================================================================

@dataclass
class NodoAsignacion:
    """actuador.atributo = valor"""
    actuador:   str        # ej. "foco_entrada"
    attr_tipo:  str        # ej. TT.ATTR_BRILLO
    attr_nombre:str        # ej. "brillo"
    valor_tipo: str        # tipo TT del valor
    valor:      str        # valor crudo del token
    linea:      int

@dataclass
class NodoCondicion:
    """Una comparacion o booleano simple dentro de IF/WHEN"""
    izq_tipo:   str        # TT.SENSOR, TT.ACTUADOR, TT.TRUE, TT.FALSE…
    izq_valor:  str
    izq_attr:   Optional[str]   # nombre del atributo si izq es ACTUADOR
    op:         Optional[str]   # TT.OP_EQ, TT.OP_GT, etc.  (None si es bool puro)
    der_tipo:   Optional[str]
    der_valor:  Optional[str]
    negada:     bool = False

@dataclass
class NodoCondicionCompuesta:
    """condicion AND/OR condicion"""
    izquierda:  object     # NodoCondicion o NodoCondicionCompuesta
    operador:   str        # "AND" | "OR"
    derecha:    object

@dataclass
class NodoCondicional:
    """IF condicion THEN cuerpo [ELSE cuerpo] END"""
    condicion:  object
    then_cuerpo: List
    else_cuerpo: List
    linea:       int

@dataclass
class NodoBloqueWhen:
    """WHEN condicion DO cuerpo END"""
    condicion:  object
    cuerpo:     List
    linea:      int

@dataclass
class NodoBloqueEvery:
    """EVERY tiempo DO cuerpo END"""
    tiempo_valor: str
    cuerpo:       List
    linea:        int

@dataclass
class NodoPrograma:
    instrucciones: List


# ======================================================================
#  2. ERRORES SINTÁCTICOS
# ======================================================================

class ErrorSintactico(Exception):
    def __init__(self, mensaje: str, tok: Token):
        super().__init__(mensaje)
        self.tok = tok

    def __str__(self):
        return (f"Error sintactico | Linea {self.tok.linea:3d}, "
                f"Col {self.tok.col:3d} | {self.args[0]} "
                f"(token: '{self.tok.valor}' [{self.tok.tipo}])")


# ======================================================================
#  3. PARSER DESCENDENTE RECURSIVO
# ======================================================================

# Tipos de token que pueden ser un "valor" (lado derecho de asignacion
# o lado derecho de una comparacion)
TIPOS_VALOR = {
    TT.TEMPERATURA, TT.PORCENTAJE, TT.ILUMINANCIA, TT.TIEMPO,
    TT.HORA, TT.FECHA, TT.EMAIL, TT.CADENA,
    TT.ON, TT.OFF, TT.TRUE, TT.FALSE,
    TT.FRIO, TT.CALOR, TT.VENT,
    TT.BLANCO, TT.ROJO, TT.AZUL,
    TT.ENTERO, TT.FLOTANTE,
    TT.IDENTIFICADOR,
}

TIPOS_OP_CMP = {
    TT.OP_EQ, TT.OP_NEQ, TT.OP_GT, TT.OP_LT, TT.OP_GTE, TT.OP_LTE,
}

TIPOS_ATTR = {
    TT.ATTR_ESTADO, TT.ATTR_BRILLO, TT.ATTR_COLOR,
    TT.ATTR_MODO, TT.ATTR_TEMP_OBJ, TT.ATTR_TEMP_ACT,
    TT.ATTR_POSICION, TT.ATTR_HORA, TT.ATTR_FECHA,
    TT.ATTR_VOLUMEN, TT.ATTR_MUTE, TT.ATTR_MENSAJE,
    TT.ATTR_EMAIL_NOTIF, TT.ATTR_ACTIVADA, TT.ATTR_GENERICO,
}


class Parser:
    """
    Parser LL(1) descendente recursivo para SMART-HOME.

    Uso:
        p = Parser(lista_de_tokens)
        ast = p.parsear()
        # p.errores contiene los errores sintácticos encontrados
    """

    def __init__(self, tokens: List[Token]):
        self._tokens  = [t for t in tokens if t.tipo != TT.EOF]
        self._tokens.append(Token(TT.EOF, "", 0, 0))
        self._pos     = 0
        self.errores:  List[str] = []

    # ── Utilidades básicas ────────────────────────────────────────

    def _actual(self) -> Token:
        return self._tokens[self._pos]

    def _es(self, *tipos) -> bool:
        return self._actual().tipo in tipos

    def _consumir(self, *tipos) -> Token:
        """Consume el token actual si es de uno de los tipos dados."""
        tok = self._actual()
        if tok.tipo not in tipos:
            esperado = " | ".join(tipos)
            raise ErrorSintactico(
                f"Se esperaba {esperado} pero se encontro {tok.tipo}",
                tok,
            )
        self._pos += 1
        return tok

    def _avanzar(self) -> Token:
        """Avanza sin validar tipo."""
        tok = self._actual()
        self._pos += 1
        return tok

    # ── Sincronización ante errores (recuperación de pánico) ──────

    def _sincronizar(self, *tokens_de_seguimiento):
        """
        Descarta tokens hasta encontrar uno del conjunto de seguimiento.
        Permite continuar el parseo tras un error.
        """
        while not self._es(TT.EOF, *tokens_de_seguimiento):
            self._avanzar()

    # ── Punto de entrada ──────────────────────────────────────────

    def parsear(self) -> NodoPrograma:
        instrucciones = []
        while not self._es(TT.EOF):
            try:
                instrucciones.append(self._instruccion())
            except ErrorSintactico as e:
                self.errores.append(str(e))
                # Recuperacion: saltar hasta el proximo inicio de instruccion
                self._sincronizar(
                    TT.WHEN, TT.EVERY, TT.IF, TT.END, TT.EOF
                )
                # Si quedamos en END, consumirlo para no quedar trabados
                if self._es(TT.END):
                    self._avanzar()
        return NodoPrograma(instrucciones)

    # ── instruccion ───────────────────────────────────────────────

    def _instruccion(self):
        if self._es(TT.WHEN):
            return self._bloque_when()
        if self._es(TT.EVERY):
            return self._bloque_every()
        if self._es(TT.IF):
            return self._condicional()
        if self._es(TT.ACTUADOR):
            return self._asignacion()
        tok = self._actual()
        raise ErrorSintactico(
            "Se esperaba WHEN, EVERY, IF o un ACTUADOR para iniciar instruccion",
            tok,
        )

    # ── bloque WHEN ───────────────────────────────────────────────

    def _bloque_when(self) -> NodoBloqueWhen:
        tok_when = self._consumir(TT.WHEN)
        cond     = self._condicion()
        self._consumir(TT.DO)
        cuerpo   = self._cuerpo()
        self._consumir(TT.END)
        return NodoBloqueWhen(cond, cuerpo, tok_when.linea)

    # ── bloque EVERY ──────────────────────────────────────────────

    def _bloque_every(self) -> NodoBloqueEvery:
        tok_every = self._consumir(TT.EVERY)
        tok_tiempo = self._consumir(TT.TIEMPO)
        self._consumir(TT.DO)
        cuerpo    = self._cuerpo()
        self._consumir(TT.END)
        return NodoBloqueEvery(tok_tiempo.valor, cuerpo, tok_every.linea)

    # ── cuerpo (lista de acciones) ────────────────────────────────

    def _cuerpo(self) -> List:
        acciones = []
        while not self._es(TT.END, TT.ELSE, TT.EOF):
            try:
                acciones.append(self._accion())
            except ErrorSintactico as e:
                self.errores.append(str(e))
                self._sincronizar(TT.ACTUADOR, TT.IF, TT.END, TT.ELSE, TT.EOF)
        return acciones

    # ── accion ────────────────────────────────────────────────────

    def _accion(self):
        if self._es(TT.IF):
            return self._condicional()
        if self._es(TT.ACTUADOR):
            return self._asignacion()
        raise ErrorSintactico(
            "Se esperaba IF o ACTUADOR para iniciar una accion",
            self._actual(),
        )

    # ── condicional IF ────────────────────────────────────────────

    def _condicional(self) -> NodoCondicional:
        tok_if = self._consumir(TT.IF)
        cond   = self._condicion()
        self._consumir(TT.THEN)
        then_cuerpo = self._cuerpo()
        else_cuerpo = []
        if self._es(TT.ELSE):
            self._avanzar()
            else_cuerpo = self._cuerpo()
        self._consumir(TT.END)
        return NodoCondicional(cond, then_cuerpo, else_cuerpo, tok_if.linea)

    # ── condicion (puede encadenar AND / OR) ──────────────────────

    def _condicion(self):
        izq = self._expr_cond()
        while self._es(TT.AND, TT.OR):
            op  = self._avanzar().tipo   # "AND" o "OR"
            der = self._expr_cond()
            izq = NodoCondicionCompuesta(izq, op, der)
        return izq

    # ── expresion de condicion simple ────────────────────────────

    def _expr_cond(self):
        # NOT expr_cond
        if self._es(TT.NOT):
            self._avanzar()
            sub = self._expr_cond()
            sub.negada = True
            return sub

        # Booleano puro: TRUE / FALSE / ON / OFF
        if self._es(TT.TRUE, TT.FALSE, TT.ON, TT.OFF):
            tok = self._avanzar()
            return NodoCondicion(tok.tipo, tok.valor, None, None, None, None)

        # SENSOR  op  valor
        if self._es(TT.SENSOR):
            tok_sensor = self._avanzar()
            op         = self._consumir(*TIPOS_OP_CMP)
            tok_val    = self._valor_literal()
            return NodoCondicion(
                TT.SENSOR, tok_sensor.valor, None,
                op.tipo, tok_val.tipo, tok_val.valor,
            )

        # ACTUADOR PUNTO ATTR  op  valor
        if self._es(TT.ACTUADOR):
            tok_act  = self._avanzar()
            self._consumir(TT.PUNTO)
            tok_attr = self._consumir(*TIPOS_ATTR)
            op       = self._consumir(*TIPOS_OP_CMP)
            tok_val  = self._valor_literal()
            return NodoCondicion(
                TT.ACTUADOR, tok_act.valor, tok_attr.valor,
                op.tipo, tok_val.tipo, tok_val.valor,
            )

        raise ErrorSintactico(
            "Condicion invalida: se esperaba SENSOR, ACTUADOR, NOT o booleano",
            self._actual(),
        )

    # ── asignacion ────────────────────────────────────────────────

    def _asignacion(self) -> NodoAsignacion:
        tok_act  = self._consumir(TT.ACTUADOR)
        self._consumir(TT.PUNTO)
        tok_attr = self._consumir(*TIPOS_ATTR)
        self._consumir(TT.OP_ASIG)
        tok_val  = self._valor_asig()
        return NodoAsignacion(
            tok_act.valor,
            tok_attr.tipo,
            tok_attr.valor,
            tok_val.tipo,
            tok_val.valor,
            tok_act.linea,
        )

    # ── valor (lado derecho) ──────────────────────────────────────

    def _valor_asig(self) -> Token:
        """Acepta cualquier literal incluyendo CADENA y EMAIL."""
        if self._es(*TIPOS_VALOR, TT.CADENA, TT.EMAIL):
            return self._avanzar()
        raise ErrorSintactico(
            "Se esperaba un valor (literal, cadena o email)",
            self._actual(),
        )

    def _valor_literal(self) -> Token:
        """Acepta literales (no CADENA/EMAIL, usados en condiciones)."""
        if self._es(*TIPOS_VALOR):
            return self._avanzar()
        raise ErrorSintactico(
            "Se esperaba un valor literal",
            self._actual(),
        )


# ======================================================================
#  4. RECOLECTOR DE CONTEXTO
#     Recorre el AST y agrupa la información que necesita el emisor HTML.
# ======================================================================

@dataclass
class InfoSensor:
    nombre: str
    op:     Optional[str]
    valor:  Optional[str]
    unidad: Optional[str]

@dataclass
class InfoActuador:
    nombre:     str
    atributos:  List[tuple]   # [(attr_nombre, valor_tipo, valor_raw), …]

@dataclass
class InfoSeccion:
    tipo:        str           # "WHEN" | "EVERY" | "IF"
    disparador:  str           # descripcion legible del disparador
    sensores:    List[InfoSensor]
    actuadores:  List[InfoActuador]   # orden de aparicion, sin duplicar nombre
    subsecciones: List         # secciones anidadas (IF dentro de WHEN, etc.)


def _op_a_texto(op: str) -> str:
    return {
        TT.OP_EQ: "==", TT.OP_NEQ: "!=",
        TT.OP_GT: ">",  TT.OP_LT:  "<",
        TT.OP_GTE: ">=", TT.OP_LTE: "<=",
    }.get(op, op)


def _condicion_a_texto(nodo) -> str:
    if isinstance(nodo, NodoCondicionCompuesta):
        return (f"{_condicion_a_texto(nodo.izquierda)} "
                f"{nodo.operador} "
                f"{_condicion_a_texto(nodo.derecha)}")
    if isinstance(nodo, NodoCondicion):
        pfx = "NOT " if nodo.negada else ""
        if nodo.op is None:
            return f"{pfx}{nodo.izq_valor}"
        suj = nodo.izq_valor
        if nodo.izq_attr:
            suj += f".{nodo.izq_attr}"
        return f"{pfx}{suj} {_op_a_texto(nodo.op)} {nodo.der_valor}"
    return "?"


class Recolector:
    """
    Recorre el AST y produce una lista de InfoSeccion lista para renderizar.
    """

    def recolectar(self, programa: NodoPrograma) -> List[InfoSeccion]:
        secciones = []
        for inst in programa.instrucciones:
            s = self._procesar_instruccion(inst)
            if s:
                secciones.append(s)
        return secciones

    def _procesar_instruccion(self, nodo) -> Optional[InfoSeccion]:
        if isinstance(nodo, NodoBloqueWhen):
            return self._seccion_when(nodo)
        if isinstance(nodo, NodoBloqueEvery):
            return self._seccion_every(nodo)
        if isinstance(nodo, NodoCondicional):
            return self._seccion_if(nodo)
        if isinstance(nodo, NodoAsignacion):
            # Asignacion suelta (nivel raiz): crear mini-seccion sin titulo
            sec = InfoSeccion("ASIG", "", [], [], [])
            self._volcar_asignacion(nodo, sec)
            return sec
        return None

    def _seccion_when(self, nodo: NodoBloqueWhen) -> InfoSeccion:
        sec = InfoSeccion(
            "WHEN",
            f"Cuando: {_condicion_a_texto(nodo.condicion)}",
            [], [], [],
        )
        self._extraer_sensores_condicion(nodo.condicion, sec)
        self._procesar_cuerpo(nodo.cuerpo, sec)
        return sec

    def _seccion_every(self, nodo: NodoBloqueEvery) -> InfoSeccion:
        sec = InfoSeccion(
            "EVERY",
            f"Cada: {nodo.tiempo_valor}",
            [], [], [],
        )
        self._procesar_cuerpo(nodo.cuerpo, sec)
        return sec

    def _seccion_if(self, nodo: NodoCondicional) -> InfoSeccion:
        sec = InfoSeccion(
            "IF",
            f"Si: {_condicion_a_texto(nodo.condicion)}",
            [], [], [],
        )
        self._extraer_sensores_condicion(nodo.condicion, sec)
        self._procesar_cuerpo(nodo.then_cuerpo, sec)
        if nodo.else_cuerpo:
            sub = InfoSeccion("ELSE", "En caso contrario:", [], [], [])
            self._procesar_cuerpo(nodo.else_cuerpo, sub)
            sec.subsecciones.append(sub)
        return sec

    def _procesar_cuerpo(self, cuerpo: List, sec: InfoSeccion):
        for accion in cuerpo:
            if isinstance(accion, NodoAsignacion):
                self._volcar_asignacion(accion, sec)
            elif isinstance(accion, NodoCondicional):
                sub = self._seccion_if(accion)
                sec.subsecciones.append(sub)

    def _volcar_asignacion(self, nodo: NodoAsignacion, sec: InfoSeccion):
        """Agrega el atributo al actuador correspondiente (creándolo si no existe)."""
        actuador = self._obtener_actuador(sec, nodo.actuador)
        actuador.atributos.append(
            (nodo.attr_nombre, nodo.valor_tipo, nodo.valor)
        )

    def _obtener_actuador(self, sec: InfoSeccion, nombre: str) -> InfoActuador:
        for a in sec.actuadores:
            if a.nombre == nombre:
                return a
        nuevo = InfoActuador(nombre, [])
        sec.actuadores.append(nuevo)
        return nuevo

    def _extraer_sensores_condicion(self, cond, sec: InfoSeccion):
        """Extrae referencias a sensores de la condicion y las agrega a sec."""
        if isinstance(cond, NodoCondicionCompuesta):
            self._extraer_sensores_condicion(cond.izquierda, sec)
            self._extraer_sensores_condicion(cond.derecha, sec)
        elif isinstance(cond, NodoCondicion):
            if cond.izq_tipo == TT.SENSOR and cond.der_valor:
                # Verificar que no este duplicado
                ya = any(s.nombre == cond.izq_valor for s in sec.sensores)
                if not ya:
                    sec.sensores.append(InfoSensor(
                        cond.izq_valor,
                        cond.op,
                        cond.der_valor,
                        None,
                    ))


# ======================================================================
#  5. EMISOR HTML
# ======================================================================

# Etiquetas legibles para cada tipo de atributo
_LABEL_ATTR = {
    TT.ATTR_ESTADO:      "Estado",
    TT.ATTR_BRILLO:      "Brillo",
    TT.ATTR_COLOR:       "Color",
    TT.ATTR_MODO:        "Modo",
    TT.ATTR_TEMP_OBJ:    "Temperatura objetivo",
    TT.ATTR_TEMP_ACT:    "Temperatura actual",
    TT.ATTR_POSICION:    "Posicion",
    TT.ATTR_HORA:        "Hora",
    TT.ATTR_FECHA:       "Fecha",
    TT.ATTR_VOLUMEN:     "Volumen",
    TT.ATTR_MUTE:        "Mute",
    TT.ATTR_MENSAJE:     "Mensaje",
    TT.ATTR_EMAIL_NOTIF: "Email de notificacion",
    TT.ATTR_ACTIVADA:    "Activada",
    TT.ATTR_GENERICO:    "Atributo",
}

# Nombre legible del sensor
_LABEL_SENSOR = {
    "sensor_temp":       "Temperatura",
    "sensor_humedad":    "Humedad",
    "sensor_luz":        "Iluminancia",
    "sensor_movimiento": "Movimiento detectado",
    "sensor_humo":       "Humo detectado",
}

# Unidad del sensor
_UNIDAD_SENSOR = {
    "sensor_temp":    "°C",
    "sensor_humedad": "%",
    "sensor_luz":     "lux",
}


class HtmlEmitter:
    """
    Recorre la lista de InfoSeccion y genera el documento HTML
    según las reglas de la sección 5 de la consigna.
    """

    ESTILO_SENSOR   = "border:1px solid green; padding:20px; margin:10px 0;"
    ESTILO_ACTUADOR = "border:1px solid gray;  padding:20px; margin:10px 0;"
    ESTILO_SECCION  = "margin:20px 0; padding:10px; border-left:3px solid #4a90d9;"

    def emitir(self, secciones: List[InfoSeccion], titulo: str) -> str:
        lines = []
        lines.append("<!DOCTYPE html>")
        lines.append('<html lang="es">')
        lines.append("<head>")
        lines.append('  <meta charset="UTF-8">')
        lines.append('  <meta name="viewport" content="width=device-width, initial-scale=1.0">')
        lines.append(f"  <title>Smart Home — {titulo}</title>")
        lines.append("  <style>")
        lines.append("    body { font-family: Arial, sans-serif; "
                     "max-width: 900px; margin: 40px auto; padding: 0 20px; "
                     "background: #f9f9f9; color: #222; }")
        lines.append("    h1 { color: #333; }")
        lines.append("    h2 { color: #2a6496; }")
        lines.append("    h3 { color: #555; font-style: italic; }")
        lines.append("    ul { margin: 8px 0; padding-left: 20px; }")
        lines.append("    li { margin: 4px 0; }")
        lines.append("    a  { color: #c0392b; }")
        lines.append("    .seccion { " + self.ESTILO_SECCION + " }")
        lines.append("    .sensor  { " + self.ESTILO_SENSOR   + " }")
        lines.append("    .actuador{ " + self.ESTILO_ACTUADOR  + " }")
        lines.append("  </style>")
        lines.append("</head>")
        lines.append("<body>")
        lines.append(f"  <h1>Dashboard Smart Home — {titulo}</h1>")

        for sec in secciones:
            lines.extend(self._renderizar_seccion(sec, nivel=0))

        lines.append("</body>")
        lines.append("</html>")
        return "\n".join(lines)

    # ── Sección (WHEN / EVERY / IF / ELSE / ASIG) ─────────────────

    def _renderizar_seccion(self, sec: InfoSeccion, nivel: int) -> List[str]:
        indent = "  " * (nivel + 1)
        lines  = []

        if sec.tipo == "ASIG":
            # Asignaciones sueltas sin encabezado de bloque
            for act in sec.actuadores:
                lines.extend(self._renderizar_actuador(act, indent))
            return lines

        lines.append(f'{indent}<div class="seccion">')
        if sec.disparador:
            tag = "h3" if nivel > 0 else "h2"
            lines.append(f"{indent}  <{tag}>{sec.disparador}</{tag}>")

        # Sensores referenciados en la condicion
        for sensor in sec.sensores:
            lines.extend(self._renderizar_sensor(sensor, indent + "  "))

        # Actuadores con sus atributos
        for act in sec.actuadores:
            lines.extend(self._renderizar_actuador(act, indent + "  "))

        # Subsecciones (IF anidados, ELSE)
        for sub in sec.subsecciones:
            lines.extend(self._renderizar_seccion(sub, nivel + 1))

        lines.append(f"{indent}</div>")
        return lines

    # ── Bloque sensor ────────────────────────────────────────────

    def _renderizar_sensor(self, info: InfoSensor, indent: str) -> List[str]:
        label  = _LABEL_SENSOR.get(info.nombre, info.nombre)
        unidad = _UNIDAD_SENSOR.get(info.nombre, "")
        op     = _op_a_texto(info.op) if info.op else ""
        valor  = info.valor or ""
        texto  = f"{label}  {op} {valor}{unidad}".strip()
        return [
            f'{indent}<div class="sensor" style="{self.ESTILO_SENSOR}">',
            f"{indent}  <h2>{texto}</h2>",
            f"{indent}</div>",
        ]

    # ── Bloque actuador ──────────────────────────────────────────

    def _renderizar_actuador(self, info: InfoActuador, indent: str) -> List[str]:
        lines = [
            f'{indent}<div class="actuador" style="{self.ESTILO_ACTUADOR}">',
            f"{indent}  <h1>{info.nombre}</h1>",
            f"{indent}  <ul>",
        ]
        for (attr_nombre, valor_tipo, valor_raw) in info.atributos:
            label = _LABEL_ATTR.get(valor_tipo, attr_nombre)
            # Determinar la etiqueta correcta usando el nombre del atributo
            # (el valor_tipo aquí es el tipo del VALOR, no del atributo;
            #  usamos attr_nombre para el label)
            label_attr = attr_nombre.replace("_", " ").capitalize()
            item_html  = self._renderizar_item(
                label_attr, valor_tipo, valor_raw, indent + "    "
            )
            lines.append(item_html)
        lines.append(f"{indent}  </ul>")
        lines.append(f"{indent}</div>")
        return lines

    def _renderizar_item(
        self, label: str, valor_tipo: str, valor_raw: str, indent: str
    ) -> str:
        """Genera un <li> para un atributo. Los EMAIL se convierten en <a>."""
        if valor_tipo == TT.EMAIL:
            usuario = valor_raw.split("@")[0]
            contenido = (f'<a href="mailto:{valor_raw}">'
                         f'Contactar a {usuario}</a>')
        elif valor_tipo == TT.CADENA:
            # Quitar comillas del token
            contenido = valor_raw.strip('"')
        else:
            contenido = valor_raw

        return f"{indent}<li>{label}: {contenido}</li>"


# ======================================================================
#  6. PIPELINE COMPLETO
# ======================================================================

def compilar(fuente: str, nombre_archivo: str):
    """
    Ejecuta el pipeline completo:
      fuente  → Lexer → tokens
              → Parser → AST
              → Recolector → secciones
              → HtmlEmitter → HTML

    Retorna (html_str, errores_lexicos, advertencias_lexico, errores_sintacticos)
    """
    # ── Fase 1: análisis léxico ───────────────────────────────────
    lexer  = SmartHomeLexer()
    tokens = lexer.tokenizar(fuente)

    # ── Fase 2: análisis sintáctico ───────────────────────────────
    parser = Parser(tokens)
    ast    = parser.parsear()

    # ── Fase 3: recolección de contexto ──────────────────────────
    recolector = Recolector()
    secciones  = recolector.recolectar(ast)

    # ── Fase 4: emisión HTML ──────────────────────────────────────
    emitter = HtmlEmitter()
    html    = emitter.emitir(secciones, nombre_archivo)

    return html, lexer.errores, lexer.advertencias, parser.errores


# ======================================================================
#  7. MODO ARCHIVO (punto de entrada principal)
# ======================================================================

def modo_archivo(ruta_entrada: str) -> None:

    # Validar existencia y extensión
    if not os.path.exists(ruta_entrada):
        print(f"Error de ejecucion | El archivo '{ruta_entrada}' no existe.")
        sys.exit(1)

    _, ext = os.path.splitext(ruta_entrada)
    if ext.lower() != ".smart":
        print(f"Error de ejecucion | Extension incorrecta '{ext}'. "
              f"Se esperaba '.smart'.")
        sys.exit(1)

    # Leer fuente
    with open(ruta_entrada, "r", encoding="utf-8") as f:
        fuente = f.read()

    nombre_base = os.path.splitext(os.path.basename(ruta_entrada))[0]
    ruta_html   = os.path.splitext(ruta_entrada)[0] + ".html"

    sep = "=" * 67
    print(sep)
    print(f"  SMART-HOME Parser + Traductor HTML")
    print(f"  Entrada : {ruta_entrada}")
    print(f"  Salida  : {ruta_html}")
    print(sep)

    # Compilar
    html, err_lex, adv_lex, err_sint = compilar(fuente, nombre_base)

    # Reportar resultados
    hay_errores = bool(err_lex or err_sint)

    if err_lex:
        print(f"\n  [ERRORES LEXICOS: {len(err_lex)}]")
        for e in err_lex:
            print(f"    {e}")

    if adv_lex:
        print(f"\n  [ADVERTENCIAS DE RANGO: {len(adv_lex)}]")
        for a in adv_lex:
            print(f"    {a}")

    if err_sint:
        print(f"\n  [ERRORES SINTACTICOS: {len(err_sint)}]")
        for e in err_sint:
            print(f"    {e}")

    # Escribir HTML siempre (incluso con errores, con lo que se pudo parsear)
    with open(ruta_html, "w", encoding="utf-8") as f:
        f.write(html)

    print()
    if not hay_errores and not adv_lex:
        print(f"  OK  Analisis exitoso. HTML generado en: {ruta_html}")
    elif not hay_errores:
        print(f"  OK  Analisis exitoso (con advertencias). HTML generado en: {ruta_html}")
    else:
        print(f"  PARCIAL  HTML generado con errores en: {ruta_html}")

    if hay_errores:
        sys.exit(2)


# ======================================================================
#  8. MODO INTERACTIVO
# ======================================================================

def modo_interactivo() -> None:
    sep = "=" * 67
    print(sep)
    print("  SMART-HOME Parser  —  Modo Interactivo")
    print("  Escriba instrucciones SMART-HOME.")
    print("  Linea en blanco para terminar el bloque y parsear.")
    print("  'salir' para terminar.")
    print(sep)

    lineas     = []
    num_linea  = 1

    while True:
        try:
            linea = input(f"[{num_linea:3d}] >>> ")
        except (EOFError, KeyboardInterrupt):
            break

        if linea.strip().lower() in ("salir", "exit", "quit"):
            break

        if linea.strip() == "" and lineas:
            fuente = "\n".join(lineas)
            html, err_lex, adv_lex, err_sint = compilar(fuente, "interactivo")

            print("\n--- RESULTADO ---")
            if err_lex:
                for e in err_lex:
                    print(f"  [LEX]  {e}")
            if adv_lex:
                for a in adv_lex:
                    print(f"  [AVS]  {a}")
            if err_sint:
                for e in err_sint:
                    print(f"  [SIN]  {e}")
            if not err_lex and not err_sint:
                print("  OK  Sin errores.")
                print("\n--- HTML GENERADO ---")
                print(html)
            lineas    = []
            num_linea = 1
            print()
        else:
            lineas.append(linea)
            num_linea += 1


# ======================================================================
#  9. SELECTOR DE ARCHIVO (GUI — tkinter)
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
        print("       Instale python3-tk o use:  python parser.py archivo.smart")
        return None

    # Crear ventana raíz invisible (obligatoria para filedialog)
    root = tk.Tk()
    root.withdraw()          # ocultarla — no queremos una ventana vacía
    root.lift()              # traerla al frente del stack de ventanas
    root.focus_force()       # darle el foco para que el diálogo no quede atrás

    ruta = filedialog.askopenfilename(
        title       = "Seleccionar archivo SMART-HOME",
        initialdir  = os.getcwd(),
        filetypes   = [
            ("Archivos SMART-HOME", "*.smart"),
            ("Todos los archivos",  "*.*"),
        ],
    )

    root.destroy()   # liberar la ventana raíz de Tk

    # askopenfilename retorna "" si el usuario cancela
    return ruta if ruta else None


# ======================================================================
#  10. PUNTO DE ENTRADA
# ======================================================================

def main():
    """
    Lógica de inicio del programa.

    Casos posibles:
      • Sin argumentos       → abre el diálogo gráfico para elegir archivo.
                               Si el usuario cancela, cae al modo interactivo.
      • Un argumento (ruta)  → usa esa ruta directamente (útil para scripts
                               o para arrastrar el archivo sobre el .py).
      • '--interactivo'      → fuerza el modo de consola sin GUI.
      • Más de un argumento  → muestra uso y termina.
    """
    if len(sys.argv) == 1:
        # Sin argumentos: intentar GUI primero
        print("Abriendo selector de archivo...")
        ruta = seleccionar_archivo_gui()

        if ruta:
            # El usuario eligió un archivo → procesar
            modo_archivo(ruta)
        else:
            # Canceló el diálogo o tkinter no disponible → modo interactivo
            print("No se seleccionó archivo. Iniciando modo interactivo.\n")
            modo_interactivo()

    elif len(sys.argv) == 2:
        if sys.argv[1] == "--interactivo":
            # Flag explícito para forzar consola
            modo_interactivo()
        else:
            # Ruta pasada directamente por argumento
            modo_archivo(sys.argv[1])

    else:
        print("Uso:")
        print("  python parser.py                   # selector gráfico de archivo")
        print("  python parser.py archivo.smart     # ruta directa")
        print("  python parser.py --interactivo     # modo consola sin GUI")
        sys.exit(1)

if __name__ == "__main__":
    main()