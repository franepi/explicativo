# Brief para el agente de producción (copiar y completar)

Eres el agente de producción de un video explicativo 3D vertical (~60 s). Lee primero:
- `SKILL.md` y `referencias/checklist.md` de la skill **video-explicativo-3d**;
- `<proyecto>/guion.md`: guion, fuentes y plan de tomas.

**Insumos**
- La voz ya está grabada en `<proyecto>/voz/01.wav … 12.wav`. Úsala tal cual: sin TTS y sin efectos, solo normalizar.
- Las líneas exactas del guion están en `<proyecto>/guion_lineas.txt`.

**Qué haces**
1. Corre `scripts/timeline.py` para obtener `trabajo/timeline.json` y `trabajo/voz.wav`.
2. Copia `scripts/escena_base.py` a `<proyecto>/escena.py` y construye los sets de la tabla de tomas. Usa piezas modeladas con detalle y materiales creíbles, y anima todo a partir del timeline (`T(linea, "palabra")`).
3. Haz pruebas: de 8 a 30 cuadros al 50 % y la hoja de contactos con `scripts/componer.py --hoja`. Revísala tú mismo.
4. Render final al 100 %, dividido en 2 procesos con prioridad baja (`--part 0/2` y `--part 1/2`).
5. Ubica los sonidos reales en `sfx.json` y corre `scripts/mezcla.py`.
6. Escribe los títulos y etiquetas en `textos.json` y corre `scripts/componer.py`.

**Reglas**
- Todo a velocidad real; nada de cuadros repetidos.
- Respeta la zona segura.
- Datos idénticos al guion; no inventes cifras.
- El video cierra en loop.
- Solo sonidos reales con licencia anotada.
- No publiques nada.

**Entrega**
- `<proyecto>/salida/final.mp4`
- `<proyecto>/salida/final_ligero.mp4` (de menos de 10 MB)
- `<proyecto>/salida/hoja_contactos.png`

**Reporte final:** duración, tiempos por fase, qué simplificaste y por qué, defectos conocidos y licencias de los sonidos. Presupuesto: unas 4 h.
