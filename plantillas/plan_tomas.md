# Plan de tomas — <TEMA>

## Sets por escala
Cada set es una "isla" en la escena con su propia unidad (evita problemas de precisión y facilita la iluminación).

| Set | Escala / unidad | Qué contiene | Líneas que cubre |
|---|---|---|---|
| A | m o mm | objeto completo, mano/usuario, vista exterior | 01–03, 11–12 |
| B | mm | módulo explotado, mecanismo | 03–05 |
| C | µm | detalle micro, comparación de escala | 05–07 |
| D | nm / abstracto | física de fondo (partículas, campos, señales) | 08–10 |

Transición entre sets: zoom rápido hacia la pieza + destello blanco de 3–4 cuadros + entrar al siguiente set.

## Tabla de tomas
| Línea | Set | Toma 3D (acción concreta) | Título (2–3 palabras) | Etiquetas | Sonido real |
|---|---|---|---|---|---|
| 01 | A | acción del gancho + congelado de 0.3 s | pregunta | — | sonido de la acción |
| 02 | A | dolly rápido hacia el mecanismo | promesa | — | whoosh suave |
| 03 | B | piezas se separan (vista explotada) | | nombre de pieza | material de la pieza |
| … | | | | | |
| 12 | A | regresa EXACTAMENTE al cuadro inicial (loop) | — | — | sonido de la acción |

## Archivo `textos.json` (para componer.py)
```json
{
  "titulos": [{"linea": 1, "texto": "¿YA LA TOMÓ?", "color_palabra": {"TOMÓ": "#FFD23A"}}],
  "etiquetas": [{"desde": 12.0, "hasta": 15.5, "texto": "BOBINA", "ancla": [540, 900], "punta": [700, 780]}],
  "colores_subtitulo": {"rojos": "#FF4D4D", "verdes": "#4DFF7A", "azules": "#4DA6FF"}
}
```

## Archivo `sfx.json` (para mezcla.py)
```json
[
  {"archivo": "sfx/clic.wav", "linea": 1, "palabra": "tocas", "ganancia_db": -6},
  {"archivo": "sfx/motor.wav", "en": 13.2, "ganancia_db": -10}
]
```
