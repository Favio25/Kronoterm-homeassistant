#!/usr/bin/env python3
import json
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional

import requests
from pymodbus.client import ModbusTcpClient

LOG_PATH = Path("/home/frelih/homeassistant/home-assistant.log")
CONFIG_ENTRIES = Path("/home/frelih/homeassistant/.storage/core.config_entries")
DEFAULT_HASS_URL = "http://10.0.0.58:8123"
TOKEN_PATH = Path("/home/frelih/.openclaw/workspace/.homeassistant-token")


def load_token() -> str:
    token = os.getenv("HASS_TOKEN")
    if token:
        return token.strip()
    if TOKEN_PATH.exists():
        return TOKEN_PATH.read_text().strip()
    raise RuntimeError("No HASS token found. Set HASS_TOKEN or provide .homeassistant-token")


def load_latest_payloads() -> Dict[str, Any]:
    payloads = {}
    if not LOG_PATH.exists():
        return payloads

    pattern = re.compile(r"Raw response GET \{'TopPage': '(\d+)', 'Subpage': '(\d+)'\}: (\{.*\})")
    with LOG_PATH.open("r", errors="ignore") as f:
        for line in f:
            m = pattern.search(line)
            if not m:
                continue
            key = f"{m.group(1)}-{m.group(2)}"
            try:
                payloads[key] = json.loads(m.group(3))
            except Exception:
                continue
    return payloads


def get_config_entries():
    data = json.loads(CONFIG_ENTRIES.read_text())
    return [e for e in data.get("data", {}).get("entries", []) if e.get("domain") == "kronoterm"]


def get_states(hass_url: str, token: str) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.get(f"{hass_url}/api/states", headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return {e["entity_id"]: e for e in data}


def modbus_read_temp(host: str, port: int, unit_id: int, address: int) -> Optional[float]:
    client = ModbusTcpClient(host=host, port=port, timeout=2)
    try:
        if not client.connect():
            return None
        result = client.read_holding_registers(address - 1, count=1, slave=unit_id)
        if not result or result.isError():
            return None
        value = result.registers[0]
        if value > 32767:
            value -= 65536
        return value / 10.0
    finally:
        client.close()


def compare_cloud(payloads: Dict[str, Any], states: Dict[str, Any]) -> None:
    print("\n[CLOUD CHECK]")
    main = payloads.get("5-3") or {}
    dhw = payloads.get("1-9") or {}

    tap_water = (dhw.get("TemperaturesAndConfig") or {}).get("tap_water_temp")
    dhw_entity = states.get("climate.kronoterm_dhw_temperature") or states.get("climate.kronoterm_heat_pump_dhw_temperature")
    if dhw_entity:
        current = dhw_entity.get("attributes", {}).get("current_temperature")
        target = dhw_entity.get("attributes", {}).get("temperature")
        print(f"DHW current (HA): {current} vs tap_water_temp (cloud): {tap_water}")
        print(f"DHW target (HA): {target}")
    else:
        print("No DHW climate entity found in HA states")

    outside = (main.get("TemperaturesAndConfig") or {}).get("outside_temp")
    outside_entity = states.get("sensor.kronoterm_outside_temperature")
    if outside_entity:
        print(f"Outside (HA): {outside_entity.get('state')} vs cloud: {outside}")


def compare_modbus(entries: list, states: Dict[str, Any]) -> None:
    modbus_entry = next((e for e in entries if e.get("data", {}).get("connection_type") == "modbus"), None)
    if not modbus_entry:
        print("\n[MODBUS CHECK] No modbus entry found")
        return

    data = modbus_entry.get("data", {})
    host = data.get("host")
    port = data.get("port", 502)
    unit_id = data.get("unit_id", 20)
    print("\n[MODBUS CHECK]")
    if not host:
        print("No modbus host configured")
        return

    regs = {
        "DHW temp (2102)": 2102,
        "Outside temp (2103)": 2103,
        "Loop2 temp (2110)": 2110,
        "Loop1 current (2130)": 2130,
        "Loop1 thermostat (2160)": 2160,
        "Loop2 thermostat (2161)": 2161,
    }

    for label, addr in regs.items():
        val = modbus_read_temp(host, port, unit_id, addr)
        print(f"{label}: {val}")


def main():
    token = load_token()
    hass_url = os.getenv("HASS_URL", DEFAULT_HASS_URL)
    payloads = load_latest_payloads()
    entries = get_config_entries()
    states = get_states(hass_url, token)

    compare_cloud(payloads, states)
    compare_modbus(entries, states)


if __name__ == "__main__":
    main()
