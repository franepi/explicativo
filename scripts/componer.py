"""Composición final: sobre los cuadros renderizados pone títulos, etiquetas y subtítulos palabra por palabra,
destellos en los cambios de escala, y codifica el video (más una versión ligera < 9.5 MB).

Uso:
  python componer.py --trabajo trabajo/ --textos textos.json --out salida/final.mp4
  python componer.py --trabajo trabajo/ --textos textos.json --hoja salida/hoja.png --solo 30,300,900
  [--frames trabajo/frames_2d] [--preset slow|medium|veryfast] [--sin-gpu] [--sin-ligero]
Si faltan cuadros (escena con --paso 2) repite el último: la imagen va a 15 fps pero los subtítulos siguen a 30.

Espera: trabajo/frames/f_0000.png … (1080x1920), trabajo/timeline.json, trabajo/mezcla.wav (o voz.wav)
textos.json:
{
  "titulos":   [{"linea": 1, "texto": "¿YA LA TOMÓ?", "color_palabra": {"TOMÓ": "#FFD23A"}}],
  "etiquetas": [{"desde": 12.0, "hasta": 15.5, "texto": "BOBINA", "ancla": [540, 900], "punta": [700, 780]}],
  "destellos": [7.9, 20.1],
  "colores_subtitulo": {"rojos": "#FF4D4D"},
  "palabras_clave": ["secreto", "cálculo"],
  "fuente": "ruta/opcional/a/fuente-negrita.ttf"
}
"""
import argparse, glob, json, os, shutil, subprocess, unicodedata
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
SUB_Y, TIT_Y = int(H * 0.65), int(H * 0.21)
AMARILLO = "#FFD23A"
FUENTES = ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf",
           "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"]


def fuente(size, ruta=None):
    for f in ([ruta] if ruta else []) + FUENTES:
        if f and os.path.exists(f): return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def norm(w):
    w = unicodedata.normalize("NFD", w.lower())
    return "".join(c for c in w if unicodedata.category(c) != "Mn" and c.isalnum())


def ease(x): x = min(1, max(0, x)); return x * x * (3 - 2 * x)


def texto_borde(d, xy, txt, f, fill, borde=8, anchor="mm"):
    d.text(xy, txt, font=f, fill=fill, anchor=anchor, stroke_width=borde, stroke_fill=(0, 0, 0, 255))


def subtitulo(d, t, tl, cfg):
    colores = {norm(k): v for k, v in cfg.get("colores_subtitulo", {}).items()}
    clave = {norm(k) for k in cfg.get("palabras_clave", [])}
    for ln in tl["lines"]:
        if not (ln["t0"] - 0.05 <= t <= ln["t1"] + 0.25): continue
        ws = ln["words"]; k = max((j for j, (_, s, _) in enumerate(ws) if s <= t + 0.02), default=-1)
        if k < 0: return
        g0 = (k // 3) * 3; grupo = ws[g0:g0 + 3]           # grupos de hasta 3 palabras; se revelan una a una
        f = fuente(86, cfg.get("fuente")); sp = 22
        anchos = [d.textlength(w, font=f) for w, _, _ in grupo]; total = sum(anchos) + sp * (len(grupo) - 1)
        esc = min(1.0, (W * 0.86) / max(total, 1)); f = fuente(int(86 * esc), cfg.get("fuente"))
        anchos = [d.textlength(w, font=f) for w, _, _ in grupo]; total = sum(anchos) + sp * (len(grupo) - 1)
        x = (W - total) / 2
        for j, (w, s, e) in enumerate(grupo):
            if s > t + 0.02: break
            nw = norm(w); col = colores.get(nw) or (AMARILLO if nw in clave or g0 + j == k else "white")
            texto_borde(d, (x, SUB_Y), w, f, col, borde=max(5, int(9 * esc)), anchor="lm"); x += anchos[j] + sp
        return


def titulos(d, t, tl, cfg):
    lineas = {ln["i"]: ln for ln in tl["lines"]}
    for ti in cfg.get("titulos", []):
        ln = lineas.get(ti["linea"])
        if not ln or not (ln["t0"] <= t <= ln["t1"] + 0.3): continue
        a = ease((t - ln["t0"]) / 0.25) * (1 - ease((t - ln["t1"]) / 0.3))
        f = fuente(96, cfg.get("fuente")); partes = ti["texto"].split(" "); sp = 26
        anchos = [d.textlength(p, font=f) for p in partes]; total = sum(anchos) + sp * (len(partes) - 1)
        if total > W * 0.86:
            f = fuente(int(96 * W * 0.86 / total), cfg.get("fuente")); anchos = [d.textlength(p, font=f) for p in partes]
            total = sum(anchos) + sp * (len(partes) - 1)
        x = (W - total) / 2; cmap = ti.get("color_palabra", {})
        for p, an in zip(partes, anchos):
            col = cmap.get(p.strip("¿?¡!,."), "white"); rgb = Image.new("RGB", (1, 1), col).getpixel((0, 0))
            texto_borde(d, (x, TIT_Y), p, f, rgb + (int(255 * a),), borde=8, anchor="lm"); x += an + sp


def etiquetas(d, t, cfg):
    for e in cfg.get("etiquetas", []):
        if not (e["desde"] <= t <= e["hasta"]): continue
        a = int(255 * ease((t - e["desde"]) / 0.25) * (1 - ease((t - e["hasta"] + 0.25) / 0.25)))
        (ax, ay), (px, py) = e["ancla"], e["punta"]
        d.line([(ax, ay), (px, py)], fill=(255, 255, 255, a), width=4); d.ellipse([ax - 9, ay - 9, ax + 9, ay + 9], outline=(255, 255, 255, a), width=4)
        f = fuente(38, cfg.get("fuente")); tw = d.textlength(e["texto"], font=f); pad = 16
        x0 = min(max(px - tw / 2 - pad, W * 0.07), W * 0.93 - tw - 2 * pad); y0 = py - 30
        d.rounded_rectangle([x0, y0, x0 + tw + 2 * pad, y0 + 60], 30, fill=(15, 15, 20, int(a * 0.85)), outline=(255, 255, 255, a), width=3)
        d.text((x0 + pad, y0 + 30), e["texto"], font=f, fill=(255, 255, 255, a), anchor="lm")


def cuadro(path, t, tl, cfg):
    im = Image.open(path).convert("RGB").resize((W, H))
    for td in cfg.get("destellos", []):               # destello blanco en los cambios de escala
        k = 1 - abs(t - td) / 0.12
        if k > 0: im = Image.blend(im, Image.new("RGB", (W, H), "white"), min(1, k) * 0.85)
    capa = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(capa)
    titulos(d, t, tl, cfg); etiquetas(d, t, cfg); subtitulo(d, t, tl, cfg)
    return Image.alpha_composite(im.convert("RGBA"), capa).convert("RGB")


def nvenc_ok():
    """NVENC aparece en la lista aunque no haya tarjeta NVIDIA: hay que probarlo de verdad."""
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "color=s=256x256:d=0.1", "-c:v", "h264_nvenc",
                        "-f", "null", "-"], capture_output=True)
    return r.returncode == 0


def encoder(preset="slow", gpu=True):
    if gpu and nvenc_ok(): return ["-c:v", "h264_nvenc", "-preset", "p6", "-cq", "18"]
    return ["-c:v", "libx264", "-preset", preset, "-crf", "17" if preset == "slow" else "19"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trabajo", required=True); ap.add_argument("--textos", required=True)
    ap.add_argument("--out"); ap.add_argument("--hoja"); ap.add_argument("--solo", default="")
    ap.add_argument("--frames"); ap.add_argument("--preset", default="slow"); ap.add_argument("--sin-gpu", action="store_true")
    ap.add_argument("--sin-ligero", action="store_true")
    a = ap.parse_args()
    tl = json.load(open(os.path.join(a.trabajo, "timeline.json"), encoding="utf8"))
    cfg = json.load(open(a.textos, encoding="utf8")); fps = tl.get("fps", 30)
    frames = sorted(glob.glob(os.path.join(a.frames or os.path.join(a.trabajo, "frames"), "f_*.png")))
    if not frames: raise SystemExit("No hay cuadros f_*.png en la carpeta de cuadros")
    idx = {int(os.path.basename(f)[2:-4]): f for f in frames}

    if a.hoja:
        sel = [int(x) for x in a.solo.split(",") if x] or sorted(idx)[:: max(1, len(idx) // 9)][:9]
        ims = [cuadro(idx[i], i / fps, tl, cfg).resize((270, 480)) for i in sel if i in idx]
        hoja = Image.new("RGB", (270 * min(len(ims), 5), 480 * ((len(ims) + 4) // 5)), "black")
        for k, im in enumerate(ims): hoja.paste(im, ((k % 5) * 270, (k // 5) * 480))
        os.makedirs(os.path.dirname(os.path.abspath(a.hoja)), exist_ok=True); hoja.save(a.hoja); print("Hoja:", a.hoja); return

    audio = os.path.join(a.trabajo, "mezcla.wav")
    if not os.path.exists(audio): audio = os.path.join(a.trabajo, "voz.wav")
    n = int(round(tl["duration"] * fps)); os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-i", audio, "-map", "0:v", "-map", "1:a", *encoder(a.preset, not a.sin_gpu), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k",
           "-shortest", "-movflags", "+faststart", a.out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE); last = None
    for i in range(n):
        f = idx.get(i, last); last = f or last
        if f is None: continue
        p.stdin.write(np.asarray(cuadro(f, i / fps, tl, cfg)).tobytes())
        if i % 300 == 0: print(f"  {i}/{n}")
    p.stdin.close(); p.wait()
    if a.sin_ligero: print("OK:", a.out); return
    dur = tl["duration"]; vb = int(max(400, 9.3 * 8000 / dur - 128))
    ligero = a.out.replace(".mp4", "_ligero.mp4")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", a.out, "-c:v", "libx264", "-preset", a.preset, "-b:v", f"{vb}k",
                    "-maxrate", f"{int(vb * 1.3)}k", "-bufsize", f"{vb * 2}k", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", ligero], check=True)
    print("OK:", a.out, "y", ligero, f"({os.path.getsize(ligero) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
