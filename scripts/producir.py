"""Corre todo el proceso con un nivel de calidad acorde al equipo: voz -> mezcla -> escena -> video final.

Uso:
  python producir.py --detectar                       # mira el equipo y recomienda un nivel
  python producir.py --calidad auto --voz voz/ --guion guion_lineas.txt --textos textos.json \
                     --trabajo trabajo/ --out salida/final.mp4 [--sfx sfx.json] [--musica musica.wav]
                     [--escena-2d mi_escena_2d.py] [--escena-3d mi_escena.py] [--blender RUTA] [--muestra]

Niveles (--calidad 1..6 o su nombre):
  1 2d-lite   PIL, 540x960, imagen a 15 fps         equipos muy modestos (2 núcleos, 4 GB, sin GPU)
  2 2d        PIL, 1080x1920 suavizado, 30 fps      cualquier laptop
  3 3d-bajo   Blender Workbench, 540x960, 15 fps    gráficos integrados
  4 3d-medio  Blender Eevee, 810x1440, 16 muestras  GPU dedicada modesta
  5 3d-alto   Blender Eevee, 1080x1920, 32 muestras GPU con 6 GB o más
  6 ultra     Blender Cycles (trazado de rayos), 256 muestras + denoise   GPU con 8 GB y 24 GB de RAM o más
--muestra renderiza solo 9 cuadros y saca una hoja de contactos (para revisar antes del render completo).
Los subtítulos y títulos siempre salen a 1080x1920 y 30 fps: solo cambia la imagen de fondo.
"""
import argparse, glob, json, os, shutil, subprocess, sys, time

AQUI = os.path.dirname(os.path.abspath(__file__))
NIVELES = {
    1: dict(nombre="2d-lite", escena="2d", pct=50, ss=1, paso=2, whisper="tiny", preset="veryfast"),
    2: dict(nombre="2d", escena="2d", pct=100, ss=2, paso=1, whisper="base", preset="medium"),
    3: dict(nombre="3d-bajo", escena="3d", motor="workbench", pct=50, samples=8, paso=2, whisper="base", preset="medium"),
    4: dict(nombre="3d-medio", escena="3d", motor="eevee", pct=75, samples=16, paso=1, whisper="small", preset="slow"),
    5: dict(nombre="3d-alto", escena="3d", motor="eevee", pct=100, samples=32, paso=1, whisper="small", preset="slow"),
    6: dict(nombre="ultra", escena="3d", motor="cycles", pct=100, samples=256, paso=1, whisper="small", preset="slow"),
}
RUTAS_BLENDER = ["C:/Program Files/Blender Foundation/*/blender.exe", "/Applications/Blender.app/Contents/MacOS/Blender",
                 "/usr/bin/blender", "/snap/bin/blender", os.path.expanduser("~/blender*/blender")]


# ---------------------------------------------------------------- detección del equipo
def ram_gb():
    try:
        if os.name == "nt":
            import ctypes
            class M(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("c", ctypes.c_ulong), ("t", ctypes.c_ulonglong), ("a", ctypes.c_ulonglong),
                            ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong),
                            ("av", ctypes.c_ulonglong), ("e", ctypes.c_ulonglong)]
            m = M(); m.l = ctypes.sizeof(M); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)); return m.t / 2**30
        if sys.platform == "darwin":
            return int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout) / 2**30
        return int(open("/proc/meminfo").readline().split()[1]) / 2**20
    except Exception:
        return 0.0


def gpu_nvidia():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10)
        nombre, mem = r.stdout.strip().splitlines()[0].rsplit(",", 1); return nombre.strip(), int(mem) / 1024
    except Exception:
        return None, 0.0


def buscar_blender(dada=None):
    for c in [dada, os.environ.get("BLENDER"), shutil.which("blender")]:
        if c and os.path.exists(c): return c
    for patron in RUTAS_BLENDER:
        hall = sorted(glob.glob(patron))
        if hall: return hall[-1]
    return None


def detectar(blender=None):
    ram, nucleos = ram_gb(), os.cpu_count() or 1
    gpu, vram = gpu_nvidia(); bl = buscar_blender(blender)
    mac_m = sys.platform == "darwin" and os.uname().machine == "arm64"
    if not bl: nivel = 2 if nucleos >= 4 and ram >= 6 else 1
    elif (gpu and vram >= 8 and ram >= 24) or (mac_m and ram >= 32): nivel = 6
    elif (gpu and vram >= 6 and ram >= 16) or (mac_m and ram >= 16): nivel = 5
    elif gpu or mac_m or ram >= 16: nivel = 4
    else: nivel = 3 if ram >= 6 else 2
    return dict(ram_gb=round(ram, 1), nucleos=nucleos, gpu=gpu or ("Apple Silicon" if mac_m else None), vram_gb=round(vram, 1),
                blender=bl, nivel=nivel, nombre=NIVELES[nivel]["nombre"])


# ---------------------------------------------------------------- ejecución
def correr(cmd, baja=True):
    kw = {}
    if baja and os.name == "nt": kw["creationflags"] = 0x00004000            # BELOW_NORMAL: el equipo sigue usable
    elif baja: kw["preexec_fn"] = lambda: os.nice(10)
    print("  $", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def nivel_de(txt, info):
    if txt == "auto": return info["nivel"]
    if txt.isdigit(): return int(txt)
    for k, v in NIVELES.items():
        if v["nombre"] == txt: return k
    sys.exit(f"Nivel desconocido: {txt}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detectar", action="store_true"); ap.add_argument("--calidad", default="auto")
    ap.add_argument("--voz"); ap.add_argument("--guion"); ap.add_argument("--textos")
    ap.add_argument("--trabajo", default="trabajo"); ap.add_argument("--out", default="salida/final.mp4")
    ap.add_argument("--sfx"); ap.add_argument("--musica"); ap.add_argument("--blender")
    ap.add_argument("--escena-2d", default=os.path.join(AQUI, "escena_2d.py"))
    ap.add_argument("--escena-3d", default=os.path.join(AQUI, "escena_base.py"))
    ap.add_argument("--rehacer-voz", action="store_true"); ap.add_argument("--muestra", action="store_true")
    ap.add_argument("--hilos", type=int, default=0, help="procesos en paralelo para la escena 2D (0 = automático)")
    ap.add_argument("--prioridad-normal", action="store_true")
    a = ap.parse_args(); py = sys.executable; baja = not a.prioridad_normal

    info = detectar(a.blender)
    if a.detectar:
        print(json.dumps(info, ensure_ascii=False, indent=1))
        print(f"\nRecomendado: --calidad {info['nivel']} ({info['nombre']})"); return
    n = nivel_de(a.calidad, info); cfg = NIVELES[n]
    if cfg["escena"] == "3d" and not info["blender"]:
        sys.exit("Este nivel necesita Blender. Instálalo, pasa --blender RUTA o usa --calidad 2d.")
    print(f"== Nivel {n}: {cfg['nombre']}  (equipo: {info['ram_gb']} GB RAM, {info['nucleos']} núcleos, GPU {info['gpu']})")
    os.makedirs(a.trabajo, exist_ok=True); tiempos = {}

    t = time.time()
    if a.rehacer_voz or not os.path.exists(os.path.join(a.trabajo, "timeline.json")):
        if not (a.voz and a.guion): sys.exit("Falta --voz y --guion para crear timeline.json")
        correr([py, os.path.join(AQUI, "timeline.py"), "--voz", a.voz, "--guion", a.guion, "--out", a.trabajo,
                "--modelo", cfg["whisper"]], baja)
    tiempos["voz"] = time.time() - t

    t = time.time()
    cmd = [py, os.path.join(AQUI, "mezcla.py"), "--trabajo", a.trabajo]
    if a.sfx: cmd += ["--sfx", a.sfx]
    if a.musica: cmd += ["--musica", a.musica]
    correr(cmd, baja); tiempos["mezcla"] = time.time() - t

    frames = os.path.join(a.trabajo, f"frames_{cfg['nombre']}"); os.makedirs(frames, exist_ok=True)
    tl = json.load(open(os.path.join(a.trabajo, "timeline.json"), encoding="utf8"))
    nf = int(round(tl["duration"] * tl.get("fps", 30)))
    solo = ",".join(str(int(nf * k / 9)) for k in range(9)) if a.muestra else ""

    t = time.time()
    if cfg["escena"] == "2d":
        base = [py, a.escena_2d, "--trabajo", a.trabajo, "--out", frames, "--pct", cfg["pct"], "--ss", cfg["ss"], "--paso", cfg["paso"]]
        if solo: correr(base + ["--frames", solo], baja)
        else:
            hilos = a.hilos or max(1, min(4, (os.cpu_count() or 2) // 2))
            kw = {"creationflags": 0x00004000} if baja and os.name == "nt" else {}
            ps = [subprocess.Popen([str(c) for c in base + ["--part", f"{i}/{hilos}"]], **kw) for i in range(hilos)]
            if any(p.wait() for p in ps): sys.exit("Falló la escena 2D")
    else:
        cmd = [info["blender"], "-b", "-P", a.escena_3d, "--", "--trabajo", a.trabajo, "--out", frames, "--motor", cfg["motor"],
               "--pct", cfg["pct"], "--samples", cfg["samples"], "--paso", cfg["paso"]]
        correr(cmd + (["--frames", solo] if solo else []), baja)
    tiempos["escena"] = time.time() - t

    t = time.time()
    if a.muestra:
        hoja = os.path.splitext(a.out)[0] + f"_{cfg['nombre']}_hoja.png"
        correr([py, os.path.join(AQUI, "componer.py"), "--trabajo", a.trabajo, "--textos", a.textos, "--frames", frames,
                "--hoja", hoja, "--solo", solo], baja)
    else:
        correr([py, os.path.join(AQUI, "componer.py"), "--trabajo", a.trabajo, "--textos", a.textos, "--frames", frames,
                "--out", a.out, "--preset", cfg["preset"]], baja)
    tiempos["componer"] = time.time() - t

    tiempos = {k: round(v, 1) for k, v in tiempos.items()}; tiempos["total"] = round(sum(tiempos.values()), 1)
    json.dump({"nivel": n, **cfg, "tiempos_s": tiempos, "equipo": info}, open(os.path.join(a.trabajo, f"tiempos_{cfg['nombre']}.json"), "w",
              encoding="utf8"), ensure_ascii=False, indent=1)
    print(f"== Listo ({cfg['nombre']}): " + ", ".join(f"{k} {v} s" for k, v in tiempos.items()))


if __name__ == "__main__":
    main()
