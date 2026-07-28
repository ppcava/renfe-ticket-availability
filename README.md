# Renfe Bot

Bot en Python que consulta billetes de Renfe y envía un aviso por Telegram cuando encuentra un tren que cumple los filtros configurados.

## Archivos

- `run.py`: realiza una búsqueda y termina.
- `run_auto.py`: repite la búsqueda hasta encontrar billetes o alcanzar el tiempo máximo.
- `requirements.txt`: dependencias de Python.
- `.env.example`: ejemplo de configuración local.
- `.github/workflows/`: workflows de GitHub Actions para ida y vuelta.

## Requisitos

- Python 3.10 o superior.
- Un bot de Telegram.

## Instalación local

```bash
git clone URL_DEL_REPOSITORIO
cd NOMBRE_DEL_REPOSITORIO

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

En Ubuntu, si faltan dependencias del sistema:

```bash
playwright install --with-deps chromium
```

## Configurar Telegram

### 1. Obtener `TELEGRAM_TOKEN`

1. Abre Telegram y busca el bot oficial `@BotFather`.
2. Inicia la conversación y envía:

```text
/newbot
```

3. Indica el nombre del bot.
4. Indica un nombre de usuario único terminado en `bot`, por ejemplo `renfe_alertas_bot`.
5. BotFather responderá con un token similar a:

```text
1234567890:AAEjemploDeToken
```

Ese valor es `TELEGRAM_TOKEN`. No lo publiques ni lo subas al repositorio.

### 2. Obtener `TELEGRAM_CHAT_ID`

1. Abre una conversación con el bot que acabas de crear.
2. Pulsa **Start** o envíale cualquier mensaje.
3. Abre esta URL en el navegador, sustituyendo `TOKEN` por el token real:

```text
https://api.telegram.org/botTOKEN/getUpdates
```

Ejemplo:

```text
https://api.telegram.org/bot1234567890:AAEjemploDeToken/getUpdates
```

4. Busca en la respuesta JSON:

```json
"chat": {
  "id": 123456789
}
```

El número de `id` es `TELEGRAM_CHAT_ID`.

Si `result` aparece vacío, vuelve a enviar un mensaje al bot y recarga la URL.

Para usar un grupo, añade el bot al grupo, envía un mensaje y consulta de nuevo `getUpdates`. El identificador del grupo normalmente será negativo.

### 3. Configuración local

Copia el archivo de ejemplo:

```bash
cp .env.example .env
```

Contenido de `.env`:

```env
TELEGRAM_TOKEN=1234567890:AAEjemploDeToken
TELEGRAM_CHAT_ID=123456789
```

El archivo `.env` no debe subirse a Git.

## Ejecutar localmente

### Una búsqueda

```bash
python -u run.py \
  -o "MADRID" \
  -d "VALENCIA" \
  -f "15/08/2026" \
  -s "08:00" \
  -l "22:00" \
  -t 180
```

### Búsqueda automática

```bash
python -u run_auto.py \
  -o "MADRID" \
  -d "VALENCIA" \
  -f "15/08/2026" \
  -s "08:00" \
  -l "22:00" \
  -t 180 \
  --intervalo-minimo 5 \
  --intervalo-maximo 10 \
  --max-minutos 45
```

Argumentos:

- `-o`: estación de origen.
- `-d`: estación de destino.
- `-f`: fecha en formato `DD/MM/AAAA`.
- `-s`: hora mínima de salida en formato `HH:MM`.
- `-l`: hora máxima de llegada en formato `HH:MM`.
- `-t`: duración máxima en minutos.
- `--intervalo-minimo`: espera mínima entre búsquedas.
- `--intervalo-maximo`: espera máxima entre búsquedas.
- `--max-minutos`: duración máxima del proceso automático.

## Configurar GitHub Actions

El repositorio tiene dos workflows:

- **Renfe Bot Ida**: se programa en el minuto 17 de cada hora.
- **Renfe Bot Vuelta**: se programa en el minuto 27 de cada hora.

Cada workflow ejecuta `run_auto.py` durante un máximo de 45 minutos y consulta cada 5-10 minutos. También puede iniciarse manualmente desde **Actions > workflow > Run workflow**.

Los cron de GitHub Actions se evalúan en UTC. `TZ: Europe/Madrid` configura la zona horaria del proceso, pero no cambia la hora del cron.

### Secrets

En el repositorio, entra en:

```text
Settings > Secrets and variables > Actions > Secrets
```

Crea estos dos **Repository secrets**:

```text
TELEGRAM_TOKEN
TELEGRAM_CHAT_ID
```

Usa los valores obtenidos en la sección anterior.

### Variables de ida

Entra en:

```text
Settings > Secrets and variables > Actions > Variables
```

Crea estas **Repository variables**:

```text
IDA_ORIGEN
IDA_DESTINO
IDA_FECHA
IDA_SALIDA
IDA_LLEGADA
IDA_DURACION
```

Ejemplo:

```text
IDA_ORIGEN=MADRID
IDA_DESTINO=VALENCIA
IDA_FECHA=15/08/2026
IDA_SALIDA=08:00
IDA_LLEGADA=22:00
IDA_DURACION=180
```

### Variables de vuelta

Crea también:

```text
VUELTA_ORIGEN
VUELTA_DESTINO
VUELTA_FECHA
VUELTA_SALIDA
VUELTA_LLEGADA
VUELTA_DURACION
```

Ejemplo:

```text
VUELTA_ORIGEN=VALENCIA
VUELTA_DESTINO=MADRID
VUELTA_FECHA=20/08/2026
VUELTA_SALIDA=08:00
VUELTA_LLEGADA=22:00
VUELTA_DURACION=180
```

## Probar la configuración

1. Abre la pestaña **Actions** del repositorio.
2. Selecciona **Renfe Bot Ida** o **Renfe Bot Vuelta**.
3. Pulsa **Run workflow**.
4. Revisa el log del paso **Ejecutar Bot**.

Si no llega el aviso de Telegram, comprueba el token, el chat ID y que hayas iniciado una conversación con el bot.

## Importante

- No subas `.env` ni el token de Telegram.
- Actualiza `IDA_FECHA` y `VUELTA_FECHA` cuando cambien los viajes.
- El bot solo avisa: no compra billetes.
- La web de Renfe puede cambiar y romper los selectores utilizados por Playwright.
