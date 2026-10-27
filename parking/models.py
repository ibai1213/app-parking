from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


class ReservationStatus(str, Enum):
    """Estados posibles de una reserva según la máquina de estados del sistema."""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    WARNING_SENT = "WARNING_SENT"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"

    @classmethod
    def active_statuses(cls) -> set["ReservationStatus"]:
        """Estados que representan una reserva viva que impide otra reserva del mismo vehículo."""
        return {cls.PENDING, cls.ACTIVE, cls.WARNING_SENT}


@dataclass
class ParkingSlot:
    """
    Entidad ParkingSlot (Plaza de aparcamiento).
    Representa una plaza numerada de 1 a total_slots.
    """
    id: int
    is_occupied: bool = False
    current_reservation_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "is_occupied": self.is_occupied,
            "current_reservation_id": self.current_reservation_id
        }


@dataclass
class Reservation:
    """
    Entidad Reservation (Reserva).
    Gestiona la asociación de vehículo, plaza y ventana de tiempo.
    """
    id: str
    slot_id: int
    license_plate: str
    car_model: str
    arrival_time: datetime
    duration_minutes: int
    end_time: datetime
    status: ReservationStatus = ReservationStatus.ACTIVE
    warning_notified: bool = False

    @classmethod
    def create(
        cls,
        slot_id: int,
        license_plate: str,
        car_model: str,
        arrival_time: datetime,
        duration_minutes: int,
        current_time: Optional[datetime] = None,
        reservation_id: Optional[str] = None
    ) -> "Reservation":
        """Factory method para construir una nueva reserva con cálculo automático de end_time y estado."""
        res_id = reservation_id or str(uuid.uuid4())
        ref_time = current_time or datetime.now()
        from datetime import timedelta
        end_time = arrival_time + timedelta(minutes=duration_minutes)

        # Si la llegada es futura frente al tiempo de referencia, arranca en PENDING; de lo contrario, ACTIVE.
        initial_status = ReservationStatus.PENDING if arrival_time > ref_time else ReservationStatus.ACTIVE

        return cls(
            id=res_id,
            slot_id=slot_id,
            license_plate=license_plate,
            car_model=car_model,
            arrival_time=arrival_time,
            duration_minutes=duration_minutes,
            end_time=end_time,
            status=initial_status,
            warning_notified=False
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "slot_id": self.slot_id,
            "license_plate": self.license_plate,
            "car_model": self.car_model,
            "arrival_time": self.arrival_time.isoformat() if self.arrival_time else None,
            "duration_minutes": self.duration_minutes,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status.value,
            "warning_notified": self.warning_notified
        }

