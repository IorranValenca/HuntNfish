import random
from datetime import datetime, timedelta
import pandas as pd

DEVICES = [
    {"id": "DEV001", "name": "Temp Sensor A1",    "type": "Temperature", "location": "Warehouse A"},
    {"id": "DEV002", "name": "Humidity Probe B2",  "type": "Humidity",    "location": "Warehouse B"},
    {"id": "DEV003", "name": "Gateway Alpha",      "type": "Gateway",     "location": "Server Room"},
    {"id": "DEV004", "name": "Temp Sensor C3",     "type": "Temperature", "location": "Office"},
    {"id": "DEV005", "name": "Motion Sensor D4",   "type": "Motion",      "location": "Entrance"},
    {"id": "DEV006", "name": "Air Quality E5",     "type": "Air Quality", "location": "Lab"},
    {"id": "DEV007", "name": "Pressure Node F6",   "type": "Pressure",    "location": "Factory"},
    {"id": "DEV008", "name": "CO₂ Monitor G7",     "type": "Air Quality", "location": "Meeting Rm"},
    {"id": "DEV009", "name": "Smart Plug H8",      "type": "Power",       "location": "Office"},
    {"id": "DEV010", "name": "GPS Tracker I9",     "type": "GPS",         "location": "Fleet"},
]

# Fixed base values — some intentionally critical for alert demos
_bases = {
    "DEV001": {"temp": 22.5, "hum": 55.0, "battery": 82, "signal": 88},
    "DEV002": {"temp": 19.0, "hum": 72.0, "battery": 45, "signal": 76},
    "DEV003": {"temp": 28.0, "hum": 40.0, "battery": 95, "signal": 99},
    "DEV004": {"temp": 21.0, "hum": 48.0, "battery": 17, "signal": 82},  # low battery
    "DEV005": {"temp": 20.5, "hum": 50.0, "battery": 67, "signal": 71},
    "DEV006": {"temp": 23.0, "hum": 60.0, "battery": 33, "signal": 38},  # weak signal
    "DEV007": {"temp": 34.5, "hum": 35.0, "battery": 78, "signal": 62},  # high temp
    "DEV008": {"temp": 22.0, "hum": 52.0, "battery": 91, "signal": 85},
    "DEV009": {"temp": 25.0, "hum": 45.0, "battery": 100, "signal": 97},
    "DEV010": {"temp": 18.0, "hum": 62.0, "battery": 9,  "signal": 43},  # critical battery
}

_start = datetime.now()

THRESHOLDS = {
    "battery_critical": 10,
    "battery_low":      20,
    "temp_high":        32.0,
    "signal_low":       40,
}


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def get_device_status() -> list[dict]:
    # Seed on current 3-second window so status is stable between renders
    tick = int(datetime.now().timestamp() / 3)
    elapsed_min = (datetime.now() - _start).total_seconds() / 60

    devices = []
    for i, dev in enumerate(DEVICES):
        base = _bases[dev["id"]]
        rng  = _rng(tick * 100 + i)

        online   = rng.random() > 0.12
        battery  = max(0, min(100, base["battery"] - elapsed_min * 0.4 + rng.uniform(-2, 1)))
        signal   = max(0, min(100, base["signal"]  + rng.randint(-4, 4)))
        temp     = round(base["temp"] + rng.uniform(-1.5, 1.5), 1) if online else None
        humidity = round(base["hum"]  + rng.uniform(-3.0, 3.0), 1) if online else None

        devices.append({
            **dev,
            "status":      "Online" if online else "Offline",
            "battery":     round(battery),
            "signal":      round(signal),
            "temperature": temp,
            "humidity":    humidity,
            "last_seen":   datetime.now().strftime("%H:%M:%S"),
        })
    return devices


def get_history(device_id: str, points: int = 50) -> pd.DataFrame:
    base = _bases[device_id]
    now  = datetime.now()
    # Seed changes each 3-second tick so the "head" of the series advances
    tick = int(now.timestamp() / 3)
    rng  = _rng(hash(device_id) + tick)

    times, temps, humids = [], [], []
    t, h = base["temp"], base["hum"]
    for i in range(points, 0, -1):
        t = round(max(10, min(45, t + rng.uniform(-0.35, 0.35))), 2)
        h = round(max(10, min(95, h + rng.uniform(-0.6,  0.6 ))), 2)
        times.append(now - timedelta(seconds=i * 3))
        temps.append(t)
        humids.append(h)

    return pd.DataFrame({"time": times, "temperature": temps, "humidity": humids})


def get_alerts(devices: list[dict]) -> list[dict]:
    alerts = []
    for d in devices:
        if d["status"] == "Offline":
            alerts.append({"device": d["name"], "type": "Device Offline",   "severity": "critical", "value": "—",                    "time": d["last_seen"]})
        if d["battery"] <= THRESHOLDS["battery_critical"]:
            alerts.append({"device": d["name"], "type": "Critical Battery", "severity": "critical", "value": f"{d['battery']} %",    "time": d["last_seen"]})
        elif d["battery"] <= THRESHOLDS["battery_low"]:
            alerts.append({"device": d["name"], "type": "Low Battery",      "severity": "warning",  "value": f"{d['battery']} %",    "time": d["last_seen"]})
        if d["temperature"] and d["temperature"] >= THRESHOLDS["temp_high"]:
            alerts.append({"device": d["name"], "type": "High Temperature", "severity": "warning",  "value": f"{d['temperature']} °C","time": d["last_seen"]})
        if d["signal"] and d["signal"] < THRESHOLDS["signal_low"]:
            alerts.append({"device": d["name"], "type": "Weak Signal",      "severity": "info",     "value": f"{d['signal']} %",     "time": d["last_seen"]})

    order = {"critical": 0, "warning": 1, "info": 2}
    return sorted(alerts, key=lambda a: order[a["severity"]])
