# Email appointments recorder

### About this app

#### What does this do?

This python application reads appointments details that a secretary forwards to an internal email when answering the patient. After fetching the email, it is parsed by an IA, and the appointments found are inserted in a google sheet.

#### Why a google sheet and not a database?

This tool is meant to save time without changing an existing workflow, the client needed a quick solution to keep in sync the sheet they use to track the appointments. A dedicated system (with a proper database and more business features) is an option in the future, but it would take both more time to develop and to train personnel.

#### How was this developed?

I used manual coding and Codex, not as SDD this time, but as a pair programmer and typing/refactoring tool. I tried to keep everything as decoupled as possible, as I was going to try different free IAs, and maybe switch the sheet by a database.

#### Learnings

Google Cloud (sheets API), Google studio (requetinng structured inputs to gemini flash), running a local IA with LM Studio. Git Workflows & Repository secrets.

## Workflow

1. Poll the configured IMAP mailbox.
2. Keep only messages from allowed senders.
3. Extract appointment data from the email body.
4. Append the email to `Correos` and each appointment to `Turnos`.
5. Reply to the sender with the result.
6. Move successful emails to the processed folder and failed emails to the failed folder.

An appointment must have an identifiable appointment date. Emails without one are treated as failed and are not written as appointments.

## Requirements

- Python 3.11+ recommended
- An IMAP/SMTP mailbox
- A Google service account with access to the target spreadsheet
- One IA provider:
  - Local LM Studio model
  - Gemini API
  - OpenRouter API

## Installation

Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configuration

Copy the example environment file and fill in the values:

```powershell
Copy-Item .env.example .env
```

Important settings include:

```env
IMAP_HOST=imap.example.com
IMAP_PORT=993
IMAP_USER=mail@example.com
IMAP_PASSWORD=...
IMAP_FOLDER=INBOX
IMAP_SEARCH=UNSEEN
ALLOWED_SENDERS=sender@example.com

SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USER=mail@example.com
SMTP_PASSWORD=...

MAIL_PROCESSED_FOLDER=INBOX.Procesados
MAIL_FAILED_FOLDER=INBOX.Fallidos

GOOGLE_CREDENTIALS=google-service-account.json
SHEET_ID=your-spreadsheet-id
SHEET_TABLE=Turnos
SHEET_EMAIL_TABLE=Correos

INTERVAL_MINUTES=15
```

### IA providers

Local LM Studio is used when `LOCAL_IA_ENABLED=true`:

```env
LOCAL_IA_ENABLED=true
LOCAL_IA_BASE_URL=http://localhost:1234/v1
LOCAL_IA_MODEL=google_gemma-3-4b-it
LOCAL_IA_TIMEOUT_SECONDS=300
```

When local IA is disabled, the application can use Gemini and OpenRouter from the configured credentials:

```env
LOCAL_IA_ENABLED=false
GEMINI_IA_API_KEY=...
GEMINI_IA_MODEL=gemini-2.0-flash
OPENROUTER_API_KEY=...
OPEN_ROUTER_MODEL=...
```

Local IA and OpenRouter can be configured to process emails individually through the extractor. Gemini uses batch processing by default.

## Running the application

```powershell
\.venv\Scripts\python.exe -m app.main
```

The application polls continuously. `Ctrl+C` stops the process.

## Tests

Run the local unit test suite:

```powershell
\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test*.py' -v
```

Optional integration tests are disabled unless explicitly enabled. Examples:

```powershell
$env:RUN_LOCAL_IA_INTEGRATION_TESTS="1"
\.venv\Scripts\python.exe -m unittest tests.integration.appointments_extractor.test_local -v
```

## End-to-end test

Create `.env.test` from `.env.test.example`, configure a dedicated test spreadsheet, and set the provider:

```env
E2E_IA_PROVIDER=local
```

Supported providers are `local`, `gemini`, and `openrouter`.

Run the real E2E test while preserving generated messages and rows:

```powershell
$env:RUN_END_TO_END_INTEGRATION_TESTS="1"
$env:KEEP_END_TO_END_DATA="1"
$env:E2E_IA_PROVIDER="local"
\.venv\Scripts\python.exe -m unittest tests.test_end_to_end_integration -v
```

Use `KEEP_END_TO_END_DATA=1` while diagnosing failures. Without it, the test cleanup removes its generated emails and matching spreadsheet rows.

The E2E test prints the structured IA response and verifies:

- appointment extraction
- mandatory appointment date
- email and appointment rows
- email URL generation
- success reply
- movement to the processed folder

## Spreadsheet tables

The `Turnos` worksheet stores appointment records, including:

- patient
- study and detail
- clinic_or_professional
- appointment date and time
- email UID and email date
- subject, sender, recipients, and URL

The `Correos` worksheet stores the original processed email and its metadata.

## Project structure

```text
app/
  appointments_extractor.py  IA prompt, parsing, validation, and provider fallback
  appointments_sheet.py      Google Sheets integration
  config.py                   Environment configuration
  email_client.py             IMAP/SMTP integration
  main.py                     Application workflow
  ia_clients/                 Gemini, OpenRouter, and LM Studio clients
tests/                        Unit, integration, and E2E tests
scripts/                      Spreadsheet setup utilities
```
