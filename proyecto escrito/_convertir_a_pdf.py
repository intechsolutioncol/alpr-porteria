"""
Convierte un archivo .md a PDF: primero a HTML con estilo de documento
imprimible, y luego a PDF usando Microsoft Edge en modo headless (ya viene
instalado en Windows, así que no hace falta ninguna herramienta nueva de
pago).

Uso:
    python _convertir_a_pdf.py                         (convierte Proyecto_de_Investigacion.md, el de siempre)
    python _convertir_a_pdf.py ruta\al\archivo.md       (convierte cualquier otro .md)
    python _convertir_a_pdf.py ruta\al\archivo.md "Título del PDF"
"""

import ctypes
import subprocess
import sys
from pathlib import Path

import markdown

CARPETA = Path(__file__).resolve().parent
RUTA_EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

ESTILO = """
<style>
  @page { size: A4; margin: 2.2cm 2cm; }
  body { font-family: Georgia, 'Times New Roman', serif; font-size: 11.5pt; line-height: 1.5; color: #1a1a1a; max-width: 100%; }
  h1 { font-size: 20pt; text-align: center; margin-top: 0; }
  h2 { font-size: 15pt; color: #14532d; border-bottom: 2px solid #14532d; padding-bottom: 4px; margin-top: 2em; page-break-after: avoid; }
  h3 { font-size: 12.5pt; color: #14532d; margin-top: 1.6em; page-break-after: avoid; }
  h4 { font-size: 11.5pt; margin-top: 1.3em; page-break-after: avoid; }
  p, li { text-align: justify; }
  table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 10pt; }
  th, td { border: 1px solid #999; padding: 5px 8px; text-align: left; }
  th { background: #eef4ee; }
  blockquote { background: #fff8e1; border-left: 4px solid #d4a017; margin: 1em 0; padding: 0.6em 1em; font-size: 10.5pt; }
  code { background: #f0f0f0; padding: 1px 4px; border-radius: 3px; font-size: 0.9em; }
  hr { border: none; border-top: 1px solid #ccc; margin: 2em 0; }
  em { color: #333; }
</style>
"""


def _ruta_corta_windows(ruta):
    """
    Convierte una ruta a su forma "8.3" de Windows (sin tildes/ñ ni
    espacios, ej. C:\\Users\\ADMINI~1\\...). Hace falta porque se detectó
    que pasarle a Edge un argumento --print-to-pdf con una ruta que tiene
    una tilde (la carpeta de usuario de este equipo es "Administración")
    hace que Edge termine SIN avisar ningún error y sin generar el PDF —
    mismo tipo de problema que ya se vio con OpenCV en utilidades_imagen.py,
    aquí resuelto igual: evitar pasarle al programa externo una ruta con
    caracteres fuera de ASCII.
    """
    buffer = ctypes.create_unicode_buffer(260)
    resultado = ctypes.windll.kernel32.GetShortPathNameW(str(ruta), buffer, 260)
    if resultado == 0:
        return ruta  # si falla la conversión, se intenta con la ruta original
    return Path(buffer.value)


def convertir(ruta_md, titulo=None, ruta_pdf=None):
    ruta_md = Path(ruta_md)
    if not ruta_md.exists():
        print(f"ERROR: no se encontró '{ruta_md}'.")
        sys.exit(1)

    titulo = titulo or ruta_md.stem.replace("_", " ")
    ruta_pdf = Path(ruta_pdf) if ruta_pdf else CARPETA / f"{ruta_md.stem}.pdf"
    ruta_html_temp = CARPETA / f"_temp_{ruta_md.stem}.html"

    texto_md = ruta_md.read_text(encoding="utf-8")
    cuerpo_html = markdown.markdown(texto_md, extensions=["tables", "toc"])

    html_completo = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{titulo}</title>
{ESTILO}
</head>
<body>
{cuerpo_html}
</body>
</html>
"""
    ruta_html_temp.write_text(html_completo, encoding="utf-8")
    print(f"HTML generado: {ruta_html_temp}")

    if not Path(RUTA_EDGE).exists():
        print(f"ERROR: no se encontró Edge en '{RUTA_EDGE}'.")
        sys.exit(1)

    # Ruta corta (sin tildes) tanto para el HTML de entrada como para el PDF
    # de salida — ver _ruta_corta_windows(). La ruta larga (con tilde) sigue
    # apuntando al MISMO archivo en el disco, así que todo lo demás del
    # script puede seguir usando `ruta_pdf` normalmente.
    html_corta = _ruta_corta_windows(ruta_html_temp)
    pdf_carpeta_corta = _ruta_corta_windows(ruta_pdf.parent)
    pdf_corta = Path(pdf_carpeta_corta) / ruta_pdf.name

    comando = [
        RUTA_EDGE,
        "--headless",
        "--disable-gpu",
        f"--print-to-pdf={pdf_corta}",
        "--print-to-pdf-no-header",
        "--no-margins",
        Path(html_corta).as_uri(),
    ]
    resultado = subprocess.run(comando, capture_output=True, text=True, timeout=60)

    if ruta_pdf.exists():
        print(f"PDF generado: {ruta_pdf} ({ruta_pdf.stat().st_size // 1024} KB)")
    else:
        print("ERROR: Edge no generó el PDF.")
        print("stdout:", resultado.stdout)
        print("stderr:", resultado.stderr)
        sys.exit(1)

    ruta_html_temp.unlink()  # el HTML era solo un paso intermedio


if __name__ == "__main__":
    args = sys.argv[1:]
    ruta_md_arg = args[0] if args else CARPETA / "Proyecto_de_Investigacion.md"
    titulo_arg = args[1] if len(args) > 1 else None
    convertir(ruta_md_arg, titulo_arg)
