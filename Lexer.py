import ply.lex as lex
import re
import os
import sys
import codecs

# 1. Agregamos WHERE y corregimos nombres
tokens = [
    # Unidades de medida y rangos
    'GRADOS1', 'GRADOS2', 'LUX', 'PORCENTAJE', 'TIEMPO',

    # Palabras reservadas
    'IF', 'THEN', 'WHERE', 'DO', 'EVERY', 'END',
    
    # Tipo de dato
    'BOOL',

    # Sensores 
    'SENSOR_TEMP'
]

t_ignore = ' \t'

def t_GRADOS1(t):
    r'(-10|-[1-9]|[0-9]|[1-4][0-9]|50)°C'
    return t 

def t_GRADOS2(t):
    r'(-10|-[1-9]|[0-9]|[1-2][0-9]|30)°C'
    return t 

def t_TIEMPO(t):
    r'([0-9]s|[1-5][0-9]s|[0-9]m|[1-5][0-9]m)'

def t_LUX(t):
    r'([0-9]|[1-9][0-9]|[1-9][0-9][0-9]|1000)lux'
    return t 

def t_PORCENTAJE(t):
    r'([0-9]|[1-9][0-9]|100)%'
    return t 

def t_IF(t):
    r'IF'
    return t 

def t_THEN(t):
    r'THEN'
    return t 

def t_WHERE(t):
    r'WHERE'
    return t 

def t_DO(t):
    r'DO'
    return t 

def t_EVERY(t):
    r'EVERY'
    return t 

def t_END(t):
    r'END'
    return t 

def t_SENSOR_TEMP(t):
    r'sensor_temp'
    return t 

def t_BOOL(t):
    r'AND|OR' # Quitamos los paréntesis innecesarios si solo querés el texto
    return t 

def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

def t_error(t):         
    print(f"Caracter ilegal: {t.value[0]}")
    t.lexer.skip(1)


# --- Lógica de carga de archivo ---
dir = input('Ingrese la direccion del archivo a analizar: ')
try: 
    fp = codecs.open(dir, "r", "utf-8")
    cadena = fp.read()
    fp.close() 
except FileNotFoundError:
    print(f"No se ha encontrado el archivo: {dir}")
    cadena = ""

# Construcción del lexer
analizador = lex.lex(reflags=re.IGNORECASE) 
analizador.input(cadena)

def main(): 
    while True:
        tok = analizador.token()
        if not tok: break
        print(f'Token: {tok.value:15} Tipo: {tok.type}')

if __name__ == '__main__':
    main()
    input('\nPresione Enter para cerrar...')