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

class SuccessItem(NamedTuple):
    appointment: AppointmentExtracted
    mail: EmailItem

class FailedItem(NamedTuple):
    error: str
    mail: EmailItem


class AppointmentsExtractor:
    def __init__(self, ia_clients, process_emails_individually: bool = False):
        self.ia_clients = list(ia_clients) if isinstance(ia_clients, (list, tuple)) else [ia_clients]
        self.process_emails_individually = process_emails_individually

    def _build_batch_prompt(self, emails: list[EmailItem]) -> str:
        prompt = (
            "Analiza cada correo y devuelve exclusivamente el JSON definido por el esquema.\n\n"
            "Para cada turno médico, agrega un objeto en 'extracted_appointments' y vincúlalo "
            "con el 'email_id' exacto del correo. Si un correo contiene varios turnos, crea un "
            "objeto por turno y repite el mismo 'email_id'.\n\n"
            "Reglas de extracción:\n"
            "- 'patient_name': si aparece 'Paciente: X', copia exactamente X.\n"
            "  Si no aparece en el cuerpo, puedes usar el asunto como posible patient_name solo si "
            "claramente parece contener un nombre; no lo des por seguro si el asunto es ambiguo.\n"
            "- 'clinic': si aparece 'Clínica: X' o una variante con problemas de codificación como "
            "'ClÃ­nica: X', copia exactamente el nombre de la clínica.\n"
            "- 'study': usa el tipo breve del estudio.\n"
            "- 'study_detail': conserva la descripción completa; si no hay detalle adicional, repite 'study'.\n"
            "- 'date': es la fecha del turno, no la fecha del correo. Si aparece 'Fecha: DD/MM/YYYY', "
            "DEBES copiar 'DD/MM/YYYY' en 'date'. Nunca devuelvas null para 'date' cuando una fecha "
            "aparezca explícitamente en el contenido. Si falta el año, conserva 'DD/MM'.\n"
            "- 'time': si aparece 'Hora: HH:MM', copia la hora en formato de 24 horas.\n"
            "Extrae todos los campos presentes. Usa null únicamente cuando el dato no figure en el correo. "
            "No inventes valores ni confundas la fecha del turno con la fecha de recepción del correo.\n\n"
            "La fecha del turno es obligatoria: si no puedes identificarla, NO agregues un objeto en "
            "'extracted_appointments'; agrega el correo en 'failed_emails' indicando que falta la fecha.\n\n"
            "Ejemplo: para 'Clínica: Centro Norte; Fecha: 31/12/2026; Hora: 23:59', "
            "la extracción debe contener 'clinic': 'Centro Norte', 'date': '31/12/2026' y "
            "'time': '23:59'.\n\n"
            "Si un correo no contiene ningún turno médico o es imposible de procesar, agrega su "
            "'email_id' y un motivo breve en 'failed_emails'. Cada email_id provisto debe aparecer "
            "exactamente en una de las dos listas.\n\n"
        )
        for mail in emails:
            prompt += f"=== INICIO CORREO ID: {mail.uid} ===\n"
            prompt += f"Asunto: {mail.subject}\n"
            prompt += f"Contenido:\n{mail.body}\n"
            prompt += f"=== FIN CORREO ID: {mail.uid} ===\n\n"
        return prompt

    def parse_all(self, emails: list[EmailItem]) -> tuple[list[SuccessItem], list[FailedItem]]:
        if len(emails) > 1 and self.process_emails_individually:
            extracted_list: list[SuccessItem] = []
            failed_list: list[FailedItem] = []
            for email in emails:
                extracted, failed = self._parse_batch([email])
                extracted_list.extend(extracted)
                failed_list.extend(failed)
            return extracted_list, failed_list

        return self._parse_batch(emails)

    def _parse_batch(self, emails: list[EmailItem]) -> tuple[list[SuccessItem], list[FailedItem]]:
        extracted_list: list[SuccessItem] = []
        failed_list: list[FailedItem] = []

        if not emails:
            return extracted_list, failed_list

        email_map: dict[str, EmailItem] = {mail.uid: mail for mail in emails}

        prompt = self._build_batch_prompt(emails)
        
        last_error = None
        for ia_client in self.ia_clients:
            try:
                gemini_result: IAExtractionResponse = ia_client.generate_structured_output(
                    prompt=prompt,
                    response_schema=IAExtractionResponse,
                )
                break
            except Exception as error:
                last_error = error
        else:
            if last_error is not None:
                raise last_error
            raise RuntimeError("No IA clients configured")

        for appt in gemini_result.extracted_appointments:
            original_mail = email_map.get(appt.email_id)
            if original_mail is None and len(emails) == 1:
                # Some local models fail to copy an opaque UID even when the
                # batch contains only one email. The sole email is unambiguous.
                original_mail = emails[0]
            if original_mail:
                if not appt.date or not appt.date.strip():
                    failed_list.append(
                        FailedItem(
                            error="El turno no contiene una fecha identificable",
                            mail=original_mail,
                        )
                    )
                    continue
                extracted_list.append(SuccessItem(appointment=appt, mail=original_mail))

        for failed_info in gemini_result.failed_emails:
            original_mail = email_map.get(failed_info.email_id)
            if original_mail is None and len(emails) == 1:
                original_mail = emails[0]
            if original_mail:
                failed_list.append(FailedItem(error=failed_info.error_message, mail=original_mail))

        return extracted_list, failed_list
