Autoclicker por imagenes
=========================

Este proyecto contiene un script que busca imágenes en una carpeta `targets/` y hace click en las coincidencias. También incluye un workflow de GitHub Actions para compilar binarios para Windows y macOS usando PyInstaller.

Archivos añadidos

- `autoclick_image.py` - script principal. Usa `pyautogui` + `pynput` y opcionalmente `opencv-python` para matching por `confidence`.
- `add_target.py` - helper para copiar imágenes a `targets/` y opcionalmente crear/actualizar `targets/config.json` con opciones por objetivo.
- `requirements.txt` - dependencias necesarias (pyautogui, pynput, opencv-python, pyinstaller).
- `targets/` - carpeta donde colocar las imágenes objetivo (`.png`, `.jpg`, ...).
- `.github/workflows/build-binaries.yml` - workflow que construye artefactos para Windows y macOS y los sube como artefactos del run.

Uso (desarrollo)

1. Instala dependencias en tu entorno (recomendado crear un virtualenv):

   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

2. Añadir imágenes objetivo

   - Manualmente: copia imágenes a la carpeta `targets/` (puedes crear subcarpetas si quieres).
   - Con helper: usa `add_target.py` para copiar la imagen y definir opciones por objetivo en `targets/config.json`:

     python3 add_target.py /ruta/a/mi-boton.png --click-interval 2.5 --confidence 0.9 --jitter 3 --button left

   Opciones del helper:
   - `--click-interval` : número de segundos mínimo entre clicks para ese objetivo (se guardará como `click_cooldown`).
   - `--confidence` : matching confidence para este objetivo (0-1). Requiere `opencv-python`.
   - `--jitter` : píxeles de jitter para este objetivo.
   - `--button` : `left`, `right` o `middle`.
   - `--enabled` : `true`/`false` para activar/desactivar el objetivo.

   El helper crea/actualiza `targets/config.json`. También puedes editar `targets/config.json` manualmente. Formato de ejemplo:

   {
     "mi-boton.png": {
       "click_cooldown": 2.5,
       "confidence": 0.9,
       "jitter": 3,
       "button": "left",
       "enabled": true
     }
   }

   Nota: la clave en el JSON es el nombre del archivo tal cual (basename) dentro de `targets/`.

3. Ejecuta el script:

   python3 autoclick_image.py

   - Presiona F6 para empezar/parar los clics.
   - Presiona Esc para salir.

Opciones útiles del autoclicker:

- `--confidence` : valor entre 0 y 1 para matching; funciona solo si `opencv-python` está instalado (recomendado 0.8-0.95). Este valor puede ser anulado por objetivo en `targets/config.json`.
- `--scan-interval` : segundos entre escaneos de pantalla (cómo de seguido busca nuevas coincidencias en general).
- `--click-delay` : pausa entre clicks cuando se encuentran múltiples coincidencias.
- `--jitter` : píxeles de jitter aleatorio por defecto (puede sobreescribirse por objetivo).
- `--click-cooldown` : cooldown por defecto (segundos) entre clicks sobre el mismo (imagen,x,y). Puedes configurar `click_cooldown` distinto por objetivo en `targets/config.json`.
- `--auto-start` : empieza automáticamente sin esperar F6 (riesgoso).

Empaquetado local con PyInstaller

- Windows (desde Windows):

  pip install pyinstaller
  pyinstaller --onefile --add-data "targets;targets" --name autoclicker autoclick_image.py

  Esto generará `dist\autoclicker.exe`. Copia la carpeta `targets/` junto al exe o usa `--add-data` como arriba para incluirlas en el bundle.

- macOS (desde macOS):

  pip install pyinstaller
  pyinstaller --onefile --add-data "targets:targets" --name autoclicker autoclick_image.py

Notas sobre permisos (macOS)

- macOS requiere permisos para controlar el ratón y monitorizar entrada de teclado.
  Ve a: System Settings → Privacy & Security → Accessibility / Input Monitoring y añade el ejecutable de Python o la app final.

Workflow de GitHub Actions

- El workflow `.github/workflows/build-binaries.yml` está configurado para ejecutarse en `push` a `main` y también manualmente (`workflow_dispatch`).
- Genera dos artefactos: `autoclicker-windows` (contiene el .exe) y `autoclicker-macos`.

Advertencias

- Este programa controla el ratón físico. Úsalo con cuidado.
- Algunos juegos o aplicaciones detectan automatizaciones. Respeta términos de servicio.

Siguientes pasos que puedo hacer por ti

- Añadir una cuenta regresiva antes de empezar a clicar (p. ej. 3 segundos),
- Generar un workflow que publique los artefactos como Releases en GitHub,
- Añadir una interfaz simple para arrastrar/soltar imágenes (sería otra tarea),
- Preparar una versión sin consola (silent) para cada sistema.
