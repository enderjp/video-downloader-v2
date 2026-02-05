# video-downloader-v2

API FastAPI para extraer imágenes y la URL directa de video de posts públicos de Facebook usando Selenium.

## Instalación

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Requisitos: Chrome (compatible con ChromeDriver) o usar `webdriver-manager` para gestionar el driver.

## Ejecutar localmente

```powershell
py -3 -m uvicorn main_selenium:app --reload --host 127.0.0.1 --port 8001
```

- Accede a la documentación interactiva en `http://127.0.0.1:8001/docs`.

## Endpoints principales

- `POST /scrape` - Body JSON `{ "url": "<facebook_post_url>" }` devuelve imágenes y metadata.
- `GET /scrape?url=...` - Mismo que POST en GET.
- `GET /scrape/video?url=...` - Devuelve `video_url` (fbcdn mp4) y `probe` con metadatos HTTP.
- `POST /scrape/video` - Body JSON `{ "url": "<facebook_post_url>" }`.

## Uso rápido (PowerShell)

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8001/scrape" -ContentType "application/json" -Body '{"url":"https://www.facebook.com/..."}'
```

## Notas

- El servicio intenta reproducir el video en el navegador y capturar recursos de red para obtener la URL real en `fbcdn.net`.
- Algunas URLs expiran o requieren cookies; el resultado incluye una comprobación `probe` que indica si la URL fue accesible.
- Para producción, considera ejecutar en Docker y administrar la versión de Chrome/driver.

---

Si quieres, puedo crear también un `Dockerfile` y un `.github/workflows` para CI.