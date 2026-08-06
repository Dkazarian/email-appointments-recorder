from datetime import datetime
from pathlib import Path
from typing import NamedTuple
from pydantic import BaseModel, Field
from app.models import Appointment
from app.email_client import EmailItem

class AppointmentExtracted(Appointment):
    email_id: str = Field(
        description="El ID único (uid o message_id) del correo electrónico del cual se extrajo este turno."
    )

class ParsingError(BaseModel):
    email_id: str = Field(description="El ID único del correo que no se pudo procesar.")
    error_message: str = Field(
        description="Breve motivo en español de por qué no se pudo extraer un turno (ej: 'El correo no contiene información de turnos')."
    )

class IAExtractionResponse(BaseModel):
    extracted_appointments: list[AppointmentExtracted] = Field(default_factory=list)
    failed_emails: list[ParsingError] = Field(default_factory=list)

class ExtractionResult(NamedTuple):
    mail: EmailItem
    appointments: list[AppointmentExtracted]
    error: str | None = None


SuccessItem = ExtractionResult
FailedItem = ExtractionResult


class AppointmentsExtractor:
    _PROMPT_TEMPLATE = (
        Path(__file__).with_name("prompts") / "appointments_extraction.txt"
    ).read_text(encoding="utf-8")

    def __init__(self, ia_clients, process_emails_individually: bool = False):
        self.ia_clients = list(ia_clients) if isinstance(ia_clients, (list, tuple)) else [ia_clients]
        self.process_emails_individually = process_emails_individually

    def _build_batch_prompt(self, emails: list[EmailItem]) -> str:
        prompt = self._PROMPT_TEMPLATE.replace("[year]", str(datetime.now().year))
        for mail in emails:
            prompt += f"=== INICIO CORREO ID: {mail.uid} ===\n"
            prompt += f"Asunto: {mail.subject}\n"
            prompt += f"Contenido:\n{mail.body}\n"
            prompt += f"=== FIN CORREO ID: {mail.uid} ===\n\n"
        return prompt

    def parse_all(self, emails: list[EmailItem]) -> list[ExtractionResult]:
        if len(emails) > 1 and self.process_emails_individually:
            results: list[ExtractionResult] = []
            for email in emails:
                results.extend(self._parse_batch([email]))
            return results
        return self._parse_batch(emails)

    def _parse_batch(self, emails: list[EmailItem]) -> list[ExtractionResult]:
        if not emails:
            return []

        email_map = {mail.uid: mail for mail in emails}
        prompt = self._build_batch_prompt(emails)
        last_error = None
        for ia_client in self.ia_clients:
            try:
                result: IAExtractionResponse = ia_client.generate_structured_output(
                    prompt=prompt, response_schema=IAExtractionResponse
                )
                break
            except Exception as error:
                last_error = error
        else:
            if last_error is not None:
                raise last_error
            raise RuntimeError("No IA clients configured")

        appointments_by_uid = {email.uid: [] for email in emails}
        errors_by_uid: dict[str, str] = {}
        undated_uids: set[str] = set()
        for appointment in result.extracted_appointments:
            mail = email_map.get(appointment.email_id)
            if mail is None and len(emails) == 1:
                mail = emails[0]
            if mail is None:
                continue
            if not appointment.date or not appointment.date.strip():
                undated_uids.add(mail.uid)
            else:
                appointments_by_uid[mail.uid].append(appointment)

        for failure in result.failed_emails:
            mail = email_map.get(failure.email_id)
            if mail is None and len(emails) == 1:
                mail = emails[0]
            if mail is not None:
                errors_by_uid[mail.uid] = failure.error_message

        for uid in undated_uids:
            if not appointments_by_uid[uid] and uid not in errors_by_uid:
                errors_by_uid[uid] = "El turno no contiene una fecha identificable"

        results = []
        for email in emails:
            appointments = appointments_by_uid[email.uid]
            error = errors_by_uid.get(email.uid)
            if not appointments and error is None:
                error = "La IA no pudo vincular el resultado con este correo"
            results.append(ExtractionResult(email, appointments, error))
        return results
