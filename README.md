# Email appointments recorder

### About this app

#### What does this do?

This Python application reads appointment details that a secretary forwards to an internal email when answering the patient. After fetching the email, it is parsed by an AI, and the appointments found are inserted in a Google Sheet.

#### Why a google sheet and not a database?

This tool is meant to save time without changing an existing workflow, the client needed a quick solution to keep in sync the sheet they use to track the appointments. A dedicated system (with a proper database and more business features) is an option in the future, but it would take both more time to develop and to train personnel.

#### How was this developed?

I used manual coding and Codex, mostly as a pair programming and typing/refactoring tool. I tried to keep everything as decoupled as possible, as I was going to try different free AI providers, and maybe switch the sheet by a database.

#### Learnings

Google Cloud (Sheets API), Google AI Studio (requesting structured inputs from Gemini Flash), and a local AI with LM Studio. Git Workflows & Repository secrets.

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
- One AI provider:
  - Local LM Studio model
  - Google AI Studio (Gemini API)
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

### AI providers

Local LM Studio is used when `LOCAL_AI_ENABLED=true`:

```env
LOCAL_AI_ENABLED=true
LOCAL_AI_BASE_URL=http://localhost:1234/v1
LOCAL_AI_MODEL=google_gemma-3-4b-it
LOCAL_AI_TIMEOUT_SECONDS=300
```

When local AI is disabled, the application can use Google AI Studio and OpenRouter from the configured credentials:

```env
LOCAL_AI_ENABLED=false
GOOGLE_AI_STUDIO_API_KEY=...
GOOGLE_AI_STUDIO_MODEL=gemini-2.0-flash
OPENROUTER_API_KEY=...
OPEN_ROUTER_MODEL=...
```

Local AI and OpenRouter can be configured to process emails individually through the extractor. Google AI Studio uses batch processing by default.

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
$env:RUN_LOCAL_AI_INTEGRATION_TESTS="1"
\.venv\Scripts\python.exe -m unittest tests.integration.appointments_extractor.test_local -v
```

## End-to-end test

Create `.env.test` from `.env.test.example`, configure a dedicated test spreadsheet, and set the provider:

```env
E2E_AI_PROVIDER=local
```

Supported providers are `local`, `google_ai_studio`, and `openrouter`.

Run the real E2E test while preserving generated messages and rows:

```powershell
$env:RUN_END_TO_END_INTEGRATION_TESTS="1"
$env:KEEP_END_TO_END_DATA="1"
$env:E2E_AI_PROVIDER="local"
\.venv\Scripts\python.exe -m unittest tests.test_end_to_end_integration -v
```

Use `KEEP_END_TO_END_DATA=1` while diagnosing failures. Without it, the test cleanup removes its generated emails and matching spreadsheet rows.

The E2E test prints the structured AI response and verifies:

- appointment extraction
- mandatory appointment date
- email and appointment rows
- email URL generation
- success reply
- movement to the processed folder

### Test classes

The test classes are organized by the application component or integration they cover:

| Test class | What it does |
| --- | --- |
| `AppointmentTests` | Verifies appointment model validation, nullable values, and rejection of fields outside the extraction schema. |
| `AppointmentsExtractorTests` | Tests email parsing, batch processing, provider errors, AI fallback, and prompt contents using mocked AI clients. |
| `AppointmentsSheetTests` | Tests Google Sheets row creation, headers, duplicate prevention, error handling, and table configuration without calling Google Sheets. |
| `AppointmentsSheetIntegrationTests` | Writes and reads a combined appointment row against a real test Google Sheet. |
| `EmailClientTests` | Tests IMAP/SMTP connection handling, message parsing, sender filtering, replies, deletion, and folder moves with mocked mail servers. |
| `EmailIntegrationTests` | Exercises fetching, completing, failing, and replying to messages through the email integration boundary. |
| `GoogleAIStudioClientTests` | Verifies conversion of Google AI Studio responses into the requested Pydantic model using a mocked client. |
| `GoogleAIStudioClientIntegrationTests` | Sends a structured-output request to the configured Google AI Studio API and validates the response. |
| `LocalAIClientTests` | Verifies structured output handling through a mocked LM Studio/OpenAI-compatible endpoint. |
| `LocalAIClientIntegrationTests` | Sends a structured-output request to a real local LM Studio model. |
| `OpenRouterAIClientIntegrationTests` | Sends a structured-output request to the configured OpenRouter API and validates the response. |
| `MainIntegrationTests` | Tests the main batch workflow orchestration, including successful processing and retry behavior after transient AI errors. |
| `EndToEndIntegrationTests` | Runs the complete email-to-AI-to-Google-Sheets workflow and verifies the reply and processed-folder movement. |
| `LocalAppointmentsExtractorIntegrationTests` | Processes sample appointment emails through the real local AI provider and validates extracted appointments. |
| `GoogleAIStudioAppointmentsExtractorIntegrationTests` | Processes sample appointment emails through the real Google AI Studio provider and validates extracted appointments. |
| `OpenRouterAppointmentsExtractorIntegrationTests` | Processes sample appointment emails through the real OpenRouter provider and validates extracted appointments. |

### Application and support classes

These are the non-test classes used by the application and its test fixtures:

| Class | What it does |
| --- | --- |
| `Appointment` | Defines the validated appointment data model extracted from emails. |
| `AIExtractionResponse` | Defines the structured response returned by an AI provider: an appointment or an extraction error. |
| `ExtractionResult` | Groups an email with its extracted appointments and any processing error. |
| `AppointmentsExtractor` | Builds extraction prompts, calls AI clients, parses responses, and falls back to the next provider when needed. |
| `SheetsError` | Represents errors while writing appointment or email data to Google Sheets. |
| `AppointmentsSheet` | Converts emails and appointments into rows and reads or appends them in the configured Google Sheets tables. |
| `EmailItem` | Stores the normalized metadata and body of an email. |
| `EmailClient` | Handles IMAP fetching, SMTP replies, sender filtering, deletion, and moving messages between folders. |
| `AppointmentsEmailClient` | Provides appointment-specific email operations on top of `EmailClient`. |
| `_TextHTMLParser` | Converts HTML email content into plain text for message parsing. |
| `GoogleAIStudioClient` | Sends structured-output requests to Google AI Studio and validates the parsed response against a Pydantic model. |
| `LocalAIError` | Represents HTTP or response-format errors from the local AI service. |
| `LocalAIClient` | Sends structured-output requests to an OpenAI-compatible LM Studio endpoint. |
| `OpenRouterError` | Represents HTTP or response-format errors from OpenRouter. |
| `OpenRouterAIClient` | Sends structured-output requests to the OpenRouter API. |
| `Config` | Stores the application configuration loaded from environment variables. |
| `Logger` | Prints formatted informational and error messages. |
| `ExpectedAppointment` | Defines the expected patient and study for a fixture assertion. |
| `AppointmentFixture` | Bundles a sample email with its expected extracted appointments for integration tests. |
| `HelloWorld` | Minimal Pydantic response model used by provider smoke tests to verify structured output. |

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
  appointments_extractor.py  AI prompt, parsing, validation, and provider fallback
  appointments_sheet.py      Google Sheets integration
  config.py                   Environment configuration
  email_client.py             IMAP/SMTP integration
  main.py                     Application workflow
  ai_clients/                 Google AI Studio, OpenRouter, and LM Studio clients
tests/                        Unit, integration, and E2E tests
scripts/                      Spreadsheet setup utilities
```
