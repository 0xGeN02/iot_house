"""Simulador de una casa IoT que genera datos de sensores y los envía a InfluxDB."""

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

# ==============================
# Cargar configuración segura
# ==============================
load_dotenv()

INFLUX_URL = os.getenv("INFLUX_URL")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")


def write_to_influx(measurement, tags, fields, timestamp=None) -> None:
    """
    Envía una línea a InfluxDB en formato Line Protocol.
    """
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
        r = requests.post(INFLUX_URL, params=params, data=line.encode("utf-8"), headers=headers, timeout=10)
        if r.status_code != 204:
            print("⚠️ Error enviando a InfluxDB:", r.status_code, r.text)
    except requests.exceptions.RequestException as e:
        print("⚠️ Error de conexión a InfluxDB:", e)


# ==============================
# Simulación de la casa IoT
# ==============================

ROOMS = ["salon", "dormitorio", "cocina", "bano"]


def simulate_temperature(room, hour) -> float:
    """
    Simula la temperatura en función de la hora del día y la habitación.
    """
    base_daily = 20 + 2 * math.sin(2 * math.pi * (hour - 14) / 24)
    room_offset = {
        "salon": -1.5,
        "dormitorio": 1.5,
        "cocina": 3.5,
        "bano": -4.5,
    }.get(room, 0.0)
    noise = random.uniform(-0.5, 0.5)
    return round(base_daily + room_offset + noise, 1)


def simulate_lights(_, hour) -> int:
    """
    Simula si las luces están encendidas o apagadas en función de la hora del día y la habitación.
    """
    if 8 <= hour < 18:
        prob_on = 0.15
    elif 18 <= hour < 23:
        prob_on = 0.7
    else:
        prob_on = 0.3
    return 1 if random.random() < prob_on else 0


def simulate_power_usage(room, lights_on) -> float:
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


def simulate_water_flow(_) -> float:
    """
    Simula el flujo de agua en función de la habitación.
    """
    # Genera valores aleatorios de consumo de agua en L/min
    valores = valores = [0.0, 1.5, 2.4, 3.7, 5.0, 7.3, 8.8, 10.1, 11.6]
    # Probabilidad de que haya consumo en cada ciclo
    if random.random() < 0.5:
        return random.choice(valores)
    return 0.0


def simulate_house_once() -> list:
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
            "timestamp": now.isoformat(),
            "room": room,
            "temperature": temp,
            "lights_on": lights_on,
            "power_usage": power,
            "water_flow": water,
        })

    return readings


def main() -> None:
    """
    Docstring for main
    """
    print("Iniciando simulación de casa IoT (Ctrl+C para detener)...\n")
    while True:
        readings = simulate_house_once()
        for r in readings:
            print(
                f"[{r['timestamp']}] room={r['room']}, "
                f"temp={r['temperature']}°C, lights_on={r['lights_on']}, "
                f"power={r['power_usage']}W, water={r['water_flow']} L/min"
            )

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

        print("-" * 80)
        time.sleep(5)


if __name__ == "__main__":
    main()
