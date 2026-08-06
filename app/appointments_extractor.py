from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from app.email_client import EmailItem
from app.models import Appointment


class AIExtractionResponse(BaseModel):
    appointments: list[Appointment] = Field(
        default_factory=list,
        description="Todos los turnos extraídos del correo; puede contener más de uno.",
    )
    error_message: str | None = Field(
        default=None,
        description=(
            "Breve motivo en español de por qué no se pudo extraer un turno; "
            "null cuando la extracción fue exitosa."
        ),
    )


@dataclass
class ExtractionResult:
    mail: EmailItem
    appointments: list[Appointment]
    error: str | None = None


class AppointmentsExtractor:
    _PROMPT_TEMPLATE = (
        Path(__file__).with_name("prompts") / "appointments_extractor.txt"
    ).read_text(encoding="utf-8")

    def __init__(self, ai_clients):
        self.ai_clients = (
            list(ai_clients)
            if isinstance(ai_clients, (list, tuple))
            else [ai_clients]
        )

    def _build_prompt(self, email: EmailItem) -> str:
        prompt = self._PROMPT_TEMPLATE.replace("[year]", str(datetime.now().year))
        return (
            f"{prompt}"
            f"=== INICIO CORREO ===\n"
            f"Asunto: {email.subject}\n"
            f"Contenido:\n{email.body}\n"
            f"=== FIN CORREO ===\n"
        )

    def parse(self, email: EmailItem) -> ExtractionResult:
        prompt = self._build_prompt(email)
        return self._parse(prompt, email)

    def parse_all(self, emails: list[EmailItem]) -> list[ExtractionResult]:
        return [self.parse(email) for email in emails]

    def _parse(self, prompt: str, email: EmailItem) -> ExtractionResult:
        last_error: Exception | None = None
        for ai_client in self.ai_clients:
            try:
                response: AIExtractionResponse = ai_client.generate_structured_output(
                    prompt=prompt,
                    response_schema=AIExtractionResponse,
                )
                appointments = [
                    self._normalize_appointment(appointment)
                    for appointment in response.appointments
                ]
                error = response.error_message if not appointments else None
                if not appointments and error is None:
                    error = "La AI no pudo extraer un turno de este correo"
                return ExtractionResult(email, appointments, error)
            except Exception as error:
                last_error = error

        if last_error is not None:
            raise last_error
        raise RuntimeError("No AI clients configured")

    @staticmethod
    def _normalize_appointment(appointment: Appointment) -> Appointment:
        nullable_fields = (
            "patient_name",
            "clinic_or_professional",
            "study_detail",
            "date",
            "time",
        )
        updates = {}
        for field in nullable_fields:
            value = getattr(appointment, field)
            if isinstance(value, str) and value.strip().lower() in {"null", "none"}:
                updates[field] = None
        return appointment.model_copy(update=updates)
