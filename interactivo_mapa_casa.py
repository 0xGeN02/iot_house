"""Simulador de una casa IoT que genera datos de sensores, los envía a InfluxDB
y muestra una simulación 2D de la casa con los sensores."""

#http://localhost:8086
#http://localhost:3000
#http://localhost:5678

import time
import math
import random
import os
from datetime import datetime
import requests
from dotenv import load_dotenv

import tkinter as tk
from tkinter import font as tkfont

# ==============================
# Cargar configuración segura
# ==============================
load_dotenv()

INFLUX_URL = os.getenv("INFLUX_URL")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")


def write_to_influx(measurement, tags, fields, timestamp=None):
    """
    Envía una línea a InfluxDB en formato Line Protocol.
    """
    # Si no hay URL o token configurados, no intentamos enviar nada
    if not INFLUX_URL or not INFLUX_TOKEN or not INFLUX_ORG or not INFLUX_BUCKET:
        return

    line = measurement
    for k, v in tags.items():
        line += f",{k}={v}"

    line += " "
    field_parts = []
    for k, v in fields.items():
        if isinstance(v, str):
            field_parts.append(f'{k}="{v}"')
        else:
            field_parts.append(f"{k}={v}")
    line += ",".join(field_parts)

    if timestamp is not None:
        line += f" {timestamp}"

    headers = {
        "Authorization": f"Token {INFLUX_TOKEN}",
        "Content-Type": "text/plain; charset=utf-8",
    }

    params = {
        "org": INFLUX_ORG,
        "bucket": INFLUX_BUCKET,
        "precision": "ns",
    }

    try:
        r = requests.post(
            INFLUX_URL,
            params=params,
            data=line.encode("utf-8"),
            headers=headers,
            timeout=5,
        )
        if r.status_code != 204:
            print("⚠️ Error enviando a InfluxDB:", r.status_code, r.text)
    except requests.exceptions.RequestException as e:
        print("⚠️ Error de conexión a InfluxDB:", e)


# ==============================
# Simulación de la casa IoT
# ==============================

ROOMS = ["salon", "dormitorio", "cocina", "bano"]


def simulate_temperature(room, hour):
    """
    Simula la temperatura en función de la hora del día y la habitación.
    """
    base_daily = 20 + 4 * math.sin(2 * math.pi * (hour - 14) / 24)
    room_offset = {
        "salon": 1.0,
        "dormitorio": -0.5,
        "cocina": 1.5,
        "bano": 0.0,
    }.get(room, 0.0)
    noise = random.uniform(-0.5, 0.5)
    return round(base_daily + room_offset + noise, 1)


def simulate_lights(_, hour):
    """
    Simula si las luces están encendidas o apagadas en función de la hora del día.
    """
    if 8 <= hour < 18:
        prob_on = 0.15
    elif 18 <= hour < 23:
        prob_on = 0.7
    else:
        prob_on = 0.3
    return 1 if random.random() < prob_on else 0


def simulate_power_usage(room, lights_on):
    """
    Simula el consumo de energía en función de la habitación y si las luces están encendidas.
    """
    base_power = {
        "salon": 60,
        "dormitorio": 20,
        "cocina": 80,
        "bano": 10,
    }.get(room, 20)

    lights_power = 10 if lights_on else 0

    peak_power = 0
    if room == "cocina" and random.random() < 0.1:
        peak_power = random.choice([500, 800, 1200])
    elif room == "bano" and random.random() < 0.05:
        peak_power = random.choice([600, 900])

    return round(base_power + lights_power + peak_power, 1)


def simulate_water_flow(room):
    """
    Simula el flujo de agua en función de la habitación.
    Ahora con más probabilidad para que se vea en la interfaz.
    """
    if room == "cocina":
        # 40% de probabilidad de que haya agua en cada lectura
        if random.random() < 0.4:
            return round(random.uniform(2, 8), 1)
    elif room == "bano":
        # 50% de probabilidad en baño
        if random.random() < 0.5:
            return round(random.uniform(3, 12), 1)
    return 0.0


def simulate_house_once():
    """
    Simula una lectura de sensores en todas las habitaciones de la casa.
    """
    now = datetime.now()
    hour = now.hour + now.minute / 60.0

    readings = []

    for room in ROOMS:
        temp = simulate_temperature(room, hour)
        lights_on = simulate_lights(room, hour)
        power = simulate_power_usage(room, lights_on)
        water = simulate_water_flow(room)

        readings.append({
            "timestamp": now.isoformat(timespec="seconds"),
            "room": room,
            "temperature": temp,
            "lights_on": lights_on,
            "power_usage": power,
            "water_flow": water,
        })

    return readings


# ==============================
# GUI: Plano 2D de la casa
# ==============================

# Definimos un plano 2x2 continuo:
#  -----------------------------------------
# |                |                       |
# |     SALÓN      |        COCINA         |
# |                |                       |
# |----------------+-----------------------|
# |                |                       |
# |  DORMITORIO    |         BAÑO          |
# |                |                       |
#  -----------------------------------------
HOUSE_BOUNDS = (80, 80, 760, 560)  # borde exterior de la casa

x1_house, y1_house, x2_house, y2_house = HOUSE_BOUNDS
mid_x = (x1_house + x2_house) // 2
mid_y = (y1_house + y2_house) // 2

ROOM_LAYOUT = {
    "salon":      (x1_house, y1_house, mid_x,   mid_y),
    "cocina":     (mid_x,    y1_house, x2_house, mid_y),
    "dormitorio": (x1_house, mid_y,    mid_x,   y2_house),
    "bano":       (mid_x,    mid_y,    x2_house, y2_house),
}

ROOM_LABELS = {
    "salon": "Salón",
    "dormitorio": "Dormitorio",
    "cocina": "Cocina",
    "bano": "Baño",
}


def temperature_to_color(temp):
    """
    Convierte una temperatura aprox. [15, 30] ºC en un color de fondo.
    Azul = frío, rojo = caliente.
    """
    t_min, t_max = 15.0, 30.0
    # Normalizamos entre 0 y 1
    n = (temp - t_min) / (t_max - t_min)
    n = max(0.0, min(1.0, n))
    # Interpolamos entre azul (0) y rojo (1)
    r = int(255 * n)
    g = int(80 * (1 - n) + 80 * n)  # un poco de verde para suavizar
    b = int(255 * (1 - n))
    return f"#{r:02x}{g:02x}{b:02x}"


class HouseGUI:
    def __init__(self, update_interval_ms=5000):
        self.update_interval_ms = update_interval_ms

        # =======================
        # Ventana principal y layout
        # =======================
        self.root = tk.Tk()
        self.root.title("Simulación Casa IoT - Plano 2D")

        # Modo de simulación: "auto" o "manual"
        self.mode = tk.StringVar(value="auto")

        # Variables de control manual por habitación
        self.manual_temperature = {}
        self.manual_lights = {}
        self.manual_power = {}
        self.manual_water = {}
        self.manual_widgets = []

        # Marco principal: plano a la izquierda, panel de control a la derecha
        self.main_frame = tk.Frame(self.root, bg="white")
        self.main_frame.pack(fill="both", expand=True)

        # Canvas para el plano
        self.canvas = tk.Canvas(self.main_frame, width=900, height=650, bg="white")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Panel lateral derecho para controles
        self.control_frame = tk.Frame(self.main_frame, width=320, bg="white")
        self.control_frame.pack(side="right", fill="y")

        self.font_title = tkfont.Font(family="Helvetica", size=16, weight="bold")
        self.font_info = tkfont.Font(family="Helvetica", size=11)
        self.font_small = tkfont.Font(family="Helvetica", size=9)

        # Diccionarios para acceder rápidamente a los elementos del canvas
        self.room_rects = {}
        self.room_texts = {}

        # Dibujar plano y construir panel de control
        self._draw_house_layout()
        self._build_control_panel()

        # Arrancamos la primera actualización
        self.root.after(200, self.update_simulation)

    def _draw_house_layout(self):
        """
        Dibuja las paredes de la casa y las habitaciones como un plano continuo.
        """
        # Título
        self.canvas.create_text(
            450, 30,
            text="Plano 2D - Casa IoT",
            font=self.font_title
        )

        # Borde exterior de la casa (pared exterior más gruesa)
        x1, y1, x2, y2 = HOUSE_BOUNDS
        self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline="black",
            width=5
        )

        # Paredes interiores (división 2x2)
        # Pared vertical central
        self.canvas.create_line(
            mid_x, y1, mid_x, y2,
            fill="black",
            width=3
        )
        # Pared horizontal central
        self.canvas.create_line(
            x1, mid_y, x2, mid_y,
            fill="black",
            width=3
        )

        # Dibujo de habitaciones (rectángulos coloreables encima del plano)
        for room, (rx1, ry1, rx2, ry2) in ROOM_LAYOUT.items():
            # Rectángulo para el color de temperatura + borde para "luces"
            rect = self.canvas.create_rectangle(
                rx1 + 3, ry1 + 3, rx2 - 3, ry2 - 3,
                fill="#d9eaf7",
                outline="black",
                width=2
            )

            # Texto centrado dentro de la habitación
            cx = (rx1 + rx2) / 2
            cy = (ry1 + ry2) / 2
            label = ROOM_LABELS.get(room, room.capitalize())
            text_id = self.canvas.create_text(
                cx, cy,
                text=f"{label}\n\n(esperando datos...)",
                font=self.font_info,
                justify="center"
            )

            self.room_rects[room] = rect
            self.room_texts[room] = text_id

    def _build_control_panel(self):
        """
        Construye el panel lateral derecho con:
        - Selector de modo (automático / manual)
        - Controles manuales por habitación (luces, temperatura, potencia, agua)
        """
        # Selector de modo
        mode_frame = tk.LabelFrame(
            self.control_frame,
            text="Modo de simulación",
            bg="white",
            font=self.font_info
        )
        mode_frame.pack(fill="x", padx=10, pady=(15, 5))

        rb_auto = tk.Radiobutton(
            mode_frame,
            text="Automático",
            variable=self.mode,
            value="auto",
            bg="white",
            font=self.font_small,
            command=self.on_mode_change
        )
        rb_manual = tk.Radiobutton(
            mode_frame,
            text="Manual",
            variable=self.mode,
            value="manual",
            bg="white",
            font=self.font_small,
            command=self.on_mode_change
        )
        rb_auto.pack(anchor="w", padx=5, pady=2)
        rb_manual.pack(anchor="w", padx=5, pady=2)

        # No añadimos los radio buttons a manual_widgets porque deben seguir activos
        # siempre para poder cambiar de modo.

        # Separador visual
        sep = tk.Frame(self.control_frame, height=2, bg="#cccccc")
        sep.pack(fill="x", padx=10, pady=(5, 10))

        # Controles por habitación
        for room in ROOMS:
            lf = tk.LabelFrame(
                self.control_frame,
                text=ROOM_LABELS.get(room, room.capitalize()),
                bg="white",
                font=self.font_info
            )
            lf.pack(fill="x", padx=10, pady=5)
            self.manual_widgets.append(lf)

            # Luces
            lights_var = tk.BooleanVar(value=False)
            self.manual_lights[room] = lights_var
            chk = tk.Checkbutton(
                lf,
                text="Luces encendidas",
                variable=lights_var,
                bg="white",
                font=self.font_small,
                command=lambda r=room: self._update_room_visual_from_manual(r)
            )
            chk.pack(anchor="w", padx=5, pady=(3, 6))
            self.manual_widgets.append(chk)

            # Temperatura
            temp_var = tk.DoubleVar(value=21.0)
            self.manual_temperature[room] = temp_var
            tk.Label(
                lf,
                text="Temperatura (°C)",
                bg="white",
                font=self.font_small
            ).pack(anchor="w", padx=5)
            temp_scale = tk.Scale(
                lf,
                from_=15,
                to=30,
                orient="horizontal",
                resolution=0.5,
                variable=temp_var,
                length=200,
                command=lambda _val, r=room: self._update_room_visual_from_manual(r),
                bg="white"
            )
            temp_scale.pack(anchor="w", padx=5)
            self.manual_widgets.append(temp_scale)

            # Potencia
            power_var = tk.DoubleVar(value=50.0)
            self.manual_power[room] = power_var
            tk.Label(
                lf,
                text="Potencia (W)",
                bg="white",
                font=self.font_small
            ).pack(anchor="w", padx=5, pady=(5, 0))
            power_scale = tk.Scale(
                lf,
                from_=0,
                to=2000,
                orient="horizontal",
                resolution=10,
                variable=power_var,
                length=200,
                command=lambda _val, r=room: self._update_room_visual_from_manual(r),
                bg="white"
            )
            power_scale.pack(anchor="w", padx=5)
            self.manual_widgets.append(power_scale)

            # Agua solo en cocina y baño
            if room in ("cocina", "bano"):
                water_var = tk.DoubleVar(value=0.0)
                self.manual_water[room] = water_var
                tk.Label(
                    lf,
                    text="Flujo de agua (L/min)",
                    bg="white",
                    font=self.font_small
                ).pack(anchor="w", padx=5, pady=(5, 0))
                water_scale = tk.Scale(
                    lf,
                    from_=0.0,
                    to=15.0,
                    orient="horizontal",
                    resolution=0.5,
                    variable=water_var,
                    length=200,
                    command=lambda _val, r=room: self._update_room_visual_from_manual(r),
                    bg="white"
                )
                water_scale.pack(anchor="w", padx=5, pady=(0, 5))
                self.manual_widgets.append(water_scale)

        # Al inicio, los controles manuales están deshabilitados porque el modo es "auto"
        self._set_manual_controls_state(enabled=False)

    def _set_manual_controls_state(self, enabled: bool):
        """
        Activa o desactiva todos los controles manuales (sliders, checkboxes).
        Los radio buttons de modo quedan siempre activos.
        """
        state = "normal" if enabled else "disabled"
        for widget in self.manual_widgets:
            try:
                widget.configure(state=state)
            except tk.TclError:
                # Algunos contenedores pueden no aceptar 'state'
                pass

    def on_mode_change(self):
        """
        Callback al cambiar entre modo automático y manual.
        """
        manual = self.mode.get() == "manual"
        self._set_manual_controls_state(enabled=manual)

        # Si cambiamos a manual, actualizamos el plano inmediatamente
        if manual:
            for room in ROOMS:
                self._update_room_visual_from_manual(room)

    def _build_manual_readings(self, now: datetime):
        """
        Construye las lecturas a partir de los valores seleccionados manualmente
        en la interfaz.
        """
        readings = []
        timestamp = now.isoformat(timespec="seconds")

        for room in ROOMS:
            temp = float(self.manual_temperature[room].get())
            lights_on = 1 if self.manual_lights[room].get() else 0
            power = float(self.manual_power[room].get())

            if room in ("cocina", "bano"):
                water = float(self.manual_water[room].get())
            else:
                water = 0.0

            readings.append({
                "timestamp": timestamp,
                "room": room,
                "temperature": temp,
                "lights_on": lights_on,
                "power_usage": power,
                "water_flow": water,
            })

        return readings

    def update_simulation(self):
        """
        Llama a la simulación (automática o manual), envía datos a InfluxDB
        y actualiza el plano.
        """
        now = datetime.now()

        if self.mode.get() == "auto":
            readings = simulate_house_once()
        else:
            readings = self._build_manual_readings(now)

        print("-" * 80)
        for r in readings:
            # Mostrar por terminal (igual que en tu script original)
            print(
                f"[{r['timestamp']}] room={r['room']}, "
                f"temp={r['temperature']}°C, lights_on={r['lights_on']}, "
                f"power={r['power_usage']}W, water={r['water_flow']} L/min"
            )

            # Enviar a InfluxDB (si está configurado)
            write_to_influx(
                measurement="temperature",
                tags={"room": r["room"]},
                fields={"value": r["temperature"]},
            )
            write_to_influx(
                measurement="lights",
                tags={"room": r["room"]},
                fields={"state": r["lights_on"]},
            )
            write_to_influx(
                measurement="power_usage",
                tags={"room": r["room"]},
                fields={"value": r["power_usage"]},
            )
            write_to_influx(
                measurement="water_flow",
                tags={"room": r["room"]},
                fields={"value": r["water_flow"]},
            )

            # Actualizar GUI
            self._update_room_visual(r)

        # Reprogramar siguiente actualización
        self.root.after(self.update_interval_ms, self.update_simulation)

    def _update_room_visual_from_manual(self, room):
        """
        Actualiza visualmente una habitación usando los valores manuales,
        pero solo si el modo actual es 'manual'.
        """
        if self.mode.get() != "manual":
            return

        rect_id = self.room_rects.get(room)
        text_id = self.room_texts.get(room)
        if rect_id is None or text_id is None:
            return

        temp = float(self.manual_temperature[room].get())
        lights_on = 1 if self.manual_lights[room].get() else 0
        power = float(self.manual_power[room].get())
        if room in ("cocina", "bano"):
            water = float(self.manual_water[room].get())
        else:
            water = 0.0

        fill_color = temperature_to_color(temp)
        outline_color = "gold" if lights_on else "black"

        self.canvas.itemconfig(rect_id, fill=fill_color, outline=outline_color)

        label = ROOM_LABELS.get(room, room.capitalize())
        lights_str = "ON" if lights_on else "OFF"
        lights_icon = "💡" if lights_on else "💤"

        text = (
            f"{label} {lights_icon}\n\n"
            f"T: {temp:.1f} °C\n"
            f"Luz: {lights_str}\n"
            f"Potencia: {power:.0f} W\n"
            f"Agua: {water:.1f} L/min"
        )
        self.canvas.itemconfig(text_id, text=text)

    def _update_room_visual(self, reading):
        """
        Actualiza el rectángulo y el texto de una habitación concreta
        a partir de una lectura (modo automático o manual).
        """
        room = reading["room"]
        if room not in self.room_rects:
            return

        rect_id = self.room_rects[room]
        text_id = self.room_texts[room]

        # Color según temperatura
        fill_color = temperature_to_color(reading["temperature"])
        # Borde amarillo si la luz está encendida
        outline_color = "gold" if reading["lights_on"] else "black"

        self.canvas.itemconfig(rect_id, fill=fill_color, outline=outline_color)

        label = ROOM_LABELS.get(room, room.capitalize())
        lights_str = "ON" if reading["lights_on"] else "OFF"
        lights_icon = "💡" if reading["lights_on"] else "💤"

        text = (
            f"{label} {lights_icon}\n\n"
            f"T: {reading['temperature']} °C\n"
            f"Luz: {lights_str}\n"
            f"Potencia: {reading['power_usage']} W\n"
            f"Agua: {reading['water_flow']} L/min"
        )
        self.canvas.itemconfig(text_id, text=text)

    def run(self):
        self.root.mainloop()


def main():
    print("Iniciando simulación de casa IoT con plano 2D (Ctrl+C para cerrar la ventana)...\n")
    gui = HouseGUI(update_interval_ms=5000)  # 5 segundos entre lecturas
    gui.run()


if __name__ == "__main__":
    main()
