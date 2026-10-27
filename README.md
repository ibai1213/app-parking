# Sistema de Gestión y Reserva de Parking Inteligente

Backend en Python de alto rendimiento y seguridad concurrente para la administración automatizada de plazas de aparcamiento, validación de matrícula única, alertas anticipadas de vencimiento (-15 min) y liberación automática de plazas por expiración.

---

## 🛠️ Arquitectura y Estructura del Proyecto

```text
app parking/
│
├── parking/
│   ├── __init__.py           # Exportaciones del paquete
│   ├── models.py             # Entidades ParkingSlot, Reservation y Enum ReservationStatus
│   ├── normalizer.py         # Normalización y validación estricta de matrículas (US-02, NFR-2)
│   ├── exceptions.py         # Jerarquía de excepciones tipadas del sistema
│   └── system.py             # Clase ParkingSystem con lógica de negocio y protección concurrente (RLock)
│
├── tests/
│   ├── __init__.py
│   └── test_parking_system.py # Suite completa de pruebas unitarias (14 tests cubriendo US-01 a US-04 y NFRs)
│
├── app.py                    # Aplicación híbrida: UI interactiva en Streamlit + CLI Demo
└── README.md                 # Documentación técnica completa
```

---

## 📋 Cumplimiento de Historias de Usuario

| Historia | Descripción | Implementación y Verificación |
| :--- | :--- | :--- |
| **US-01: Reserva de Plaza** | Matrícula, modelo, hora y duración. Asignación secuencial (1 a N), bloqueo de plaza (`is_occupied=True`) y retorno de `reservation_id` y `end_time`. | `ParkingSystem.create_reservation()`. Comprueba plazas disponibles y rechaza con mensaje claro si está completo. |
| **US-02: Matrícula Única** | Normalización de matrícula (mayúsculas, sin espacios ni guiones). Denegación si ya tiene reserva `PENDING`, `ACTIVE` o `WARNING_SENT`. | `normalize_license_plate()` y `ParkingSystem.has_active_reservation()`. |
| **US-03: Alerta -15 min y Ampliación** | Proceso periódico detecta $\le 15$ min restantes, pasa a `WARNING_SENT` y emite evento/notificación. Posibilidad de ampliar estancia con `extend_reservation()`. | `ParkingSystem.process_background_tasks()` y `ParkingSystem.extend_reservation()` (vuelve a `ACTIVE` y resetea flags). |
| **US-04: Liberación Automática** | Si `current_time >= end_time` y no se amplió, estado pasa a `EXPIRED` y la plaza queda inmediatamente libre (`is_occupied=False`). | `ParkingSystem.process_background_tasks()`. La plaza vuelve a estar disponible para nuevos vehículos. |

---

## 🔒 Requisitos No Funcionales (NFR)

1. **Concurrencia / Thread-Safety (NFR-1):**
   - Toda operación de asignación de plazas, comprobación de matrículas activas, ampliación y liberación automática está protegida mediante `threading.RLock()`.
   - Testeado con 50 hilos concurrentes compitiendo por 20 plazas: 20 asignaciones únicas exactas, 30 rechazos controlados sin colisión de plazas.
2. **Normalización de Matrículas (NFR-2):**
   - Transforma automáticamente formatos como `" 1234 - abc "` o `"12-34.abc"` a `"1234ABC"`.
   - Previene duplicidades por errores de digitación.

---

## 🚀 Ejecución y Pruebas

### 1. Ejecutar la Suite de Pruebas Unitarias
Para correr los 14 tests automatizados con Python 3.12:

```powershell
& "C:\Users\hp\AppData\Local\Programs\Python\Python312\python.exe" -m unittest discover -s tests -v
```

### 2. Ejecutar la Demo en Consola (CLI)
Muestra paso a paso el ciclo de vida de una reserva: creación, rechazo por duplicado, alerta a 15 min, ampliación y auto-liberación.

```powershell
& "C:\Users\hp\AppData\Local\Programs\Python\Python312\python.exe" app.py
```

### 3. Ejecutar el Panel Interactivo (Streamlit UI)
Interfaz web interactiva donde puedes ver el mapa de plazas en tiempo real (verde, rojo, naranja, azul), registrar reservas, simular el avance del tiempo (+5m, +15m, +30m, +60m) y gestionar ampliaciones:

```powershell
& "C:\Users\hp\AppData\Local\Programs\Python\Python312\python.exe" -m streamlit run app.py
```

---

## 💻 Ejemplo de Uso de la API en Python

```python
from datetime import datetime
from parking import ParkingSystem

# 1. Inicializar sistema con 100 plazas
parking = ParkingSystem(total_slots=100)

# 2. Comprobar si un vehículo tiene reserva activa
has_active = parking.has_active_reservation("1234-ABC") # False

# 3. Crear una reserva
res = parking.create_reservation(
    license_plate=" 1234 - abc ",
    car_model="Tesla Model Y",
    arrival_time=datetime.now(),
    duration_minutes=60
)
print(res)
# {
#   'success': True,
#   'reservation_id': 'd69e...',
#   'slot_id': 1,
#   'end_time': datetime(...),
#   'status': 'ACTIVE',
#   ...
# }

# 4. Ampliar tiempo de estancia (+30 minutos)
ext = parking.extend_reservation(res["reservation_id"], extra_minutes=30)

# 5. Ejecutar tareas en segundo plano (alertas y auto-liberación)
parking.process_background_tasks()

# También se puede iniciar un hilo en segundo plano automático:
# parking.start_background_worker(interval_seconds=1.0)
```

