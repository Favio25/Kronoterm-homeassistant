"""
Kronoterm Modbus TCP Register Definitions - CORRECTED

Based on official documentation: KRONOTERM CNS – Navodila za priklop in uporabo
All register addresses, scales, and access modes verified against manufacturer specs.
"""

from enum import IntEnum
from typing import NamedTuple, Optional, Callable


class RegisterType(IntEnum):
    """Register data types."""
    UINT16 = 0
    TEMP = 1      # Temperature (scale varies: 0.1 or 1.0)
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
    access: str = "R"  # R, W, or RW


def read_bit(value: int, bit: int) -> bool:
    """Extract specific bit from register value."""
    return bool((value >> bit) & 1)


# =============================================================================
# SYSTEM CONTROL REGISTERS
# =============================================================================

SYSTEM_OPERATION_CONTROL = Register(
    address=2012,
    name="System On/Off",
    reg_type=RegisterType.BINARY,
    access="RW"
)

PROGRAM_SELECTION = Register(
    address=2013,
    name="Program Selection",
    reg_type=RegisterType.ENUM,
    access="RW",
    enum_values={
        0: "auto",
        1: "comfort",
        2: "eco"
    }
)

MAIN_TEMP_CORRECTION = Register(
    address=2014,
    name="Main Temperature Correction",
    reg_type=RegisterType.TEMP,
    scale=1.0,  # IMPORTANT: Scale is 1, not 0.1!
    unit="°C",
    access="RW"
)

FAST_DHW_HEATING = Register(
    address=2015,
    name="Fast DHW Heating",
    reg_type=RegisterType.BINARY,
    access="RW"
)

ADDITIONAL_SOURCE_SWITCH = Register(
    address=2016,
    name="Additional Source",
    reg_type=RegisterType.BINARY,
    access="RW"
)

RESERVE_SOURCE_SWITCH = Register(
    address=2018,
    name="Reserve Source",
    reg_type=RegisterType.BINARY,
    access="RW"
)

VACATION_MODE = Register(
    address=2022,
    name="Vacation Mode",
    reg_type=RegisterType.BINARY,
    access="RW"
)

# =============================================================================
# TEMPERATURE SENSORS (Scale 0.1)
# =============================================================================

# =============================================================================
# TEMPERATURE SENSORS (500-range - ACTUAL DEVICE SENSORS)
# These were discovered during original testing and match Cloud API values
# =============================================================================

SUPPLY_TEMP = Register(
    address=546,
    name="Supply Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

RETURN_TEMP = Register(
    address=553,
    name="Return Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

DHW_SENSOR_TEMP = Register(
    address=572,
    name="DHW Sensor Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)


OUTDOOR_TEMP = Register(
    address=2102,  # DEVICE TESTED: 2102 is outdoor (official docs wrong)
    name="Outdoor Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

HP_RETURN_TEMP = Register(
    address=2101,
    name="Heat Pump Return Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

DHW_TANK_TEMP = Register(
    address=2103,  # DEVICE TESTED: 2103 is DHW (official docs wrong)
    name="DHW Tank Temperature",
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

ALTERNATIVE_SOURCE_TEMP = Register(
    address=2107,
    name="Alternative Source Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

# =============================================================================
# DHW (SANITARY WATER) REGISTERS
# =============================================================================

DHW_SETPOINT = Register(
    address=2023,
    name="DHW Setpoint",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C",
    access="RW"
)

DHW_CURRENT_TEMP = Register(
    address=2024,
    name="DHW Current Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

DHW_MODE = Register(
    address=2026,
    name="DHW Operation Mode",
    reg_type=RegisterType.ENUM,
    access="RW",
    enum_values={
        0: "off",
        1: "on",
        2: "scheduled"
    }
)

DHW_TEMP2 = Register(
    address=2030,  # CORRECTED: This is DHW temp 2, NOT offset!
    name="DHW Temperature 2",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

DHW_OFFSET = Register(
    address=2031,
    name="DHW Offset",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C",
    access="RW"
)

# =============================================================================
# ANTI-LEGIONELLA (THERMAL DISINFECTION)
# =============================================================================

ANTI_LEGIONELLA_ENABLE = Register(
    address=2301,
    name="Anti-Legionella Enable",
    reg_type=RegisterType.BINARY,
    access="RW"
)

ANTI_LEGIONELLA_TEMP = Register(
    address=2302,
    name="Anti-Legionella Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C",
    access="RW"
)

ANTI_LEGIONELLA_DAY = Register(
    address=2303,
    name="Anti-Legionella Day",
    reg_type=RegisterType.UINT16,
    access="RW"
)

ANTI_LEGIONELLA_MINUTE = Register(
    address=2304,
    name="Anti-Legionella Start Minute",
    reg_type=RegisterType.UINT16,
    access="RW"
)

# =============================================================================
# HEATING CIRCUIT 1 (LOOP 1)
# =============================================================================

LOOP1_MODE = Register(
    address=2042,
    name="Loop 1 Operation Mode",
    reg_type=RegisterType.ENUM,
    access="RW",
    enum_values={
        0: "off",
        1: "normal",
        2: "eco",
        3: "comfort"
    }
)

LOOP1_CURRENT_TEMP = Register(
    address=2047,  # CORRECTED: This is current temp, not offset!
    name="Loop 1 Current Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

LOOP1_OFFSET = Register(
    address=2048,
    name="Loop 1 Offset",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C",
    access="RW"
)

LOOP1_CIRCUIT_TEMP = Register(
    address=2128,
    name="Loop 1 Circuit Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

LOOP1_CIRCUIT_TEMP_ALT = Register(
    address=2130,
    name="Loop 1 Circuit Temperature (Alt)",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

LOOP1_ROOM_SETPOINT = Register(
    address=2187,
    name="Loop 1 Room Setpoint",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C",
    access="RW"
)

LOOP1_ROOM_CURRENT = Register(
    address=2191,
    name="Loop 1 Room Current Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

# =============================================================================
# HEATING CIRCUIT 2 (LOOP 2)
# =============================================================================

LOOP2_CURRENT_TEMP = Register(
    address=2049,
    name="Loop 2 Current Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

LOOP2_ROOM_TEMP = Register(
    address=2051,
    name="Loop 2 Room Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

LOOP2_MODE = Register(
    address=2052,
    name="Loop 2 Operation Mode",
    reg_type=RegisterType.ENUM,
    access="RW",
    enum_values={
        0: "off",
        1: "normal",
        2: "eco",
        3: "comfort"
    }
)

LOOP2_CURRENT_TEMP2 = Register(
    address=2057,  # CORRECTED: This is current temp, not offset!
    name="Loop 2 Current Temperature 2",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

LOOP2_OFFSET = Register(
    address=2058,
    name="Loop 2 Offset",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C",
    access="RW"
)

LOOP2_CIRCUIT_TEMP = Register(
    address=2110,
    name="Loop 2 Circuit Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

# =============================================================================
# HEATING CIRCUIT 3 (LOOP 3)
# =============================================================================

LOOP3_CURRENT_TEMP = Register(
    address=2059,
    name="Loop 3 Current Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

LOOP3_MODE = Register(
    address=2062,
    name="Loop 3 Operation Mode",
    reg_type=RegisterType.ENUM,
    access="RW",
    enum_values={
        0: "off",
        1: "normal",
        2: "eco",
        3: "comfort"
    }
)

LOOP3_CURRENT_TEMP2 = Register(
    address=2067,  # CORRECTED: This is current temp, not offset!
    name="Loop 3 Current Temperature 2",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

LOOP3_OFFSET = Register(
    address=2068,
    name="Loop 3 Offset",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C",
    access="RW"
)

LOOP3_CIRCUIT_TEMP = Register(
    address=2111,
    name="Loop 3 Circuit Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

# =============================================================================
# HEATING CIRCUIT 4 (LOOP 4)
# =============================================================================

LOOP4_CURRENT_TEMP = Register(
    address=2069,
    name="Loop 4 Current Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

LOOP4_MODE = Register(
    address=2072,
    name="Loop 4 Operation Mode",
    reg_type=RegisterType.ENUM,
    access="RW",
    enum_values={
        0: "off",
        1: "normal",
        2: "eco",
        3: "comfort"
    }
)

LOOP4_CURRENT_TEMP2 = Register(
    address=2077,  # CORRECTED: This is current temp, not offset!
    name="Loop 4 Current Temperature 2",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

LOOP4_OFFSET = Register(
    address=2078,
    name="Loop 4 Offset",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C",
    access="RW"
)

LOOP4_CIRCUIT_TEMP = Register(
    address=2112,
    name="Loop 4 Circuit Temperature",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C"
)

# =============================================================================
# SYSTEM SETPOINTS & OFFSETS
# =============================================================================

SYSTEM_SETPOINT = Register(
    address=2040,
    name="System Setpoint",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C",
    access="RW"
)

SYSTEM_OFFSET = Register(
    address=2041,
    name="System Offset",
    reg_type=RegisterType.TEMP,
    scale=0.1,
    unit="°C",
    access="RW"
)

# =============================================================================
# STATUS SENSORS
# =============================================================================

SYSTEM_OPERATION_STATUS = Register(
    address=2000,
    name="System Operation Status",
    reg_type=RegisterType.BINARY
)

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

OPERATION_PROGRAM = Register(
    address=2008,
    name="Operation Program",
    reg_type=RegisterType.ENUM,
    enum_values={
        0: "auto",
        1: "comfort",
        2: "eco"
    }
)

DEFROST_STATUS = Register(
    address=2011,
    name="Defrost Active",
    reg_type=RegisterType.BINARY
)

# =============================================================================
# BINARY SENSORS (PUMPS, HEATERS)
# =============================================================================

ADDITIONAL_VKLOPI_BITFIELD = Register(
    address=2002,
    name="Additional Activations Bitfield",
    reg_type=RegisterType.BITS
)

RESERVE_SOURCE_STATUS = Register(
    address=2003,
    name="Reserve Source Active",
    reg_type=RegisterType.BINARY
)

ADDITIONAL_SOURCE_STATUS = Register(
    address=2004,
    name="Additional Source Active",
    reg_type=RegisterType.BINARY
)

DHW_BITFIELD = Register(
    address=2028,
    name="DHW Pumps Bitfield",
    reg_type=RegisterType.BITS
)

# =============================================================================
# POWER & EFFICIENCY
# =============================================================================

CURRENT_POWER = Register(
    address=2129,
    name="Current Power Consumption",
    reg_type=RegisterType.POWER,
    unit="W"
)

HEATING_POWER = Register(
    address=2329,
    name="Current Heating Power",
    reg_type=RegisterType.POWER,
    unit="W"
)

HP_LOAD_PERCENT = Register(
    address=2327,
    name="Heat Pump Load",
    reg_type=RegisterType.PERCENT,
    unit="%"
)

COP = Register(
    address=2371,
    name="COP",
    reg_type=RegisterType.COP,
    scale=0.01
)

SCOP = Register(
    address=2372,
    name="SCOP",
    reg_type=RegisterType.COP,
    scale=0.01
)

# =============================================================================
# PRESSURE SENSORS
# =============================================================================

PRESSURE_SETPOINT = Register(
    address=2325,
    name="Pressure Setpoint",
    reg_type=RegisterType.PRESSURE,
    scale=0.1,
    unit="bar"
)

PRESSURE_MEASURED = Register(
    address=2326,
    name="Pressure Measured",
    reg_type=RegisterType.PRESSURE,
    scale=0.1,
    unit="bar"
)

# =============================================================================
# OPERATING HOURS
# =============================================================================

OPERATING_HOURS_COMPRESSOR = Register(
    address=2089,
    name="Operating Hours Compressor",
    reg_type=RegisterType.HOURS,
    unit="h"
)

OPERATING_HOURS_HEATING = Register(
    address=2090,
    name="Operating Hours Heating",
    reg_type=RegisterType.HOURS,
    unit="h"
)

OPERATING_HOURS_DHW = Register(
    address=2091,
    name="Operating Hours DHW",
    reg_type=RegisterType.HOURS,
    unit="h"
)

OPERATING_HOURS_HEATER1 = Register(
    address=2095,
    name="Operating Hours Heater 1",
    reg_type=RegisterType.HOURS,
    unit="h"
)

OPERATING_HOURS_HEATER2 = Register(
    address=2096,
    name="Operating Hours Heater 2",
    reg_type=RegisterType.HOURS,
    unit="h"
)

OPERATING_HOURS_ALTERNATIVE = Register(
    address=2097,
    name="Operating Hours Alternative Source",
    reg_type=RegisterType.HOURS,
    unit="h"
)

# =============================================================================
# REGISTER COLLECTIONS
# =============================================================================

# Temperature sensors
TEMPERATURE_SENSORS = [
    # 500-range: Actual sensor values
    SUPPLY_TEMP,
    RETURN_TEMP,
    DHW_SENSOR_TEMP,
    # 2000-range: Control/status registers
    OUTDOOR_TEMP,
    HP_RETURN_TEMP,
    DHW_TANK_TEMP,
    HP_OUTLET_TEMP,
    EVAPORATING_TEMP,
    COMPRESSOR_TEMP,
    ALTERNATIVE_SOURCE_TEMP,
    DHW_CURRENT_TEMP,
    DHW_TEMP2,
    LOOP1_CURRENT_TEMP,
    LOOP1_CIRCUIT_TEMP,
    LOOP1_CIRCUIT_TEMP_ALT,
    LOOP1_ROOM_CURRENT,
    LOOP2_CURRENT_TEMP,
    LOOP2_ROOM_TEMP,
    LOOP2_CURRENT_TEMP2,
    LOOP2_CIRCUIT_TEMP,
    LOOP3_CURRENT_TEMP,
    LOOP3_CURRENT_TEMP2,
    LOOP3_CIRCUIT_TEMP,
    LOOP4_CURRENT_TEMP,
    LOOP4_CURRENT_TEMP2,
    LOOP4_CIRCUIT_TEMP,
]

# Pump status registers
LOOP1_PUMP_STATUS = Register(
    address=2045,
    name="Loop 1 Pump Status",
    reg_type=RegisterType.BINARY
)

LOOP2_PUMP_STATUS = Register(
    address=2055,
    name="Loop 2 Pump Status",
    reg_type=RegisterType.BINARY
)

LOOP3_PUMP_STATUS = Register(
    address=2065,
    name="Loop 3 Pump Status",
    reg_type=RegisterType.BINARY
)

LOOP4_PUMP_STATUS = Register(
    address=2075,
    name="Loop 4 Pump Status",
    reg_type=RegisterType.BINARY
)

DHW_PUMP_BITFIELD = Register(
    address=2028,
    name="DHW Pumps Bitfield",
    reg_type=RegisterType.BITS
)

# Binary sensors
BINARY_SENSORS = [
    SYSTEM_OPERATION_STATUS,
    RESERVE_SOURCE_STATUS,
    ADDITIONAL_SOURCE_STATUS,
    DEFROST_STATUS,
    LOOP1_PUMP_STATUS,
    LOOP2_PUMP_STATUS,
    LOOP3_PUMP_STATUS,
    LOOP4_PUMP_STATUS,
    DHW_PUMP_BITFIELD,
    ADDITIONAL_VKLOPI_BITFIELD,  # Register 2002
]

# Status sensors
STATUS_SENSORS = [
    WORKING_FUNCTION,
    ERROR_WARNING_STATUS,
    OPERATION_PROGRAM,
]

# Power sensors
POWER_SENSORS = [
    CURRENT_POWER,
    HEATING_POWER,
    HP_LOAD_PERCENT,
    PRESSURE_SETPOINT,
    PRESSURE_MEASURED,
    COP,
    SCOP,
]

# Operating hours
HOUR_SENSORS = [
    OPERATING_HOURS_COMPRESSOR,
    OPERATING_HOURS_HEATING,
    OPERATING_HOURS_DHW,
    OPERATING_HOURS_HEATER1,
    OPERATING_HOURS_HEATER2,
    OPERATING_HOURS_ALTERNATIVE,
]

# Offset registers (writable)
OFFSET_REGISTERS = [
    DHW_OFFSET,
    LOOP1_OFFSET,
    LOOP2_OFFSET,
    LOOP3_OFFSET,
    LOOP4_OFFSET,
    SYSTEM_OFFSET,
]

# Control switches (writable)
CONTROL_SWITCHES = [
    SYSTEM_OPERATION_CONTROL,
    FAST_DHW_HEATING,
    ADDITIONAL_SOURCE_SWITCH,
    RESERVE_SOURCE_SWITCH,
    ANTI_LEGIONELLA_ENABLE,
    VACATION_MODE,
]

# Mode selects (writable)
MODE_SELECTS = [
    PROGRAM_SELECTION,
    DHW_MODE,
    LOOP1_MODE,
    LOOP2_MODE,
    LOOP3_MODE,
    LOOP4_MODE,
]

# Setpoints (writable)
SETPOINT_REGISTERS = [
    DHW_SETPOINT,
    LOOP1_ROOM_SETPOINT,
    SYSTEM_SETPOINT,
]

# All readable registers for batch reading
ALL_REGISTERS = (
    TEMPERATURE_SENSORS +
    BINARY_SENSORS +
    STATUS_SENSORS +
    POWER_SENSORS +
    HOUR_SENSORS +
    OFFSET_REGISTERS +
    SETPOINT_REGISTERS
)

# All writable registers
WRITABLE_REGISTERS = (
    CONTROL_SWITCHES +
    MODE_SELECTS +
    SETPOINT_REGISTERS +
    OFFSET_REGISTERS +
    [MAIN_TEMP_CORRECTION, ANTI_LEGIONELLA_TEMP, ANTI_LEGIONELLA_DAY, ANTI_LEGIONELLA_MINUTE]
)


def scale_value(register: Register, raw_value: int) -> float:
    """Scale raw register value based on register type."""
    # Check for error values
    if raw_value >= 64000:
        return None
    
    return raw_value * register.scale


def format_enum(register: Register, raw_value: int) -> str:
    """Format enumeration value to human-readable string."""
    if register.enum_values and raw_value in register.enum_values:
        return register.enum_values[raw_value]
    return f"unknown_{raw_value}"


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
