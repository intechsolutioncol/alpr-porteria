"""Verifica que el entorno tenga instaladas todas las librerías del proyecto."""

import sys

print(f"Python: {sys.version.split()[0]}")

errores = []
for lib in ["ultralytics", "easyocr", "cv2", "streamlit", "pandas", "matplotlib", "PIL"]:
    try:
        __import__(lib)
        print(f"OK  - {lib}")
    except ImportError as e:
        print(f"FALLA - {lib}: {e}")
        errores.append(lib)

if errores:
    print(f"\nFaltan por instalar: {', '.join(errores)}")
else:
    print("\nEntorno listo.")
