"""Barra de progreso de un render: cuenta los cuadros ya escritos y estima cuánto falta.

Uso:
  python progreso.py --trabajo trabajo/ --frames trabajo/frames_3d-alto [--paso 2] [--seguir]
--seguir  vuelve a dibujar la barra cada 10 s hasta terminar
"""
import argparse, glob, json, os, sys, time


def barra(trabajo, carpeta, paso, ancho=24):
    tl = json.load(open(os.path.join(trabajo, "timeline.json"), encoding="utf8"))
    total = len(range(0, int(round(tl["duration"] * tl.get("fps", 30))), paso))
    fs = sorted(glob.glob(os.path.join(carpeta, "f_*.png")), key=os.path.getmtime); n = len(fs)
    vel = (os.path.getmtime(fs[-1]) - os.path.getmtime(fs[0])) / (n - 1) if n > 1 else 0
    falta = (total - n) * vel; k = n / total if total else 0; llenos = int(ancho * k)
    eta = f"faltan ~{falta / 60:.0f} min" if n < total else "cuadros listos (falta componer ~1-2 min)"
    return f"[{'█' * llenos}{'░' * (ancho - llenos)}] {k * 100:4.0f} %  {n}/{total} cuadros · {vel:.2f} s/cuadro · {eta}", n >= total


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--trabajo", required=True); ap.add_argument("--frames", required=True)
    ap.add_argument("--paso", type=int, default=1); ap.add_argument("--seguir", action="store_true")
    a = ap.parse_args()
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")      # consolas de Windows
    except Exception: pass
    while True:
        txt, listo = barra(a.trabajo, a.frames, a.paso)
        sys.stdout.write("\r" + txt); sys.stdout.flush()
        if not a.seguir or listo: print(); break
        time.sleep(10)
