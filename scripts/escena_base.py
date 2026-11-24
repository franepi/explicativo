"""Escena 3D para Blender (4.2+ / 5.x) con acabado "premium", guiada por la voz. Ejemplo: "cómo funciona un microondas".

Uso:
  blender -b -P escena_base.py -- --trabajo trabajo/ --out trabajo/frames [--frames 0,30,60] [--pct 50]
                                   [--samples 32] [--part 0/2] [--paso 1] [--motor workbench|eevee|cycles]
--motor workbench  = sin luz realista, corre hasta en gráficos integrados (nivel 3d-bajo)
--motor cycles     = trazado de rayos real (nivel ultra); usa la GPU si hay
--paso N           = renderiza 1 de cada N cuadros; componer.py repite el último

Estructura (igual que escena_2d.py, así el plan de tomas sirve para los dos):
- construir_set_X(origen): cada set vive lejos de los demás con su propia unidad (A = cm, B = mm, C = ~Å).
- TOMAS: cámara por plano, con posición, objetivo, lente y fstop iniciales y finales. Corte seco entre planos.
- actualizar(t): mueve TODO lo animado en cada cuadro a partir de T(linea, "palabra"). Sin keyframes a mano.
Acabado premium (no lo quites): profundidad de campo, 4 luces de área por set, AgX alto contraste, raytracing,
fondo con contexto (un lugar real o un ambiente por escala), biseles, materiales procedurales (azulejo, madera,
piedra, malla perforada) y piezas pequeñas.
"""
import bpy, json, math, os, random, sys, unicodedata
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(k, d=None): return argv[argv.index(k) + 1] if k in argv else d
TRAB = os.path.abspath(arg("--trabajo", "trabajo")); OUT = os.path.abspath(arg("--out", os.path.join(TRAB, "frames")))
TL = json.load(open(os.path.join(TRAB, "timeline.json"), encoding="utf8"))
FPS = TL.get("fps", 30); NF = int(round(TL["duration"] * FPS)); DUR = TL["duration"]
PCT = int(arg("--pct", "100")); SAMPLES = int(arg("--samples", "32")); MOTOR = arg("--motor", "eevee")
FRAMES = [int(x) for x in arg("--frames").split(",")] if arg("--frames") else list(range(NF))
if arg("--part"):
    i, n = map(int, arg("--part").split("/")); FRAMES = FRAMES[i::n]
if arg("--paso") and not arg("--frames"):
    FRAMES = [f for f in FRAMES if f % int(arg("--paso")) == 0]
FUENTES = ["C:/Windows/Fonts/seguibl.ttf", "C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"]


def norm(w):
    w = unicodedata.normalize("NFD", w.lower()); return "".join(c for c in w if unicodedata.category(c) != "Mn" and c.isalnum())


def T(linea, palabra=None, occ=1):
    """Segundo en que empieza una palabra (o la línea si palabra=None)."""
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
def tramo(t, t0, t1): return ease((t - t0) / max(1e-6, t1 - t0))
def ventana(t, t0, t1, f=0.4): return tramo(t, t0, t0 + f) * (1 - tramo(t, t1 - f, t1))


# ================================================================ utilidades (kit reutilizable)
def _set(obj, **kw):
    for k, v in kw.items():
        try: setattr(obj, k, v)
        except Exception: pass


def _inp(b, nombres, v):
    for k in nombres:
        if k in b.inputs: b.inputs[k].default_value = v; return


def _transparente(m):
    _set(m, surface_render_method="DITHERED", blend_method="HASHED", use_raytrace_refraction=True)


def material(nombre, color=(0.8, 0.8, 0.8), metal=0.0, rugosidad=0.4, transmision=0.0, emision=0.0, capa=0.0, ior=None, alfa=None):
    m = bpy.data.materials.new(nombre); m.use_nodes = True; b = m.node_tree.nodes["Principled BSDF"]
    m.diffuse_color = (*color, 1); m.metallic = metal; m.roughness = rugosidad          # lo que usa Workbench
    b.inputs["Base Color"].default_value = (*color, 1); b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rugosidad
    if capa: _inp(b, ["Coat Weight"], capa); _inp(b, ["Coat Roughness"], 0.04)
    if ior: _inp(b, ["IOR"], ior)
    if transmision:
        _inp(b, ["Transmission Weight", "Transmission"], transmision); _transparente(m); _set(m, thickness_mode="SLAB")
    if emision:
        _inp(b, ["Emission Color", "Emission"], (*color, 1)); _inp(b, ["Emission Strength"], emision)
    if alfa is not None:
        b.inputs["Alpha"].default_value = alfa; _transparente(m)
    return m


def _nodos(m):
    nt = m.node_tree; return nt, nt.nodes["Principled BSDF"], nt.nodes.new("ShaderNodeTexCoord")


def material_azulejo(nombre, color, junta, escala=1.0, rug=0.25):
    m = material(nombre, color, rugosidad=rug, capa=0.5); nt, b, tc = _nodos(m)
    br = nt.nodes.new("ShaderNodeTexBrick"); br.offset = 0.0; br.squash = 1.0
    br.inputs["Scale"].default_value = escala; br.inputs["Mortar Size"].default_value = 0.012
    br.inputs["Color1"].default_value = (*color, 1); br.inputs["Color2"].default_value = tuple(min(1, v * 1.12) for v in color) + (1,)
    br.inputs["Mortar"].default_value = (*junta, 1); br.inputs["Brick Width"].default_value = 0.5; br.inputs["Row Height"].default_value = 0.5
    nt.links.new(tc.outputs["Object"], br.inputs["Vector"]); nt.links.new(br.outputs["Color"], b.inputs["Base Color"])
    return m


def material_veta(nombre, c1, c2, escala=0.08, rug=0.45):
    """Madera: ondas distorsionadas entre dos tonos."""
    m = material(nombre, c1, rugosidad=rug, capa=0.3); nt, b, tc = _nodos(m)
    wv = nt.nodes.new("ShaderNodeTexWave"); wv.wave_type = "BANDS"; wv.inputs["Scale"].default_value = escala
    wv.inputs["Distortion"].default_value = 8; wv.inputs["Detail"].default_value = 3
    r = nt.nodes.new("ShaderNodeValToRGB"); r.color_ramp.elements[0].color = (*c1, 1); r.color_ramp.elements[1].color = (*c2, 1)
    nt.links.new(tc.outputs["Object"], wv.inputs["Vector"]); nt.links.new(wv.outputs["Fac"], r.inputs[0])
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"]); return m


def material_ruido(nombre, c1, c2, escala=0.3, rug=0.3, metal=0.0):
    """Piedra, metal cepillado, etc.: ruido suave entre dos colores."""
    m = material(nombre, c1, rugosidad=rug, metal=metal, capa=0.4); nt, b, tc = _nodos(m)
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = escala; nz.inputs["Detail"].default_value = 6
    r = nt.nodes.new("ShaderNodeValToRGB"); r.color_ramp.elements[0].color = (*c1, 1); r.color_ramp.elements[1].color = (*c2, 1)
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"]); nt.links.new(nz.outputs["Fac"], r.inputs[0])
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"]); return m


def material_malla(nombre, paso=0.25, radio=0.32):
    """Lámina perforada (puerta del microondas). Devuelve (material, nodo 'opacidad' para animar)."""
    m = material(nombre, (0.02, 0.02, 0.022), metal=0.6, rugosidad=0.35); nt, b, tc = _nodos(m); _transparente(m)
    mp = nt.nodes.new("ShaderNodeVectorMath"); mp.operation = "SCALE"; mp.inputs["Scale"].default_value = 1 / paso
    nt.links.new(tc.outputs["Object"], mp.inputs[0])
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(mp.outputs["Vector"], sep.inputs[0])
    def op(o, a=None, bb=None, v=None):
        n = nt.nodes.new("ShaderNodeMath"); n.operation = o
        if a is not None: nt.links.new(a, n.inputs[0])
        if bb is not None: nt.links.new(bb, n.inputs[1])
        if v is not None: n.inputs[1].default_value = v
        return n
    fx = op("FRACT", sep.outputs["X"]); fz = op("FRACT", sep.outputs["Z"])
    dx = op("SUBTRACT", fx.outputs[0], v=0.5); dz = op("SUBTRACT", fz.outputs[0], v=0.5)
    cb = nt.nodes.new("ShaderNodeCombineXYZ"); nt.links.new(dx.outputs[0], cb.inputs[0]); nt.links.new(dz.outputs[0], cb.inputs[1])
    ln = nt.nodes.new("ShaderNodeVectorMath"); ln.operation = "LENGTH"; nt.links.new(cb.outputs[0], ln.inputs[0])
    hueco = op("LESS_THAN", ln.outputs["Value"], v=radio)
    lam = op("SUBTRACT", None, hueco.outputs[0]); lam.inputs[0].default_value = 1.0        # 1 en la lámina, 0 en el hueco
    a = op("MULTIPLY_ADD", lam.outputs[0], v=0.9); a.inputs[2].default_value = 0.05
    opac = nt.nodes.new("ShaderNodeValue"); opac.outputs[0].default_value = 1.0
    fin = op("MULTIPLY", a.outputs[0], opac.outputs[0]); nt.links.new(fin.outputs[0], b.inputs["Alpha"])
    m.diffuse_color = (0.05, 0.05, 0.06, 1); return m, opac


def material_emision(nombre, color, fuerza, alfa=1.0):
    """Luz pura (pantallas, haces, chispas). Con alfa < 1 se mezcla con transparencia. Devuelve (mat, nodo_emision, nodo_mezcla)."""
    m = bpy.data.materials.new(nombre); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission"); tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mx = nt.nodes.new("ShaderNodeMixShader"); mx.inputs["Fac"].default_value = alfa
    em.inputs["Color"].default_value = (*color, 1); em.inputs["Strength"].default_value = fuerza
    nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], out.inputs[0])
    _transparente(m); _set(m, surface_render_method="BLENDED", blend_method="BLEND", use_backface_culling=False)
    m.diffuse_color = (*color, 1); return m, em, mx


def material_fondo_radial(nombre, escala=70.0):
    """Telón de fondo con degradado radial (color del nodo 'centro' -> casi negro en los bordes); el color se anima."""
    m = bpy.data.materials.new(nombre); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission"); tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeVectorMath"); mp.operation = "SCALE"; mp.inputs["Scale"].default_value = 1 / escala
    gr = nt.nodes.new("ShaderNodeTexGradient"); gr.gradient_type = "SPHERICAL"
    c = nt.nodes.new("ShaderNodeRGB"); c.name = "centro"; c.outputs[0].default_value = (0.05, 0.1, 0.3, 1)
    mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.inputs["A"].default_value = (0.003, 0.005, 0.012, 1)
    nt.links.new(tc.outputs["Object"], mp.inputs[0]); nt.links.new(mp.outputs["Vector"], gr.inputs["Vector"])
    nt.links.new(gr.outputs["Fac"], mx.inputs["Factor"]); nt.links.new(c.outputs[0], mx.inputs["B"])
    nt.links.new(mx.outputs["Result"], em.inputs["Color"]); em.inputs["Strength"].default_value = 1.4
    nt.links.new(em.outputs[0], out.inputs[0]); m.diffuse_color = (0.05, 0.1, 0.3, 1); return m


def ocultar(o, flag):
    """hide_render NO se hereda: un vacío oculto deja visibles a sus hijos. Esto oculta todo el grupo."""
    o.hide_render = flag
    for h in o.children_recursive: h.hide_render = flag


def _obj(nombre, data, mat=None, padre=None):
    o = bpy.data.objects.new(nombre, data); bpy.context.scene.collection.objects.link(o)
    if mat is not None and data is not None: o.data.materials.append(mat)
    if padre: o.parent = padre
    return o


def _suave(o):
    for p in o.data.polygons: p.use_smooth = True


_MALLAS = {}
def _malla_base(tipo):
    if tipo not in _MALLAS:
        if tipo == "cubo": bpy.ops.mesh.primitive_cube_add()
        elif tipo == "esfera": bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16)
        elif tipo == "cil": bpy.ops.mesh.primitive_cylinder_add(vertices=48)
        elif tipo == "cono": bpy.ops.mesh.primitive_cone_add(vertices=48)
        o = bpy.context.object; me = o.data; me.name = "base_" + tipo
        if tipo != "cubo":
            for p in me.polygons: p.use_smooth = True
        if len(me.materials) == 0: me.materials.append(None)                    # 1 ranura; el material va por objeto
        bpy.data.objects.remove(o); _MALLAS[tipo] = me
    return _MALLAS[tipo]


def caja(nombre, pos, medio, mat, bisel=0.0, seg=3, padre=None, propia=False):
    """Caja con medio tamaño 'medio' (x, y, z). Con bisel o propia=True la malla es propia y mide en unidades reales:
    úsalo si el material usa coordenadas de objeto (malla perforada, degradados), o el patrón se estira con la escala."""
    if bisel or propia:
        me = _malla_base("cubo").copy(); me.transform(Matrix.Diagonal((*medio, 1))); me.materials[0] = mat
        o = _obj(nombre, me, None, padre); o.location = pos
        if not bisel: return o
        md = o.modifiers.new("bisel", "BEVEL"); md.width = bisel; md.segments = seg; md.limit_method = "ANGLE"; md.harden_normals = True
        _suave(o); return o
    o = _obj(nombre, _malla_base("cubo"), None, padre); o.location = pos; o.scale = medio
    return _con_mat(o, mat)


def _con_mat(o, mat):
    """Material por objeto sobre una malla compartida (miles de piezas sin duplicar mallas)."""
    o.material_slots[0].link = "OBJECT"; o.material_slots[0].material = mat; return o


def esfera(nombre, pos, r, mat, padre=None):
    o = _obj(nombre, _malla_base("esfera"), None, padre); o.location = pos; o.scale = (r, r, r); return _con_mat(o, mat)


def cilindro(nombre, pos, radio, alto, mat, padre=None, rot=(0, 0, 0)):
    o = _obj(nombre, _malla_base("cil"), None, padre); o.location = pos; o.scale = (radio, radio, alto / 2); o.rotation_euler = rot
    return _con_mat(o, mat)


def torneado(nombre, perfil, mat, pos=(0, 0, 0), seg=96, padre=None):
    """Pieza de revolución alrededor de Z. perfil = [(radio, z), ...] cerrado (lentes, tazones, anillos, imanes)."""
    vs, fs, n = [], [], len(perfil)
    for i in range(seg):
        a = 2 * math.pi * i / seg; ca, sa = math.cos(a), math.sin(a)
        vs += [(r * ca, r * sa, z) for r, z in perfil]
    for i in range(seg):
        j = (i + 1) % seg
        for k in range(n):
            k2 = (k + 1) % n; fs.append((i * n + k, j * n + k, j * n + k2, i * n + k2))
    me = bpy.data.meshes.new(nombre); me.from_pydata(vs, [], fs); me.update()
    o = _obj(nombre, me, mat, padre); o.location = pos; _suave(o); return o


def texto3d(nombre, txt, pos, tam, mat, rot=(math.pi / 2, 0, 0), padre=None):
    cu = bpy.data.curves.new(nombre, "FONT"); cu.body = txt; cu.size = tam; cu.align_x = "CENTER"; cu.align_y = "CENTER"
    for f in FUENTES:
        if os.path.exists(f): cu.font = bpy.data.fonts.load(f, check_existing=True); break
    cu.extrude = tam * 0.04
    o = _obj(nombre, cu, mat, padre); o.location = pos; o.rotation_euler = rot; return o


def curva(nombre, n, grosor, mat):
    cu = bpy.data.curves.new(nombre, "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = grosor; cu.bevel_resolution = 3
    sp = cu.splines.new("POLY"); sp.points.add(n - 1); o = _obj(nombre, cu, mat); return o


def poner_curva(o, pts):
    sp = o.data.splines[0]; n = len(sp.points)
    if not pts: o.hide_render = True; return
    o.hide_render = False
    for i in range(n):
        p = pts[min(i, len(pts) - 1)]; sp.points[i].co = (*p, 1)


def luz(tipo, pos, energia, color=(1, 1, 1), tam=1.0, objetivo=None):
    ld = bpy.data.lights.new("luz", tipo); ld.energy = energia; ld.color = color
    if tipo == "AREA": ld.size = tam
    else: ld.shadow_soft_size = tam
    l = _obj("luz", ld); l.location = pos
    if objetivo is not None:
        d = Vector(objetivo) - Vector(pos); l.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return l


def iluminacion_estudio(centro, d, fuerza=1.0, frente=-1):
    """Las 4 luces del look premium alrededor de 'centro', a distancia ~d; la cámara mira desde y = frente·∞."""
    c = Vector(centro); e = fuerza * 900 * (d / 10) ** 2; f = frente
    luz("AREA", c + Vector((-0.65 * d, 0.8 * d * f, 0.65 * d)), e, (1.0, 0.95, 0.88), 0.55 * d, c)        # principal cálida
    luz("AREA", c + Vector((0.75 * d, -0.45 * d * f, 0.5 * d)), e * 0.9, (0.55, 0.70, 1.0), 0.4 * d, c)   # contraluz azul
    luz("AREA", c + Vector((0.6 * d, 0.7 * d * f, -0.3 * d)), e * 0.25, (1.0, 0.85, 0.75), 0.5 * d, c)    # relleno bajo
    luz("AREA", c + Vector((0, -0.1 * d * f, 1.1 * d)), e * 0.3, (0.9, 0.95, 1.0), 0.6 * d, c)            # cenital


def onda_en_camino(puntos, t, amp, longitud, vel, crecer=1.0, eje=(0, 1, 0)):
    """Puntos 3D (en el plano XZ, y fija) de una onda senoidal que viaja por una poligonal."""
    segs = list(zip(puntos[:-1], puntos[1:])); total = sum(math.dist(a, b) for a, b in segs); lim = total * crecer
    out, s0 = [], 0.0
    for a, b in segs:
        L = math.dist(a, b); nx, nz = -(b[1] - a[1]) / L, (b[0] - a[0]) / L; n = max(2, int(L / longitud * 24))
        for i in range(n + 1):
            s = s0 + L * i / n
            if s > lim: return out
            u = i / n; y = amp * math.sin(2 * math.pi * s / longitud - vel * t)
            out.append((a[0] + (b[0] - a[0]) * u + nx * y, a[1] + (b[1] - a[1]) * u + nz * y))
        s0 += L
    return out


ANIM = {}           # referencias a lo que se mueve en actualizar(t)
SOLO_LUZ = []       # objetos de luz/transparencia que se ocultan en Workbench


# ================================================================ EJEMPLO: MICROONDAS
ORIGENES = {"A": (0, 0, 0), "B": (1000, 0, 0), "B2": (1500, 0, 0), "C": (2000, 0, 0)}


def construir_set_A(o):
    """Cocina de noche + microondas (1 u = 1 cm). Frente del horno hacia -y."""
    o = Vector(o); rnd = random.Random(3)
    # --- cocina
    pared = material_azulejo("A_azulejo", (0.13, 0.23, 0.25), (0.08, 0.1, 0.1), 0.11)
    caja("A_pared", o + Vector((0, 40, 60)), (260, 1, 110), pared)
    caja("A_cubierta", o + Vector((0, 0, -2)), (220, 40, 2), material_ruido("A_piedra", (0.62, 0.6, 0.56), (0.82, 0.8, 0.76), 0.12, 0.25), bisel=0.6)
    madera = material_veta("A_madera", (0.22, 0.12, 0.06), (0.36, 0.21, 0.11))
    caja("A_bajos", o + Vector((0, 2, -50)), (220, 36, 46), madera)
    tirador = material("A_tirador", (0.8, 0.78, 0.72), metal=1, rugosidad=0.2)
    for k in range(-4, 5):
        x = k * 48; caja(f"A_puertab{k}", o + Vector((x, -34.6, -48)), (22, 0.8, 40), madera, bisel=0.8)
        caja(f"A_tirb{k}", o + Vector((x + 12, -35.8, -14)), (5, 0.6, 0.6), tirador, bisel=0.3)
        caja(f"A_alto{k}", o + Vector((x, 26, 92)), (23, 14, 30), madera, bisel=0.8)
        caja(f"A_tira{k}", o + Vector((x + 12, 11.4, 66)), (5, 0.6, 0.6), tirador, bisel=0.3)
    caja("A_ventana", o + Vector((-110, 39, 52)), (28, 0.5, 26), material_emision("A_noche", (0.08, 0.1, 0.35), 1.2)[0])
    marco = material("A_marco", (0.25, 0.17, 0.1), rugosidad=0.5)
    for dx, dz, sx, sz in ((0, 27, 30, 1.4), (0, -27, 30, 1.4), (-29, 0, 1.4, 28), (29, 0, 1.4, 28), (0, 0, 30, 0.8), (0, 0, 0.8, 28)):
        caja("A_mv", o + Vector((-110 + dx, 38, 52 + dz)), (sx, 1.5, sz), marco)
    esfera("A_luna", o + Vector((-120, 38.3, 66)), 3, material_emision("A_luna", (1.0, 0.97, 0.85), 6)[0])
    # lámpara colgante
    cilindro("A_cable", o + Vector((0, 5, 150)), 0.3, 90, material("A_negro", (0.02, 0.02, 0.02)))
    torneado("A_pantallaL", [(1, 108), (14, 92), (14.5, 92), (1.5, 108.5)], material("A_lampara", (0.06, 0.06, 0.07), metal=0.8, rugosidad=0.3), o + Vector((0, 5, 0)))
    esfera("A_foco", o + Vector((0, 5, 94)), 3, material_emision("A_foco", (1.0, 0.85, 0.6), 30)[0])
    luz("POINT", o + Vector((0, 5, 90)), 2.5e5, (1.0, 0.8, 0.55), 4)
    # utilería: maceta con planta y tetera
    torneado("A_maceta", [(0.01, 0), (6, 0), (7.5, 14), (6.8, 14), (5.4, 1), (0.01, 1)], material("A_barro", (0.6, 0.27, 0.16), rugosidad=0.6), o + Vector((-55, 5, 0)))
    hoja = material("A_hoja", (0.12, 0.45, 0.16), rugosidad=0.45, capa=0.3)
    for k in range(14):
        a = rnd.uniform(0, 6.28); h = rnd.uniform(14, 34); r = rnd.uniform(1, 7)
        e = esfera("A_hojaP", o + Vector((-55 + r * math.cos(a), 5 + r * math.sin(a), h)), 1, hoja); e.scale = (4, 1.2, 2.2); e.rotation_euler = (rnd.uniform(-.6, .6), 0, a)
    torneado("A_tetera", [(0.01, 0), (9, 0), (11, 7), (9, 15), (4, 18), (4, 20), (0.01, 20)], material("A_rojo", (0.7, 0.06, 0.05), rugosidad=0.2, capa=1), o + Vector((52, 6, 0)))
    cilindro("A_pico", o + Vector((63, 6, 11)), 1.3, 12, material("A_rojo2", (0.7, 0.06, 0.05), rugosidad=0.2, capa=1), rot=(0, math.radians(50), 0))
    # --- microondas (60 x 40 x 34 cm), con hueco al frente para la puerta
    acero = material_ruido("A_acero", (0.55, 0.57, 0.6), (0.72, 0.74, 0.77), 2.0, 0.28, metal=0.9)
    cx, cz = 0, 18; Y0 = -20
    for nombre, pos, medio in (("arriba", (0, 0, 35), (30, 20, 1)), ("abajo", (0, 0, 1), (30, 20, 1)), ("atras", (0, 19.5, 18), (30, 0.5, 17)),
                               ("izq", (-29.5, 0, 18), (0.5, 20, 17)), ("der", (29.5, 0, 18), (0.5, 20, 17))):
        caja("A_horno_" + nombre, o + Vector(pos), medio, acero, bisel=0.4)
    for k in range(4): caja("A_pata", o + Vector((-26 + (k % 2) * 52, -16 + (k // 2) * 32, -0.2)), (1.5, 1.5, 0.6), material("A_goma", (0.02, 0.02, 0.02)))
    esmalte = material("A_esmalte", (0.75, 0.68, 0.52), rugosidad=0.45)
    for nombre, pos, medio in (("fondo", (-8, 17, 18), (15, 0.3, 15)), ("piso", (-8, 0, 2.2), (15, 17, 0.3)), ("techo", (-8, 0, 33.8), (15, 17, 0.3)),
                               ("li", (-23, 0, 18), (0.3, 17, 15)), ("ld", (7, 0, 18), (0.3, 17, 15))):
        caja("A_cav_" + nombre, o + Vector(pos), medio, esmalte)
    luz("POINT", o + Vector((-8, -4, 30)), 3500, (1.0, 0.82, 0.5), 2)                                      # foco interior
    luz("POINT", o + Vector((20, -12, 22)), 1500, (1.0, 0.9, 0.8), 3)                                       # luz del compartimento del panel
    marco_f = material("A_marcof", (0.05, 0.05, 0.055), rugosidad=0.3, capa=0.6)
    for nombre, pos, medio in (("fa", (-8, Y0 + 0.5, 34.4), (16, 0.6, 1.6)), ("fb", (-8, Y0 + 0.5, 1.6), (16, 0.6, 1.6)),
                               ("fi", (-24.4, Y0 + 0.5, 18), (1.6, 0.6, 17.5))):
        caja("A_" + nombre, o + Vector(pos), medio, marco_f, bisel=0.3)
    # puerta: marco negro + lámina perforada (se vuelve transparente en la línea 7)
    malla, opac = material_malla("A_malla"); ANIM["puerta_opac"] = opac
    puerta = caja("A_puerta", o + Vector((-8, Y0 - 0.6, 18)), (15.5, 0.3, 15.5), malla, propia=True); SOLO_LUZ.append(puerta)
    negro_p = material("A_puertam", (0.03, 0.03, 0.035), rugosidad=0.2, capa=1)
    marcos = [caja("A_pm", o + Vector(p_), m_, negro_p, bisel=0.4) for p_, m_ in (
        ((-8, Y0 - 0.9, 33.6), (16.6, 0.6, 1.6)), ((-8, Y0 - 0.9, 2.4), (16.6, 0.6, 1.6)),
        ((-23.4, Y0 - 0.9, 18), (1.6, 0.6, 16.8)), ((7.4, Y0 - 0.9, 18), (1.6, 0.6, 16.8)))]
    manija = caja("A_manija", o + Vector((9.3, Y0 - 2.6, 18)), (0.8, 1.2, 10), material("A_cromo", (0.9, 0.9, 0.92), metal=1, rugosidad=0.12), bisel=0.6)
    ANIM["puerta"] = [puerta, manija] + marcos
    # panel de control (su tapa se vuelve transparente en la línea 3)
    panel = material("A_panel", (0.03, 0.03, 0.035), rugosidad=0.25, capa=0.8); pb = panel.node_tree.nodes["Principled BSDF"]
    _transparente(panel); ANIM["panel_alfa"] = pb.inputs["Alpha"]
    tapa = caja("A_tapa", o + Vector((19.8, Y0 + 0.2, 18)), (9.4, 0.4, 16.6), panel, bisel=0.4)
    piezas_tapa = [tapa]
    piezas_tapa.append(caja("A_display", o + Vector((19.8, Y0 - 0.3, 29.5)), (7, 0.15, 2.6), material("A_lcd", (0.0, 0.02, 0.01), rugosidad=0.1, capa=1)))
    verde = material_emision("A_verde", (0.25, 1.0, 0.45), 8)[0]
    disp = texto3d("A_tiempo", "1:30", o + Vector((19.8, Y0 - 0.5, 29.2)), 3.4, verde); ANIM["display"] = disp; piezas_tapa.append(disp)
    bot = material("A_boton", (0.16, 0.17, 0.19), rugosidad=0.35, capa=0.5)
    for fy in range(4):
        for fx in range(3):
            piezas_tapa.append(caja("A_bt", o + Vector((14.8 + fx * 5, Y0 - 0.4, 23.5 - fy * 3.2)), (2, 0.4, 1.1), bot, bisel=0.4))
    piezas_tapa.append(caja("A_inicio", o + Vector((19.8, Y0 - 0.4, 9.3)), (7, 0.5, 1.4), material("A_go", (0.06, 0.55, 0.22), rugosidad=0.3, capa=0.6), bisel=0.5))
    perilla = torneado("A_perilla", [(0.01, 0), (3.2, 0), (3.2, 2.2), (2.6, 2.8), (0.01, 2.8)], material("A_cromo2", (0.75, 0.76, 0.78), metal=1, rugosidad=0.2),
                       o + Vector((19.8, Y0 - 0.2, 4.6))); perilla.rotation_euler.x = math.pi / 2; piezas_tapa.append(perilla)
    ANIM["tapa_piezas"] = piezas_tapa[1:]
    # lo que hay detrás del panel: magnetrón, guía de onda y transformador
    cobre = material("A_cobre", (0.95, 0.45, 0.25), metal=1, rugosidad=0.25)
    alu = material("A_alu", (0.8, 0.82, 0.85), metal=1, rugosidad=0.3)
    cilindro("A_mag_anodo", o + Vector((20, 0, 22)), 3.2, 6, cobre)
    for k in range(7): caja("A_aleta", o + Vector((20, 0, 19.4 + k * 0.9)), (5.5, 5.5, 0.15), alu)
    caja("A_guia", o + Vector((14, 0, 30.5)), (6.5, 3.5, 1.5), alu, bisel=0.2)
    caja("A_trafo", o + Vector((20, 0, 8)), (5, 5, 4.5), material("A_hierro", (0.08, 0.08, 0.09), metal=0.7, rugosidad=0.4), bisel=0.3)
    torneado("A_bobina", [(3.5, 5), (5.8, 5), (5.8, 11), (3.5, 11)], cobre, o + Vector((20, 0, 0)))
    # plato giratorio, sopa y plato seco
    giro = bpy.data.objects.new("A_giro", None); bpy.context.scene.collection.objects.link(giro); giro.location = o + Vector((-8, 0, 3)); ANIM["giro"] = giro
    torneado("A_platog", [(0.01, 0), (13, 0), (13.3, 0.4), (13, 0.8), (0.01, 0.8)], material("A_vidriog", (0.85, 0.9, 0.95), rugosidad=0.05, transmision=0.9, ior=1.5), padre=giro)
    ceramica = material("A_ceramica", (0.93, 0.92, 0.88), rugosidad=0.2, capa=1)
    torneado("A_tazon", [(0.01, 0.8), (3.2, 0.8), (3.4, 1.3), (5.5, 2.6), (6.8, 4.5), (7.3, 6.5), (7.4, 7.4), (6.9, 7.5), (6.8, 6.4), (6.3, 4.6), (5.0, 3.0), (3.2, 2.0), (0.01, 2.0)], ceramica, (-3.5, 0, 0), padre=giro)
    sopa = material("A_sopa", (0.75, 0.32, 0.06), rugosidad=0.15, capa=0.5, emision=0.0); ANIM["sopa"] = sopa.node_tree.nodes["Principled BSDF"]
    cilindro("A_sopa", (-3.5, 0, 6.4), 6.6, 0.4, sopa, padre=giro)
    plato = material("A_plato", (0.9, 0.9, 0.92), rugosidad=0.25, capa=1); ANIM["plato"] = plato.node_tree.nodes["Principled BSDF"]
    torneado("A_platoseco", [(0.01, 0.8), (5.5, 0.8), (7, 1.7), (6.6, 1.8), (5.2, 1.2), (0.01, 1.2)], plato, (6.5, 0, 0), padre=giro)
    # vapor, onda en la cavidad y onda frente a la rejilla
    vap = material_emision("A_vapor", (1, 1, 1), 1.5, 0.0); ANIM["vapor_mx"] = vap[2]
    ANIM["vapor"] = [esfera(f"A_vap{k}", (0, 0, 0), 1, vap[0]) for k in range(16)]; SOLO_LUZ.extend(ANIM["vapor"])
    amarillo = material_emision("A_onda", (1.0, 0.75, 0.2), 25)[0]
    ANIM["onda_cav"] = curva("A_ondacav", 500, 0.25, amarillo); ANIM["onda_rej"] = curva("A_ondarej", 160, 0.12, amarillo)
    SOLO_LUZ.extend([ANIM["onda_cav"], ANIM["onda_rej"]])
    blanco = material_emision("A_blanco", (1, 1, 1), 6)[0]
    hx, hz = -8 - 0.125, 18 + 3.375                                  # centro real de un agujero (paso 0.25 cm)
    ANIM["etq"] = [texto3d("A_1mm", "≈ 1.6 mm", o + Vector((hx, Y0 - 1.6, hz - 0.42)), 0.3, blanco),
                   texto3d("A_onda12", "onda ≈ 12 cm", o + Vector((-9.5, Y0 - 1.6, 17.6)), 0.5, material_emision("A_am", (1.0, 0.8, 0.3), 8)[0])]
    aro = torneado("A_aro", [(0.1, -0.015), (0.125, -0.015), (0.125, 0.015), (0.1, 0.015)], blanco, o + Vector((hx, Y0 - 1.5, hz)), seg=48)
    aro.rotation_euler.x = math.pi / 2; ANIM["etq"].append(aro)
    iluminacion_estudio(o + Vector((0, 0, 18)), 110, 1.0)


def construir_set_B(o):
    """Magnetrón de lado (1 u = 1 mm): ánodo de cobre, aletas, imanes N/S, antena y caja de filtro."""
    o = Vector(o)
    cobre = material("B_cobre", (0.95, 0.45, 0.25), metal=1, rugosidad=0.22)
    alu = material_ruido("B_alu", (0.7, 0.72, 0.75), (0.85, 0.87, 0.9), 3, 0.3, metal=1)
    ferrita = material_ruido("B_ferrita", (0.08, 0.08, 0.09), (0.16, 0.16, 0.17), 4, 0.5, metal=0.3)
    cilindro("B_anodo", o, 4.5, 8, cobre)
    for k in range(5):                                                       # cavidades vistas por una ventana de corte
        caja("B_cav", o + Vector((-3 + k * 1.5, -4.4, 0)), (0.3, 0.3, 2.6), material("B_osc", (0.12, 0.04, 0.01), rugosidad=0.6))
    for s in (-1, 1):
        for k in range(7): caja("B_aleta", o + Vector((s * 8, 0, -3 + k * 1.0)), (3.6, 5, 0.17), alu, bisel=0.05)
    ANIM["imanes"] = []
    for s, letra, col in ((1, "N", (0.9, 0.15, 0.1)), (-1, "S", (0.15, 0.35, 0.95))):
        g = bpy.data.objects.new("B_iman" + letra, None); bpy.context.scene.collection.objects.link(g); g.location = o + Vector((0, 0, s * 5.5))
        torneado("B_ferr" + letra, [(2, -1.1), (6, -1.1), (6, 1.1), (2, 1.1)], ferrita, padre=g)
        for zb in (-1.0, 1.0):
            torneado("B_borde" + letra, [(5.9, zb - 0.1), (6.1, zb - 0.1), (6.1, zb + 0.1), (5.9, zb + 0.1)], material_emision("B_b" + letra, col, 4)[0], padre=g)
        texto3d("B_letra" + letra, letra, (0, -6.1, 0), 1.6, material_emision("B_l" + letra, col, 6)[0], padre=g)
        ANIM["imanes"].append((g, s))
    ant = bpy.data.objects.new("B_antena", None); bpy.context.scene.collection.objects.link(ant); ant.parent = ANIM["imanes"][0][0]
    cromo = material("B_cromo", (0.9, 0.9, 0.92), metal=1, rugosidad=0.12)
    cilindro("B_vara", (0, 0, 2.8), 0.4, 3.6, cromo, padre=ant)
    torneado("B_domo", [(0.01, 0), (1.8, 0), (1.4, 1.0), (0.01, 1.4)], cromo, (0, 0, 4.4), padre=ant); ANIM["antena"] = ant
    caja("B_filtro", o + Vector((0, 0, -10)), (6, 5, 2.6), alu, bisel=0.3)
    oro = material("B_oro", (1.0, 0.75, 0.35), metal=1, rugosidad=0.25)
    for x in (-2.5, 2.5): cilindro("B_term", o + Vector((x, 0, -13.5)), 0.5, 2, oro)
    azul = material_emision("B_campo", (0.2, 0.45, 1.0), 2.0, 0.0); ANIM["campo_mx"] = azul[2]
    ANIM["campo"] = [cilindro("B_linea", o + Vector((x, -4.8, 0)), 0.07, 1, azul[0]) for x in (-3, 0, 3)]; SOLO_LUZ.extend(ANIM["campo"])
    amar = material_emision("B_ondas", (1.0, 0.75, 0.2), 12, 1.0); ANIM["ondas_mx"] = amar[2]
    ANIM["ondas"] = [torneado(f"B_anillo{k}", [(1, -0.08), (1.12, -0.08), (1.12, 0.08), (1, 0.08)], amar[0], seg=64) for k in range(5)]
    SOLO_LUZ.extend(ANIM["ondas"])
    rejilla = material_emision("B_rej", (0.12, 0.25, 0.5), 1.2, 0.35)[0]                       # fondo técnico: cuadrícula
    for k in range(-15, 16):
        caja("B_gx", o + Vector((k * 4, 30, 0)), (0.05, 0.05, 70), rejilla); caja("B_gz", o + Vector((0, 30, k * 4)), (70, 0.05, 0.05), rejilla)
    caja("B_piso", o + Vector((0, 0, -15)), (80, 80, 0.3), material("B_piso", (0.02, 0.025, 0.04), rugosidad=0.3, capa=0.5))
    iluminacion_estudio(o, 32)


def construir_set_B2(o):
    """Ánodo visto desde arriba (1 u = 1 mm): 8 cavidades, cátodo incandescente y 4 rayos de electrones."""
    o = Vector(o)
    cobre = material("B2_cobre", (0.95, 0.45, 0.25), metal=1, rugosidad=0.2)
    an = cilindro("B2_anodo", o + Vector((0, 0, -1)), 4.6, 2, cobre)
    cortes = []
    for k in range(8):
        a = 2 * math.pi * k / 8
        cortes.append(cilindro("B2_c", o + Vector((3.1 * math.cos(a), 3.1 * math.sin(a), -1)), 0.55, 3, None))
        r = caja("B2_r", o + Vector((2.35 * math.cos(a), 2.35 * math.sin(a), -1)), (0.75, 0.16, 1.5), None); r.rotation_euler.z = a; cortes.append(r)
    cortes.append(cilindro("B2_bore", o + Vector((0, 0, -1)), 1.9, 3, None))
    for c in cortes:
        md = an.modifiers.new("hueco", "BOOLEAN"); md.object = c; md.operation = "DIFFERENCE"; c.hide_render = True; c.hide_viewport = True
    caja("B2_fondo", o + Vector((0, 0, -2.2)), (6, 6, 0.1), material("B2_fondo", (0.05, 0.02, 0.01), rugosidad=0.6))
    torneado("B2_iman", [(4.7, -2.2), (6.5, -2.2), (6.5, -0.3), (4.7, -0.3)], material("B2_ferr", (0.1, 0.1, 0.11), rugosidad=0.5), o)
    cilindro("B2_catodo", o + Vector((0, 0, -0.6)), 0.5, 2.2, material_emision("B2_cat", (1.0, 0.45, 0.1), 25)[0])
    luz("POINT", o + Vector((0, 0, 0.5)), 60, (1.0, 0.5, 0.2), 0.3)
    azul = material_emision("B2_e", (0.4, 0.75, 1.0), 40)[0]
    ANIM["electrones"] = [esfera("B2_el", o, 0.13, azul) for _ in range(36)]; SOLO_LUZ.extend(ANIM["electrones"])
    caja("B2_piso", o + Vector((0, 0, -2.6)), (60, 60, 0.2), material_ruido("B2_mesa", (0.02, 0.03, 0.05), (0.05, 0.07, 0.1), 0.5, 0.4))
    iluminacion_estudio(o, 16, 0.8)


MOLS = []
def construir_set_C(o):
    """Moléculas de agua (1 u ≈ 1 Å): oxígeno rojo, dos hidrógenos, flechas del campo y fondo que se calienta."""
    o = Vector(o); rnd = random.Random(5)
    oxi = material("C_O", (0.8, 0.07, 0.05), rugosidad=0.25, capa=1); hid = material("C_H", (0.92, 0.93, 0.95), rugosidad=0.25, capa=1)
    def mol(pos, esc=1.0):
        g = bpy.data.objects.new("C_mol", None); bpy.context.scene.collection.objects.link(g); g.location = pos; g.scale = (esc,) * 3
        esfera("C_o", (0, 0, 0), 0.55, oxi, padre=g)
        for s in (-1, 1):
            a = math.radians(90 + s * 52); esfera("C_h", (0.62 * math.cos(a), 0, 0.62 * math.sin(a)), 0.33, hid, padre=g)
        return g
    ANIM["mol0"] = mol(o)
    for x in range(-5, 6):
        for z in range(-8, 9):
            for capa, yy in ((0, 0.0), (1, 4.5)):
                if capa == 0 and abs(x) <= 0 and abs(z) <= 0: continue
                p = o + Vector((x * 2.6 + rnd.uniform(-0.5, 0.5), yy + rnd.uniform(-0.6, 0.6), z * 2.6 + rnd.uniform(-0.5, 0.5)))
                MOLS.append((mol(p), p.copy(), rnd.uniform(0, 6.28), rnd.uniform(0.6, 1.4)))
    signo = material_emision("C_signos", (1, 1, 1), 5)[0]
    ANIM["signos"] = [texto3d("C_mas", "+", (0, 0, 0), 0.55, material_emision("C_az", (0.3, 0.7, 1.0), 8)[0]),
                      texto3d("C_mas2", "+", (0, 0, 0), 0.55, material_emision("C_az2", (0.3, 0.7, 1.0), 8)[0]),
                      texto3d("C_menos", "−", (0, 0, 0), 0.8, material_emision("C_rj", (1.0, 0.35, 0.3), 8)[0])]
    flecha = material_emision("C_flecha", (0.3, 0.5, 1.0), 2.5, 0.35); ANIM["flecha_mx"] = flecha[2]
    ANIM["flechas"] = []
    for x in range(-12, 13, 6):
        g = bpy.data.objects.new("C_fl", None); bpy.context.scene.collection.objects.link(g); g.location = o + Vector((x, 9, 0))
        cilindro("C_fc", (0, 0, -2), 0.5, 18, flecha[0], padre=g)
        c = _obj("C_fp", _malla_base("cono"), None, g); c.location = (0, 0, 8); c.scale = (1.6, 1.6, 1.8); _con_mat(c, flecha[0])
        ANIM["flechas"].append(g); SOLO_LUZ.append(g)
    fondo = material_fondo_radial("C_fondo", 22); ANIM["fondo_C"] = fondo.node_tree.nodes["centro"]
    caja("C_fondo", o + Vector((0, 40, 0)), (120, 0.5, 120), fondo, propia=True)
    bok = material_emision("C_bokeh", (0.4, 0.6, 1.0), 3)[0]; ANIM["bokeh_em"] = bok.node_tree.nodes["Emission"]
    for k in range(30):
        esfera("C_bok", o + Vector((rnd.uniform(-30, 30), rnd.uniform(14, 30), rnd.uniform(-40, 40))), rnd.uniform(0.3, 1.0), bok)
    chispa = material_emision("C_chispa", (1.0, 0.6, 0.2), 30)[0]
    ANIM["chispas"] = [esfera("C_ch", o, 0.35, chispa) for _ in range(10)]; SOLO_LUZ.extend(ANIM["chispas"])
    iluminacion_estudio(o, 30, 0.8)


# Planos: (set, inicio=(linea, palabra|None), cam_ini, cam_fin, obj_ini, obj_fin, lente_mm, fstop). Coordenadas relativas al set.
TOMAS = [
    ("A", (1, None), (-40, -220, 55), (-16, -125, 30), (-5, 0, 16), (-7, 0, 14), 50, 4.0),
    ("A", (2, None), (-12, -56, 26), (-12, -42, 22), (-10, 0, 7), (-11, 0, 7), 50, 1.4),
    ("A", (3, None), (30, -78, 24), (24, -52, 20), (19, 0, 18), (19, 0, 18), 50, 2.0),
    ("B", (4, None), (12, -52, 8), (9, -42, 5), (0, 0, 0), (0, 0, 1), 50, 1.0),
    ("B2", (5, None), (0, -7, 26), (0, -5, 18), (0, 0, -0.5), (0, 0, -0.5), 50, 0.8),
    ("B", (6, None), (7, -32, 16), (9, -44, 22), (0, 0, 12), (0, 0, 15), 50, 1.0),
    ("A", (7, None), (-2, -120, 26), (-4, -105, 22), (-4, 0, 17), (-5, 0, 17), 50, 2.8),
    ("C", (8, None), (0, -9, 0.3), (0, -7.6, 0.2), (0, 0, 0), (0, 0, 0), 50, 0.25),
    ("C", (9, None), (0, -30, 0), (0, -38, 0), (0, 0, 0), (0, 0, 0), 50, 0.6),
    ("C", (10, None), (0, -38, 0), (0, -25, 0), (0, 0, 0), (0, 0, 0), 50, 0.5),
    ("A", (11, None), (-6, -50, 24), (-7, -40, 21), (-7, 0, 7), (-7, 0, 7), 50, 1.4),
    ("A", (12, None), (-9.5, -34, 20.3), (-9.5, -40, 20.3), (-9.5, -20, 20.3), (-9.5, -20, 20.3), 50, 1.2),
    ("A", (12, "por"), (-12, -80, 24), (-40, -220, 55), (-8, 0, 18), (-5, 0, 16), 50, 4.0),   # regreso al plano inicial -> loop
]
INICIOS = [T(*t[1]) for t in TOMAS] + [DUR]


def camara():
    cd = bpy.data.cameras.new("cam"); cam = _obj("cam", cd); bpy.context.scene.camera = cam
    cd.sensor_fit = "VERTICAL"; cd.sensor_height = cd.sensor_width = 36; cd.clip_start = 0.05; cd.clip_end = 5000
    obj = bpy.data.objects.new("objetivo", None); bpy.context.scene.collection.objects.link(obj)
    c = cam.constraints.new("TRACK_TO"); c.target = obj; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
    cd.dof.use_dof = MOTOR != "workbench"; cd.dof.focus_object = obj; ANIM["cam"] = (cam, obj, cd)


def poner_camara(t):
    cam, obj, cd = ANIM["cam"]
    for k, (s, _, ci, cf, oi, of, lente, fst) in enumerate(TOMAS):
        if t < INICIOS[k + 1] or k == len(TOMAS) - 1:
            a = 0 if (k == 0 and t < INICIOS[0]) else tramo(t, INICIOS[k], INICIOS[k + 1]); o = Vector(ORIGENES[s])
            cam.location = o + Vector(ci).lerp(Vector(cf), a); obj.location = o + Vector(oi).lerp(Vector(of), a)
            cd.lens = lente; cd.dof.aperture_fstop = fst; return s


def actualizar(t):
    """Todo lo animado, en función del segundo t (sincronizado con la voz)."""
    poner_camara(t); oA, oB, oB2, oC = (Vector(ORIGENES[k]) for k in ("A", "B", "B2", "C"))
    wb = MOTOR == "workbench"
    # --- A: puerta, panel, display, plato, vapor, ondas
    corte = ventana(t, T(7) - 0.1, T(8), 0.6); cerca = max(ventana(t, T(2), T(3) + 0.4, 0.5), ventana(t, T(11), T(12), 0.5))
    rej = ventana(t, T(12, "rejilla") - 0.3, T(12, "por") + 0.6, 0.4)
    ANIM["puerta_opac"].outputs[0].default_value = lerp(lerp(0.75, 0.35, cerca), 1.0, rej) * (1 - corte)
    for p in ANIM["puerta"]: p.hide_render = corte > 0.97 or (wb and p.name == "A_puerta" and rej < 0.5)
    tapa = 1 - 0.88 * ventana(t, T(3, "panel"), T(4) + 0.2, 0.8)
    ANIM["panel_alfa"].default_value = tapa
    for p in ANIM["tapa_piezas"]: p.hide_render = tapa < 0.5
    bpy.data.objects["A_tapa"].hide_render = wb and tapa < 0.5
    seg = max(0, 90 - int(t)); ANIM["display"].data.body = f"{seg // 60}:{seg % 60:02d}"
    ANIM["giro"].rotation_euler.z = t * 0.6
    calor = ventana(t, T(11), T(12), 0.6)
    _inp(ANIM["sopa"], ["Emission Color", "Emission"], (1.0, 0.45, 0.1, 1)); _inp(ANIM["sopa"], ["Emission Strength"], 1.2 * calor)
    ANIM["plato"].inputs["Base Color"].default_value = (lerp(0.9, 0.45, calor), lerp(0.9, 0.65, calor), lerp(0.92, 1.0, calor), 1)
    ANIM["vapor_mx"].inputs["Fac"].default_value = 0.035 * calor
    g = ANIM["giro"]; bx = g.matrix_world @ Vector((-3.5, 0, 0))
    for k, v in enumerate(ANIM["vapor"]):
        u = (t * 0.5 + k / 16) % 1; v.location = bx + Vector((2.5 * math.sin(k * 2.1 + t), 2 * math.cos(k * 1.7), 8 + u * 12))
        v.scale = (0.4 + u * 1.4, 0.4 + u * 1.4, 0.8 + u * 2.0); v.hide_render = calor < 0.02 or wb
    if corte > 0.01:
        camino = [(14, 30.5), (6, 30.5), (-21, 22), (-3, 4), (5.5, 25), (-22, 31), (-9, 4)]
        pts = onda_en_camino(camino, t, 0.9, 3.0, 9, crecer=tramo(t, T(7, "lleva"), T(7, "paredes") + 0.5))
        poner_curva(ANIM["onda_cav"], [(oA.x + x, -4, z) for x, z in pts])
    else: ANIM["onda_cav"].hide_render = True
    if rej > 0.01:
        tt = t - T(12, "rejilla"); amp = 2.2 * (1 - 2 * tramo(tt, 1.2, 2.0))
        poner_curva(ANIM["onda_rej"], [(x, -21.6, 20.3 + amp * math.sin(2 * math.pi * x / 12.2 - 3 * tt)) for x in [lerp(-16, -3, i / 159) for i in range(160)]])
    else: ANIM["onda_rej"].hide_render = True
    for e in ANIM["etq"]: e.hide_render = rej < 0.3
    # --- B: imanes que se separan, líneas de campo, ondas de la antena
    sep = tramo(t, T(4, "atrapado") - 0.2, T(4, "imanes") + 0.4) * (1 - tramo(t, T(5, "silban"), T(6)))
    for gobj, s in ANIM["imanes"]: gobj.location = oB + Vector((0, 0, s * (5.5 + 4 * sep)))
    ANIM["campo_mx"].inputs["Fac"].default_value = sep
    for c in ANIM["campo"]: c.scale = (0.07, 0.07, 4.4 + 4 * sep); c.hide_render = sep < 0.05
    a = tramo(t, T(6), T(6) + 0.5) * (1 - tramo(t, T(7), T(7) + 0.3)); ya = 5.5 + 4 * sep + 1.1 + 5.8
    ANIM["ondas_mx"].inputs["Fac"].default_value = a
    for j, r in enumerate(ANIM["ondas"]):
        u = (t * 0.9 + j / 5) % 1; r.location = oB + Vector((0, 0, ya + u * 6)); r.scale = (1 + u * 9, 1 + u * 9, 1); r.hide_render = a < 0.02
    # --- B2: electrones en 4 rayos que giran
    giro = t * 2.2; n = tramo(t, T(5, "electrones"), T(5, "giran") + 0.4)
    for i, e in enumerate(ANIM["electrones"]):
        r_, j = divmod(i, 9); u = j / 8; ang = giro + r_ * math.pi / 2 + u * 1.1; rr = 0.6 + u * 1.2
        e.location = oB2 + Vector((rr * math.cos(ang), rr * math.sin(ang), 0.2)); e.hide_render = u > n
    # --- C: el campo cambia de dirección, el agua intenta girar, choques y calor
    calC = tramo(t, T(10), T(10, "calor") + 0.6)
    campo = math.tanh(3 * math.sin(2 * math.pi * 0.9 * (t - T(9)))) if t >= T(9, "cambian") else 1.0
    act = tramo(t, T(9, "cambian"), T(9, "cambian") + 0.5); obj = 0.0 if campo > 0 else math.pi
    otros = tramo(t, T(9) - 0.3, T(9) + 0.8)
    for k, (gobj, p, a0, vel) in enumerate(MOLS):
        ocultar(gobj, otros < 0.05)
        ang = lerp(a0 + 0.3 * math.sin(t * vel), obj + 0.25 * math.sin(t * 7 * vel + k), act * 0.85)
        gobj.rotation_euler = (0, ang, 0); j = calC * 0.35
        gobj.location = p + Vector((j * math.sin(t * 13 * vel + k), 0, j * math.cos(t * 11 * vel + 2 * k)))
    a0 = lerp(math.radians(25 * math.sin(t)), obj, act * 0.9); ANIM["mol0"].rotation_euler = (0, a0, 0)
    ANIM["mol0"].location = oC + Vector((0.15 * calC * math.sin(t * 20), 0, 0))
    sig = t < T(10) + 1; c0 = ANIM["mol0"].location
    def rot_y(x, z, a): return Vector((x * math.cos(a) + z * math.sin(a), -0.9, -x * math.sin(a) + z * math.cos(a)))
    for k, s in enumerate(ANIM["signos"]):
        if k < 2: aa = math.radians(90 + (-1 if k == 0 else 1) * 52); loc = rot_y(1.2 * math.cos(aa), 1.2 * math.sin(aa), a0)
        else: loc = rot_y(0, -1.05, a0)
        s.location = c0 + loc; s.hide_render = not sig
    fa = tramo(t, T(9), T(9) + 0.6) * abs(campo)
    ANIM["flecha_mx"].inputs["Fac"].default_value = 0.35 * fa
    for f in ANIM["flechas"]: f.rotation_euler = (0, 0 if campo > 0 else math.pi, 0); ocultar(f, fa < 0.03 or wb)
    ANIM["fondo_C"].outputs[0].default_value = (lerp(0.05, 0.45, calC), lerp(0.1, 0.12, calC), lerp(0.3, 0.05, calC), 1)
    ANIM["bokeh_em"].inputs["Color"].default_value = (lerp(0.4, 1.0, calC), lerp(0.6, 0.5, calC), lerp(1.0, 0.2, calC), 1)
    for k, ch in enumerate(ANIM["chispas"]):
        fase = (t * 3 + k * 0.37) % 1; gobj, p, _, _ = MOLS[(k * 7 + int(t * 3)) % len(MOLS)]
        ch.location = p + Vector((0, -0.8, 0)); ch.scale = (0.35 * (1 - fase * 4),) * 3; ch.hide_render = calC < 0.05 or fase > 0.25
    if wb:
        for o in SOLO_LUZ:
            if o.name.startswith(("A_vap", "C_fl")): o.hide_render = True


def fondo_mundo(sc):
    """Degradado radial azul pizarra -> casi negro para la cámara; gris azulado para los reflejos."""
    w = bpy.data.worlds.new("mundo"); sc.world = w; w.use_nodes = True; nt = w.node_tree; bg = nt.nodes["Background"]
    w.color = (0.012, 0.014, 0.02)
    lp = nt.nodes.new("ShaderNodeLightPath"); tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Window"], sep.inputs[0])
    cx = nt.nodes.new("ShaderNodeMath"); cx.operation = "SUBTRACT"; cx.inputs[1].default_value = 0.5; nt.links.new(sep.outputs["X"], cx.inputs[0])
    cy = nt.nodes.new("ShaderNodeMath"); cy.operation = "SUBTRACT"; cy.inputs[1].default_value = 0.55; nt.links.new(sep.outputs["Y"], cy.inputs[0])
    cy2 = nt.nodes.new("ShaderNodeMath"); cy2.operation = "MULTIPLY"; cy2.inputs[1].default_value = 0.62; nt.links.new(cy.outputs[0], cy2.inputs[0])
    v = nt.nodes.new("ShaderNodeCombineXYZ"); nt.links.new(cx.outputs[0], v.inputs[0]); nt.links.new(cy2.outputs[0], v.inputs[1])
    ln = nt.nodes.new("ShaderNodeVectorMath"); ln.operation = "LENGTH"; nt.links.new(v.outputs[0], ln.inputs[0])
    rampa = nt.nodes.new("ShaderNodeValToRGB"); e = rampa.color_ramp.elements
    e[0].position, e[0].color = 0.0, (0.035, 0.045, 0.07, 1); e[1].position, e[1].color = 0.62, (0.004, 0.005, 0.008, 1)
    nt.links.new(ln.outputs["Value"], rampa.inputs[0])
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.inputs["A"].default_value = (0.05, 0.055, 0.07, 1)
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Factor"]); nt.links.new(rampa.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], bg.inputs[0])


def render_config():
    sc = bpy.context.scene; sc.render.fps = FPS; sc.frame_start, sc.frame_end = 0, NF - 1
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1080, 1920, PCT
    if MOTOR == "workbench":
        sc.render.engine = "BLENDER_WORKBENCH"; sh = sc.display.shading
        sh.light = "STUDIO"; sh.color_type = "MATERIAL"; sh.show_shadows = True; sh.show_cavity = True
        sh.cavity_type = "BOTH"; sh.show_specular_highlight = True
        sc.display.render_aa = "8" if SAMPLES >= 8 else "FXAA"
    elif MOTOR == "cycles":
        sc.render.engine = "CYCLES"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
        _set(sc.cycles, use_adaptive_sampling=True, max_bounces=8, transparent_max_bounces=16)
        try:
            pr = bpy.context.preferences.addons["cycles"].preferences
            for tp in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
                try:
                    pr.compute_device_type = tp; pr.get_devices()
                    if any(d.type == tp for d in pr.devices): break
                except Exception: continue
            for d in pr.devices: d.use = True
            sc.cycles.device = "GPU"
        except Exception: pass
    else:
        for e in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
            try: sc.render.engine = e; break
            except TypeError: continue
        ee = sc.eevee
        for k, v in (("taa_render_samples", SAMPLES), ("use_shadows", True), ("use_raytracing", True), ("shadow_ray_count", 2),
                     ("shadow_step_count", 6), ("use_gtao", True), ("use_bloom", True), ("fast_gi_distance", 0.0)):
            _set(ee, **{k: v})
        try:
            ee.ray_tracing_method = "SCREEN"; ee.ray_tracing_options.resolution_scale = "1"; ee.ray_tracing_options.use_denoise = True
        except Exception: pass
    fondo_mundo(sc)
    nombres = [i.identifier for i in sc.view_settings.bl_rna.properties["view_transform"].enum_items]
    sc.view_settings.view_transform = "AgX" if "AgX" in nombres else "Filmic"
    _set(sc.view_settings, look="AgX - Medium High Contrast")
    sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGB"


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    construir_set_A(ORIGENES["A"]); construir_set_B(ORIGENES["B"]); construir_set_B2(ORIGENES["B2"]); construir_set_C(ORIGENES["C"])
    camara(); render_config()
    os.makedirs(OUT, exist_ok=True); sc = bpy.context.scene
    for fr in FRAMES:
        dst = os.path.join(OUT, f"f_{fr:04d}.png")
        if os.path.exists(dst) and not arg("--frames"): continue      # permite reanudar
        sc.frame_set(fr); actualizar(fr / FPS); sc.render.filepath = dst; bpy.ops.render.render(write_still=True)
        print(f"cuadro {fr}/{NF}", flush=True)


main()
