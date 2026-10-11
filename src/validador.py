"""
Validador y corrector de formato de placa (Semana 4).

La idea clave: una placa colombiana NO puede ser cualquier cadena de
caracteres. Si el OCR devuelve "A8C123", sabemos que la segunda posición
debe ser una letra (formato LLLNNN), así que ese "8" casi con seguridad es
una "B". Esta corrección basada en reglas del dominio no requiere entrenar
nada y, según el experimento de la Semana 2 (probar_ocr_sinteticas.py),
suele subir la precisión entre 10 y 20 puntos.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config


def validar_formato(texto):
    """
    Determina a qué formato de placa colombiana corresponde un texto.

    Retorna "carro", "moto" o None si no coincide con ningún formato válido.
    """
    if re.match(config.PATRON_PLACA_CARRO, texto):
        return "carro"
    if re.match(config.PATRON_PLACA_MOTO, texto):
        return "moto"
    return None


def _patron_posiciones(tipo):
    if tipo == "carro":
        return config.POSICIONES_CARRO
    elif tipo == "moto":
        return config.POSICIONES_MOTO
    else:
        raise ValueError(f"Tipo de placa desconocido: '{tipo}' (use 'carro' o 'moto')")


def corregir_por_posicion(texto, tipo=None):
    """
    Corrige caracteres que el OCR probablemente confundió, usando la
    posición esperada (letra o número) según el formato de placa.

    Si `tipo` no se indica, primero se revisa si el texto YA es válido tal
    cual (sin corregir nada) para carro o para moto. Esto importa porque
    los dos formatos son idénticos en las primeras 5 posiciones (LLLNN) y
    solo difieren en la última (N en carro, L en moto): si se intentara
    "corregir como carro" a ciegas, una placa de moto que termina en una
    letra confundible (O, I, S, B, Z) se reinterpretaría como número y
    -aunque el OCR la haya leído bien- quedaría dañada por el propio
    corrector (medido: bajaba la precisión real del pipeline de 94% a 87%
    en pruebas/probar_ocr_sinteticas.py — ver BITACORA_EXPERIMENTOS.md
    sección 6). Si el texto crudo ya es válido para alguno de los dos
    formatos, se confía en él sin tocarlo. Solo si NO es válido para
    ninguno se intenta corregir, probando carro y luego moto.

    Antes de lo anterior, si el texto mide 7 caracteres se intenta primero
    un recorte de longitud: en fotos reales, un tornillo de montaje o el
    marco de la placa a veces se lee como un carácter de más pegado al
    número real (medido: EasyOCR devolvió "IHOP198" en vez de "HOP198",
    con confianza alta —0.84— así que el umbral de baja confianza no lo
    filtra; ver BITACORA_EXPERIMENTOS.md sección 6.3). Si quitar el primer
    o el último carácter deja un formato válido, se usa esa versión.

    Retorna el texto corregido. Si el texto no tiene 6 ni 7 caracteres, se
    devuelve sin cambios (no hay suficiente información para corregir).
    """
    if len(texto) == 7:
        for candidato in (texto[1:], texto[:-1]):
            if validar_formato(candidato) is not None:
                texto = candidato
                break

    if len(texto) != 6:
        return texto

    if tipo is None and validar_formato(texto) is not None:
        return texto

    candidatos = [tipo] if tipo else ["carro", "moto"]
    mejor_resultado = texto

    for candidato in candidatos:
        patron = _patron_posiciones(candidato)
        corregido = []
        for caracter, esperado in zip(texto, patron):
            if esperado == "L" and caracter in config.CONFUSIONES_NUMERO_A_LETRA:
                corregido.append(config.CONFUSIONES_NUMERO_A_LETRA[caracter])
            elif esperado == "N" and caracter in config.CONFUSIONES_LETRA_A_NUMERO:
                corregido.append(config.CONFUSIONES_LETRA_A_NUMERO[caracter])
            else:
                corregido.append(caracter)
        corregido = "".join(corregido)

        # Si esta corrección produce un formato válido, la preferimos.
        if validar_formato(corregido):
            return corregido

        mejor_resultado = corregido  # por si ninguna corrección da un formato 100% válido

    return mejor_resultado


def calcular_confianza(texto, confianza_ocr):
    """
    Combina la confianza que reportó el OCR con si el texto (ya corregido)
    tiene un formato válido de placa colombiana.

    Un texto con formato válido es mucho más probable que sea una placa real
    que uno que "casi" cuadra, así que el formato pesa fuerte en el puntaje
    final: penaliza fuertemente lo que no encaja en ningún formato conocido.
    """
    formato = validar_formato(texto)

    if formato is not None:
        # Formato válido: confiamos principalmente en el OCR, con un pequeño bono.
        return min(1.0, confianza_ocr * 0.9 + 0.1)
    else:
        # Formato inválido: penalización fuerte, aunque el OCR esté "seguro".
        return confianza_ocr * 0.4


if __name__ == "__main__":
    # Casos concretos que demuestran cada tipo de corrección. Sirven como
    # prueba rápida (no reemplazan pruebas unitarias formales, pero uno
    # puede correr este archivo y ver en pantalla que las reglas funcionan).
    casos = [
        # (texto leído por el OCR, tipo a pasar, texto correcto esperado)
        ("A8C123", "carro", "ABC123"),   # 8 en posición de letra -> B
        ("ABC12Z", "moto", "ABC12Z"),    # ya válido para moto, sin cambios
        ("4BC123", "carro", "4BC123"),   # 4 en posición de letra: no está en la tabla, se deja igual
        ("ABC1O3", "carro", "ABC103"),   # O en posición de número -> 0
        ("ABC 123", None, "ABC123"),     # con espacio; sin tipo, ya es válido como carro tal cual
        # Sin conocer el tipo (None): el bug real que se corrigió. Antes del
        # fix, esto se interpretaba primero como carro y la 'S' final se
        # "corregía" a '5', dañando una placa de moto que el OCR había leído
        # bien. Ahora se detecta que ya es válida como moto y se deja intacta.
        ("ABC12S", None, "ABC12S"),
        ("ABC12O", None, "ABC12O"),
        ("ABC12B", None, "ABC12B"),
        # 7 caracteres: caso real medido en fotos (un tornillo de montaje
        # de la placa se leyó como una "I" de más). Se prueba quitar el
        # primer o el último carácter antes de rendirse.
        ("IHOP198", None, "HOP198"),
        ("HOP198I", None, "HOP198"),
    ]

    print("Pruebas de validador.py\n" + "-" * 40)

    for texto_original, tipo, esperado in casos:
        texto_limpio = texto_original.replace(" ", "")
        formato_detectado = validar_formato(texto_limpio)
        corregido = corregir_por_posicion(texto_limpio, tipo)
        confianza = calcular_confianza(corregido, confianza_ocr=0.8)

        print(f"Original: '{texto_original}'")
        print(f"  Formato detectado (antes de corregir): {formato_detectado}")
        print(f"  Corregido: '{corregido}'")
        print(f"  Confianza final: {confianza:.2f}")
        if esperado is not None:
            resultado = "OK" if corregido == esperado else "REVISAR"
            print(f"  Esperado: '{esperado}' -> {resultado}")
        print()

    print("Nota: '4BC123' no cambia porque '4' no está en la tabla de")
    print("confusiones de config.py (CONFUSIONES_NUMERO_A_LETRA). Ajusten esa")
    print("tabla con los resultados reales del experimento de la Semana 2.")
