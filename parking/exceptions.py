class ParkingSystemError(Exception):
    """Excepción base del sistema de parking."""
    pass


class InvalidLicensePlateError(ParkingSystemError):
    """Lanzada cuando la matrícula no tiene un formato válido."""
    pass


class ActiveReservationExistsError(ParkingSystemError):
    """Lanzada cuando el vehículo ya posee una reserva activa o pendiente."""
    pass


class NoSlotsAvailableError(ParkingSystemError):
    """Lanzada cuando no hay plazas libres en el aparcamiento."""
    pass


class ReservationNotFoundError(ParkingSystemError):
    """Lanzada cuando el identificador de reserva no existe."""
    pass


class InvalidOperationError(ParkingSystemError):
    """Lanzada ante operaciones inválidas en el estado actual de la reserva."""
    pass

