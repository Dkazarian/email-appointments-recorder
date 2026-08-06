"""Anonymized appointment emails shared by extractor and E2E tests."""

from dataclasses import dataclass
from datetime import datetime

from app.email_client import EmailItem


CURRENT_YEAR = datetime.now().year


@dataclass(frozen=True)
class ExpectedAppointment:
    patient_name: str | None
    study: str
    date: str | None = None
    time: str | None = None


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
                "Turno 1 - Estudio: Laboratorio; Clínica: Clinica Central; "
                "Fecha: 24/03; Hora: 15:30\n"
                "Turno 2 - Estudio: Radiografia; Detalle: Radiografia mano izquierda; "
                "Clínica: Centro Norte; Fecha: 25/03; Hora: 09:00"
            ),
        ),
        extracted=(
            ExpectedAppointment("Ana Perez", "Laboratorio", f"24/03/{CURRENT_YEAR}", "15:30"),
            ExpectedAppointment("Ana Perez", "Radiografia", f"25/03/{CURRENT_YEAR}", "09:00"),
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
                "Turno 2 - Estudio: Audiometria; Clí­nica: Calle 123; "
                "Fecha: 15/05; Hora: 10:30"
            ),
        ),
        extracted=(
            ExpectedAppointment("Juan Gomez", "Radiografia", f"14/05/{CURRENT_YEAR}", "19:30"),
            ExpectedAppointment("Juan Gomez", "Audiometria", f"15/05/{CURRENT_YEAR}", "10:30"),
        ),
    ),
    AppointmentFixture(
        email=EmailItem(
            uid="email-3", url=None, sender="secretaria@example.com",
            reply_to="secretaria@example.com", recipients=[],
            subject="Solicitud de Turno - Paciente SORIA, Leandro Matías", sent_at=None,
            body=(
                "Buenas tardes,\n\n"
                "RMN: Turno para el 25/8- 8hs en Aráoz 1180 entre Güemes y Charcas, CABA\n\n"
                "PSICO:La Licenciada se comunicara con su Actor para coordinar y luego lo informaremos\n\n"
                "Saludos\n Valeria"
            ),
        ),
        extracted=(ExpectedAppointment("Leandro Matías Soria", "RMN", f"25/08/{CURRENT_YEAR}", "08:00"),),
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
            ExpectedAppointment("Julieta Belén Ferraro", "RX", f"18/08/{CURRENT_YEAR}", "09:00"),
            ExpectedAppointment("Julieta Belén Ferraro", "EMG", f"18/08/{CURRENT_YEAR}", "15:10"),
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
            ExpectedAppointment(None, "TAC", f"05/05/{CURRENT_YEAR}", "09:30"),
            ExpectedAppointment(None, "RMN", f"05/05/{CURRENT_YEAR}", "10:00"),
            ExpectedAppointment(None, "PSICO", f"05/05/{CURRENT_YEAR}", "09:45"),
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
        extracted=(ExpectedAppointment("Tomás Alejandro Martínez", "RMN", f"20/08/{CURRENT_YEAR}", "12:00"),),
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
        extracted=(ExpectedAppointment("BUGS BUNNY", "PSICO", f"03/08/{CURRENT_YEAR}", "13:20"),),
    ),
]

EMAILS = [fixture.email for fixture in APPOINTMENT_FIXTURES]
