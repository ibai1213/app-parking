from datetime import datetime, timedelta
import threading
import unittest

from parking.models import ParkingSlot, Reservation, ReservationStatus
from parking.normalizer import normalize_license_plate
from parking.exceptions import InvalidLicensePlateError
from parking.system import ParkingSystem


class TestParkingNormalizer(unittest.TestCase):
    """Pruebas unitarias de normalización de matrículas (US-02, NFR-2)."""

    def test_normalize_valid_variants(self):
        self.assertEqual(normalize_license_plate("1234abc"), "1234ABC")
        self.assertEqual(normalize_license_plate(" 1234 ABC "), "1234ABC")
        self.assertEqual(normalize_license_plate("12-34-abc"), "1234ABC")
        self.assertEqual(normalize_license_plate("12.34.ABC"), "1234ABC")
        self.assertEqual(normalize_license_plate("12_34_abc"), "1234ABC")
        self.assertEqual(normalize_license_plate(" 5678 - ZYX "), "5678ZYX")

    def test_normalize_invalid_inputs(self):
        with self.assertRaises(InvalidLicensePlateError):
            normalize_license_plate("")
        with self.assertRaises(InvalidLicensePlateError):
            normalize_license_plate("   ")
        with self.assertRaises(InvalidLicensePlateError):
            normalize_license_plate("---")
        with self.assertRaises(InvalidLicensePlateError):
            normalize_license_plate("123$ABC")


class TestParkingSystemUserStories(unittest.TestCase):
    """Pruebas completas de los Criterios de Aceptación US-01, US-02, US-03, US-04."""

    def setUp(self):
        # Crear un parking con 5 plazas para pruebas ágiles
        self.parking = ParkingSystem(total_slots=5)
        self.base_time = datetime(2026, 10, 27, 10, 0, 0)

    # -------------------------------------------------------------
    # US-01: Reserva de Plaza de Aparcamiento
    # -------------------------------------------------------------
    def test_us01_create_reservation_success(self):
        """Asigna la primera plaza libre (1 a N), marca plaza como ocupada y retorna id y end_time."""
        result = self.parking.create_reservation(
            license_plate="1234BBB",
            car_model="Toyota Corolla",
            arrival_time=self.base_time,
            duration_minutes=60,
            current_time=self.base_time
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["slot_id"], 1)
        self.assertIsNotNone(result["reservation_id"])
        expected_end = self.base_time + timedelta(minutes=60)
        self.assertEqual(result["end_time"], expected_end)
        self.assertEqual(result["status"], ReservationStatus.ACTIVE.value)

        # Verificar que la plaza 1 está ocupada
        slot = self.parking.get_slot(1)
        self.assertTrue(slot.is_occupied)
        self.assertEqual(slot.current_reservation_id, result["reservation_id"])

    def test_us01_assigns_sequential_free_slots(self):
        """Asigna plazas disponibles en orden (primera libre de 1 a N)."""
        r1 = self.parking.create_reservation("1111AAA", "Model S", self.base_time, 30, current_time=self.base_time)
        r2 = self.parking.create_reservation("2222BBB", "Golf", self.base_time, 30, current_time=self.base_time)
        r3 = self.parking.create_reservation("3333CCC", "Focus", self.base_time, 30, current_time=self.base_time)

        self.assertEqual(r1["slot_id"], 1)
        self.assertEqual(r2["slot_id"], 2)
        self.assertEqual(r3["slot_id"], 3)

    def test_us01_reject_when_parking_is_full(self):
        """Si el parking está lleno, rechaza con mensaje de error descriptivo."""
        # Llenar las 5 plazas
        for i in range(1, 6):
            res = self.parking.create_reservation(
                license_plate=f"{i}{i}{i}{i}ABC",
                car_model="Car",
                arrival_time=self.base_time,
                duration_minutes=60,
                current_time=self.base_time
            )
            self.assertTrue(res["success"])

        # Intentar una 6ta reserva
        overflow = self.parking.create_reservation(
            license_plate="9999XYZ",
            car_model="Truck",
            arrival_time=self.base_time,
            duration_minutes=30,
            current_time=self.base_time
        )
        self.assertFalse(overflow["success"])
        self.assertIn("está completo", overflow["message"])
        self.assertIsNone(overflow["slot_id"])

    # -------------------------------------------------------------
    # US-02: Restricción de Matrícula Única
    # -------------------------------------------------------------
    def test_us02_duplicate_active_reservation_rejected(self):
        """Impide que un mismo vehículo tenga múltiples reservas activas/pendientes simultáneas."""
        res1 = self.parking.create_reservation(
            license_plate="1234-xyz",
            car_model="Audi A3",
            arrival_time=self.base_time,
            duration_minutes=60,
            current_time=self.base_time
        )
        self.assertTrue(res1["success"])

        # Intentar de nuevo con ligeras variaciones de formato (" 1234 XYZ ")
        res2 = self.parking.create_reservation(
            license_plate=" 1234 XYZ ",
            car_model="Audi A3",
            arrival_time=self.base_time,
            duration_minutes=45,
            current_time=self.base_time
        )
        self.assertFalse(res2["success"])
        self.assertIn("ya cuenta con una reserva activa o pendiente", res2["message"])

    def test_us02_has_active_reservation_check(self):
        """Verifica la respuesta de has_active_reservation con normalización."""
        self.assertFalse(self.parking.has_active_reservation("7777KLM"))

        self.parking.create_reservation(
            license_plate=" 7777-klm ",
            car_model="Nissan Leaf",
            arrival_time=self.base_time,
            duration_minutes=60,
            current_time=self.base_time
        )

        self.assertTrue(self.parking.has_active_reservation("7777KLM"))
        self.assertTrue(self.parking.has_active_reservation("77-77 klm"))

    def test_us02_allows_new_reservation_after_previous_completed_or_expired(self):
        """Permite una nueva reserva una vez que la anterior ya expiró o se completó."""
        res1 = self.parking.create_reservation(
            license_plate="5555ZZZ",
            car_model="BMW 320",
            arrival_time=self.base_time,
            duration_minutes=30,
            current_time=self.base_time
        )
        self.assertTrue(res1["success"])

        # Completar la reserva
        comp = self.parking.complete_reservation(res1["reservation_id"])
        self.assertTrue(comp["success"])
        self.assertFalse(self.parking.has_active_reservation("5555ZZZ"))

        # Crear nueva reserva para la misma matrícula
        res2 = self.parking.create_reservation(
            license_plate="5555ZZZ",
            car_model="BMW 320",
            arrival_time=self.base_time + timedelta(hours=1),
            duration_minutes=30,
            current_time=self.base_time
        )
        self.assertTrue(res2["success"])

    # -------------------------------------------------------------
    # US-03: Alerta de Vencimiento (-15 min) y Ampliación
    # -------------------------------------------------------------
    def test_us03_warning_sent_at_15_minutes(self):
        """Evalúa reservas: cuando faltan <= 15 min, pasa a WARNING_SENT y dispara notificación."""
        notifications_received = []

        def notification_listener(res, notif):
            notifications_received.append((res.id, notif["remaining_minutes"]))

        self.parking.register_notification_callback(notification_listener)

        # Reserva de 60 minutos: fin a las 11:00
        res = self.parking.create_reservation(
            license_plate="8888JJJ",
            car_model="Seat Leon",
            arrival_time=self.base_time,
            duration_minutes=60,
            current_time=self.base_time
        )
        res_id = res["reservation_id"]

        # 1. A las 10:30 (faltan 30 min): No debe disparar alerta
        t_10_30 = self.base_time + timedelta(minutes=30)
        self.parking.process_background_tasks(current_time=t_10_30)
        r_obj = self.parking.get_reservation(res_id)
        self.assertEqual(r_obj.status, ReservationStatus.ACTIVE)
        self.assertFalse(r_obj.warning_notified)
        self.assertEqual(len(notifications_received), 0)

        # 2. A las 10:46 (faltan 14 minutos <= 15 min): Debe pasar a WARNING_SENT y notificar
        t_10_46 = self.base_time + timedelta(minutes=46)
        stats = self.parking.process_background_tasks(current_time=t_10_46)
        self.assertEqual(stats["warnings_triggered"], 1)

        r_obj = self.parking.get_reservation(res_id)
        self.assertEqual(r_obj.status, ReservationStatus.WARNING_SENT)
        self.assertTrue(r_obj.warning_notified)
        self.assertEqual(len(notifications_received), 1)
        self.assertEqual(notifications_received[0][0], res_id)
        self.assertEqual(notifications_received[0][1], 14.0)

        # 3. Segunda llamada a las 10:47: No debe duplicar notificación (warning_notified == True)
        t_10_47 = self.base_time + timedelta(minutes=47)
        stats2 = self.parking.process_background_tasks(current_time=t_10_47)
        self.assertEqual(stats2["warnings_triggered"], 0)
        self.assertEqual(len(notifications_received), 1)

    def test_us03_extend_reservation(self):
        """Amplía el tiempo, actualiza end_time y retorna el estado a ACTIVE reseteando flags."""
        res = self.parking.create_reservation(
            license_plate="9999KKK",
            car_model="Renault Clio",
            arrival_time=self.base_time,
            duration_minutes=60,
            current_time=self.base_time
        )
        res_id = res["reservation_id"]

        # Simular alerta a los 46 minutos (faltan 14 min)
        t_10_46 = self.base_time + timedelta(minutes=46)
        self.parking.process_background_tasks(current_time=t_10_46)
        r_obj = self.parking.get_reservation(res_id)
        self.assertEqual(r_obj.status, ReservationStatus.WARNING_SENT)
        self.assertTrue(r_obj.warning_notified)

        # Ampliar estancia en 30 minutos a las 10:48 (nuevo fin: 11:30, tiempo restante: 42 min > 15 min)
        t_10_48 = self.base_time + timedelta(minutes=48)
        ext = self.parking.extend_reservation(res_id, extra_minutes=30, current_time=t_10_48)

        self.assertTrue(ext["success"])
        self.assertEqual(ext["duration_minutes"], 90)
        expected_new_end = self.base_time + timedelta(minutes=90)
        self.assertEqual(ext["new_end_time"], expected_new_end)
        self.assertEqual(ext["status"], ReservationStatus.ACTIVE.value)

        # Comprobar que warning_notified se reseteó a False
        r_obj = self.parking.get_reservation(res_id)
        self.assertEqual(r_obj.status, ReservationStatus.ACTIVE)
        self.assertFalse(r_obj.warning_notified)

    # -------------------------------------------------------------
    # US-04: Liberación Automática de Plaza por Expiración
    # -------------------------------------------------------------
    def test_us04_auto_release_on_expiration(self):
        """Cuando current_time >= end_time, pasa a EXPIRED y la plaza pasa inmediatamente a libre."""
        res = self.parking.create_reservation(
            license_plate="1212MMM",
            car_model="Ford Fiesta",
            arrival_time=self.base_time,
            duration_minutes=30,
            current_time=self.base_time
        )
        res_id = res["reservation_id"]
        slot_id = res["slot_id"]

        # Plaza ocupada
        self.assertTrue(self.parking.get_slot(slot_id).is_occupied)

        # Simular tiempo después del vencimiento (10:31 >= 10:30)
        t_10_31 = self.base_time + timedelta(minutes=31)
        stats = self.parking.process_background_tasks(current_time=t_10_31)

        self.assertEqual(stats["expirations_triggered"], 1)

        # Estado de la reserva -> EXPIRED
        r_obj = self.parking.get_reservation(res_id)
        self.assertEqual(r_obj.status, ReservationStatus.EXPIRED)

        # Plaza liberada
        slot = self.parking.get_slot(slot_id)
        self.assertFalse(slot.is_occupied)
        self.assertIsNone(slot.current_reservation_id)

        # La plaza ahora puede ser ocupada por otro vehículo
        new_res = self.parking.create_reservation(
            license_plate="3434NNN",
            car_model="Peugeot 208",
            arrival_time=t_10_31,
            duration_minutes=45,
            current_time=t_10_31
        )
        self.assertTrue(new_res["success"])
        self.assertEqual(new_res["slot_id"], slot_id)

    # -------------------------------------------------------------
    # Pruebas de Concurrencia / Thread-Safety (NFR-1)
    # -------------------------------------------------------------
    def test_thread_safety_concurrent_reservations(self):
        """Verifica que múltiples hilos compitiendo por plazas no generen dobles asignaciones."""
        parking = ParkingSystem(total_slots=20)
        num_threads = 50  # Más peticiones concurrentes que plazas disponibles
        results = []

        def worker(thread_idx: int):
            plate = f"{thread_idx:04d}TH"
            res = parking.create_reservation(
                license_plate=plate,
                car_model="TestCar",
                arrival_time=datetime.now(),
                duration_minutes=30
            )
            results.append(res)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]

        # Deben haber exactamente 20 asignaciones exitosas (plazas 1 a 20)
        self.assertEqual(len(successful), 20)
        self.assertEqual(len(failed), 30)

        # Cada plaza asignada debe ser única (sin colisiones)
        assigned_slots = [r["slot_id"] for r in successful]
        self.assertEqual(len(assigned_slots), len(set(assigned_slots)))
        self.assertEqual(set(assigned_slots), set(range(1, 21)))

    # -------------------------------------------------------------
    # Pruebas de Casos Extremos y Manejo de Errores
    # -------------------------------------------------------------
    def test_invalid_parameters(self):
        # Duración <= 0
        r1 = self.parking.create_reservation("1111AAA", "Model", self.base_time, duration_minutes=0)
        self.assertFalse(r1["success"])
        self.assertIn("mayor a 0", r1["message"])

        # Modelo vacío
        r2 = self.parking.create_reservation("1111AAA", "", self.base_time, duration_minutes=30)
        self.assertFalse(r2["success"])
        self.assertIn("no puede estar vacío", r2["message"])

        # Matrícula inválida
        r3 = self.parking.create_reservation("$$$$$", "Model", self.base_time, duration_minutes=30)
        self.assertFalse(r3["success"])

        # Ampliación de reserva inexistente
        ext = self.parking.extend_reservation("non-existent-id", 15)
        self.assertFalse(ext["success"])

    def test_background_worker_lifecycle(self):
        """Verifica que el background worker inicie y se detenga limpiamente sin excepciones."""
        self.parking.start_background_worker(interval_seconds=0.1)
        self.assertTrue(self.parking._worker_thread.is_alive())
        # Llamar de nuevo es idempotente
        self.parking.start_background_worker(interval_seconds=0.1)
        self.parking.stop_background_worker()
        self.assertIsNone(self.parking._worker_thread)


if __name__ == "__main__":
    unittest.main()

