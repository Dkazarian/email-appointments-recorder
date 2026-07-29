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
    def __init__(self, ia_clients):
        self.ia_clients = list(ia_clients) if isinstance(ia_clients, (list, tuple)) else [ia_clients]

    def _build_batch_prompt(self, emails: list[EmailItem]) -> str:
        prompt = (
            "Analiza el siguiente lote de correos electrónicos y clasifícalos en el JSON de respuesta:\n"
            "1. Si encuentras turnos, extrae los datos en 'extracted_appointments' vinculando su 'email_id'.\n"
            "Un mismo correo puede informar varios turnos para el mismo paciente; en ese caso, "
            "crea un elemento separado por cada turno y repite el mismo 'email_id'.\n"
            "La primera línea suele contener el nombre del paciente y las líneas siguientes contienen "
            "estudio, lugar, fecha y hora. Usa el nombre del encabezado para cada turno del correo. "
            "Extrae todos los datos que estén presentes; no uses null para un dato que aparezca en el texto.\n"
            "2. Si un correo NO contiene ningún turno médico o es imposible de parsear, agrega su 'email_id' "
            "junto con el motivo del fallo en la lista 'failed_emails'.\n\n"
            "Sé estricto. Cada email_id provisto debe aparecer en alguna de las dos listas.\n\n"
        )
        for mail in emails:
            prompt += f"=== INICIO CORREO ID: {mail.uid} ===\n"
            prompt += f"Contenido:\n{mail.body}\n"
            prompt += f"=== FIN CORREO ID: {mail.uid} ===\n\n"
        return prompt

    def parse_all(self, emails: list[EmailItem]) -> tuple[list[SuccessItem], list[FailedItem]]:
   
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
            if original_mail:
                extracted_list.append(SuccessItem(appointment=appt, mail=original_mail))

        for failed_info in gemini_result.failed_emails:
            original_mail = email_map.get(failed_info.email_id)
            if original_mail:
                failed_list.append(FailedItem(error=failed_info.error_message, mail=original_mail))

        return extracted_list, failed_list
