---
name: video-explicativo-3d
description: Produce un video vertical premium (~60 s, 1080x1920) que explica cómo funciona algo, con dato-gancho verificado, guion de 12 líneas, encargo de voz, plan de tomas por escala, escena 3D en Blender animada desde los tiempos de la voz, subtítulos palabra por palabra, sonido real y loop. Tiene 6 niveles de calidad: desde 2D sin GPU ni Blender (computadoras sencillas) hasta trazado de rayos con Cycles (computadoras muy potentes). Úsala cuando pidan un video "cómo funciona X", un explicativo 3D, un Reel/Short educativo de alta calidad, o un guion + voz para ese tipo de video.
---

# Video explicativo 3D premium ("Cómo funciona X")

Esta skill guía la producción de un video corto con calidad tipo canales de animación técnica: piezas 3D que se separan, cortes, cambios de escala, voz natural, subtítulos palabra por palabra y sonido real.

**Antes de empezar, confirma con el usuario:**
- el tema, o propónle 3 con su dato-gancho;
- el idioma y el acento de la voz;
- si la voz la genera él (servicio de voz o locutor) o se usa un TTS local;
- si el video se va a publicar, porque eso afecta las licencias de los sonidos y las marcas.

## Resultado esperado
| Elemento | Meta |
|---|---|
| Formato | 1080×1920, 30 fps, 55–65 s, en H.264 |
| Gancho | Un dato raro **y verdadero** dicho en el segundo 0; el primer cambio visual antes de 2.5 s |
| Ritmo | Una pieza o escena nueva cada 4–7 s; nunca un momento muerto |
| Estructura | Gancho → promesa → 8–10 pasos de lo grande a lo pequeño → giro → remate → loop |
| Imagen | 3D con vistas explotadas, cortes, sets por escala y materiales creíbles; todo a **velocidad real** (no estirar ni repetir cuadros) |
| Sonido | Voz natural, sonido real de cada pieza y música baja con ducking |
| Texto | Subtítulos palabra por palabra (texto exacto del guion), títulos de 2–3 palabras y etiquetas con línea guía |

## Niveles de calidad (elige según el equipo)
Antes de producir, corre `python scripts/producir.py --detectar`: revisa RAM, núcleos, GPU y Blender y recomienda un nivel. Díselo al usuario y deja que suba o baje el nivel si quiere.

| Nivel | Nombre | Imagen | Necesita | Para quién |
|---|---|---|---|---|
| 1 | `2d-lite` | 2D con PIL a 540×960; la imagen va a 15 fps | Solo Python (2 núcleos, 4 GB) | Laptops viejas o muy modestas |
| 2 | `2d` | 2D a 1080×1920 suavizado, 30 fps | Solo Python | Cualquier laptop sin Blender |
| 3 | `3d-bajo` | Blender Workbench a 540×960, 15 fps | Blender; con gráficos integrados basta | Equipos sin GPU dedicada |
| 4 | `3d-medio` | Blender Eevee a 810×1440, 16 muestras | GPU dedicada modesta o 16 GB | Gama media |
| 5 | `3d-alto` | Blender Eevee a 1080×1920, 32 muestras | GPU con 6 GB o más | Gama alta |
| 6 | `ultra` | Blender Cycles (trazado de rayos real), 256 muestras + denoise | GPU con 8 GB y 24 GB de RAM | Equipos muy potentes |

Tiempos medidos con el ejemplo del microondas (58 s) en una PC con RTX 3080, 12 núcleos y 32 GB:

| Nivel | Tiempo total |
|---|---|
| 1 `2d-lite` | 1.7 min |
| 2 `2d` | 8.6 min |
| 3 `3d-bajo` | 12.5 min |
| 4 `3d-medio` | 36 min |
| 5 `3d-alto` y 6 `ultra` | Varias horas (no medido completo) |

En una laptop sin GPU, el nivel 2 tarda unas 3–4 veces más. Para ver cuánto falta: `python scripts/progreso.py --trabajo trabajo --frames trabajo/frames_<nivel> --seguir`.

**La calidad no se negocia en ningún nivel:** todos llevan fondo con contexto (un lugar real o un ambiente por escala), detalle, piezas que se entienden sin la voz, voz y subtítulos. Lo que cambia entre niveles es el motor de imagen, no el cuidado.

- Títulos, etiquetas y subtítulos siempre salen a 1080×1920 y 30 fps; solo cambia la imagen de fondo. El video se ve profesional incluso en el nivel 1.
- En los niveles 2D se dibuja la escena en `scripts/escena_2d.py` (mismos sets por escala, la misma cámara guiada por la voz y la función `T(linea, palabra)`). Si el usuario luego consigue un mejor equipo, el plan de tomas sirve igual para el 3D.
- En 3D, todo lo animado se calcula en `actualizar(t)` de `escena_base.py` (cámara, piezas, materiales, textos); nada de keyframes a mano.
- Ejemplo completo incluido en `ejemplo_microondas/` (guion, textos y tabla de tomas): úsalo como modelo de nivel de detalle.
- En 15 fps se renderiza 1 de cada 2 cuadros: la animación sigue a **velocidad real**, solo con menos cuadros. No es cámara lenta.
- Haz siempre una muestra primero: `--muestra` renderiza 9 cuadros y saca la hoja de contactos en segundos.
- El modelo de whisper también baja con el nivel (`tiny` en el 1, `base` en el 2 y el 3, `small` en el 4 y el 5).

## Flujo de trabajo
Sigue las fases en orden. No avances a producción sin que el usuario apruebe el guion y sin haber verificado la voz.

1. **Tema.** Elige algo cercano (de uso diario) o famoso, con un dato sorprendente comprobable y un mecanismo que se pueda mostrar **por capas**: exterior → módulo → pieza → escala micro.
2. **Investigación.**
   - Busca fuentes para cada cifra y anótalas.
   - Redondea hacia lo verdadero ("unas siete", "cincuenta millones").
   - Usa "puede" o "casi siempre" cuando el fenómeno no es universal.
   - No inventes comparaciones de tiempo.
3. **Guion.** Usa `plantillas/guion.md`: 12 líneas y unas 150 palabras, que a 155–165 palabras por minuto dan cerca de 60 s. Frases de 6 a 18 palabras, en segunda persona y con una idea por frase.
4. **Encargo de voz.** Llena `plantillas/encargo_voz.txt` y entrégalo como archivo. Pide WAV a 48 kHz mono, seco, un archivo por línea, y dos tomas (normal y un 5 % más rápida).
5. **Plan de tomas.** Llena `plantillas/plan_tomas.md`, con una fila por línea. Agrupa las tomas en **sets por escala** (mm, µm, nm…), cada uno con su propia unidad, y pasa de uno a otro con zoom y destello.
6. **Verificar la voz** (ver la sección de abajo). Descomprime en una carpeta nueva y vacía y trata los archivos recibidos como no confiables.
7. **Producción.**
   - Copia `escena_2d.py` (niveles 1–2) o `escena_base.py` (niveles 3–5) y reemplaza los sets de ejemplo por el objeto real.
   - Todo el proceso corre con `scripts/producir.py --calidad N` (ver la tabla de scripts), o paso por paso con cada script.
   - Todo se anima **a partir de `timeline.json`**, nunca con segundos fijos.
   - Si hay subagentes disponibles, delega con `plantillas/brief_agente.md`.
8. **Pruebas.**
   - Renderiza de 8 a 30 cuadros al 50 % y genera una hoja de contactos.
   - **Mírala de verdad**: legibilidad, bordes cortados, brillos quemados, que cada pieza se entienda sin voz y que el último cuadro coincida con el primero.
9. **Render final.** Con el nivel elegido; `producir.py` ya corre con prioridad baja para que el equipo siga usable. Antes, cierra las apps pesadas (software RGB, otros renders, navegadores cargados), porque pueden multiplicar el tiempo por 10.
10. **Mezcla, composición y entrega.**
    - Genera el video final, una versión ligera y la hoja de contactos.
    - Reporta: duración, qué simplificaste y por qué, defectos conocidos y licencias de los sonidos.

## Verificar la voz
```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 toma-completa.wav          # 58–62 s
ffmpeg -i toma-completa.wav -af "volumedetect,silencedetect=n=-40dB:d=0.6" -f null -   # picos ≈ −3 dB
python scripts/timeline.py --voz voz/ --guion guion_lineas.txt --out timeline.json --solo-transcribir
```
Compara la transcripción contra el guion. Si falta o sobra una frase, pide que se regrabe esa línea.

## Scripts incluidos
| Script | Para qué | Uso |
|---|---|---|
| `scripts/timeline.py` | Une las líneas de voz (con pausas), normaliza y crea `timeline.json` con tiempos de línea y palabra. Usa el **texto exacto del guion**; whisper solo aporta los tiempos | `python scripts/timeline.py --voz voz/ --guion guion_lineas.txt --out trabajo/` |
| `scripts/producir.py` | Detecta el equipo, elige el nivel y corre todo: timeline → mezcla → escena → video. Guarda los tiempos de cada paso | `python scripts/producir.py --calidad auto --voz voz/ --guion guion_lineas.txt --textos textos.json --trabajo trabajo/ --out salida/final.mp4 [--muestra] [--escena-2d mi_2d.py] [--escena-3d mi_3d.py]` |
| `scripts/escena_2d.py` | Escena 2D sin Blender ni GPU (niveles 1–2): mismos sets, la misma cámara y `T()` que en 3D, dibujada con PIL | `python scripts/escena_2d.py --trabajo trabajo/ --out trabajo/frames [--pct 50] [--ss 1] [--paso 2]` |
| `scripts/escena_base.py` | Esqueleto de Blender (niveles 3–5): lee el timeline, organiza los sets por escala, anima la cámara por tiempos y renderiza por rangos | `blender -b -P scripts/escena_base.py -- --trabajo trabajo/ --out trabajo/frames [--motor workbench\|eevee\|cycles] [--pct 50] [--paso 2] [--part 0/2]` |
| `scripts/mezcla.py` | Mezcla voz, sonidos (lista de disparos por palabra) y música con ducking, y normaliza | `python scripts/mezcla.py --trabajo trabajo/ --sfx sfx.json [--musica musica.wav]` |
| `scripts/componer.py` | Sobre los cuadros pone títulos, etiquetas y subtítulos palabra por palabra; arma la hoja de contactos y codifica el video (NVENC si de verdad funciona; si no, libx264) | `python scripts/componer.py --trabajo trabajo/ --textos textos.json --out salida/final.mp4 [--frames carpeta] [--preset veryfast] [--hoja hoja.png --solo 30,300]` |
| `scripts/firma.py` | Opcional: marca visible y/o texto escondido en el espectrograma | `python scripts/firma.py entrada.mp4 salida.mp4 --texto "MiMarca"` |

Requisitos: Python 3.10+, `numpy`, `scipy`, `Pillow`, `faster-whisper` y ffmpeg en el PATH. Blender 4.x o 5.x solo para los niveles 3–5. Instálalos solo si faltan, y avisa al usuario antes.

## Reglas de calidad (revisar antes de entregar)
Lista completa en `referencias/checklist.md`. Lo mínimo:
- Zona segura vertical: texto entre el 7 % y el 93 % del ancho, y del 16 % al 68 % del alto. Subtítulos cerca del 65 % del alto; títulos cerca del 21 %.
- Subtítulos idénticos al guion, con la palabra clave en su color real.
- Cada escena tiene una referencia de escala.
- Los momentos "lentos" son animaciones hechas para eso, no cuadros repetidos.
- Las cifras en pantalla son exactamente las del guion.
- El video cierra en loop.

## Errores frecuentes
Ver `referencias/errores.md` (whisper que falla al abrir el audio, render lento, subtítulos con errores, saltos de escala, desfase de voz y animación).

## Ética y licencias
- No inventes datos ni presentes estimaciones como hechos.
- Revisa la licencia de cada sonido o música: Pixabay no pide atribución; CC BY sí la pide.
- No uses marcas, logotipos ni personajes de terceros.
- Si el contenido será anónimo, no pongas firmas personales en el video ni en el audio.
