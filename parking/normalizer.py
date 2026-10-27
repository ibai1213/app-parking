import re
from parking.exceptions import InvalidLicensePlateError


def normalize_license_plate(plate: str) -> str:
    """
    Normaliza y valida una matrícula vehicular según la especificación:
    - Convierte a mayúsculas.
    - Elimina espacios en blanco (iniciales, intermedios, finales).
    - Elimina guiones, puntos y separadores comunes.

    Ejemplos:
        " 1234 abc "   -> "1234ABC"
        "12-34-ABC"    -> "1234ABC"
        " 5678 - ZYX " -> "5678ZYX"
    """
    if not plate or not isinstance(plate, str):
        raise InvalidLicensePlateError("La matrícula debe ser una cadena de texto no vacía.")

    # Eliminar espacios en blanco, guiones, puntos y barras
    cleaned = re.sub(r"[\s\-_./]+", "", plate).upper()

    if not cleaned:
        raise InvalidLicensePlateError("La matrícula no contiene caracteres válidos tras la normalización.")

    # Validar que contenga caracteres alfanuméricos razonables
    if not re.match(r"^[A-Z0-9]+$", cleaned):
        raise InvalidLicensePlateError(f"La matrícula normalizada '{cleaned}' contiene caracteres no permitidos.")

    return cleaned

