# Ejemplo completo: "Cómo funciona un microondas" (58 s)

Es el ejemplo con el que se probaron los 6 niveles de calidad. `escena_2d.py` y `escena_base.py` ya traen este tema dibujado.

| Archivo | Qué es |
|---|---|
| `guion_lineas.txt` | 12 líneas, 149 palabras (una línea = un archivo de voz) |
| `textos.json` | Títulos, etiquetas, destellos y colores de subtítulos |

## Reproducirlo
```bash
# voz local gratuita (opcional; mejor una voz humana o un servicio de voz)
pip install edge-tts
n=0; while IFS= read -r l; do n=$((n+1)); f=$(printf "%02d" $n)
  edge-tts --voice es-MX-JorgeNeural --rate=+6% --text "$l" --write-media voz/$f.mp3
  ffmpeg -loglevel error -y -i voz/$f.mp3 -ar 48000 -ac 1 voz/$f.wav; rm voz/$f.mp3; done < guion_lineas.txt

python ../scripts/timeline.py --voz voz --guion guion_lineas.txt --out trabajo --pausa-extra "3:0.25,8:0.25,12:0.2"
python ../scripts/producir.py --calidad auto --textos textos.json --trabajo trabajo --out salida/microondas.mp4
```

## Sets y tomas
| Líneas | Set | Escala | Qué se ve |
|---|---|---|---|
| 1–2 | A | cm | Cocina de noche; acercamiento al tazón de sopa que gira |
| 3 | A | cm | La tapa del panel se vuelve transparente: magnetrón, guía de onda, transformador |
| 4 | B | mm | Magnetrón de lado: los imanes N/S se separan y muestran el ánodo de cobre |
| 5 | B2 | mm | Ánodo desde arriba: 8 cavidades y 4 rayos de electrones girando |
| 6 | B | mm | La antena suelta anillos de microondas |
| 7 | A | cm | Corte del horno: la onda viaja por la guía y rebota en las paredes |
| 8–10 | C | Å | Molécula de agua (+/−), el campo cambia de dirección, el agua gira, choques y calor |
| 11 | A | cm | La sopa humea; el plato seco sigue frío |
| 12 | A | cm | Primer plano de la malla de la puerta frente a una onda de 12 cm; regreso al plano inicial (loop) |

Datos: magnetrón de 2.45 GHz (longitud de onda ≈ 12.2 cm); agujeros de la puerta de 1–2 mm.
