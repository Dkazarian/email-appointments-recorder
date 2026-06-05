# Procesador de Mails Administrativos

App Python para procesar mails administrativos, interpretar pedidos humanos con Ollama y actualizar un Google Sheet con una capa de validacion.

## Flujo

1. Lee mails por IMAP.
2. Envia asunto y cuerpo a un modelo local via Ollama.
3. Fuerza una respuesta JSON con una accion permitida.
4. Valida esa accion en Python.
5. Actualiza Google Sheets, o muestra lo que haria con `--dry-run`.

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
3. Crea una Service Account.
4. Descarga el JSON de credenciales.
5. Comparte el Google Sheet con el email de la Service Account.
6. En `.env`, configura `GOOGLE_APPLICATION_CREDENTIALS` y `SHEET_ID`.

## Ollama

Instala Ollama y descarga un modelo:

```powershell
ollama pull llama3.1
```

Luego configura `OLLAMA_MODEL=llama3.1` en `.env`.

El proveedor de IA se selecciona con:

```env
AI_PROVIDER=ollama
```

## Uso

Probar sin modificar la planilla:

```powershell
python -m app.main --dry-run --limit 5
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
python -m app.main --limit 5
```

Procesar continuamente, revisando cada 15 minutos:

```powershell
python -m app.main --watch --interval-minutes 15 --limit 20
```

En modo continuo, `--limit` es el maximo de mails por ciclo.

Despues de procesar cada mail, la app siempre lo mueve fuera del inbox:

- Los mails exitosos van a `MAIL_PROCESSED_FOLDER`.
- Los mails que fallan van a `MAIL_FAILED_FOLDER`.

En `--dry-run` no se mueven mails.

## Estructura esperada de la planilla

Por defecto la app trabaja con una hoja llamada `Solicitudes` y estas columnas:

- `fecha`
- `remitente`
- `estado`
- `descripcion`
- `categoria`
- `monto`
- `vencimiento`
- `notas`
- `mail_id`

Puedes cambiar la hoja con `SHEET_TAB` en `.env`.

## Acciones soportadas

El modelo puede devolver estas acciones:

- `append_row`: agregar una fila nueva.
- `update_row`: actualizar una fila encontrada por `mail_id`.
- `ignore`: no hacer nada.
- `needs_review`: registrar que el mail requiere revision humana.

La app no ejecuta texto libre generado por IA. Solo acepta JSON con campos conocidos.

## Destinos de escritura

La escritura esta desacoplada con un objeto polimorfico `ResultSink` en `app/sinks.py`.

Destinos actuales:

- `NoopSink`: no persiste nada, usado por `--dry-run`.
- `TextSink`: escribe en TXT, usado por `--output-txt`.
- `SheetsSink`: escribe en Google Sheets, usado por defecto cuando no hay modo de prueba.

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
