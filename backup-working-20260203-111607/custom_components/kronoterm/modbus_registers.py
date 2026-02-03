"""
Kronoterm Modbus TCP Register Definitions.

Based on validation scan 2026-02-02 with kosl/kronoterm2mqtt corrections.
All registers validated against live Home Assistant cloud API integration.
"""

from enum import IntEnum
from typing import NamedTuple, Optional, Callable


class RegisterType(IntEnum):
    """Register data types."""
    UINT16 = 0
    TEMP = 1      # Temperature (scale 0.1)
    PRESSURE = 2  # Pressure (scale 0.1)
    COP = 3       # COP/SCOP (scale 0.01)
    PERCENT = 4   # Percentage (no scale)
    POWER = 5     # Power in Watts (no scale)
    HOURS = 6     # Operating hours (no scale)
    ENUM = 7      # Enumeration
    BINARY = 8    # Binary ON/OFF
    BITS = 9      # Bit-masked values


class Register(NamedTuple):
    """Modbus register definition."""
    address: int
    name: str
    reg_type: RegisterType
    scale: float = 1.0
    unit: Optional[str] = None
    bit: Optional[int] = None  # For bit-masked registers
    enum_values: Optional[dict] = None  # For enumerations


def read_bit(value: int, bit: int) -> bool:
    """Extract specific bit from register value."""
    return bool((value >> bit) & 1)


# =============================================================================
# TEMPERATURE SENSORS (scale 0.1 = divide by 10)
# =============================================================================

OUTDOOR_TEMP = Register(
    address=2102,
    name="Outdoor Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

LOOP1_CURRENT_TEMP = Register(
    address=2109,  # CORRECTED: Not 2130!
    name="Loop 1 Current Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

LOOP1_SETPOINT = Register(
    address=2187,
    name="Loop 1 Setpoint",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

LOOP2_SETPOINT = Register(
    address=2049,
    name="Loop 2 Setpoint",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

DHW_SETPOINT = Register(
    address=2023,
    name="DHW Setpoint",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

DHW_CURRENT_SETPOINT = Register(
    address=2024,
    name="DHW Current Setpoint",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

HP_INLET_TEMP = Register(
    address=2101,
    name="Heat Pump Inlet Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

HP_OUTLET_TEMP = Register(
    address=2104,
    name="Heat Pump Outlet Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

EVAPORATING_TEMP = Register(
    address=2105,
    name="Evaporating Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

COMPRESSOR_TEMP = Register(
    address=2106,
    name="Compressor Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

LOOP1_THERMOSTAT_TEMP = Register(
    address=2160,
    name="Loop 1 Thermostat Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

LOOP2_THERMOSTAT_TEMP = Register(
    address=2161,
    name="Loop 2 Thermostat Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

LOOP2_CURRENT_TEMP = Register(
    address=2110,
    name="Loop 2 Current Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

ALTERNATIVE_SOURCE_TEMP = Register(
    address=2107,
    name="Alternative Source Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

# =============================================================================
# BINARY SENSORS (ON/OFF)
# =============================================================================

SYSTEM_OPERATION = Register(
    address=2000,
    name="System Operation",
    reg_type=RegisterType.BINARY
)

LOOP1_PUMP = Register(
    address=2045,
    name="Loop 1 Circulation Pump",
    reg_type=RegisterType.BINARY
)

LOOP2_PUMP = Register(
    address=2055,
    name="Loop 2 Circulation Pump",
    reg_type=RegisterType.BINARY
)

DHW_CIRCULATION_PUMP = Register(
    address=2028,
    name="DHW Circulation Pump",
    reg_type=RegisterType.BITS,
    bit=0
)

DHW_TANK_CIRCULATION_PUMP = Register(
    address=2028,
    name="DHW Tank Circulation Pump",
    reg_type=RegisterType.BITS,
    bit=1
)

ADDITIONAL_SOURCE_ACTIVATION = Register(
    address=2002,
    name="Additional Source Activation",
    reg_type=RegisterType.BITS,
    bit=0
)

ADDITIONAL_SOURCE_ACTIVE = Register(
    address=2002,
    name="Additional Source Active",
    reg_type=RegisterType.BITS,
    bit=4
)

# =============================================================================
# STATUS & ENUMERATION SENSORS
# =============================================================================

WORKING_FUNCTION = Register(
    address=2001,
    name="Working Function",
    reg_type=RegisterType.ENUM,
    enum_values={
        0: "heating",
        1: "dhw",
        2: "cooling",
        3: "pool_heating",
        4: "thermal_disinfection",
        5: "standby",
        7: "remote_deactivation"
    }
)

ERROR_WARNING_STATUS = Register(
    address=2006,
    name="Error/Warning Status",
    reg_type=RegisterType.ENUM,
    enum_values={
        0: "no_error",
        1: "warning",
        2: "error"
    }
)

OPERATION_REGIME = Register(
    address=2007,
    name="Operation Regime",
    reg_type=RegisterType.ENUM,
    enum_values={
        0: "cooling",
        1: "heating",
        2: "off"
    }
)

LOOP1_OPERATION_STATUS = Register(
    address=2044,
    name="Loop 1 Operation Status",
    reg_type=RegisterType.ENUM,
    enum_values={
        0: "off",
        1: "normal",
        2: "eco",
        3: "com"
    }
)

DHW_OPERATION = Register(
    address=2026,
    name="DHW Operation",
    reg_type=RegisterType.ENUM,
    enum_values={
        0: "off",
        1: "on",
        2: "scheduled"
    }
)

# =============================================================================
# POWER & LOAD SENSORS
# =============================================================================

CURRENT_POWER = Register(
    address=2129,
    name="Current Power Consumption",
    reg_type=RegisterType.POWER,
    unit="W"
)

HP_LOAD = Register(
    address=2327,
    name="Heat Pump Load",
    reg_type=RegisterType.PERCENT,
    unit="%"
)

HEATING_POWER = Register(
    address=2329,
    name="Current Heating Power",
    reg_type=RegisterType.POWER,
    unit="W"
)

# =============================================================================
# PRESSURE SENSORS (scale 0.1 = divide by 10)
# =============================================================================

SYSTEM_PRESSURE = Register(
    address=2325,  # CORRECTED: Not 2326!
    name="System Pressure",
    reg_type=RegisterType.PRESSURE,
    scale=0.1,
    unit="bar"
)

PRESSURE_SETTING = Register(
    address=2326,
    name="Heating System Pressure Setting",
    reg_type=RegisterType.PRESSURE,
    scale=0.1,
    unit="bar"
)

SOURCE_PRESSURE = Register(
    address=2348,
    name="Source Pressure",
    reg_type=RegisterType.PRESSURE,
    scale=0.1,
    unit="bar"
)

# =============================================================================
# EFFICIENCY SENSORS (scale 0.01 = divide by 100)
# =============================================================================

COP = Register(
    address=2371,
    name="COP",
    reg_type=RegisterType.COP,
    scale=0.01,
    unit=""
)

SCOP = Register(
    address=2372,
    name="SCOP",
    reg_type=RegisterType.COP,
    scale=0.01,
    unit=""
)

# =============================================================================
# OPERATING HOURS
# =============================================================================

OPERATING_HOURS_HEATING = Register(
    address=2090,
    name="Operating Hours Compressor Heating",
    reg_type=RegisterType.HOURS,
    unit="h"
)

OPERATING_HOURS_DHW = Register(
    address=2091,
    name="Operating Hours Compressor DHW",
    reg_type=RegisterType.HOURS,
    unit="h"
)

OPERATING_HOURS_ADDITIONAL = Register(
    address=2095,
    name="Operating Hours Additional Source",
    reg_type=RegisterType.HOURS,
    unit="h"
)

# =============================================================================
# ACTIVATION COUNTERS
# =============================================================================

ACTIVATIONS_HEATING = Register(
    address=2155,
    name="Compressor Activations Heating",
    reg_type=RegisterType.UINT16,
    unit=""
)

ACTIVATIONS_COOLING = Register(
    address=2156,
    name="Compressor Activations Cooling",
    reg_type=RegisterType.UINT16,
    unit=""
)

ACTIVATIONS_BOILER = Register(
    address=2157,
    name="Activations Boiler",
    reg_type=RegisterType.UINT16,
    unit=""
)

ACTIVATIONS_DEFROST = Register(
    address=2158,
    name="Activations Defrost",
    reg_type=RegisterType.UINT16,
    unit=""
)

# =============================================================================
# WRITABLE SWITCHES
# =============================================================================

FAST_DHW_HEATING = Register(
    address=2015,
    name="Fast DHW Heating",
    reg_type=RegisterType.BINARY
)

ADDITIONAL_SOURCE_SWITCH = Register(
    address=2016,
    name="Additional Source",
    reg_type=RegisterType.BINARY
)

DHW_CIRCULATION_SWITCH = Register(
    address=2328,
    name="Circulation of Sanitary Water",
    reg_type=RegisterType.BINARY
)

# =============================================================================
# DEVICE INFORMATION (READ-ONLY)
# =============================================================================

DEVICE_ID = Register(
    address=5054,
    name="Device ID",
    reg_type=RegisterType.UINT16
)

FIRMWARE_VERSION = Register(
    address=5056,
    name="Firmware Version",
    reg_type=RegisterType.UINT16
)

# =============================================================================
# REGISTER COLLECTIONS
# =============================================================================

# All temperature sensors for monitoring
TEMPERATURE_SENSORS = [
    OUTDOOR_TEMP,
    LOOP1_CURRENT_TEMP,
    LOOP1_SETPOINT,
    LOOP2_SETPOINT,
    DHW_SETPOINT,
    DHW_CURRENT_SETPOINT,
    HP_INLET_TEMP,
    HP_OUTLET_TEMP,
    EVAPORATING_TEMP,
    COMPRESSOR_TEMP,
    LOOP1_THERMOSTAT_TEMP,
    LOOP2_THERMOSTAT_TEMP,
    LOOP2_CURRENT_TEMP,
    ALTERNATIVE_SOURCE_TEMP,
]

# Binary sensors (pumps, heater, etc.)
BINARY_SENSORS = [
    SYSTEM_OPERATION,
    LOOP1_PUMP,
    LOOP2_PUMP,
    DHW_CIRCULATION_PUMP,
    DHW_TANK_CIRCULATION_PUMP,
    ADDITIONAL_SOURCE_ACTIVATION,
    ADDITIONAL_SOURCE_ACTIVE,
]

# Status/enum sensors
STATUS_SENSORS = [
    WORKING_FUNCTION,
    ERROR_WARNING_STATUS,
    OPERATION_REGIME,
    LOOP1_OPERATION_STATUS,
    DHW_OPERATION,
]

# Power and efficiency sensors
POWER_SENSORS = [
    CURRENT_POWER,
    HP_LOAD,
    HEATING_POWER,
    SYSTEM_PRESSURE,
    COP,
    SCOP,
]

# Operating hours
HOUR_SENSORS = [
    OPERATING_HOURS_HEATING,
    OPERATING_HOURS_DHW,
    OPERATING_HOURS_ADDITIONAL,
]

# Activation counters
ACTIVATION_SENSORS = [
    ACTIVATIONS_HEATING,
    ACTIVATIONS_COOLING,
    ACTIVATIONS_BOILER,
    ACTIVATIONS_DEFROST,
]

# Writable registers (setpoints and switches)
WRITABLE_REGISTERS = [
    LOOP1_SETPOINT,
    LOOP2_SETPOINT,
    DHW_SETPOINT,
    FAST_DHW_HEATING,
    ADDITIONAL_SOURCE_SWITCH,
    DHW_CIRCULATION_SWITCH,
    DHW_OPERATION,
]

# All registers for batch reading
ALL_REGISTERS = (
    TEMPERATURE_SENSORS +
    BINARY_SENSORS +
    STATUS_SENSORS +
    POWER_SENSORS +
    HOUR_SENSORS +
    ACTIVATION_SENSORS
)


def scale_value(register: Register, raw_value: int) -> float:
    """Scale raw register value based on register type."""
    # Check for error values
    if raw_value in [64936, 64937, 65535]:
        return None
    
    return raw_value * register.scale


def format_enum(register: Register, raw_value: int) -> str:
    """Format enumeration value to human-readable string."""
    if register.enum_values and raw_value in register.enum_values:
        return register.enum_values[raw_value]
    return f"unknown_{raw_value}"
