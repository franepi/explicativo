"""Escena 2D detallada (sin Blender ni GPU) guiada por la voz. Ejemplo incluido: "cómo funciona un microondas".

Uso:
  python escena_2d.py --trabajo trabajo/ --out trabajo/frames [--pct 100] [--ss 2] [--paso 1]
                      [--frames 0,30,60] [--part 0/2]
Lee trabajo/timeline.json. Escribe f_0000.png … (1080x1920 * pct/100). componer.py los lleva a 1080x1920.

--pct   resolución de dibujo (50 = 540x960, más rápido)       --ss    supermuestreo de bordes (2 recomendado)
--paso  dibuja 1 de cada N cuadros; componer.py repite el último (los subtítulos siguen a 30 fps)

Cómo adaptarlo a otro tema:
- Cada SET es una función que dibuja en coordenadas del mundo (y hacia arriba) con su propia unidad: cm, mm, nm…
- TOMAS define la cámara: (set, inicio=(línea, palabra|None), (cx, cy, ancho) inicial, (cx, cy, ancho) final).
- Todo lo que se mueve usa T(linea, "palabra") para quedar sincronizado con la voz.
- Herramientas: degradados (rect_grad), esferas con volumen (esfera), sombras suaves (sombra), brillos (Brillo),
  ondas (onda_en_camino), texto en escena (texto). Fondo SIEMPRE con contexto: un lugar real o un ambiente por escala.
"""
import argparse, json, math, os, random, time, unicodedata
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("--trabajo", default="trabajo"); ap.add_argument("--out")
ap.add_argument("--pct", type=int, default=100); ap.add_argument("--ss", type=int, default=2)
ap.add_argument("--paso", type=int, default=1); ap.add_argument("--frames", default=""); ap.add_argument("--part", default="")
A = ap.parse_args()
TRAB = os.path.abspath(A.trabajo); OUT = os.path.abspath(A.out or os.path.join(TRAB, "frames"))
TL = json.load(open(os.path.join(TRAB, "timeline.json"), encoding="utf8"))
FPS = TL.get("fps", 30); NF = int(round(TL["duration"] * FPS)); DUR = TL["duration"]
W, H = 1080 * A.pct // 100, 1920 * A.pct // 100; SS = max(1, A.ss); WS, HS = W * SS, H * SS
FUENTES = ["C:/Windows/Fonts/seguibl.ttf", "C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"]


def norm(w):
    w = unicodedata.normalize("NFD", w.lower()); return "".join(c for c in w if unicodedata.category(c) != "Mn" and c.isalnum())


def T(linea, palabra=None, occ=1):
    for ln in TL["lines"]:
        if ln["i"] != linea: continue
        if palabra is None: return ln["t0"]
        k = 0
        for w, s, _ in ln["words"]:
            if norm(w).startswith(norm(palabra)):
                k += 1
                if k == occ: return s
    raise KeyError((linea, palabra))


def ease(x): x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)
def lerp(a, b, k): return a + (b - a) * k
def mezcla(c1, c2, k): k = min(1, max(0, k)); return tuple(int(lerp(a, b, k)) for a, b in zip(c1, c2))
def tramo(t, t0, t1): return ease((t - t0) / max(1e-6, t1 - t0))
def ventana(t, t0, t1, f=0.4): return tramo(t, t0, t0 + f) * (1 - tramo(t, t1 - f, t1))


_F = {}
def fuente(px):
    px = max(6, int(px))
    if px not in _F:
        _F[px] = next((ImageFont.truetype(f, px) for f in FUENTES if os.path.exists(f)), None) or ImageFont.load_default()
    return _F[px]


# ---------------------------------------------------------------- cámara 2D
class Cam:
    """Mundo -> pantalla. (cx, cy) centro en unidades del set; 'ancho' = unidades visibles de lado a lado."""
    def __init__(self, cx, cy, ancho): self.cx, self.cy, self.k = cx, cy, WS / ancho
    def p(self, x, y): return (WS / 2 + (x - self.cx) * self.k, HS / 2 - (y - self.cy) * self.k)
    def s(self, v): return v * self.k
    def w(self, v): return max(1, int(round(v * self.k)))
    def rect(self, x0, y0, x1, y1):
        (a, b), (c, d) = self.p(x0, y1), self.p(x1, y0); return [a, b, c, d]
    def visible(self, x0, y0, x1, y1):
        r = self.rect(x0, y0, x1, y1); return r[2] > 0 and r[0] < WS and r[3] > 0 and r[1] < HS


# ---------------------------------------------------------------- herramientas de dibujo
def rect_grad(im, caja, c_arriba, c_abajo, radio=0, horizontal=False):
    """Rectángulo redondeado con degradado. Se recorta a la pantalla: con zoom, una pared de 4 m mide 100 000 px."""
    x0, y0, x1, y1 = [int(round(v)) for v in caja]; w, h = x1 - x0, y1 - y0
    vx0, vy0, vx1, vy1 = max(x0, 0), max(y0, 0), min(x1, im.width), min(y1, im.height)
    if w < 1 or h < 1 or vx1 <= vx0 or vy1 <= vy0: return
    vw, vh = vx1 - vx0, vy1 - vy0
    if horizontal: k = np.linspace((vx0 - x0) / w, (vx1 - x0) / w, vw, dtype=np.float32)[None, :, None]
    else: k = np.linspace((vy0 - y0) / h, (vy1 - y0) / h, vh, dtype=np.float32)[:, None, None]
    a, b = np.array(c_arriba, np.float32), np.array(c_abajo, np.float32)
    capa = Image.fromarray(np.broadcast_to(a * (1 - k) + b * k, (vh, vw, 3)).astype(np.uint8), "RGB")
    m = Image.new("L", (vw, vh), 0)
    ImageDraw.Draw(m).rounded_rectangle([x0 - vx0, y0 - vy0, x1 - vx0 - 1, y1 - vy0 - 1], radius=max(0, int(radio)), fill=255)
    im.paste(capa, (vx0, vy0), m)


_SPR = {}
def esfera(im, centro, r, color, luz=(-0.35, -0.4)):
    """Esfera con volumen (sprite con sombreado, brillo y borde oscuro) escalada al radio en píxeles."""
    r = int(r)
    if r < 2: ImageDraw.Draw(im).ellipse([centro[0] - 2, centro[1] - 2, centro[0] + 2, centro[1] + 2], fill=color); return
    key = color
    if key not in _SPR:
        n = 256; y, x = np.mgrid[-1:1:n * 1j, -1:1:n * 1j]; d = np.sqrt(x * x + y * y)
        z = np.sqrt(np.clip(1 - d * d, 0, 1)); lam = np.clip(0.25 + 0.75 * (-x * 0.45 - y * 0.55 + z * 0.7), 0, 1.2)
        spec = np.clip(1 - np.hypot(x - luz[0], y - luz[1]) / 0.32, 0, 1) ** 2
        rgb = np.array(color, np.float32)[None, None] * lam[..., None] + 255 * 0.85 * spec[..., None]
        rgb = rgb * (0.55 + 0.45 * np.clip((1 - d) * 6, 0, 1))[..., None]
        a = np.clip((1 - d) * n / 2, 0, 1) * 255
        _SPR[key] = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), a]).astype(np.uint8), "RGBA")
    s = _SPR[key].resize((2 * r, 2 * r), Image.BILINEAR)
    im.paste(s, (int(centro[0] - r), int(centro[1] - r)), s)


def sombra(im, caja, radio, fuerza=150):
    x0, y0, x1, y1 = caja; pad = int(radio * 3)
    bx0, by0 = int(min(x0, x1)) - pad, int(min(y0, y1)) - pad; bw, bh = int(abs(x1 - x0)) + 2 * pad, int(abs(y1 - y0)) + 2 * pad
    if bw <= 0 or bh <= 0 or bw > 4 * WS or bh > 4 * HS: return
    m = Image.new("L", (bw, bh), 0); ImageDraw.Draw(m).ellipse([pad, pad, bw - pad, bh - pad], fill=fuerza)
    m = m.filter(ImageFilter.GaussianBlur(max(1, radio))); im.paste((0, 0, 0), (bx0, by0), m)


class Brillo:
    """Capa de luz a 1/4 de resolución: dibuja con d y s(x) (coordenadas de pantalla), se desenfoca y se suma."""
    def __init__(self, im, radio):
        self.im, self.r = im, radio; self.capa = Image.new("RGB", (WS // 4 + 1, HS // 4 + 1)); self.d = ImageDraw.Draw(self.capa)
    def s(self, v): return [c / 4 for c in v] if isinstance(v, (list, tuple)) else v / 4
    def listo(self, fuerza=1.0):
        c = self.capa.filter(ImageFilter.GaussianBlur(max(1, self.r / 4))).resize((WS, HS), Image.BILINEAR)
        if fuerza != 1.0: c = Image.eval(c, lambda v: int(min(255, v * fuerza)))
        self.im.paste(ImageChops.screen(self.im, c))


def texto(d, xy, txt, px, color=(255, 255, 255), borde=0, anchor="mm"):
    d.text(xy, txt, font=fuente(px), fill=color, anchor=anchor, stroke_width=int(borde), stroke_fill=(10, 12, 16))


def onda_en_camino(puntos, t, amp, longitud, vel, crecer=1.0):
    """Puntos de una onda senoidal que viaja a lo largo de una poligonal (en unidades del mundo)."""
    segs = list(zip(puntos[:-1], puntos[1:])); total = sum(math.dist(a, b) for a, b in segs); lim = total * crecer
    out, s0 = [], 0.0
    for a, b in segs:
        L = math.dist(a, b); nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L; n = max(2, int(L / longitud * 24))
        for i in range(n + 1):
            s = s0 + L * i / n
            if s > lim: return out
            u = i / n; y = amp * math.sin(2 * math.pi * (s / longitud) - vel * t)
            out.append((a[0] + (b[0] - a[0]) * u + nx * y, a[1] + (b[1] - a[1]) * u + ny * y))
        s0 += L
    return out


def fondo_radial(c_centro, c_borde, cy=0.45):
    y, x = np.mgrid[0:HS // 4, 0:WS // 4].astype(np.float32)
    r = np.clip(np.sqrt(((x - WS / 8) / (WS / 4)) ** 2 + ((y - HS / 4 * cy) / (HS / 4)) ** 2 * 0.6) / 0.75, 0, 1)[..., None]
    im = np.array(c_centro, np.float32) * (1 - r) + np.array(c_borde, np.float32) * r
    return Image.fromarray(im.astype(np.uint8), "RGB").resize((WS, HS), Image.BICUBIC)


# ================================================================ EJEMPLO: MICROONDAS
# Unidades: A = cm (cocina y horno) · B y B2 = mm (magnetrón de lado y desde arriba) · C = nm (moléculas de agua)
TOMAS = [
    ("A", (1, None), (0, 4, 82), (-7, -1, 50)),
    ("A", (2, None), (-9, -5, 26), (-10, -7, 18)),
    ("A", (3, None), (13, 1, 46), (17, 2, 30)),
    ("B", (4, None), (0, 0, 26), (0, 0.5, 21)),
    ("B2", (5, None), (0, 0, 13), (0, 0, 10)),
    ("B", (6, None), (0, 7, 16), (0, 10, 24)),
    ("A", (7, None), (-1, 1, 64), (-3, 1, 56)),
    ("C", (8, None), (0, 0, 5.5), (0, 0, 4.6)),
    ("C", (9, None), (0, 0, 13), (0, 0, 17)),
    ("C", (10, None), (0, 0, 17), (0, 0, 11)),
    ("A", (11, None), (-7, -6, 24), (-8, -7, 18)),
    ("A", (12, None), (-9.5, 3, 5.5), (-9.5, 3, 8)),
    ("A", (12, "por"), (-6, 2, 40), (0, 4, 82)),            # regreso al plano inicial -> loop
]
INICIOS = [T(*t[1]) for t in TOMAS] + [DUR]


def camara(t):
    for k, (s, _, ci, cf) in enumerate(TOMAS):
        if t < INICIOS[k + 1] or k == len(TOMAS) - 1:
            a = 0 if (k == 0 and t < INICIOS[0]) else tramo(t, INICIOS[k], INICIOS[k + 1])
            return s, Cam(*(lerp(i, f, a) for i, f in zip(ci, cf)))


rnd = random.Random(7)
VAPOR = [(rnd.uniform(-3, 3), rnd.uniform(0, 1), rnd.uniform(0.6, 1.2)) for _ in range(7)]
BOKEH = [(rnd.uniform(-30, 30), rnd.uniform(-50, 50), rnd.uniform(0.3, 1.6), rnd.uniform(0.2, 0.6)) for _ in range(40)]
MOLS = [(x * 2.6 + rnd.uniform(-0.5, 0.5), y * 2.6 + rnd.uniform(-0.5, 0.5), rnd.uniform(0, 6.28), rnd.uniform(0.6, 1.4))
        for x in range(-4, 5) for y in range(-7, 8) if (x, y) != (0, 0)]
PANEL_A = lambda t: 1 - 0.85 * ventana(t, T(3, "panel"), T(4) + 0.2, 0.8)               # tapa del panel
CORTE = lambda t: ventana(t, T(7) - 0.1, T(8), 0.6)                                         # puerta en corte (línea 7)
CALOR = lambda t: tramo(t, T(10), T(10, "calor") + 0.6)


# ---------------------------------------------------------------- set A: cocina + horno (cm)
def cocina(im, d, c, t):
    rect_grad(im, c.rect(-200, -16, 200, 160), (22, 40, 48), (40, 64, 70))                                  # pared
    for gx in range(-200, 200, 9):                                                                          # azulejo
        d.line([c.p(gx, -16), c.p(gx, 30)], fill=(50, 76, 82), width=c.w(0.35))
    for gy in range(-16, 31, 9):
        d.line([c.p(-200, gy), c.p(200, gy)], fill=(50, 76, 82), width=c.w(0.35))
    rect_grad(im, c.rect(-200, 30, 200, 32), (60, 50, 40), (40, 32, 26))                                    # moldura
    for x0 in range(-180, 180, 52):                                                                         # gabinetes
        rect_grad(im, c.rect(x0, 48, x0 + 48, 110), (88, 60, 40), (62, 40, 26), c.s(1.5))
        d.rounded_rectangle(c.rect(x0 + 3, 51, x0 + 45, 107), radius=c.s(1), outline=(110, 78, 52), width=c.w(0.4))
        d.rounded_rectangle(c.rect(x0 + 21, 52, x0 + 27, 54), radius=c.s(0.5), fill=(200, 190, 170))
    rect_grad(im, c.rect(-95, 36, -55, 44), (0, 0, 0), (0, 0, 0))
    rect_grad(im, c.rect(-150, -2, -96, 40), (16, 26, 60), (60, 50, 90), c.s(1))                            # ventana nocturna
    esfera(im, c.p(-110, 30), c.s(3), (240, 236, 210))
    d.rectangle(c.rect(-124, -2, -122, 40), fill=(70, 56, 44)); d.rectangle(c.rect(-150, 18, -96, 20), fill=(70, 56, 44))
    br = Brillo(im, c.s(30)); br.d.ellipse(br.s(c.rect(-30, 0, 30, 70)), fill=(70, 55, 25)); br.listo()   # luz de la lámpara
    d.line([c.p(0, 160), c.p(0, 72)], fill=(20, 20, 20), width=c.w(0.4))                                   # lámpara
    d.pieslice(c.rect(-9, 60, 9, 80), 180, 360, fill=(30, 30, 34)); d.ellipse(c.rect(-3, 68, 3, 72), fill=(255, 235, 180))
    rect_grad(im, c.rect(-200, -24, 200, -16), (214, 208, 196), (150, 144, 134))                            # cubierta
    rect_grad(im, c.rect(-200, -120, 200, -24), (70, 46, 30), (40, 26, 18))                                 # muebles bajos
    for x0 in range(-190, 190, 48):
        d.rounded_rectangle(c.rect(x0, -110, x0 + 44, -28), radius=c.s(1), outline=(96, 66, 44), width=c.w(0.4))
        d.rounded_rectangle(c.rect(x0 + 18, -34, x0 + 26, -32), radius=c.s(0.5), fill=(200, 190, 170))
    # utilería: maceta y tetera
    sombra(im, c.rect(-52, -17, -34, -14), c.s(1)); rect_grad(im, c.rect(-50, -16, -36, -4), (190, 100, 70), (130, 64, 44), c.s(1.5))
    for k in range(7):
        a = math.radians(50 + k * 13); x, y = -43 + 9 * math.cos(a), -2 + 12 * math.sin(a)
        d.line([c.p(-43, -4), c.p(x, y)], fill=(60, 150, 80), width=c.w(1.2)); esfera(im, c.p(x, y), c.s(1.6), (70, 170, 90))
    sombra(im, c.rect(34, -17, 56, -14), c.s(1)); rect_grad(im, c.rect(36, -16, 54, -2), (220, 70, 60), (150, 40, 36), c.s(5))
    d.line([c.p(54, -6), c.p(60, 0)], fill=(150, 40, 36), width=c.w(1.4)); d.ellipse(c.rect(43, -2, 47, 1), fill=(40, 40, 44))


def plato_y_sopa(im, d, c, t):
    giro = t * 1.6
    d.ellipse(c.rect(-19, -11.6, 5, -8.4), fill=(200, 205, 210), outline=(150, 155, 160), width=c.w(0.15))    # plato giratorio
    calor = ventana(t, T(11), T(12), 0.6)
    plato = mezcla((215, 215, 220), (120, 170, 255), calor)
    d.ellipse(c.rect(-3 + 1.5 * math.sin(giro), -10.6, 3 + 1.5 * math.sin(giro), -9.4), fill=plato)          # plato seco
    bx = -11 + 1.2 * math.sin(giro + 2)
    d.chord(c.rect(bx - 5, -14, bx + 5, -4), 0, 180, fill=(235, 232, 224))                                  # tazón
    d.ellipse(c.rect(bx - 5, -10.2, bx + 5, -7.8), fill=mezcla((200, 110, 40), (255, 150, 50), calor))     # sopa
    for k in range(3):                                                                    # brillos sobre la sopa
        x = bx - 3 + ((k * 2.3 + giro * 1.4) % 6)
        d.ellipse(c.rect(x - 0.7, -9.15, x + 0.7, -8.85), fill=mezcla((200, 110, 40), (255, 225, 170), 0.6))
    if calor > 0.01:
        for k, (ox, fase, vel) in enumerate(VAPOR):
            y0 = -7 + ((t * vel + fase) % 1.0) * 9; a = calor * (1 - ((t * vel + fase) % 1.0))
            pts = [c.p(bx + ox + 0.6 * math.sin(y * 1.3 + k), y) for y in np.linspace(y0, y0 + 3, 8)]
            d.line(pts, fill=mezcla((60, 50, 30), (255, 250, 240), a), width=c.w(0.35))


def horno(im, d, c, t):
    sombra(im, c.rect(-27, -17, 27, -13), c.s(1.2))
    rect_grad(im, c.rect(-26, -15, 26, 16), (226, 229, 233), (150, 154, 160), c.s(2))                       # carcasa
    d.rounded_rectangle(c.rect(-26, -15, 26, 16), radius=c.s(2), outline=(110, 114, 120), width=c.w(0.25))
    for k in range(6): d.line([c.p(-14 + k * 1.2, 15), c.p(-14 + k * 1.2, 13.5)], fill=(120, 124, 130), width=c.w(0.3))  # rejillas
    corte = CORTE(t)
    # interior de la cavidad
    rect_grad(im, c.rect(-22, -12, 8, 12), (130, 105, 50), (80, 60, 30))
    rect_grad(im, c.rect(-22, -12, 8, -9), (90, 70, 36), (60, 44, 22))
    plato_y_sopa(im, d, c, t)
    if corte < 0.98:                                                                                         # puerta con vidrio
        vid = Image.new("RGB", (WS, HS), (0, 0, 0)); m = Image.new("L", (WS, HS), 0); dm = ImageDraw.Draw(m)
        dm.rounded_rectangle(c.rect(-22, -12, 8, 12), radius=c.s(1), fill=int(95 * (1 - corte)))
        im.paste(vid, (0, 0), m)
        if c.k > WS / 10:                                                                                    # malla perforada: solo en primer plano
            paso = 0.25; x0 = max(-22, c.cx - WS / c.k / 2 - 1); x1 = min(8, c.cx + WS / c.k / 2 + 1)
            y0 = max(-12, c.cy - HS / c.k / 2 - 1); y1 = min(12, c.cy + HS / c.k / 2 + 1)
            d.rectangle(c.rect(x0, y0, x1, y1), fill=(34, 34, 38))                                           # lámina de metal
            for gx in np.arange(math.floor(x0 / paso) * paso, x1, paso):
                for gy in np.arange(math.floor(y0 / paso) * paso, y1, paso):
                    d.ellipse(c.rect(gx - 0.08, gy - 0.08, gx + 0.08, gy + 0.08), fill=(235, 190, 110))
        else:                                                                                                # de lejos: trama muy tenue
            for gx in range(-22, 9, 1): d.line([c.p(gx, -12), c.p(gx, 12)], fill=(60, 50, 34), width=1)
        d.rounded_rectangle(c.rect(-24.5, -14, 10, 14.5), radius=c.s(1.5), outline=mezcla((60, 62, 66), (150, 155, 160), corte), width=c.w(2.2))
        refl = Image.new("L", (WS, HS), 0); ImageDraw.Draw(refl).polygon([c.p(-21, 11), c.p(-17, 11), c.p(-24, 1), c.p(-26, 1)], fill=28)
        im.paste((255, 255, 255), (0, 0), refl)                                                              # reflejo suave
        rect_grad(im, c.rect(8.6, -9, 9.8, 9), (240, 242, 245), (170, 174, 180), c.s(0.6))                  # manija
    # panel de control (su tapa se vuelve transparente en la línea 3)
    tapa = PANEL_A(t)
    rect_grad(im, c.rect(11, -13, 25, 14), (70, 74, 80), (50, 52, 56), c.s(1))
    magnetron_mini(im, d, c, t)
    if tapa > 0.02:
        capa = Image.new("RGB", (WS, HS)); rect_grad(capa, c.rect(11, -13, 25, 14), (44, 46, 52), (26, 27, 31), c.s(1))
        m = Image.new("L", (WS, HS), 0); ImageDraw.Draw(m).rounded_rectangle(c.rect(11, -13, 25, 14), radius=c.s(1), fill=int(255 * tapa))
        im.paste(capa, (0, 0), m)
        if tapa > 0.5:
            d.rounded_rectangle(c.rect(12.5, 8, 23.5, 12.5), radius=c.s(0.6), fill=(8, 20, 12))             # pantalla
            seg = max(0, 90 - int(t)); texto(d, c.p(18, 10.3), f"{seg // 60}:{seg % 60:02d}", c.s(3.2), (90, 255, 140))
            for fy in range(4):
                for fx in range(3):
                    x, y = 13.2 + fx * 3.6, 5.2 - fy * 2.6
                    d.rounded_rectangle(c.rect(x, y - 1, x + 2.8, y + 0.8), radius=c.s(0.4), fill=(78, 82, 90))
            d.rounded_rectangle(c.rect(13.2, -10.6, 23, -8.2), radius=c.s(0.5), fill=(40, 170, 90))           # inicio
            esfera(im, c.p(18, -5.2), c.s(1.7), (150, 155, 165))                                             # perilla
    if corte > 0.01: ondas_cavidad(im, d, c, t, corte)


def magnetron_mini(im, d, c, t):
    """Lo que hay detrás del panel: magnetrón con aletas, guía de onda y transformador."""
    rect_grad(im, c.rect(14, -11, 23, -3), (40, 40, 44), (20, 20, 24), c.s(0.5))                          # transformador
    for k in range(7): d.line([c.p(15, -10 + k * 1.1), c.p(22, -10 + k * 1.1)], fill=(184, 110, 60), width=c.w(0.45))
    rect_grad(im, c.rect(11.5, 9, 18, 11.6), (190, 194, 200), (130, 134, 140))                            # guía de onda
    for k in range(6):
        rect_grad(im, c.rect(13, 0 + k * 1.2, 23, 0.5 + k * 1.2), (210, 214, 220), (160, 164, 170))       # aletas
    rect_grad(im, c.rect(15.5, -0.5, 20.5, 8), (230, 150, 90), (150, 80, 40), c.s(0.5))                   # ánodo de cobre
    br = Brillo(im, c.s(2.5)); br.d.ellipse(br.s(c.rect(16, 1, 20, 7)), fill=(255, 130, 40)); br.listo(0.8 * (1 - PANEL_A(t)) + 0.2)


def ondas_cavidad(im, d, c, t, k):
    camino = [(18, 10.3), (6, 10.3), (-20, 4), (-2, -10), (6, 6), (-21, 10), (-8, -11)]
    pts = onda_en_camino(camino, t, 0.7, 3.0, 9, crecer=tramo(t, T(7, "lleva"), T(7, "paredes") + 0.5))
    if len(pts) > 1:
        br = Brillo(im, c.s(1.5)); br.d.line([br.s(c.p(*p)) for p in pts], fill=(255, 210, 60), width=max(2, c.w(0.8) // 4)); br.listo(k)
        d.line([c.p(*p) for p in pts], fill=mezcla((0, 0, 0), (255, 240, 150), k), width=c.w(0.25))


def rejilla_onda(im, d, c, t):
    """Primer plano de la puerta (línea 12): agujeros de ~1 mm contra una onda de 12 cm que rebota."""
    a = ventana(t, T(12, "rejilla"), T(12, "por") + 0.6, 0.5)
    if a < 0.01: return
    tt = t - T(12, "rejilla"); rebote = tramo(tt, 1.2, 2.0)
    amp = 2.2 * (1 - 2 * rebote)                                               # la onda choca y regresa (se invierte)
    pts = [(x, 3 + amp * math.sin(2 * math.pi * x / 12.2 - 3 * tt)) for x in np.linspace(-16, -3, 120)]   # λ = 12.2 cm real
    br = Brillo(im, c.s(0.35)); br.d.line([br.s(c.p(*p)) for p in pts], fill=(255, 200, 60), width=max(2, c.w(0.25) // 4)); br.listo(1.6 * a)
    d.line([c.p(*p) for p in pts], fill=mezcla((0, 0, 0), (255, 245, 190), a), width=c.w(0.07))
    hx, hy = -8.25, 3.75                                                        # un agujero señalado (lejos de subtítulos)
    d.ellipse(c.rect(hx - 0.2, hy - 0.2, hx + 0.2, hy + 0.2), outline=mezcla((0, 0, 0), (255, 255, 255), a), width=c.w(0.04))
    texto(d, c.p(hx, hy - 0.45), "1 mm", c.s(0.3), mezcla((0, 0, 0), (255, 255, 255), a), c.s(0.05))
    texto(d, c.p(-11.2, 2.2), "onda ≈ 12 cm", c.s(0.38), mezcla((0, 0, 0), (255, 215, 90), a), c.s(0.06))


def set_A(im, d, c, t):
    cocina(im, d, c, t); horno(im, d, c, t); rejilla_onda(im, d, c, t)


# ---------------------------------------------------------------- set B: magnetrón de lado (mm)
def set_B(im, d, c, t):
    im.paste(FONDOS["B"]); dg = d
    for g in range(-60, 61, 4):                                                                              # cuadrícula técnica
        dg.line([c.p(g, -60), c.p(g, 60)], fill=(26, 40, 62), width=c.w(0.06))
        dg.line([c.p(-60, g), c.p(60, g)], fill=(26, 40, 62), width=c.w(0.06))
    sep = tramo(t, T(4, "atrapado") - 0.2, T(4, "imanes") + 0.4) * (1 - tramo(t, T(5, "silban"), T(6)))
    sombra(im, c.rect(-11, -12.5, 11, -10.5), c.s(0.8))
    rect_grad(im, c.rect(-6, -12, 6, -6.5), (150, 154, 160), (96, 100, 106), c.s(0.5))                      # caja de filtro
    for x in (-2.5, 2.5): rect_grad(im, c.rect(x - 0.5, -14, x + 0.5, -12), (230, 200, 120), (170, 130, 60))
    for k in range(7):                                                                                       # aletas
        y = -3 + k * 1.0; rect_grad(im, c.rect(-11, y, 11, y + 0.35), (225, 228, 232), (165, 170, 176), c.s(0.1))
    rect_grad(im, c.rect(-4.5, -4, 4.5, 4), (240, 160, 96), (160, 82, 40), c.s(0.4), horizontal=True)        # ánodo
    if sep > 0.05:                                                                                           # cavidades visibles al separar
        for k in range(5):
            x = -3 + k * 1.5; d.rounded_rectangle(c.rect(x - 0.3, -2.4, x + 0.3, 2.4), radius=c.s(0.3), fill=(70, 30, 12))
    dy = sep * 4
    for s, y0, y1, letra, col in ((1, 4.4 + dy, 6.6 + dy, "N", (200, 60, 50)), (-1, -6.6 - dy, -4.4 - dy, "S", (60, 100, 210))):
        rect_grad(im, c.rect(-6, y0, 6, y1), (90, 92, 98), (46, 48, 54), c.s(0.5))
        d.rounded_rectangle(c.rect(-6, y0, 6, y1), radius=c.s(0.5), outline=col, width=c.w(0.18))
        texto(d, c.p(0, (y0 + y1) / 2), letra, c.s(1.3), col)
    if sep > 0.05:                                                                                           # líneas de campo
        for x in (-3, 0, 3):
            d.line([c.p(x, 4.2 + dy), c.p(x, -4.2 - dy)], fill=mezcla((20, 30, 50), (120, 170, 255), sep), width=c.w(0.08))
    ya = 6.6 + dy
    rect_grad(im, c.rect(-0.35, ya, 0.35, ya + 3.2), (230, 232, 236), (160, 164, 170))                       # antena
    d.chord(c.rect(-1.6, ya + 2.4, 1.6, ya + 4.8), 180, 360, fill=(210, 214, 220))
    a = tramo(t, T(6), T(6) + 0.5) * (1 - tramo(t, T(7), T(7) + 0.3))
    if a > 0.01:                                                                                             # microondas que salen
        br = Brillo(im, c.s(0.5))
        for j in range(5):
            r = ((t * 1.4 + j / 5) % 1) * 12 + 1
            br.d.arc(br.s(c.rect(-r, ya + 3.6 - r, r, ya + 3.6 + r)), 200, 340, fill=(255, 200, 60), width=max(2, c.w(0.3) // 4))
        br.listo(a * 1.4)


# ---------------------------------------------------------------- set B2: ánodo visto desde arriba (mm)
def set_B2(im, d, c, t):
    im.paste(FONDOS["B"])
    esfera(im, c.p(0, 0), c.s(5.6), (140, 144, 150))
    d.ellipse(c.rect(-4.6, -4.6, 4.6, 4.6), fill=(205, 120, 62)); d.ellipse(c.rect(-4.6, -4.6, 4.6, 4.6), outline=(250, 180, 120), width=c.w(0.12))
    for k in range(8):                                                                                       # 8 cavidades en ojo de cerradura
        a = 2 * math.pi * k / 8; x, y = 3.1 * math.cos(a), 3.1 * math.sin(a)
        d.ellipse(c.rect(x - 0.55, y - 0.55, x + 0.55, y + 0.55), fill=(26, 14, 8))
        d.line([c.p(1.6 * math.cos(a), 1.6 * math.sin(a)), c.p(x, y)], fill=(26, 14, 8), width=c.w(0.32))
    d.ellipse(c.rect(-1.9, -1.9, 1.9, 1.9), fill=(14, 10, 10))
    br = Brillo(im, c.s(0.6)); br.d.ellipse(br.s(c.rect(-0.5, -0.5, 0.5, 0.5)), fill=(255, 140, 40))
    giro = t * 2.2; n = tramo(t, T(5, "electrones"), T(5, "giran") + 0.4)
    for r_ in range(4):                                                                                      # 4 rayos de electrones
        for j in range(9):
            u = j / 8; ang = giro + r_ * math.pi / 2 + u * 1.1; rr = 0.45 + u * 1.35
            if u > n: break
            x, y = rr * math.cos(ang), rr * math.sin(ang)
            br.d.ellipse(br.s(c.rect(x - 0.12, y - 0.12, x + 0.12, y + 0.12)), fill=(90, 170, 255))
    br.listo(1.6)
    for r_ in range(4):
        for j in range(9):
            u = j / 8; ang = giro + r_ * math.pi / 2 + u * 1.1; rr = 0.45 + u * 1.35
            if u > n: break
            x, y = rr * math.cos(ang), rr * math.sin(ang); d.ellipse(c.rect(x - 0.06, y - 0.06, x + 0.06, y + 0.06), fill=(230, 245, 255))
    d.arc(c.rect(-1.25, -1.25, 1.25, 1.25), math.degrees(-giro) - 40, math.degrees(-giro) + 40, fill=(255, 255, 255), width=c.w(0.06))


# ---------------------------------------------------------------- set C: moléculas de agua (nm)
def molecula(im, d, c, x, y, ang, esc=1.0, alfa=1.0, cargas=False):
    if alfa < 0.03: return
    def col(cc): return mezcla((14, 22, 46), cc, alfa)
    for s in (-1, 1):
        a = ang + s * math.radians(52); hx, hy = x + 0.62 * esc * math.cos(a), y + 0.62 * esc * math.sin(a)
        esfera(im, c.p(hx, hy), c.s(0.33 * esc), col((236, 238, 242)))
        if cargas: texto(d, c.p(x + 1.15 * esc * math.cos(a), y + 1.15 * esc * math.sin(a)), "+", c.s(0.38 * esc), (120, 200, 255), c.s(0.05))
    esfera(im, c.p(x, y), c.s(0.55 * esc), col((225, 60, 50)))
    if cargas: texto(d, c.p(x - 1.05 * esc * math.cos(ang), y - 1.05 * esc * math.sin(ang)), "−", c.s(0.5 * esc), (255, 120, 110), c.s(0.05))


def set_C(im, d, c, t):
    calor = CALOR(t)
    im.paste(Image.blend(FONDOS["C"], FONDOS["Ccal"], calor))
    br = Brillo(im, c.s(0.8))
    for bx, by, r, a in BOKEH:                                                                               # partículas desenfocadas
        x, y = bx + 0.15 * c.cx, by
        br.d.ellipse(br.s(c.rect(x - r, y - r, x + r, y + r)), fill=mezcla((0, 0, 0), mezcla((60, 110, 200), (255, 140, 60), calor), a * 0.5))
    br.listo()
    campo = math.tanh(3 * math.sin(2 * math.pi * 0.9 * (t - T(9)))) if t >= T(9, "cambian") else 1.0
    act = tramo(t, T(9, "cambian"), T(9, "cambian") + 0.5)
    if t >= T(9) - 0.5:                                                                                      # flechas del campo
        fa = tramo(t, T(9), T(9) + 0.6)
        for x in range(-12, 13, 6):
            col = mezcla((14, 22, 46), (60, 90, 150), fa * abs(campo))
            y0, y1 = (-9, 9) if campo > 0 else (9, -9)
            d.line([c.p(x, y0), c.p(x, y1)], fill=col, width=c.w(0.6))
            d.polygon([c.p(x - 1.2, y1 - math.copysign(1.6, y1)), c.p(x + 1.2, y1 - math.copysign(1.6, y1)), c.p(x, y1)], fill=col)
    otros = tramo(t, T(9) - 0.3, T(9) + 0.8)
    obj = math.pi / 2 if campo > 0 else -math.pi / 2
    for k, (x, y, a0, vel) in enumerate(MOLS):
        jit = calor * 0.35
        ang = lerp(a0 + 0.3 * math.sin(t * vel), obj + 0.25 * math.sin(t * 7 * vel + k), act * 0.85)
        molecula(im, d, c, x + jit * math.sin(t * 13 * vel + k), y + jit * math.cos(t * 11 * vel + 2 * k), ang, 1.0, otros)
    ang0 = lerp(math.radians(-90 + 25 * math.sin(t)), obj, act * 0.9)
    molecula(im, d, c, 0.15 * calor * math.sin(t * 20), 0, ang0, 1.0, 1.0, cargas=t < T(10) + 1)
    if calor > 0.05:                                                                                         # destellos de choques
        br = Brillo(im, c.s(0.4))
        for k in range(10):
            fase = (t * 3 + k * 0.37) % 1
            if fase < 0.25:
                x, y = MOLS[(k * 7 + int(t * 3)) % len(MOLS)][:2]
                br.d.ellipse(br.s(c.rect(x - 0.5, y - 0.5, x + 0.5, y + 0.5)), fill=(255, 170, 60))
        br.listo(calor * 1.5)


SETS = {"A": set_A, "B": set_B, "B2": set_B2, "C": set_C}
FONDOS = {}


def cuadro(fr):
    t = fr / FPS; s, c = camara(t)
    if not FONDOS:
        FONDOS["B"] = fondo_radial((24, 40, 70), (6, 9, 18)); FONDOS["C"] = fondo_radial((24, 40, 90), (4, 8, 20), 0.5)
        FONDOS["Ccal"] = fondo_radial((110, 50, 30), (24, 8, 6), 0.5)
    im = Image.new("RGB", (WS, HS), (10, 12, 16)); d = ImageDraw.Draw(im); SETS[s](im, d, c, t)
    return im.resize((W, H), Image.LANCZOS) if SS > 1 else im


def main():
    frames = [int(x) for x in A.frames.split(",") if x] or list(range(0, NF, max(1, A.paso)))
    if A.part:
        i, n = map(int, A.part.split("/")); frames = frames[i::n]
    os.makedirs(OUT, exist_ok=True); t0 = time.time(); hechos = 0
    for fr in frames:
        dst = os.path.join(OUT, f"f_{fr:04d}.png")
        if os.path.exists(dst) and not A.frames: continue
        cuadro(fr).save(dst, compress_level=1); hechos += 1
        if hechos % 100 == 0: print(f"cuadro {fr}/{NF}  {(time.time() - t0) / hechos:.3f} s/cuadro", flush=True)
    print(f"OK 2D: {hechos} cuadros en {time.time() - t0:.1f} s ({W}x{H}, ss={SS}, paso={A.paso}) -> {OUT}")


main()
