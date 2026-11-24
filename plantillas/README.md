# Skill: video-explicativo-3d

Skill para Claude Code / Claude que produce videos verticales explicativos en 3D ("Cómo funciona X") de ~60 s.

## Instalar
- Solo para ti: copia la carpeta `video-explicativo-3d/` a `~/.claude/skills/`
- Para un proyecto: cópiala a `<proyecto>/.claude/skills/`
- En claude.ai: Configuración → Capacidades → Skills → subir este .zip

## Requisitos
Python 3.10+ con `pip install numpy scipy pillow faster-whisper` y ffmpeg en el PATH. Blender 4.x o 5.x es opcional: sin Blender se usan los niveles 2D.

## Niveles de calidad
`python scripts/producir.py --detectar` recomienda uno según tu equipo.

| Nivel | Imagen | Necesita |
|---|---|---|
| 1 `2d-lite` | 2D, 540×960, 15 fps | Solo Python |
| 2 `2d` | 2D, 1080×1920, 30 fps | Solo Python |
| 3 `3d-bajo` | Blender Workbench, 540×960, 15 fps | Blender (gráficos integrados) |
| 4 `3d-medio` | Blender Eevee, 810×1440 | GPU dedicada modesta |
| 5 `3d-alto` | Blender Eevee, 1080×1920, 32 muestras | GPU de 6 GB o más |
| 6 `ultra` | Blender Cycles, 256 muestras + denoise | GPU de 8 GB y 24 GB de RAM |

## Uso
Pídele a Claude: "Hazme un video de cómo funciona una licuadora". La skill se activa sola y sigue las fases de `SKILL.md`.

## Contenido
- `SKILL.md`: flujo completo (tema → guion → voz → plan de tomas → 3D → mezcla → composición)
- `plantillas/`: guion de 12 líneas, encargo de voz, plan de tomas, brief para agente
- `referencias/`: checklist de calidad y errores frecuentes
- `ejemplo_microondas/`: ejemplo completo (guion, textos, tabla de tomas) con el que se probaron los 6 niveles
- `scripts/`: producir.py (todo en un comando), timeline.py, escena_2d.py, escena_base.py, mezcla.py, componer.py, firma.py (probados)
