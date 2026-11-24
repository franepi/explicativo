"""Une la voz por líneas y crea timeline.json con tiempos de línea y de palabra.

El texto de cada palabra es SIEMPRE el del guion; whisper solo aporta los tiempos.

Uso:
  python timeline.py --voz voz/ --guion guion_lineas.txt --out trabajo/
       [--pausa 0.08] [--pausa-extra "6:0.3,11:0.3"] [--lufs -16] [--modelo small] [--solo-transcribir]

Entrada:  voz/01.wav, 02.wav … (un archivo por línea, mismo orden que guion_lineas.txt)
Salida:   trabajo/voz.wav (48 kHz estéreo, normalizada) y trabajo/timeline.json
          {"duration": s, "fps": 30, "lines": [{"i": 1, "text": "...", "t0": s, "t1": s,
                                                  "words": [["palabra", ini, fin], ...]}]}
"""
import argparse, difflib, glob, json, os, re, subprocess, sys, unicodedata
import numpy as np
from scipy.io import wavfile

SR = 48000


def decode(path, sr=SR):
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
                       stdout=subprocess.PIPE, check=True)
    return np.frombuffer(r.stdout, np.float32).copy()


def norm(w):
    w = unicodedata.normalize("NFD", w.lower())
    return "".join(c for c in w if unicodedata.category(c) != "Mn" and c.isalnum())


def trim_lead(x, thr=0.01, keep=0.03):
    idx = np.argmax(np.abs(x) > thr) if np.any(np.abs(x) > thr) else 0
    return x[max(0, idx - int(keep * SR)):]


def whisper_words(model, audio16):
    segs, _ = model.transcribe(audio16, word_timestamps=True, language=None)
    out = []
    for s in segs:
        for w in (s.words or []):
            out.append((w.word.strip(), float(w.start), float(w.end)))
    return out


def align(script_words, asr_words, t0, t1):
    """Empareja palabras del guion con las de whisper; interpola las que no casan."""
    a = [norm(w) for w in script_words]; b = [norm(w) for w, _, _ in asr_words]
    times = [None] * len(a)
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            _, s, e = asr_words[blk.b + k]; times[blk.a + k] = (s, e)
    # interpolación por longitud de caracteres para huecos
    weights = [max(1, len(w)) for w in script_words]
    i = 0
    while i < len(a):
        if times[i] is not None: i += 1; continue
        j = i
        while j < len(a) and times[j] is None: j += 1
        start = times[i - 1][1] if i > 0 else t0
        end = times[j][0] if j < len(a) else t1
        tot = sum(weights[i:j]); cur = start
        for k in range(i, j):
            d = (end - start) * weights[k] / tot; times[k] = (cur, cur + d); cur += d
        i = j
    return [[w, round(s, 3), round(e, 3)] for w, (s, e) in zip(script_words, times)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voz", required=True); ap.add_argument("--guion", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--pausa", type=float, default=0.08); ap.add_argument("--pausa-extra", default="")
    ap.add_argument("--lufs", type=float, default=-16); ap.add_argument("--modelo", default="small")
    ap.add_argument("--cola", type=float, default=1.0); ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--solo-transcribir", action="store_true")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)

    lines = [l.strip() for l in open(a.guion, encoding="utf8") if l.strip()]
    files = sorted(glob.glob(os.path.join(a.voz, "[0-9][0-9]*.wav")))
    if len(files) != len(lines):
        sys.exit(f"Hay {len(files)} archivos de voz y {len(lines)} líneas en el guion: deben coincidir.")
    extra = {int(k): float(v) for k, v in (p.split(":") for p in a.pausa_extra.split(",") if p)}

    from faster_whisper import WhisperModel
    model = WhisperModel(a.modelo, device="cpu", compute_type="int8")

    chunks, meta, t = [], [], 0.0
    for i, (f, text) in enumerate(zip(files, lines), start=1):
        x = decode(f)
        if i == 1: x = trim_lead(x)
        if i > 1:
            gap = a.pausa + extra.get(i, 0.0); chunks.append(np.zeros(int(gap * SR), np.float32)); t += gap
        x16 = decode(f, 16000)
        if i == 1: x16 = trim_lead(x16)
        asr = whisper_words(model, x16)
        if a.solo_transcribir:
            print(f"[{i:02d}] guion : {text}\n     whisper: {' '.join(w for w, _, _ in asr)}")
        dur = len(x) / SR
        words = align(re.findall(r"\S+", text), [(w, s + t, e + t) for w, s, e in asr], t, t + dur)
        meta.append({"i": i, "text": text, "t0": round(t, 3), "t1": round(t + dur, 3), "words": words})
        chunks.append(x); t += dur
    if a.solo_transcribir: return

    v = np.concatenate(chunks + [np.zeros(int(a.cola * SR), np.float32)])
    raw = os.path.join(a.out, "voz_raw.wav"); wavfile.write(raw, SR, (np.clip(v, -1, 1) * 32767).astype(np.int16))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", raw, "-af",
                    f"highpass=f=70,loudnorm=I={a.lufs}:TP=-2:LRA=9", "-ar", str(SR), "-ac", "2",
                    os.path.join(a.out, "voz.wav")], check=True)
    tl = {"duration": round(len(v) / SR, 3), "fps": a.fps, "lines": meta}
    json.dump(tl, open(os.path.join(a.out, "timeline.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(f"OK: {tl['duration']} s, {len(meta)} líneas -> {a.out}")


if __name__ == "__main__":
    main()
