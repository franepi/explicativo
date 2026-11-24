# Errores frecuentes y su solución

| Síntoma | Causa | Solución |
|---|---|---|
| faster-whisper falla al abrir el archivo (error de PyAV/`av.open`) | Incompatibilidad de versiones al decodificar | Decodifica con ffmpeg a un arreglo numpy de 16 kHz y pásaselo (ya lo hace `timeline.py`) |
| El render va a 5–15 s por cuadro con una GPU decente | Otras apps se comen la CPU o la GPU | Cierra el software RGB, los navegadores pesados y los otros renders; baja la prioridad; máximo 2 procesos |
| Los primeros minutos del render no avanzan | Blender está compilando shaders (Eevee) | Es normal (~10 min); no lo interrumpas |
| Subtítulos con palabras mal escritas | Se usó el texto de whisper | Usa el texto del guion con los tiempos de whisper emparejados (`timeline.py`) |
| La voz y la animación se desfasan | La animación usa segundos fijos | Anima con `T(linea, palabra)` a partir de `timeline.json` |
| La "cámara lenta" se ve barata | Se estiraron o repitieron cuadros | Anima la versión lenta como tal |
| Las piezas micro "tiemblan" o desaparecen | Precisión numérica al mezclar mm y µm en un mismo espacio | Usa un set por escala, cada uno con su unidad, y transición entre ellos |
| Brillo quemado en primeros planos | Emisión o bloom demasiado altos | Baja la emisión y revisa la hoja de contactos en esas tomas |
| Texto cortado por la interfaz de la app | Fuera de la zona segura | Mantén el texto entre el 16 % y el 68 % del alto |
| El sonido suena "de computadora" | Sonidos sintéticos | Usa grabaciones reales (Pixabay, Freesound, Commons) |
| La versión ligera pesa más de 10 MB | Bitrate fijo demasiado alto | `componer.py` calcula el bitrate a partir de la duración |
| El equipo se congela durante el render | Equipo modesto en un nivel demasiado alto | `producir.py --detectar` y baja de nivel; `producir.py` ya corre con prioridad baja |
| Sin Blender ni GPU | Equipo sin tarjeta de video o sin permisos para instalar | Niveles 1–2 (`escena_2d.py`): solo necesitan Python, PIL y ffmpeg |
| `h264_nvenc` falla aunque ffmpeg lo lista | La compilación de ffmpeg lo incluye, pero no hay tarjeta NVIDIA | `componer.py` lo prueba antes de usarlo y si falla usa libx264 (`--sin-gpu` para forzarlo) |
| En Workbench todo sale gris o sin color | Workbench no lee los nodos del material | `material()` también llena `diffuse_color`; si haces materiales a mano, llénalo tú |
| Whisper tarda mucho en un equipo lento | Modelo demasiado grande | `--modelo tiny` o `base` (los niveles 1–3 ya lo usan) |
| 2D: tarda 10–20 s por cuadro con zoom | Una pared de 4 m dibujada a 400 px/cm crea imágenes gigantes fuera de pantalla | Recorta cada figura a la pantalla antes de crearla (`rect_grad` ya lo hace) |
| 3D: un patrón (malla perforada, degradado) sale enorme o estirado | La pieza usa una malla compartida escalada; las coordenadas de objeto no están en unidades reales | `caja(..., propia=True)` o `bisel`: la malla propia mide en cm/mm reales |
| 3D: algo "oculto" sigue apareciendo | `hide_render` en un vacío no oculta a sus hijos | Usa `ocultar(obj, True)`, que oculta todo el grupo |
| 3D: los primeros planos salen grises o empañados | Un vidrio con refracción delante de la cámara desenfoca todo lo de atrás | Quita el vidrio en esas tomas o usa solo una lámina con transparencia |
| 3D: una pieza que brilla tiñe todo de rosa o celeste | Una superficie emisiva demasiado grande con AgX se ve pastel | Emisión solo en bordes finos; el color sólido con material normal |
| La animación se desincroniza al cambiar la voz | Keyframes puestos a mano | Todo lo animado se calcula en `actualizar(t)` a partir de `T(linea, "palabra")` |
| Workbench muestra cajas sólidas donde había luz o vidrio | Workbench no entiende emisión con transparencia | Ocúltalas en Workbench (`SOLO_LUZ`) |
