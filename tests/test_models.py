import unittest

from app.models import Appointment


class AppointmentTests(unittest.TestCase):
    def test_accepts_unstructured_appointment_data(self):
        appointment = Appointment(
            study="Radiografia",
            clinic="Clinica Rosa",
            date="24/3",
            time="15:55",
            patient_name="Ernesto",
        )

        self.assertEqual(appointment.patient_name, "Ernesto")
        self.assertEqual(appointment.model_dump(), {
            "patient_name": "Ernesto",
            "clinic": "Clinica Rosa",
            "study": "Radiografia",
            "study_detail": None,
            "date": "24/3",
            "time": "15:55",
        })

    def test_missing_values_are_nullable(self):
        appointment = Appointment(study="Laboratorio")

        self.assertIsNone(appointment.clinic)
        self.assertIsNone(appointment.date)
        self.assertIsNone(appointment.time)
        self.assertIsNone(appointment.study_detail)

    def test_rejects_fields_not_in_the_extraction_schema(self):
        with self.assertRaises(ValueError):
            Appointment(study="Radiografia", doctor="Dr. Smith")


if __name__ == "__main__":
    unittest.main()
