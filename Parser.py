"""
╔══════════════════════════════════════════════════════════════════╗
║   SMART-HOME Parser de una sola pasada + Traductor HTML         ║
║   Sintaxis y Semántica de Lenguajes  —  UTN FRRe  |  2026      ║
╚══════════════════════════════════════════════════════════════════╝

Parser descendente recursivo LL(1) que genera HTML directamente
durante el recorrido sintáctico, sin construir un AST intermedio.

Esta técnica se conoce como "traducción dirigida por la sintaxis"
(syntax-directed translation): cada regla gramatical tiene asociada
una acción semántica que emite el HTML correspondiente en el momento
en que esa regla es reconocida.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GRAMÁTICA CON ACCIONES SEMÁNTICAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

programa    ::= { instruccion }  EOF
                { emitir cabecera HTML }   { emitir cierre HTML }

instruccion ::= bloque_when | bloque_every | condicional | asignacion_suelta

bloque_when ::= WHEN condicion DO
                { emitir <div seccion> + <h2>Cuando: …</h2> }
                { emitir sensores de la condicion }
                cuerpo
                END
                { emitir </div> }

bloque_every::= EVERY TIEMPO DO
                { emitir <div seccion> + <h2>Cada: TIEMPO</h2> }
                cuerpo
                END
                { emitir </div> }

cuerpo      ::= { accion }+
                — acumula asignaciones por actuador en un dict
                — al finalizar vuelca cada actuador como <div gray>

accion      ::= asignacion | condicional

condicional ::= IF condicion THEN
                { emitir <div seccion> + <h3>Si: …</h3> }
                { emitir sensores de la condicion }
                cuerpo
                [ ELSE
                  { emitir <div seccion> + <h3>En caso contrario</h3> }
                  cuerpo
                  { emitir </div> }
                ]
                END
                { emitir </div> }

asignacion  ::= ACTUADOR PUNTO ATTR OP_ASIG valor
                { acumular en dict[actuador] → [(attr, valor)] }

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRUCO PARA EL AGRUPAMIENTO EN UNA SOLA PASADA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

El problema: varias asignaciones seguidas del mismo actuador deben
producir UN único <div> con todos sus atributos.

La solución sin AST: cada llamada a _cuerpo() mantiene un dict
local  acumulador  { nombre_actuador: [lineas_html_li] }.
Las asignaciones NO emiten HTML directamente sino que depositan
sus <li> en ese dict. Al llegar al END (o ELSE), _cuerpo() vuelca
el dict emitiendo un <div gray><h1>…</h1><ul>…</ul></div> por cada
actuador, respetando el orden de primera aparición.
"""

import sys
import os
from collections import OrderedDict
from typing import Optional, List

sys.path.insert(0, os.path.dirname(__file__))
from Lexer import SmartHomeLexer, Token, TT


# ======================================================================
#  1. ERROR SINTÁCTICO
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
#  2. CONJUNTOS DE TIPOS (lookahead)
# ======================================================================

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

TIPOS_VALOR = {
    TT.TEMPERATURA, TT.PORCENTAJE, TT.ILUMINANCIA, TT.TIEMPO,
    TT.HORA, TT.FECHA, TT.EMAIL, TT.CADENA,
    TT.ON, TT.OFF, TT.TRUE, TT.FALSE,
    TT.FRIO, TT.CALOR, TT.VENT,
    TT.BLANCO, TT.ROJO, TT.AZUL,
    TT.ENTERO, TT.FLOTANTE,
    TT.IDENTIFICADOR,
}

# Mapa operador TT → símbolo legible
_OP_TEXTO = {
    TT.OP_EQ:  "==", TT.OP_NEQ: "!=",
    TT.OP_GT:  ">",  TT.OP_LT:  "<",
    TT.OP_GTE: ">=", TT.OP_LTE: "<=",
}

# Nombres legibles de sensores para el HTML
_LABEL_SENSOR = {
    "sensor_temp":       "Temperatura",
    "sensor_humedad":    "Humedad",
    "sensor_luz":        "Iluminancia",
    "sensor_movimiento": "Movimiento detectado",
    "sensor_humo":       "Humo detectado",
}
_UNIDAD_SENSOR = {
    "sensor_temp":    "°C",
    "sensor_humedad": "%",
    "sensor_luz":     "lux",
}


# ======================================================================
#  3. PARSER CON TRADUCCIÓN DIRECTA
# ======================================================================

class ParserHTML:
    """
    Parser LL(1) descendente recursivo para SMART-HOME.
    Genera el HTML completo durante el análisis sintáctico,
    sin construir ningún árbol intermedio.

    Uso:
        p = ParserHTML(tokens, titulo="mi_script")
        html = p.parsear()
        # p.errores contiene los errores sintácticos
    """

    # Estilos según la consigna (sección 5)
    _CSS_SENSOR   = "border:1px solid green; padding:20px; margin:10px 0;"
    _CSS_ACTUADOR = "border:1px solid gray;  padding:20px; margin:10px 0;"
    _CSS_SECCION  = ("margin:20px 0; padding:12px 16px; "
                     "border-left:3px solid #4a90d9; background:#f8f9ff;")

    def __init__(self, tokens: List[Token], titulo: str = "Smart Home"):
        # Filtrar EOF intermedios y añadir uno al final
        self._tokens = [t for t in tokens if t.tipo != TT.EOF]
        self._tokens.append(Token(TT.EOF, "", 0, 0))
        self._pos    = 0
        self._titulo = titulo
        self.errores: List[str] = []

        # Buffer de salida HTML — se construye línea a línea
        self._out: List[str] = []

    # ──────────────────────────────────────────────────────────────
    #  Utilidades de cursor
    # ──────────────────────────────────────────────────────────────

    def _actual(self) -> Token:
        return self._tokens[self._pos]

    def _es(self, *tipos) -> bool:
        return self._actual().tipo in tipos

    def _consumir(self, *tipos) -> Token:
        """Verifica el tipo, avanza y retorna el token consumido."""
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

    def _sincronizar(self, *tipos_seguimiento):
        """Recuperación de pánico: descarta tokens hasta el próximo punto seguro."""
        while not self._es(TT.EOF, *tipos_seguimiento):
            self._avanzar()

    # ──────────────────────────────────────────────────────────────
    #  Utilidades de emisión HTML
    # ──────────────────────────────────────────────────────────────

    def _emit(self, linea: str):
        """Agrega una línea al buffer de salida."""
        self._out.append(linea)

    def _html_sensor(self, nombre: str, op: str, valor: str, ind: str):
        """
        Emite el bloque HTML de un sensor con borde verde.
        Acción semántica asociada a la regla expr_cond cuando
        el lado izquierdo es un SENSOR.
        """
        label  = _LABEL_SENSOR.get(nombre, nombre)
        unidad = _UNIDAD_SENSOR.get(nombre, "")
        op_txt = _OP_TEXTO.get(op, op) if op else ""
        texto  = f"{label}  {op_txt} {valor}{unidad}".strip()
        self._emit(f'{ind}<div style="{self._CSS_SENSOR}">')
        self._emit(f"{ind}  <h2>{texto}</h2>")
        self._emit(f"{ind}</div>")

    def _html_actuador(self, nombre: str, items: List[str], ind: str):
        """
        Emite el bloque HTML completo de un actuador con borde gris.
        Recibe la lista de <li> ya construidos y los vuelca de una vez.
        Acción semántica llamada al cerrar un cuerpo (END / ELSE).
        """
        self._emit(f'{ind}<div style="{self._CSS_ACTUADOR}">')
        self._emit(f"{ind}  <h1>{nombre}</h1>")
        self._emit(f"{ind}  <ul>")
        for li in items:
            self._emit(f"{ind}    {li}")
        self._emit(f"{ind}  </ul>")
        self._emit(f"{ind}</div>")

    def _html_item(self, attr_nombre: str, valor_tipo: str, valor_raw: str) -> str:
        """
        Construye el string <li> para un atributo.
        Si el valor es EMAIL genera un <a href="mailto:…">.
        Si es CADENA elimina las comillas del token.
        Retorna el string sin emitirlo aún (se acumula en el dict).
        """
        label = attr_nombre.replace("_", " ").capitalize()

        if valor_tipo == TT.EMAIL:
            usuario   = valor_raw.split("@")[0]
            contenido = (f'<a href="mailto:{valor_raw}">'
                         f'Contactar a {usuario}</a>')
        elif valor_tipo == TT.CADENA:
            contenido = valor_raw.strip('"')
        else:
            contenido = valor_raw

        return f"<li>{label}: {contenido}</li>"

    def _volcar_actuadores(self, acumulador: "OrderedDict[str, List[str]]", ind: str):
        """
        Emite los bloques HTML de todos los actuadores acumulados
        en el dict del cuerpo actual y lo limpia.
        Se llama justo antes de cerrar un bloque (END / ELSE).
        """
        for nombre, items in acumulador.items():
            self._html_actuador(nombre, items, ind)
        acumulador.clear()

    # ──────────────────────────────────────────────────────────────
    #  Punto de entrada
    # ──────────────────────────────────────────────────────────────

    def parsear(self) -> str:
        """
        Inicia el análisis. Emite la cabecera HTML, parsea el
        programa completo y emite el cierre. Retorna el HTML como str.
        """
        self._emitir_cabecera()

        while not self._es(TT.EOF):
            try:
                self._instruccion(nivel=0)
            except ErrorSintactico as e:
                self.errores.append(str(e))
                self._sincronizar(TT.WHEN, TT.EVERY, TT.IF, TT.END, TT.EOF)
                if self._es(TT.END):
                    self._avanzar()

        self._emitir_cierre()
        return "\n".join(self._out)

    # ──────────────────────────────────────────────────────────────
    #  Cabecera y cierre del documento HTML
    # ──────────────────────────────────────────────────────────────

    def _emitir_cabecera(self):
        t = self._titulo
        self._emit("<!DOCTYPE html>")
        self._emit('<html lang="es">')
        self._emit("<head>")
        self._emit('  <meta charset="UTF-8">')
        self._emit('  <meta name="viewport" content="width=device-width, initial-scale=1.0">')
        self._emit(f"  <title>Smart Home — {t}</title>")
        self._emit("  <style>")
        self._emit("    body { font-family: Arial, sans-serif; max-width: 900px; "
                   "margin: 40px auto; padding: 0 20px; background:#f9f9f9; color:#222; }")
        self._emit("    h1 { color: #333; } h2 { color: #2a6496; } "
                   "h3 { color: #555; font-style: italic; }")
        self._emit("    ul { margin: 8px 0; padding-left: 20px; } li { margin: 4px 0; }")
        self._emit("    a  { color: #c0392b; }")
        self._emit("  </style>")
        self._emit("</head>")
        self._emit("<body>")
        self._emit(f'  <h1>Dashboard Smart Home — {t}</h1>')

    def _emitir_cierre(self):
        self._emit("</body>")
        self._emit("</html>")

    # ──────────────────────────────────────────────────────────────
    #  instruccion
    # ──────────────────────────────────────────────────────────────

    def _instruccion(self, nivel: int):
        """
        instruccion ::= bloque_when | bloque_every | condicional | asignacion_suelta
        Despacha según el token actual (lookahead de 1).
        """
        if self._es(TT.WHEN):
            self._bloque_when(nivel)
        elif self._es(TT.EVERY):
            self._bloque_every(nivel)
        elif self._es(TT.IF):
            self._condicional(nivel)
        elif self._es(TT.ACTUADOR):
            # Asignación suelta en nivel raíz: bloque actuador sin sección padre
            acum = OrderedDict()
            self._asignacion(acum)
            self._volcar_actuadores(acum, ind="  ")
        else:
            raise ErrorSintactico(
                "Se esperaba WHEN, EVERY, IF o ACTUADOR",
                self._actual(),
            )

    # ──────────────────────────────────────────────────────────────
    #  bloque WHEN
    # ──────────────────────────────────────────────────────────────

    def _bloque_when(self, nivel: int):
        """
        bloque_when ::= WHEN condicion DO cuerpo END

        Acción semántica:
          - Al reconocer WHEN: abre <div seccion> y emite <h2>
          - Al reconocer los sensores de la condicion: emite bloques verdes
          - Al reconocer DO: llama a _cuerpo() que acumula y vuelca actuadores
          - Al reconocer END: cierra </div>
        """
        ind = "  " * (nivel + 1)
        self._consumir(TT.WHEN)

        # Parsear la condicion y capturar su texto + sensores mencionados
        texto_cond, sensores = self._condicion()

        self._consumir(TT.DO)

        # ── Acción semántica: abrir sección ──────────────────────
        self._emit(f'{ind}<div style="{self._CSS_SECCION}">')
        self._emit(f"{ind}  <h2>Cuando: {texto_cond}</h2>")

        # Emitir los sensores que aparecen en la condición
        for nombre, op, valor in sensores:
            self._html_sensor(nombre, op, valor, ind + "  ")

        # Parsear y emitir el cuerpo (actuadores)
        self._cuerpo(nivel + 1)

        self._consumir(TT.END)

        # ── Acción semántica: cerrar sección ─────────────────────
        self._emit(f"{ind}</div>")

    # ──────────────────────────────────────────────────────────────
    #  bloque EVERY
    # ──────────────────────────────────────────────────────────────

    def _bloque_every(self, nivel: int):
        """
        bloque_every ::= EVERY TIEMPO DO cuerpo END

        Acción semántica: igual que WHEN pero el disparador es
        el intervalo de tiempo en lugar de una condición.
        """
        ind = "  " * (nivel + 1)
        self._consumir(TT.EVERY)
        tok_tiempo = self._consumir(TT.TIEMPO)
        self._consumir(TT.DO)

        # ── Acción semántica: abrir sección ──────────────────────
        self._emit(f'{ind}<div style="{self._CSS_SECCION}">')
        self._emit(f"{ind}  <h2>Cada: {tok_tiempo.valor}</h2>")

        self._cuerpo(nivel + 1)

        self._consumir(TT.END)

        # ── Acción semántica: cerrar sección ─────────────────────
        self._emit(f"{ind}</div>")

    # ──────────────────────────────────────────────────────────────
    #  cuerpo  ← el núcleo del agrupamiento en una pasada
    # ──────────────────────────────────────────────────────────────

    def _cuerpo(self, nivel: int):
        """
        cuerpo ::= accion+

        Mantiene un OrderedDict local  { nombre_actuador: [items_li] }
        mientras parsea las acciones del bloque.

        Las asignaciones NO emiten HTML directamente; depositan sus
        <li> en el acumulador. Los IF anidados sí emiten HTML (son
        secciones completas) pero primero se vuelcan los actuadores
        pendientes para no mezclar el orden visual.

        Al llegar a END o ELSE (el token que cierra este cuerpo),
        se vuelcan todos los actuadores acumulados como bloques grises.

        Esto es lo que permite agrupar múltiples asignaciones del
        mismo actuador en un solo <div> sin necesitar un AST.
        """
        ind   = "  " * (nivel + 1)
        acum  = OrderedDict()   # { "foco_sala": ["<li>estado: ON</li>", …] }

        while not self._es(TT.END, TT.ELSE, TT.EOF):
            try:
                if self._es(TT.IF):
                    # Antes de entrar al IF, volcar los actuadores acumulados
                    # para que aparezcan ANTES de la subsección IF en el HTML
                    self._volcar_actuadores(acum, ind)
                    self._condicional(nivel)

                elif self._es(TT.ACTUADOR):
                    # Acumular la asignación sin emitir HTML todavía
                    self._asignacion(acum)

                else:
                    raise ErrorSintactico(
                        "Se esperaba IF o ACTUADOR dentro del cuerpo",
                        self._actual(),
                    )
            except ErrorSintactico as e:
                self.errores.append(str(e))
                self._sincronizar(TT.ACTUADOR, TT.IF, TT.END, TT.ELSE, TT.EOF)

        # Al salir del bucle (encontramos END o ELSE):
        # volcar los actuadores que quedaron pendientes
        self._volcar_actuadores(acum, ind)

    # ──────────────────────────────────────────────────────────────
    #  condicional IF
    # ──────────────────────────────────────────────────────────────

    def _condicional(self, nivel: int):
        """
        condicional ::= IF condicion THEN cuerpo [ELSE cuerpo] END

        Acción semántica:
          - Al reconocer IF: abre <div seccion> con <h3>
          - Al reconocer ELSE: cierra el div THEN, abre uno nuevo con <h3>
          - Al reconocer END: cierra el último div
        """
        ind = "  " * (nivel + 1)
        self._consumir(TT.IF)

        texto_cond, sensores = self._condicion()

        self._consumir(TT.THEN)

        # ── Acción semántica: abrir sección THEN ─────────────────
        tag = "h3" if nivel > 0 else "h2"
        self._emit(f'{ind}<div style="{self._CSS_SECCION}">')
        self._emit(f"{ind}  <{tag}>Si: {texto_cond}</{tag}>")

        for nombre, op, valor in sensores:
            self._html_sensor(nombre, op, valor, ind + "  ")

        self._cuerpo(nivel + 1)

        if self._es(TT.ELSE):
            self._avanzar()

            # ── Acción semántica: cerrar THEN, abrir ELSE ─────────
            self._emit(f"{ind}</div>")
            self._emit(f'{ind}<div style="{self._CSS_SECCION}">')
            self._emit(f"{ind}  <{tag}>En caso contrario:</{tag}>")

            self._cuerpo(nivel + 1)

        self._consumir(TT.END)

        # ── Acción semántica: cerrar sección ─────────────────────
        self._emit(f"{ind}</div>")

    # ──────────────────────────────────────────────────────────────
    #  condicion  (retorna texto + lista de sensores mencionados)
    # ──────────────────────────────────────────────────────────────

    def _condicion(self) -> tuple:
        """
        condicion ::= expr_cond ((AND|OR) expr_cond)*

        Retorna:
            (texto_legible: str,  sensores: list[(nombre, op, valor)])

        El texto se usa para el <h2>/<h3> del disparador.
        La lista de sensores se usa para emitir los bloques verdes.
        El HTML NO se emite aquí — se emite en el llamador que ya
        conoce la indentación correcta.
        """
        texto, sensores = self._expr_cond()

        while self._es(TT.AND, TT.OR):
            op_logic = self._avanzar().valor.upper()   # "AND" | "OR"
            texto2, sensores2 = self._expr_cond()
            texto   = f"{texto} {op_logic} {texto2}"
            sensores.extend(sensores2)

        return texto, sensores

    # ──────────────────────────────────────────────────────────────
    #  expresión de condición simple
    # ──────────────────────────────────────────────────────────────

    def _expr_cond(self) -> tuple:
        """
        expr_cond ::= NOT expr_cond
                    | TRUE | FALSE | ON | OFF
                    | SENSOR op_cmp valor_literal
                    | ACTUADOR PUNTO ATTR op_cmp valor_literal

        Retorna (texto_legible, sensores_encontrados).
        No emite HTML — devuelve los datos al llamador.
        """
        # NOT expr_cond
        if self._es(TT.NOT):
            self._avanzar()
            texto, sensores = self._expr_cond()
            return f"NOT {texto}", sensores

        # Booleano puro
        if self._es(TT.TRUE, TT.FALSE, TT.ON, TT.OFF):
            tok = self._avanzar()
            return tok.valor.upper(), []

        # SENSOR op valor
        if self._es(TT.SENSOR):
            tok_s  = self._avanzar()
            tok_op = self._consumir(*TIPOS_OP_CMP)
            tok_v  = self._valor_literal()
            op_txt = _OP_TEXTO.get(tok_op.tipo, tok_op.valor)
            texto  = f"{tok_s.valor} {op_txt} {tok_v.valor}"
            # Registrar el sensor para emitir bloque verde
            sensor = (tok_s.valor, tok_op.tipo, tok_v.valor)
            return texto, [sensor]

        # ACTUADOR PUNTO ATTR op valor
        if self._es(TT.ACTUADOR):
            tok_a  = self._avanzar()
            self._consumir(TT.PUNTO)
            tok_at = self._consumir(*TIPOS_ATTR)
            tok_op = self._consumir(*TIPOS_OP_CMP)
            tok_v  = self._valor_literal()
            op_txt = _OP_TEXTO.get(tok_op.tipo, tok_op.valor)
            texto  = f"{tok_a.valor}.{tok_at.valor} {op_txt} {tok_v.valor}"
            return texto, []   # actuadores en condición no generan bloque verde

        raise ErrorSintactico(
            "Condicion invalida: se esperaba SENSOR, ACTUADOR, NOT o booleano",
            self._actual(),
        )

    # ──────────────────────────────────────────────────────────────
    #  asignacion  (acumula en el dict, NO emite HTML)
    # ──────────────────────────────────────────────────────────────

    def _asignacion(self, acum: "OrderedDict[str, List[str]]"):
        """
        asignacion ::= ACTUADOR PUNTO ATTR OP_ASIG valor_asig

        Acción semántica: en lugar de emitir HTML, construye el
        string <li> y lo deposita en acum[nombre_actuador].
        El HTML del <div> completo se emite luego en _volcar_actuadores().

        Este es el mecanismo central del agrupamiento en una pasada:
        las asignaciones se 'recuerdan' hasta que se cierra el bloque.
        """
        tok_act  = self._consumir(TT.ACTUADOR)
        self._consumir(TT.PUNTO)
        tok_attr = self._consumir(*TIPOS_ATTR)
        self._consumir(TT.OP_ASIG)
        tok_val  = self._valor_asig()

        nombre = tok_act.valor
        li     = self._html_item(tok_attr.valor, tok_val.tipo, tok_val.valor)

        # Inicializar la entrada del actuador si no existe todavía
        if nombre not in acum:
            acum[nombre] = []
        acum[nombre].append(li)

    # ──────────────────────────────────────────────────────────────
    #  valores
    # ──────────────────────────────────────────────────────────────

    def _valor_asig(self) -> Token:
        """Acepta cualquier literal + CADENA + EMAIL (lado derecho de =)."""
        if self._es(*TIPOS_VALOR, TT.CADENA, TT.EMAIL):
            return self._avanzar()
        raise ErrorSintactico(
            "Se esperaba un valor (literal, cadena o email)",
            self._actual(),
        )

    def _valor_literal(self) -> Token:
        """Acepta literales sin CADENA/EMAIL (usado en condiciones)."""
        if self._es(*TIPOS_VALOR):
            return self._avanzar()
        raise ErrorSintactico(
            "Se esperaba un valor literal",
            self._actual(),
        )


# ======================================================================
#  4. FUNCIÓN DE COMPILACIÓN
# ======================================================================

def compilar(fuente: str, nombre_archivo: str):
    """
    Pipeline de dos fases (en lugar de cuatro):

      fuente → Lexer → tokens → ParserHTML → HTML

    Retorna (html_str, errores_lexicos, advertencias_lexicas, errores_sintacticos)
    """
    # Fase 1: análisis léxico
    lexer  = SmartHomeLexer()
    tokens = lexer.tokenizar(fuente)

    # Fase 2: análisis sintáctico + traducción HTML en una sola pasada
    parser = ParserHTML(tokens, titulo=nombre_archivo)
    html   = parser.parsear()

    return html, lexer.errores, lexer.advertencias, parser.errores


# ======================================================================
#  5. MODO ARCHIVO
# ======================================================================

def modo_archivo(ruta_entrada: str) -> None:
    if not os.path.exists(ruta_entrada):
        print(f"Error de ejecucion | El archivo '{ruta_entrada}' no existe.")
        sys.exit(1)

    _, ext = os.path.splitext(ruta_entrada)
    if ext.lower() != ".smart":
        print(f"Error de ejecucion | Extension incorrecta '{ext}'. "
              "Se esperaba '.smart'.")
        sys.exit(1)

    with open(ruta_entrada, "r", encoding="utf-8") as f:
        fuente = f.read()

    nombre_base = os.path.splitext(os.path.basename(ruta_entrada))[0]
    ruta_html   = os.path.splitext(ruta_entrada)[0] + ".html"

    sep = "=" * 67
    print(sep)
    print("  SMART-HOME Parser (una pasada) + Traductor HTML")
    print(f"  Entrada : {ruta_entrada}")
    print(f"  Salida  : {ruta_html}")
    print(sep)

    html, err_lex, adv_lex, err_sint = compilar(fuente, nombre_base)

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
#  6. MODO INTERACTIVO
# ======================================================================

def modo_interactivo() -> None:
    sep = "=" * 67
    print(sep)
    print("  SMART-HOME Parser (una pasada)  —  Modo Interactivo")
    print("  Escriba instrucciones SMART-HOME.")
    print("  Linea en blanco para parsear el bloque ingresado.")
    print("  'salir' para terminar.")
    print(sep)

    lineas    = []
    num_linea = 1

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
            for e in err_lex:   print(f"  [LEX] {e}")
            for a in adv_lex:   print(f"  [AVS] {a}")
            for e in err_sint:  print(f"  [SIN] {e}")
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
#  7. SELECTOR DE ARCHIVO (GUI — tkinter)
# ======================================================================

def seleccionar_archivo_gui() -> Optional[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        print("Error: tkinter no disponible. Use: python parser_una_pasada.py archivo.smart")
        return None

    root = tk.Tk()
    root.withdraw()
    root.lift()
    root.focus_force()

    ruta = filedialog.askopenfilename(
        title      = "Seleccionar archivo SMART-HOME",
        initialdir = os.getcwd(),
        filetypes  = [
            ("Archivos SMART-HOME", "*.smart"),
            ("Todos los archivos",  "*.*"),
        ],
    )
    root.destroy()
    return ruta if ruta else None


# ======================================================================
#  8. PUNTO DE ENTRADA
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
        print("  python parser_una_pasada.py                  # selector grafico")
        print("  python parser_una_pasada.py archivo.smart    # ruta directa")
        print("  python parser_una_pasada.py --interactivo    # modo consola")
        sys.exit(1)

if __name__ == "__main__":
    main()