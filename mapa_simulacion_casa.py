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
    """
    if room == "cocina" and random.random() < 0.1:
        return round(random.uniform(2, 8), 1)
    if room == "bano" and random.random() < 0.15:
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

# Definimos un plano sencillo 2D de la casa (coherente con una casa normal)
# Ventana de ~800x600 con habitaciones tipo:
# [   SALÓN    |  COCINA   ]
# [DORMITORIO |   BAÑO    ]
ROOM_LAYOUT = {
    "salon":      (50, 50, 380, 260),
    "cocina":     (420, 50, 750, 260),
    "dormitorio": (50, 300, 380, 550),
    "bano":       (420, 300, 750, 450),
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
    g = int(80 * (1 - n) + 80 * n)  # un poco de verde para no ser tan chillón
    b = int(255 * (1 - n))
    return f"#{r:02x}{g:02x}{b:02x}"


class HouseGUI:
    def __init__(self, update_interval_ms=5000):
        self.update_interval_ms = update_interval_ms

        self.root = tk.Tk()
        self.root.title("Simulación Casa IoT - Plano 2D")

        self.canvas = tk.Canvas(self.root, width=820, height=600, bg="white")
        self.canvas.pack(fill="both", expand=True)

        self.font_title = tkfont.Font(family="Helvetica", size=14, weight="bold")
        self.font_info = tkfont.Font(family="Helvetica", size=11)

        # Diccionarios para acceder rápidamente a los elementos del canvas
        self.room_rects = {}
        self.room_texts = {}

        self._draw_house_layout()

        # Arrancamos la primera actualización
        self.root.after(200, self.update_simulation)

    def _draw_house_layout(self):
        """
        Dibuja las habitaciones como rectángulos con su nombre.
        """
        for room, (x1, y1, x2, y2) in ROOM_LAYOUT.items():
            rect = self.canvas.create_rectangle(
                x1, y1, x2, y2,
                fill="#d9eaf7",
                outline="black",
                width=2
            )
            # Texto centrado dentro de la habitación
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            label = ROOM_LABELS.get(room, room.capitalize())
            text_id = self.canvas.create_text(
                cx, cy,
                text=f"{label}\n\n(esperando datos...)",
                font=self.font_info,
                justify="center"
            )

            self.room_rects[room] = rect
            self.room_texts[room] = text_id

        # Título arriba
        self.canvas.create_text(
            410, 20,
            text="Plano 2D - Sensores Casa IoT",
            font=self.font_title
        )

    def update_simulation(self):
        """
        Llama a la simulación, envía datos a InfluxDB y actualiza el plano.
        """
        readings = simulate_house_once()

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

    def _update_room_visual(self, reading):
        """
        Actualiza el rectángulo y el texto de una habitación concreta.
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
        text = (
            f"{label}\n\n"
            f"T: {reading['temperature']} °C\n"
            f"Luz: {lights_str}\n"
            f"Potencia: {reading['power_usage']} W\n"
            f"Agua: {reading['water_flow']} L/min"
        )
        self.canvas.itemconfig(text_id, text=text)

    def run(self):
        self.root.mainloop()


def main():
    print("Iniciando simulación de casa IoT con plano 2D (Ctrl+C para detener ventana)...\n")
    gui = HouseGUI(update_interval_ms=5000)  # 5 segundos entre lecturas
    gui.run()


if __name__ == "__main__":
    main()
