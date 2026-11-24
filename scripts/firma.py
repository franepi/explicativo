"""Opcional: marca visible y/o texto escondido en el espectrograma del audio.

Uso:
  python firma.py entrada.mp4 salida.mp4 --texto "MiMarca" [--sin-visible] [--sin-espectro]
       [--t0 6] [--dur 8] [--f0 14000] [--f1 17000] [--nivel -34] [--vb 3000k]
Verificar:
  ffmpeg -i salida.mp4 -lavfi "showspectrumpic=s=1200x500:fscale=lin:start=10000:stop=20000" espectro.png
No uses firmas personales en contenido que deba ser anónimo.
"""
import argparse, os, subprocess, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.io import wavfile

SR = 48000
FUENTES = ["C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"]


def fuente(size):
    for f in FUENTES:
        if os.path.exists(f): return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def png_marca(texto, path, w, h, alpha=95):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im); f = fuente(int(w * 0.11))
    d.text((w / 2 + 4, h / 2 + 4), texto, font=f, fill=(0, 0, 0, int(alpha * 0.6)), anchor="mm")
    d.text((w / 2, h / 2), texto, font=f, fill=(255, 255, 255, alpha), anchor="mm"); im.save(path)


def senal_espectro(texto, n, t0, dur, f0, f1, nivel_db, filas=48):
    f = fuente(filas); w = int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(texto, font=f)) + 8
    im = Image.new("L", (w, filas + 12), 0); ImageDraw.Draw(im).text((4, 2), texto, font=f, fill=255)
    a = np.asarray(im, np.float32)[::-1] / 255.0                 # fila 0 = frecuencia más grave
    R, C = a.shape; L = int(dur * SR); t = np.arange(L) / SR; col = np.linspace(0, C - 1, L)
    rng = np.random.default_rng(1); sig = np.zeros(L)
    for r, fr in enumerate(np.linspace(f0, f1, R)):
        env = np.interp(col, np.arange(C), a[r])
        if env.max() > 0.05: sig += env * np.sin(2 * np.pi * fr * t + rng.uniform(0, 6.28))
    sig *= np.minimum(1, np.minimum(t, dur - t) / 0.05); sig /= np.abs(sig).max() + 1e-9; sig *= 10 ** (nivel_db / 20)
    out = np.zeros(n, np.float32); i0 = int(t0 * SR); m = max(0, min(L, n - i0)); out[i0:i0 + m] = sig[:m]
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("--texto", required=True)
    ap.add_argument("--sin-visible", action="store_true"); ap.add_argument("--sin-espectro", action="store_true")
    ap.add_argument("--t0", type=float, default=6); ap.add_argument("--dur", type=float, default=8)
    ap.add_argument("--f0", type=float, default=14000); ap.add_argument("--f1", type=float, default=17000)
    ap.add_argument("--nivel", type=float, default=-34); ap.add_argument("--vb", default="3000k")
    a = ap.parse_args(); tmp = tempfile.mkdtemp()
    w, h = map(int, subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                                    "-of", "csv=p=0", a.src], capture_output=True, text=True).stdout.strip().split(","))
    wav = os.path.join(tmp, "a.wav")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", a.src, "-vn", "-ac", "2", "-ar", str(SR), wav], check=True)
    _, x = wavfile.read(wav); x = x.astype(np.float32) / 32768
    if not a.sin_espectro:
        x = np.clip(x + senal_espectro(a.texto, len(x), a.t0, a.dur, a.f0, a.f1, a.nivel)[:, None], -1, 1)
    wavfile.write(wav, SR, (x * 32767).astype(np.int16))
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", a.src, "-i", wav]
    if a.sin_visible:
        cmd += ["-map", "0:v", "-map", "1:a", "-c:v", "copy"]
    else:
        png = os.path.join(tmp, "m.png"); png_marca(a.texto, png, w, h)
        cmd += ["-i", png, "-filter_complex", "[0:v][2:v]overlay=0:0[v]", "-map", "[v]", "-map", "1:a",
                "-c:v", "libx264", "-preset", "slow", "-b:v", a.vb, "-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "aac", "-b:a", "256k", "-ar", str(SR), "-movflags", "+faststart", a.dst]
    subprocess.run(cmd, check=True); print("OK:", a.dst)


if __name__ == "__main__":
    main()
