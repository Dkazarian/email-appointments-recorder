from pydantic import BaseModel, ConfigDict, Field


class Appointment(BaseModel):
    """Datos de un turno extraídos de un correo electrónico en español."""
    model_config = ConfigDict(extra="forbid")

    patient_name: str | None = Field(
        default=None,
        description="Nombre completo del paciente, o null si no se puede identificar.",
    )
    clinic: str | None = Field(
        default=None,
        description="Nombre de la clínica, centro médico, doctor, o null si no se menciona.",
    )
    study: str | None = Field(
        default=None,
        description="Estudio médico o examen solicitado, conservando el texto en español.",
    )
    study_detail: str | None = Field(
        default=None,
        description="Full study description as it appears in the email.",
    )
    date: str | None = Field(
        default=None,
        description=(
            "Fecha del turno tal como aparece en el correo. Preferir DD/MM/YYYY; "
            "si no aparece el año, conservar DD/MM."
        ),
    )
    time: str | None = Field(
        default=None,
        description="Hora del turno en formato de 24 horas HH:MM, o null si no aparece.",
    )
