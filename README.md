# Bot de picks con valor esperado (EV) para Telegram

## Qué hace
1. Cada día (a la hora que configures) revisa cuotas de varias casas de apuestas
   para muchos deportes/ligas.
2. Calcula la probabilidad de consenso (promedio sin margen entre casas) y la
   compara contra la mejor cuota disponible.
3. Si detecta EV positivo (≥3% por default), te manda el pick por Telegram con
   dos botones: **Voy a apostarle** / **Paso**.
4. Guarda tu decisión. Cuando el partido termine, tú marcas el resultado con
   `/resultado <id> ganada|perdida` y el bot te arma tu historial real con
   `/stats` (win rate y ROI en unidades).

## Paso 1: Crear el bot de Telegram
1. Habla con **@BotFather** en Telegram.
2. Manda `/newbot`, ponle nombre.
3. Te da un `TELEGRAM_BOT_TOKEN` — guárdalo.
4. Manda cualquier mensaje a tu bot nuevo, luego visita:
   `https://api.telegram.org/bot<TU_TOKEN>/getUpdates`
   Ahí busca `"chat":{"id": ...}` — ese número es tu `TELEGRAM_CHAT_ID`.

## Paso 2: Conseguir la API de cuotas
1. Regístrate gratis en https://the-odds-api.com
2. Copia tu API key -> `ODDS_API_KEY`.
3. El plan gratis da 500 solicitudes/mes. Con ~10 deportes cubiertos, ajusta
   la lista `SPORTS` en `odds_api.py` si necesitas estirar la cuota.

## Paso 3: Subir el código a GitHub
```bash
cd betbot
git init
git add .
git commit -m "bot de picks inicial"
# crea un repo vacío en github.com y luego:
git remote add origin https://github.com/TU_USUARIO/betbot.git
git push -u origin main
```

## Paso 4: Desplegar en Render (gratis)
1. Entra a https://render.com, conecta tu cuenta de GitHub.
2. "New +" -> "Web Service" -> selecciona el repo `betbot`.
3. Runtime: Python 3. Build command: `pip install -r requirements.txt`.
   Start command: ya está en el `Procfile`, Render lo detecta solo.
4. En "Environment", agrega estas variables:
   - `ODDS_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `DAILY_HOUR_UTC` (opcional, default 13 = 7am CDMX)
5. Deploy. Render te da una URL tipo `https://betbot-xxxx.onrender.com`.

## Paso 5: Conectar el webhook de Telegram a tu Render
Corre esto una sola vez (cambia los valores):
```bash
curl "https://api.telegram.org/bot<TU_TOKEN>/setWebhook?url=https://betbot-xxxx.onrender.com/webhook"
```

## Paso 6: Probar
- Visita `https://betbot-xxxx.onrender.com/run-now` en el navegador para forzar
  una corrida sin esperar al horario.
- Deberías recibir los picks (o el aviso de NO BET) con botones en Telegram.
- Prueba `/stats` en el chat del bot.

## Nota sobre el plan gratis de Render
Se "duerme" tras ~15 min sin tráfico y tarda unos segundos en despertar con la
siguiente visita. El scheduler interno (APScheduler) solo corre si el proceso
está despierto — si te preocupa que se duerma justo a la hora programada,
puedes usar un servicio gratuito tipo UptimeRobot para hacerle ping cada 10
minutos y mantenerlo despierto.

## Ajustar el umbral de EV
En `value_finder.py`, cambia `MIN_EV_TO_FLAG = 0.03` (3%) por el número que
prefieras. Más alto = menos picks pero más "seguros" en términos de margen
matemático (nunca en términos de resultado garantizado).
