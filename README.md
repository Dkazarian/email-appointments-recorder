# Procesador de Mails Administrativos

App Python para procesar mails administrativos, interpretar pedidos humanos con Ollama y actualizar un Google Sheet con una capa de validacion.

## Flujo

1. Lee mails por IMAP.
2. Envia asunto y cuerpo a un modelo local via Ollama.
3. Fuerza una respuesta JSON con una accion permitida.
4. Valida esa accion en Python.
5. Persiste opcionalmente en TXT o Google Sheets.
6. Responde el mail original.
7. Mueve el mail a procesados o fallidos.

## Instalacion

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edita `.env` con tus credenciales.

## Google Sheets

1. Crea un proyecto en Google Cloud.
2. Habilita Google Sheets API.
3. Crea credenciales OAuth:
   - `APIs & Services`
   - `Credentials`
   - `Create credentials`
   - `OAuth client ID`
   - Tipo: `Desktop app`
4. Descarga el JSON y guardalo como `client_secret_google.json` en la raiz del proyecto.
5. En `.env`, configura:

```env
GOOGLE_OAUTH_CLIENT_SECRET=client_secret_google.json
GOOGLE_OAUTH_TOKEN=token_google_sheets.json
SHEET_ID=tu_google_sheet_id
```

La primera vez que ejecutes con `--output-gsheets`, se abre el navegador para autorizar tu usuario de Google. Luego se guarda `token_google_sheets.json` para reutilizar el acceso.

`client_secret_google.json` y `token_google_sheets.json` estan ignorados por git.

## Ollama

Instala Ollama y descarga un modelo:

```powershell
ollama pull llama3.1
```

Luego configura `OLLAMA_MODEL=llama3.1` en `.env`.

Para mails largos o modelos lentos, puedes subir el timeout:

```env
OLLAMA_TIMEOUT_SECONDS=300
```

El proveedor de IA se selecciona con:

```env
AI_PROVIDER=ollama
```

## Uso

Procesar sin persistir en TXT ni Google Sheets:

```powershell
python -m app.main --limit 5
```

Probar mail + Ollama escribiendo el resultado en un archivo de texto:

```powershell
python -m app.main --output-txt --limit 5
```

Por defecto escribe en `work/processed_mails.txt`. Tambien puedes elegir una ruta:

```powershell
python -m app.main --output-txt work/test_mails.txt --limit 5
```

Procesar mails administrativos y actualizar Google Sheets:

```powershell
python -m app.main --output-gsheets --limit 5
```

Procesar continuamente, revisando cada 15 minutos:

```powershell
python -m app.main --watch --interval-minutes 15 --limit 5
```

En modo continuo, `--limit` es el tamano del lote. La app procesa lotes seguidos hasta que no encuentra mas mails; recien entonces espera `--interval-minutes`.

Despues de procesar cada mail, la app siempre lo mueve fuera del inbox:

- Los mails exitosos van a `MAIL_PROCESSED_FOLDER`.
- Los mails que fallan van a `MAIL_FAILED_FOLDER`.
- Los mails con accion `ignore` tambien se consideran fallidos.
- Los mails con accion `needs_review` tambien se consideran fallidos y no se agregan a la planilla.

Ademas, en ejecucion normal la app responde el mail original:

- Si se proceso bien, responde `Procesado` con los datos extraidos.
- Si fallo, responde `Error` con el error y el mensaje recibido.
- Si la IA devuelve `ignore`, responde `Error` e incluye el texto original del mail.
- Si la IA devuelve `needs_review`, responde `Error` e incluye el texto original del mail.

La respuesta usa `In-Reply-To` y `References` para quedar en la misma conversacion del mail original. Configura SMTP en `.env`:

```env
SMTP_HOST=mail.ig-gestiones.com.ar
SMTP_PORT=465
SMTP_USER=tu-email@example.com
SMTP_PASSWORD=app-password
```

Algunos servidores IMAP exigen que las carpetas cuelguen de `INBOX`. En ese caso usa:

```env
MAIL_PROCESSED_FOLDER=INBOX.Procesados
MAIL_FAILED_FOLDER=INBOX.Fallidos
```

## Estructura esperada de la planilla

Por defecto la app trabaja con una hoja llamada `Solicitudes` y estas columnas:

- `Concepto`
- `Monto`
- `Estado`
- `Fecha de vencimiento`
- `Fecha de pago`

En el JSON interno se usan estos nombres:

- `concepto`
- `monto`
- `estado`
- `fecha_vencimiento`
- `fecha_pago`

Si `fecha_pago` queda vacia, `estado` debe ser `pendiente`. Si hay `fecha_pago`, `estado` debe ser `pagado`.

Puedes cambiar la hoja con `SHEET_TAB` en `.env`.

## Acciones soportadas

El modelo puede devolver estas acciones:

- `append_row`: agregar una fila nueva.
- `ignore`: se considera fallido; responde error y mueve el mail a fallidos.
- `needs_review`: se considera fallido; responde error, mueve el mail a fallidos y no escribe en la planilla.

La app no ejecuta texto libre generado por IA. Solo acepta JSON con campos conocidos.

## Destinos de escritura

La escritura esta desacoplada con un objeto polimorfico `ResultSink` en `app/sinks.py`.

Destinos actuales:

- `NoopSink`: no persiste nada, usado cuando no se indica destino.
- `TextSink`: escribe en TXT, usado por `--output-txt`.
- `SheetsSink`: escribe en Google Sheets, usado por `--output-gsheets`.

Para agregar una base de datos, crea una clase con este metodo:

```python
def apply(self, mail, action) -> str:
    ...
```

Luego conectala en `build_sink`.

## Extractores de IA

La construccion del proveedor de IA esta desacoplada en `app/extractors.py`.

Por ahora el extractor disponible es:

- `OllamaExtractor`: usa Ollama local.

Para agregar otro proveedor, crea una clase con este metodo:

```python
def extract(self, mail) -> SheetAction:
    ...
```

Luego conectala en `build_extractor` y selecciona el proveedor con `AI_PROVIDER`.

## Prompt de IA

Las instrucciones que se le pasan a Ollama estan en:

```text
prompts/system_prompt.txt
```

Puedes editar ese archivo para ajustar criterios, columnas o reglas sin tocar codigo. Si quieres usar otro archivo, configura `PROMPT_FILE` en `.env`.
