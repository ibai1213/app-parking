import os
import sys
from datetime import datetime, timedelta
import streamlit as st

# Asegurar que el módulo parking sea localizable
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from parking.models import ReservationStatus
from parking.normalizer import normalize_license_plate
from parking.system import ParkingSystem


def init_session_state():
    if "simulated_time" not in st.session_state:
        st.session_state.simulated_time = datetime.now().replace(microsecond=0)

    if "parking_system" not in st.session_state:
        # Por defecto 50 plazas para una visualización clara en cuadrícula (ampliable a 100)
        st.session_state.parking_system = ParkingSystem(total_slots=40)

        # Sembrar un par de reservas de ejemplo para apreciar el funcionamiento inmediato
        base_t = st.session_state.simulated_time
        st.session_state.parking_system.create_reservation(
            license_plate="1234ABC",
            car_model="Tesla Model 3",
            arrival_time=base_t - timedelta(minutes=40),
            duration_minutes=50,  # Le quedan 10 min -> entrará en alerta
            current_time=base_t
        )
        st.session_state.parking_system.create_reservation(
            license_plate="5678XYZ",
            car_model="Toyota RAV4",
            arrival_time=base_t,
            duration_minutes=120, # Le quedan 120 min -> activo normal
            current_time=base_t
        )
        # Procesar estado inicial
        st.session_state.parking_system.process_background_tasks(current_time=base_t)


def run_streamlit():
    st.set_page_config(
        page_title="Gestión de Parking Inteligente",
        page_icon="🚗",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    init_session_state()
    parking: ParkingSystem = st.session_state.parking_system
    sim_time: datetime = st.session_state.simulated_time

    # Sidebar: Control de Simulación Temporal y Configuración
    with st.sidebar:
        st.header("⏱️ Reloj del Sistema")
        st.markdown(f"**Hora Actual:** `{sim_time.strftime('%Y-%m-%d %H:%M:%S')}`")

        st.subheader("Simular Avance de Tiempo")
        st.caption("Avanza el tiempo para probar alertas a 15 min (US-03) y auto-liberación por expiración (US-04).")

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            if st.button("+5 min", use_container_width=True):
                st.session_state.simulated_time += timedelta(minutes=5)
                parking.process_background_tasks(current_time=st.session_state.simulated_time)
                st.rerun()
            if st.button("+15 min", use_container_width=True):
                st.session_state.simulated_time += timedelta(minutes=15)
                parking.process_background_tasks(current_time=st.session_state.simulated_time)
                st.rerun()

        with col_t2:
            if st.button("+30 min", use_container_width=True):
                st.session_state.simulated_time += timedelta(minutes=30)
                parking.process_background_tasks(current_time=st.session_state.simulated_time)
                st.rerun()
            if st.button("+60 min", use_container_width=True):
                st.session_state.simulated_time += timedelta(minutes=60)
                parking.process_background_tasks(current_time=st.session_state.simulated_time)
                st.rerun()

        if st.button("🔄 Ejecutar Background Tasks", use_container_width=True):
            tasks_res = parking.process_background_tasks(current_time=st.session_state.simulated_time)
            st.success(
                f"Tareas ejecutadas. Alertas: {tasks_res['warnings_triggered']} | Expiradas: {tasks_res['expirations_triggered']}"
            )
            st.rerun()

        st.divider()
        st.subheader("Configuración")
        new_total = st.number_input("Total de Plazas", min_value=5, max_value=200, value=parking.total_slots, step=5)
        if new_total != parking.total_slots:
            if st.button("Reiniciar Parking con nuevo tamaño"):
                st.session_state.parking_system = ParkingSystem(total_slots=new_total)
                st.rerun()

    # Título Principal
    st.title("🚗 Sistema de Gestión y Reserva de Parking Inteligente")
    st.markdown(
        "Backend automatizado con detección de matrícula única, asignación secuencial, "
        "alertas automáticas a $\\le 15$ min y auto-liberación."
    )

    # Métricas Globales
    summary = parking.get_system_summary()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Plazas Totales", summary["total_slots"])
    m2.metric("Plazas Libres", summary["available_slots"])
    m3.metric("Plazas Ocupadas", summary["occupied_slots"])
    m4.metric("Reservas Activas", summary["active_reservations"])

    st.markdown("---")

    # Contenedor dividido en 2 columnas: Formulario y Grid de Plazas
    col_left, col_right = st.columns([1, 1.4])

    with col_left:
        st.subheader("📝 Nueva Reserva (US-01 / US-02)")
        with st.form("form_nueva_reserva"):
            input_plate = st.text_input("Matrícula del Vehículo", placeholder="Ej: 1234-ABC o 1234 abc")
            input_model = st.text_input("Modelo del Vehículo", placeholder="Ej: Audi A4, Seat Ibiza")

            col_dur1, col_dur2 = st.columns(2)
            with col_dur1:
                input_duration = st.number_input("Duración (minutos)", min_value=15, max_value=1440, value=60, step=15)
            with col_dur2:
                arrival_option = st.selectbox("Momento de Llegada", ["Llegada Ahora", "En 15 minutos", "En 30 minutos"])

            submitted = st.form_submit_button("Confirmar Reserva", use_container_width=True)

            if submitted:
                if arrival_option == "Llegada Ahora":
                    arr_time = st.session_state.simulated_time
                elif arrival_option == "En 15 minutos":
                    arr_time = st.session_state.simulated_time + timedelta(minutes=15)
                else:
                    arr_time = st.session_state.simulated_time + timedelta(minutes=30)

                res = parking.create_reservation(
                    license_plate=input_plate,
                    car_model=input_model,
                    arrival_time=arr_time,
                    duration_minutes=int(input_duration),
                    current_time=st.session_state.simulated_time
                )

                if res["success"]:
                    st.success(
                        f"✅ {res['message']} (Fin previsto: {res['end_time'].strftime('%H:%M:%S')})"
                    )
                    st.rerun()
                else:
                    st.error(f"❌ {res['message']}")

    with col_right:
        st.subheader("🅿️ Mapa de Ocupación en Tiempo Real")
        st.caption("🟢 Libre | 🔴 Ocupado Activo | 🟠 Alerta Vencimiento (<= 15 min) | 🔵 Pendiente")

        # Visualizar grid de plazas
        grid_cols = 8
        slots = list(parking.slots.values())
        rows = [slots[i:i + grid_cols] for i in range(0, len(slots), grid_cols)]

        for row in rows:
            cols = st.columns(grid_cols)
            for idx, slot in enumerate(row):
                with cols[idx]:
                    if not slot.is_occupied:
                        color = "#28a745" # verde
                        status_text = "Libre"
                        tooltip = f"Plaza #{slot.id}: Libre"
                    else:
                        res = parking.get_reservation(slot.current_reservation_id)
                        if res:
                            if res.status == ReservationStatus.WARNING_SENT:
                                color = "#fd7e14" # naranja/alerta
                                status_text = "Aviso"
                            elif res.status == ReservationStatus.PENDING:
                                color = "#17a2b8" # celeste pendiente
                                status_text = "Pend"
                            else:
                                color = "#dc3545" # rojo ocupado
                                status_text = "Ocup"
                            tooltip = f"Plaza #{slot.id}: {res.license_plate} ({res.car_model}) - Fin: {res.end_time.strftime('%H:%M')}"
                        else:
                            color = "#6c757d"
                            status_text = "Ocup"
                            tooltip = f"Plaza #{slot.id}: Ocupada"

                    st.markdown(
                        f"""
                        <div title="{tooltip}" style="
                            background-color: {color};
                            color: white;
                            border-radius: 6px;
                            padding: 8px 2px;
                            text-align: center;
                            font-size: 11px;
                            font-weight: bold;
                            margin-bottom: 6px;
                            box-shadow: 0 1px 3px rgba(0,0,0,0.15);
                        ">
                            P{slot.id}<br><span style="font-size: 9px; opacity: 0.9;">{status_text}</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

    st.markdown("---")

    # Sección de Gestión de Reservas Activas y Ampliaciones (US-03)
    st.subheader("📋 Gestión de Reservas Activas (US-03 / US-04)")

    active_reservations = [
        r for r in parking.reservations.values()
        if r.status in ReservationStatus.active_statuses()
    ]

    if not active_reservations:
        st.info("No hay reservas activas en este momento.")
    else:
        for r in active_reservations:
            with st.container():
                remaining_sec = (r.end_time - sim_time).total_seconds()
                rem_min = round(remaining_sec / 60, 1)

                badge_color = {
                    ReservationStatus.ACTIVE: "green",
                    ReservationStatus.WARNING_SENT: "orange",
                    ReservationStatus.PENDING: "blue"
                }.get(r.status, "grey")

                c1, c2, c3, c4, c5 = st.columns([1.2, 1.2, 1.2, 1.5, 2])
                with c1:
                    st.markdown(f"**Plaza #{r.slot_id}**")
                    st.caption(f"ID: {r.id[:8]}...")
                with c2:
                    st.markdown(f"🚗 `{r.license_plate}`")
                    st.caption(r.car_model)
                with c3:
                    st.markdown(f"**Fin:** {r.end_time.strftime('%H:%M:%S')}")
                    if rem_min > 0:
                        st.caption(f"Quedan: {rem_min} min")
                    else:
                        st.caption("⚠️ Tiempo vencido")
                with c4:
                    if r.status == ReservationStatus.WARNING_SENT:
                        st.warning("⚠️ ALERTA: <= 15 min")
                    elif r.status == ReservationStatus.PENDING:
                        st.info("🕒 PENDIENTE")
                    else:
                        st.success("🟢 ACTIVA")

                with c5:
                    btn_c1, btn_c2, btn_c3 = st.columns(3)
                    with btn_c1:
                        if st.button("+15m", key=f"ext15_{r.id}", help="Ampliar estancia en 15 minutos"):
                            ext_res = parking.extend_reservation(r.id, 15, current_time=sim_time)
                            if ext_res["success"]:
                                st.success("Ampliado +15 min")
                                st.rerun()
                    with btn_c2:
                        if st.button("+30m", key=f"ext30_{r.id}", help="Ampliar estancia en 30 minutos"):
                            ext_res = parking.extend_reservation(r.id, 30, current_time=sim_time)
                            if ext_res["success"]:
                                st.success("Ampliado +30 min")
                                st.rerun()
                    with btn_c3:
                        if st.button("Salida", key=f"comp_{r.id}", help="Registrar salida y liberar plaza"):
                            comp_res = parking.complete_reservation(r.id)
                            if comp_res["success"]:
                                st.info("Plaza liberada.")
                                st.rerun()
                st.divider()

    # Historial de Notificaciones y Eventos (US-03)
    st.subheader("🔔 Registro de Alertas y Eventos Automáticos")
    if parking.notifications_log:
        for notif in reversed(parking.notifications_log[-5:]):
            st.warning(
                f"[{notif['timestamp'].strftime('%H:%M:%S')}] {notif['message']}"
            )
    else:
        st.caption("Aún no se han emitido alertas de vencimiento.")


def cli_demo():
    """Modo demostración en consola si se ejecuta directamente con Python."""
    print("=" * 65)
    print("DEMO: Sistema de Gestión y Reserva de Parking Inteligente")
    print("=" * 65)

    parking = ParkingSystem(total_slots=5)
    t0 = datetime.now().replace(microsecond=0)

    print("\n1. Creando reserva para matrícula ' 1234 - abc '...")
    res1 = parking.create_reservation(" 1234 - abc ", "Tesla Model 3", t0, duration_minutes=30, current_time=t0)
    print("Resultado:", res1)

    print("\n2. Probando restricción de matrícula única (US-02)...")
    res2 = parking.create_reservation("1234ABC", "Otro Coche", t0, duration_minutes=60, current_time=t0)
    print("Resultado:", res2)

    print("\n3. Avanzando el tiempo 16 minutos (quedan 14 min <= 15 min)...")
    t1 = t0 + timedelta(minutes=16)
    stats1 = parking.process_background_tasks(current_time=t1)
    print("Alertas disparadas:", stats1["warnings_triggered"])
    print("Estado actual:", parking.get_reservation(res1["reservation_id"]).status)

    print("\n4. Ampliando la reserva 30 minutos (US-03)...")
    ext = parking.extend_reservation(res1["reservation_id"], extra_minutes=30, current_time=t1)
    print("Resultado:", ext)
    print("Nuevo estado:", parking.get_reservation(res1["reservation_id"]).status)

    print("\n5. Avanzando el tiempo al vencimiento total (US-04)...")
    t2 = t0 + timedelta(minutes=65)
    stats2 = parking.process_background_tasks(current_time=t2)
    print("Expiraciones procesadas:", stats2["expirations_triggered"])
    print("Estado final de reserva:", parking.get_reservation(res1["reservation_id"]).status)
    print("Plaza 1 ocupada?:", parking.get_slot(1).is_occupied)

    print("\n" + "=" * 65)
    print("Para iniciar el panel interactivo visual, ejecute:")
    print("  streamlit run app.py")
    print("=" * 65)


if __name__ == "__main__":
    # Si se invoca desde streamlit run
    if "streamlit" in sys.modules and any("streamlit" in arg for arg in sys.argv):
        run_streamlit()
    else:
        try:
            # Comprobar si se llamó dentro de un contexto de Streamlit
            from streamlit.runtime.scriptrunner import get_script_run_ctx
            if get_script_run_ctx():
                run_streamlit()
            else:
                cli_demo()
        except ImportError:
            cli_demo()

