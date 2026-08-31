# Berlin Wohnung Watcher

Revisa https://www.inberlinwohnen.de/wohnungsfinder cada 15 minutos y
avisa por Telegram, ntfy.sh y/o email en cuanto aparece un piso nuevo
que cumpla tu filtro (por defecto Kaltmiete ≤ 600 €).

Corre gratis en GitHub Actions, sin necesidad de tener tu ordenador
encendido.

## 1. Crear el repositorio

1. Crea un repo nuevo (puede ser privado) en GitHub, p.ej. `wohnung-watcher`.
2. Sube estos archivos tal cual (misma estructura de carpetas).

## 2. Configurar los avisos

Ve a **Settings → Secrets and variables → Actions** en tu repo y añade
los "Secrets" que quieras usar. Puedes activar uno, dos o los tres canales.

### Telegram
1. Habla con [@BotFather](https://t.me/BotFather) en Telegram → `/newbot` → sigue los pasos → te da un **token**.
2. Escríbele algo a tu bot nuevo (cualquier mensaje).
3. Abre en el navegador: `https://api.telegram.org/bot<TU_TOKEN>/getUpdates` y busca `"chat":{"id":...}` → ese número es tu **chat_id**.
4. Añade los secrets: `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`.

### ntfy.sh (push al móvil, sin cuenta)
1. Instala la app **ntfy** (Android/iOS) o usa el navegador.
2. Elige un nombre de "topic" único y secreto, p.ej. `diego-berlin-pisos-83jd`.
3. En la app, suscríbete a ese topic.
4. Añade el secret `NTFY_TOPIC` con ese nombre.

### Email
1. Si usas Gmail, crea una ["contraseña de aplicación"](https://myaccount.google.com/apppasswords) (necesitas verificación en 2 pasos activada).
2. Añade los secrets: `EMAIL_USER` (tu Gmail), `EMAIL_PASS` (la contraseña de aplicación), `EMAIL_TO` (a quién avisar, puede ser el mismo Gmail).
3. Si usas otro proveedor, añade también `SMTP_HOST` y `SMTP_PORT` como Variables (no secrets) si no es Gmail.

## 3. (Opcional) Cambiar el filtro de búsqueda

Ve a **Settings → Secrets and variables → Actions → Variables** y añade
una variable `SEARCH_URL` con tu URL de búsqueda filtrada, por ejemplo:

```
https://www.inberlinwohnen.de/wohnungsfinder?q[rent_net][max]=600&q[save_search_profile]=0
```

Si no la defines, se usa esta misma por defecto.

## 4. Activarlo

- El workflow ya está programado para correr cada 15 minutos automáticamente
  en cuanto hagas push (GitHub Actions lo detecta solo).
- La primera ejecución NO envía avisos: solo guarda los pisos que hay
  ahora mismo como "ya vistos" (si no, te bombardearía con 75 avisos
  el primer día). A partir de la segunda ejecución, solo avisa de lo
  realmente nuevo.
- Puedes lanzarlo a mano en cualquier momento desde la pestaña
  **Actions → Check Berlin listings → Run workflow**.

## Notas

- El scraping usa el HTML público de la web, sin login. Si Immobilien
  cambia el diseño de la página, el parser (`scraper.py`) podría dejar
  de detectar los pisos correctamente — revisa los logs del workflow
  en la pestaña Actions si un día deja de avisar.
- El intervalo de 15 min es un buen equilibrio entre rapidez y no
  saturar su servidor. Los cron jobs de GitHub Actions no son 100%
  puntuales en el minuto exacto (a veces hay unos minutos de retraso).
