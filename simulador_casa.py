import time
import math
import random
from datetime import datetime

ROOMS = ["salon", "dormitorio", "cocina", "bano"]


def simulate_temperature(room, hour):
    """
    Temperatura simulada en función de la hora del día y de la habitación.
    """
    # Curva diaria: más calor por la tarde, más frío de madrugada
    base_daily = 20 + 4 * math.sin(2 * math.pi * (hour - 14) / 24)

    # Ajuste por habitación
    room_offset = {
        "salon": 1.0,
        "dormitorio": -0.5,
        "cocina": 1.5,
        "bano": 0.0,
    }.get(room, 0.0)

    noise = random.uniform(-0.5, 0.5)

    return round(base_daily + room_offset + noise, 1)


def simulate_lights(room, hour):
    """
    Luces encendidas/apagadas según la hora.
    - Más probable que estén encendidas por la noche.
    """
    if 8 <= hour < 18:
        # Día: las luces suelen estar apagadas
        prob_on = 0.15
    elif 18 <= hour < 23:
        # Tarde / noche temprana: muchas veces encendidas
        prob_on = 0.7
    else:
        # Madrugada: menos probabilidad, pero pueden quedar encendidas
        prob_on = 0.3

    return 1 if random.random() < prob_on else 0


def simulate_power_usage(room, lights_on):
    """
    Consumo eléctrico en W.
    Depende de si las luces están encendidas y de picos aleatorios (electrodomésticos).
    """
    # Consumo base de la habitación
    base_power = {
        "salon": 60,       # standby TV, router, etc.
        "dormitorio": 20,
        "cocina": 80,      # nevera, etc.
        "bano": 10,
    }.get(room, 20)

    # Luces (supongamos 10W por habitación si están encendidas)
    lights_power = 10 if lights_on else 0

    # Picos aleatorios (microondas, horno, secador, etc.)
    peak_power = 0
    if room == "cocina" and random.random() < 0.1:
        # 10% de las veces hay un pico fuerte en la cocina
        peak_power = random.choice([500, 800, 1200])
    elif room == "bano" and random.random() < 0.05:
        # secador de pelo, por ejemplo
        peak_power = random.choice([600, 900])

    total = base_power + lights_power + peak_power
    return round(total, 1)


def simulate_water_flow(room):
    """
    Caudal de agua en L/min.
    Normalmente 0, pero a veces hay consumo en cocina y baño.
    """
    if room == "cocina":
        # probabilidad de estar fregando, lavando, etc.
        if random.random() < 0.1:
            return round(random.uniform(2, 8), 1)
    elif room == "bano":
        # probabilidad de ducha / grifo
        if random.random() < 0.15:
            return round(random.uniform(3, 12), 1)

    # En salón y dormitorio normalmente no hay agua
    return 0.0


def simulate_house_once():
    """
    Genera una "foto" de la casa en un instante.
    Devuelve una lista de lecturas (una por habitación).
    """
    now = datetime.now()
    hour = now.hour + now.minute / 60.0

    readings = []

    for room in ROOMS:
        temp = simulate_temperature(room, hour)
        lights_on = simulate_lights(room, hour)
        power = simulate_power_usage(room, lights_on)
        water = simulate_water_flow(room)

        reading = {
            "timestamp": now.isoformat(),
            "room": room,
            "temperature": temp,
            "lights_on": lights_on,
            "power_usage": power,
            "water_flow": water,
        }
        readings.append(reading)

    return readings


def main():
    print("Iniciando simulación de casa IoT (Ctrl+C para detener)...\n")
    while True:
        readings = simulate_house_once()
        for r in readings:
            print(
                f"[{r['timestamp']}] room={r['room']}, "
                f"temp={r['temperature']}°C, "
                f"lights_on={r['lights_on']}, "
                f"power={r['power_usage']}W, "
                f"water={r['water_flow']} L/min"
            )
        print("-" * 80)
        time.sleep(5)  # espera 5 segundos entre lecturas


if __name__ == "__main__":
    main()
