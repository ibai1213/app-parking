"""
Parking Management System Package.
"""
from parking.models import ParkingSlot, Reservation, ReservationStatus
from parking.normalizer import normalize_license_plate
from parking.system import ParkingSystem
from parking.exceptions import (
    ParkingSystemError,
    InvalidLicensePlateError,
    ActiveReservationExistsError,
    NoSlotsAvailableError,
    ReservationNotFoundError,
    InvalidOperationError,
)

__all__ = [
    "ParkingSlot",
    "Reservation",
    "ReservationStatus",
    "normalize_license_plate",
    "ParkingSystem",
    "ParkingSystemError",
    "InvalidLicensePlateError",
    "ActiveReservationExistsError",
    "NoSlotsAvailableError",
    "ReservationNotFoundError",
    "InvalidOperationError",
]

