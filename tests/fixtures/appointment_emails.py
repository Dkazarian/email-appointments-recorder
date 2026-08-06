"""Anonymized appointment emails shared by extractor and E2E tests."""

from dataclasses import dataclass

from app.email_client import EmailItem


@dataclass(frozen=True)
class ExpectedAppointment:
    patient_name: str | None
    study: str


@dataclass(frozen=True)
class AppointmentFixture:
    email: EmailItem
    extracted: tuple[ExpectedAppointment, ...]


APPOINTMENT_FIXTURES = [
    AppointmentFixture(
        email=EmailItem(
            uid="email-1", url=None, sender="secretaria@example.com",
            reply_to="secretaria@example.com", recipients=[],
            subject="Turno de Ana", sent_at=None,
            body=(
                "Paciente: Ana Perez\n"
                "Turno 1 - Estudio: Laboratorio; ClÃ­nica: Clinica Central; "
                "Fecha: 24/03; Hora: 15:30\n"
                "Turno 2 - Estudio: Radiografia; Detalle: Radiografia mano izquierda; "
                "ClÃ­nica: Centro Norte; Fecha: 25/03; Hora: 09:00"
            ),
        ),
        extracted=(
            ExpectedAppointment("Ana Perez", "Laboratorio"),
            ExpectedAppointment("Ana Perez", "Radiografia"),
        ),
    ),
    AppointmentFixture(
        email=EmailItem(
            uid="email-2", url=None, sender="secretaria@example.com",
            reply_to="secretaria@example.com", recipients=[],
            subject="Turno de Juan", sent_at=None,
            body=(
                "Paciente: Juan Gomez\n"
                "Turno 1 - Estudio: Radiografia; Detalle: Radiografia mano izquierda; "
                "Fecha: 14/05; Hora: 19:30\n"
                "Turno 2 - Estudio: Audiometria; ClÃ­nica: Calle 123; "
                "Fecha: 15/05; Hora: 10:30"
            ),
        ),
        extracted=(
            ExpectedAppointment("Juan Gomez", "Radiografia"),
            ExpectedAppointment("Juan Gomez", "Audiometria"),
        ),
    ),
    AppointmentFixture(
        email=EmailItem(
            uid="email-3", url=None, sender="secretaria@example.com",
            reply_to="secretaria@example.com", recipients=[],
            subject="Solicitud de Turno – Paciente SORIA, Leandro Matías", sent_at=None,
            body=(
                "Buenas tardes,\n\n"
                "RMN: Turno para el 25/8- 8hs en Aráoz 1180 entre Güemes y Charcas, CABA\n\n"
                "PSICO:La Licenciada se comunicara con su Actor para coordinar y luego lo informaremos\n\n"
                "Saludos\n Valeria"
            ),
        ),
        extracted=(ExpectedAppointment("Leandro Matías Soria", "RMN"),),
    ),
    AppointmentFixture(
        email=EmailItem(
            uid="email-4", url=None, sender="secretaria@example.com",
            reply_to="secretaria@example.com", recipients=[],
            subject="SOLICITO TURNO MEDICO FERRARO, Julieta Belén - [CASE-QZL-417]", sent_at=None,
            body=(
                "Buen dia REPROGRAMACION TURNOS\n\n"
                "RX: 18/08 de 09:00 hs a 17:30 hs en Lavalle 142  CABA   CONCURRIR CON DNI\n\n"
                "EMG: 18/08 a las 15:10 hs en Perú 736 CABA\n\n"
                "Saludos\nMariela"
            ),
        ),
        extracted=(
            ExpectedAppointment("Julieta Belén Ferraro", "RX"),
            ExpectedAppointment("Julieta Belén Ferraro", "EMG"),
        ),
    ),
    AppointmentFixture(
        email=EmailItem(
            uid="email-5", url=None, sender="secretaria@example.com",
            reply_to="secretaria@example.com", recipients=[],
            subject="Solicita turno estudios", sent_at=None,
            body=(
                "Buen dia  \n\n"
                "TAC . 05/05  a las 9:30 hs EN ARÁOZ  1180 CABA \n\n"
                "RMN: 05/05 a las 10:00 hs EN ARÁOZ 1180 CABA \n\n"
                "PSICO :  \nFecha de turno: 5/5\nHorario: 9.45 hs\n"
                "Profesional: Lic. Salvatierra Nora\nDirección: Honduras 2240 CABA\n"
                "MODALIDAD VIRTUAL (videollamada de WhatsApp)\n\nSaludos\nMariela"
            ),
        ),
        extracted=(
            ExpectedAppointment(None, "TAC"),
            ExpectedAppointment(None, "RMN"),
            ExpectedAppointment(None, "PSICO"),
        ),
    ),
    AppointmentFixture(
        email=EmailItem(
            uid="email-6", url=None, sender="secretaria@example.com",
            reply_to="secretaria@example.com", recipients=[],
            subject="MARTÍNEZ TOMÁS ALEJANDRO - DNI: 31.456.789", sent_at=None,
            body=(
                "RMN:Turno 20/08 12.00 hs.- en Aráoz 1180 entre Güemes y Charcas, CABA\n\n"
                "PSICODIAGNÓSTICO:  Se contactarán con su actor para coordinar cita. "
                "Luego enviaremos los datos para declarar.\n\nSaludos\n\nValeria"
            ),
        ),
        extracted=(ExpectedAppointment("Tomás Alejandro Martínez", "RMN"),),
    ),
    AppointmentFixture(
        email=EmailItem(
            uid="email-7", url=None, sender="secretaria@example.com",
            reply_to="secretaria@example.com", recipients=[],
            subject="BUGS BUNNY - DNI: 12.345.678", sent_at=None,
            body=(
                "PSICO: 3/8\n"
                "Horario: 13.20 hs\n"
                "Profesional: Lic. Maria\n"
                "Dirección: Segurola 1234 CABA\n"
                "\n"
                "MODALIDAD VIRTUAL (plataforma Google Meet)\n"
                "Área de Coordinación de Psicologia\n"
                "\n"
                "Saludos\n"
                "Lu"
            ),
        ),
        extracted=(ExpectedAppointment("BUGS BUNNY", "PSICO"),),
    ),
]

EMAILS = [fixture.email for fixture in APPOINTMENT_FIXTURES]
