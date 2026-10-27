from datetime import datetime, timedelta
import logging
import threading
import time
from typing import Callable, Dict, List, Optional

from parking.models import ParkingSlot, Reservation, ReservationStatus
from parking.normalizer import normalize_license_plate
from parking.exceptions import (
    ActiveReservationExistsError,
    InvalidLicensePlateError,
    NoSlotsAvailableError,
    ReservationNotFoundError,
)

logger = logging.getLogger("ParkingSystem")


class ParkingSystem:
    """
    Sistema de Gestión y Reserva de Parking Inteligente.
    Cumple con la especificación ParkingSystemSpec, historias de usuario (US-01 a US-04)
    y requisitos no funcionales (concurrencia y normalización).
    """

    def __init__(self, total_slots: int = 100):
        """Inicializa el parking con N plazas y estructuras de almacenamiento protegidas por lock."""
        if total_slots <= 0:
            raise ValueError("El número total de plazas debe ser mayor a 0.")

        self.total_slots = total_slots
        self.lock = threading.RLock()

        # Plazas indexadas de 1 a total_slots
        self.slots: Dict[int, ParkingSlot] = {
            slot_id: ParkingSlot(id=slot_id, is_occupied=False, current_reservation_id=None)
            for slot_id in range(1, total_slots + 1)
        }

        # Registro de reservas indexadas por ID (UUID)
        self.reservations: Dict[str, Reservation] = {}

        # Sistema de eventos / callbacks para alertas de vencimiento
        self.notification_callbacks: List[Callable[[Reservation, dict], None]] = []
        self.notifications_log: List[dict] = []

        # Control de hilo secundario periódico opcional
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_worker_event = threading.Event()

    def register_notification_callback(self, callback: Callable[[Reservation, dict], None]) -> None:
        """Registra un callback que se invocará cuando se dispare una notificación."""
        with self.lock:
            self.notification_callbacks.append(callback)

    def has_active_reservation(self, license_plate: str) -> bool:
        """
        Verifica si la matrícula ya tiene una reserva activa (PENDING, ACTIVE, WARNING_SENT).
        Aplica normalización automática previa a la consulta.
        """
        try:
            normalized_plate = normalize_license_plate(license_plate)
        except InvalidLicensePlateError:
            return False

        with self.lock:
            active_statuses = ReservationStatus.active_statuses()
            for res in self.reservations.values():
                if res.license_plate == normalized_plate and res.status in active_statuses:
                    return True
            return False

    def create_reservation(
        self,
        license_plate: str,
        car_model: str,
        arrival_time: datetime,
        duration_minutes: int,
        current_time: Optional[datetime] = None
    ) -> dict:
        """
        Crea una nueva reserva si el coche no tiene reservas previas y hay plazas libres.
        Retorna dict con éxito, slot_id asignado, reservation_id y end_time.
        """
        ref_time = current_time or datetime.now()

        # 1. Normalización y validación de matrícula
        try:
            normalized_plate = normalize_license_plate(license_plate)
        except InvalidLicensePlateError as e:
            return {
                "success": False,
                "message": f"Error de validación de matrícula: {str(e)}",
                "reservation_id": None,
                "slot_id": None,
                "end_time": None
            }

        # 2. Validación de modelo de coche y duración
        if not car_model or not car_model.strip():
            return {
                "success": False,
                "message": "El modelo de coche no puede estar vacío.",
                "reservation_id": None,
                "slot_id": None,
                "end_time": None
            }

        if duration_minutes <= 0:
            return {
                "success": False,
                "message": "La duración de la reserva debe ser un número entero mayor a 0 minutos.",
                "reservation_id": None,
                "slot_id": None,
                "end_time": None
            }

        if not isinstance(arrival_time, datetime):
            return {
                "success": False,
                "message": "La hora de llegada debe ser un objeto datetime válido.",
                "reservation_id": None,
                "slot_id": None,
                "end_time": None
            }

        with self.lock:
            # 3. Comprobar restricción de matrícula única activa
            if self.has_active_reservation(normalized_plate):
                return {
                    "success": False,
                    "message": f"Operación denegada: La matrícula '{normalized_plate}' ya cuenta con una reserva activa o pendiente.",
                    "reservation_id": None,
                    "slot_id": None,
                    "end_time": None
                }

            # 4. Asignación de la primera plaza libre (de 1 a N)
            assigned_slot: Optional[ParkingSlot] = None
            for slot_id in range(1, self.total_slots + 1):
                slot = self.slots[slot_id]
                if not slot.is_occupied:
                    assigned_slot = slot
                    break

            if assigned_slot is None:
                return {
                    "success": False,
                    "message": "Operación denegada: El aparcamiento está completo (no hay plazas libres).",
                    "reservation_id": None,
                    "slot_id": None,
                    "end_time": None
                }

            # 5. Crear la reserva y bloquear la plaza
            reservation = Reservation.create(
                slot_id=assigned_slot.id,
                license_plate=normalized_plate,
                car_model=car_model.strip(),
                arrival_time=arrival_time,
                duration_minutes=duration_minutes,
                current_time=ref_time
            )

            # Asignación y bloqueo atómico
            assigned_slot.is_occupied = True
            assigned_slot.current_reservation_id = reservation.id
            self.reservations[reservation.id] = reservation

            logger.info(
                f"Reserva creada: {reservation.id} | Plaza {assigned_slot.id} | Matrícula {normalized_plate} | Fin: {reservation.end_time}"
            )

            return {
                "success": True,
                "reservation_id": reservation.id,
                "slot_id": assigned_slot.id,
                "license_plate": reservation.license_plate,
                "car_model": reservation.car_model,
                "arrival_time": reservation.arrival_time,
                "duration_minutes": reservation.duration_minutes,
                "end_time": reservation.end_time,
                "status": reservation.status.value,
                "message": f"Reserva creada exitosamente. Plaza {assigned_slot.id} asignada."
            }

    def extend_reservation(
        self,
        reservation_id: str,
        extra_minutes: int,
        current_time: Optional[datetime] = None
    ) -> dict:
        """
        Amplía el tiempo de una reserva activa existente.
        Incrementa end_time y resetea flags de aviso y estado según la máquina de estados.
        """
        if extra_minutes <= 0:
            return {
                "success": False,
                "message": "Los minutos adicionales deben ser mayores a 0.",
                "reservation_id": reservation_id,
                "new_end_time": None
            }

        ref_time = current_time or datetime.now()

        with self.lock:
            reservation = self.reservations.get(reservation_id)
            if reservation is None:
                return {
                    "success": False,
                    "message": f"No se encontró ninguna reserva con el identificador '{reservation_id}'.",
                    "reservation_id": reservation_id,
                    "new_end_time": None
                }

            # Solo se pueden ampliar reservas que no hayan concluido ni expirado
            if reservation.status in (ReservationStatus.EXPIRED, ReservationStatus.COMPLETED):
                return {
                    "success": False,
                    "message": f"No se puede ampliar una reserva con estado '{reservation.status.value}'.",
                    "reservation_id": reservation_id,
                    "new_end_time": None
                }

            # Incrementar tiempo
            reservation.end_time += timedelta(minutes=extra_minutes)
            reservation.duration_minutes += extra_minutes

            # Máquina de estados: Vuelve a ACTIVE si el nuevo tiempo restante supera los 15 minutos
            remaining_seconds = (reservation.end_time - ref_time).total_seconds()
            if remaining_seconds > 15 * 60:
                reservation.status = ReservationStatus.ACTIVE
                reservation.warning_notified = False
            else:
                # Si aún queda <= 15 minutos a pesar de la ampliación, permanece o pasa a WARNING_SENT
                reservation.status = ReservationStatus.WARNING_SENT

            logger.info(
                f"Reserva ampliada: {reservation.id} (+{extra_minutes} min). Nueva hora fin: {reservation.end_time}"
            )

            return {
                "success": True,
                "reservation_id": reservation.id,
                "slot_id": reservation.slot_id,
                "new_end_time": reservation.end_time,
                "duration_minutes": reservation.duration_minutes,
                "status": reservation.status.value,
                "message": f"Reserva ampliada con éxito por {extra_minutes} minutos. Nueva hora fin: {reservation.end_time.isoformat()}."
            }

    def process_background_tasks(self, current_time: Optional[datetime] = None) -> dict:
        """
        Método de ejecución periódica (cron/loop/worker):
        1. Transiciona reservas PENDING a ACTIVE si ya alcanzaron la hora de llegada.
        2. Comprueba alertas de 15 minutos: si remaining <= 15 min y no advertido -> WARNING_SENT y notificación.
        3. Comprueba expiraciones (current_time >= end_time): pasa a EXPIRED y libera plazas automáticamente.
        """
        ref_time = current_time or datetime.now()
        warnings_triggered = 0
        expirations_triggered = 0
        activated_count = 0

        with self.lock:
            for reservation in list(self.reservations.values()):
                # 1. Activación de PENDING si ya es su hora
                if reservation.status == ReservationStatus.PENDING:
                    if ref_time >= reservation.arrival_time:
                        reservation.status = ReservationStatus.ACTIVE
                        activated_count += 1

                # 2. Comprobación de expiración (current_time >= end_time)
                if reservation.status in (ReservationStatus.ACTIVE, ReservationStatus.WARNING_SENT, ReservationStatus.PENDING):
                    if ref_time >= reservation.end_time:
                        # Expirar reserva
                        reservation.status = ReservationStatus.EXPIRED
                        expirations_triggered += 1

                        # Liberar plaza asociada inmediatamente
                        slot = self.slots.get(reservation.slot_id)
                        if slot and slot.current_reservation_id == reservation.id:
                            slot.is_occupied = False
                            slot.current_reservation_id = None

                        logger.info(
                            f"Reserva expirada automáticamente: {reservation.id} | Plaza {reservation.slot_id} liberada."
                        )
                        continue

                # 3. Comprobación de alertas a 15 minutos del vencimiento
                if reservation.status in (ReservationStatus.ACTIVE, ReservationStatus.PENDING):
                    remaining_seconds = (reservation.end_time - ref_time).total_seconds()
                    # Si faltan <= 15 minutos (900 segundos) y > 0
                    if 0 < remaining_seconds <= (15 * 60) and not reservation.warning_notified:
                        reservation.status = ReservationStatus.WARNING_SENT
                        reservation.warning_notified = True
                        warnings_triggered += 1

                        remaining_min = round(remaining_seconds / 60, 1)
                        notification = {
                            "type": "EXPIRATION_WARNING",
                            "reservation_id": reservation.id,
                            "license_plate": reservation.license_plate,
                            "slot_id": reservation.slot_id,
                            "end_time": reservation.end_time,
                            "remaining_minutes": remaining_min,
                            "timestamp": ref_time,
                            "message": (
                                f"ALERTA: Faltan {remaining_min} minutos para que expire la reserva de la plaza "
                                f"{reservation.slot_id} (Vehículo: {reservation.license_plate}). "
                                f"Puede ampliar su estancia mediante extend_reservation."
                            )
                        }

                        self.notifications_log.append(notification)
                        logger.warning(notification["message"])

                        # Disparar callbacks registrados
                        for cb in self.notification_callbacks:
                            try:
                                cb(reservation, notification)
                            except Exception as e:
                                logger.error(f"Error al ejecutar callback de notificación: {e}")

        return {
            "ref_time": ref_time,
            "activated_count": activated_count,
            "warnings_triggered": warnings_triggered,
            "expirations_triggered": expirations_triggered
        }

    def complete_reservation(self, reservation_id: str) -> dict:
        """
        Permite a un vehículo retirarse antes de tiempo, liberando la plaza y marcando COMPLETED.
        """
        with self.lock:
            reservation = self.reservations.get(reservation_id)
            if not reservation:
                return {"success": False, "message": f"Reserva '{reservation_id}' no encontrada."}

            if reservation.status not in ReservationStatus.active_statuses():
                return {
                    "success": False,
                    "message": f"No se puede completar una reserva con estado {reservation.status.value}."
                }

            reservation.status = ReservationStatus.COMPLETED
            slot = self.slots.get(reservation.slot_id)
            if slot and slot.current_reservation_id == reservation.id:
                slot.is_occupied = False
                slot.current_reservation_id = None

            return {
                "success": True,
                "reservation_id": reservation.id,
                "slot_id": reservation.slot_id,
                "message": f"Reserva {reservation.id} completada. Plaza {reservation.slot_id} liberada."
            }

    def get_reservation(self, reservation_id: str) -> Optional[Reservation]:
        """Obtiene una reserva por su identificador."""
        with self.lock:
            return self.reservations.get(reservation_id)

    def get_slot(self, slot_id: int) -> Optional[ParkingSlot]:
        """Obtiene el estado de una plaza por su ID."""
        with self.lock:
            return self.slots.get(slot_id)

    def get_available_slots(self) -> List[int]:
        """Retorna la lista de identificadores de plazas actualmente libres."""
        with self.lock:
            return [s.id for s in self.slots.values() if not s.is_occupied]

    def get_occupied_slots(self) -> List[int]:
        """Retorna la lista de identificadores de plazas ocupadas."""
        with self.lock:
            return [s.id for s in self.slots.values() if s.is_occupied]

    def get_system_summary(self) -> dict:
        """Retorna métricas generales del estado actual del parking."""
        with self.lock:
            occupied = sum(1 for s in self.slots.values() if s.is_occupied)
            available = self.total_slots - occupied
            active_res = sum(
                1 for r in self.reservations.values()
                if r.status in ReservationStatus.active_statuses()
            )
            return {
                "total_slots": self.total_slots,
                "occupied_slots": occupied,
                "available_slots": available,
                "active_reservations": active_res,
                "total_reservations_recorded": len(self.reservations),
                "total_notifications_sent": len(self.notifications_log)
            }

    # ==========================
    # Background Thread Support
    # ==========================

    def start_background_worker(self, interval_seconds: float = 1.0) -> None:
        """Inicia un hilo en segundo plano que llama a process_background_tasks periódicamente."""
        with self.lock:
            if self._worker_thread and self._worker_thread.is_alive():
                return

            self._stop_worker_event.clear()

            def _worker_loop():
                while not self._stop_worker_event.is_set():
                    try:
                        self.process_background_tasks()
                    except Exception as e:
                        logger.error(f"Excepción en background worker: {e}")
                    time.sleep(interval_seconds)

            self._worker_thread = threading.Thread(target=_worker_loop, daemon=True)
            self._worker_thread.start()

    def stop_background_worker(self) -> None:
        """Detiene el hilo en segundo plano."""
        self._stop_worker_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3.0)
            self._worker_thread = None

