"""Mezcla voz + sonidos reales (disparados por palabra o por segundo) + música con ducking.

Uso:
  python mezcla.py --trabajo trabajo/ [--sfx sfx.json] [--musica musica.wav] [--musica-db -12] [--lufs -14]

sfx.json: [{"archivo": "sfx/clic.wav", "linea": 1, "palabra": "tocas", "ocurrencia": 1, "desfase": 0.0, "ganancia_db": -6},
           {"archivo": "sfx/motor.wav", "en": 13.2, "ganancia_db": -10, "duracion": 2.0, "reversa": false}]
Salida: trabajo/mezcla.wav
"""
import argparse, json, os, subprocess, unicodedata
import numpy as np
from scipy.io import wavfile

SR = 48000


def load(path):
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                       stdout=subprocess.PIPE, check=True)
    return np.frombuffer(r.stdout, np.float32).reshape(-1, 2).copy()


def norm(w):
    w = unicodedata.normalize("NFD", w.lower())
    return "".join(c for c in w if unicodedata.category(c) != "Mn" and c.isalnum())


def tiempo_palabra(tl, linea, palabra, occ=1):
    k = 0
    for ln in tl["lines"]:
        if ln["i"] != linea: continue
        for w, s, _ in ln["words"]:
            if norm(w).startswith(norm(palabra)):
                k += 1
                if k == occ: return s
    raise KeyError(f"No encontré '{palabra}' en la línea {linea}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trabajo", required=True); ap.add_argument("--sfx"); ap.add_argument("--musica")
    ap.add_argument("--musica-db", type=float, default=-12); ap.add_argument("--musica-sola-db", type=float, default=-7)
    ap.add_argument("--lufs", type=float, default=-14)
    a = ap.parse_args()
    tl = json.load(open(os.path.join(a.trabajo, "timeline.json"), encoding="utf8"))
    voz = load(os.path.join(a.trabajo, "voz.wav")); n = len(voz)
    out = voz.copy()

    if a.sfx:
        for c in json.load(open(a.sfx, encoding="utf8")):
            t = c["en"] if "en" in c else tiempo_palabra(tl, c["linea"], c["palabra"], c.get("ocurrencia", 1))
            t += c.get("desfase", 0.0)
            x = load(c["archivo"])
            if c.get("reversa"): x = x[::-1]
            if "duracion" in c: x = x[: int(c["duracion"] * SR)]
            fade = min(len(x), int(0.03 * SR)); x[-fade:] *= np.linspace(1, 0, fade)[:, None]
            x *= 10 ** (c.get("ganancia_db", -8) / 20)
            i0 = int(max(0, t) * SR); m = min(len(x), n - i0)
            if m > 0: out[i0:i0 + m] += x[:m]

    if a.musica:
        mus = load(a.musica); reps = int(np.ceil(n / len(mus))); mus = np.tile(mus, (reps, 1))[:n]
        # ducking: envolvente de la voz suavizada
        env = np.sqrt(np.convolve(voz.mean(1) ** 2, np.ones(int(0.25 * SR)) / int(0.25 * SR), "same"))
        hablando = np.clip(env / (env.max() * 0.15 + 1e-9), 0, 1)
        g = 10 ** ((a.musica_sola_db + (a.musica_db - a.musica_sola_db) * hablando) / 20)
        mus /= (np.abs(mus).max() + 1e-9); mus *= 0.5
        out += mus * g[:, None]

    tmp = os.path.join(a.trabajo, "mezcla_raw.wav")
    wavfile.write(tmp, SR, (np.clip(out, -1, 1) * 32767).astype(np.int16))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", tmp, "-af", f"loudnorm=I={a.lufs}:TP=-1.5:LRA=11",
                    "-ar", str(SR), os.path.join(a.trabajo, "mezcla.wav")], check=True)
    print("OK:", os.path.join(a.trabajo, "mezcla.wav"))


if __name__ == "__main__":
    main()
