"""Kronoterm Modbus Register Map Loader.

Loads the official register mapping from kronoterm.json and provides
structured access to register definitions.
"""
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any

_LOGGER = logging.getLogger(__name__)


@dataclass
class RegisterDefinition:
    """A single Modbus register definition."""
    address: int
    name: str  # Original Slovenian name
    name_en: str  # Auto-translated English name (snake_case)
    type: str  # Status, Control, Value, Value32, Enum, Bitmask
    access: str  # Read, Read/Write
    unit: Optional[str]
    scale: float  # Scaling factor (e.g., 0.1 for temperatures)
    values: Optional[Dict[int, str]]  # Enum mappings
    bit_definitions: Optional[Dict[int, Dict[str, Any]]]  # Bitmask definitions
    source: str  # Documentation source
    range: Optional[str] = None
    note: Optional[str] = None
    register32_high: Optional[int] = None  # For 32-bit combined registers
    register32_low: Optional[int] = None   # For 32-bit combined registers
    disabled: bool = False  # If True, register stays in JSON but won't create entities


class RegisterMap:
    """Register map loader and accessor."""

    def __init__(self, json_path: Path):
        """Load register map from JSON file."""
        self._registers: Dict[int, RegisterDefinition] = {}
        self._meta_info: Dict[str, Any] = {}
        self._load_json(json_path)

    def _load_json(self, json_path: Path) -> None:
        """Load and parse the JSON file."""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._meta_info = data.get("meta_info", {})
            _LOGGER.info(
                "Loaded Kronoterm register map: %s (Controller: %s)",
                self._meta_info.get("title"),
                self._meta_info.get("controller"),
            )

            # Parse all registers
            for reg_data in data.get("registers", []):
                address = reg_data["address"]
                
                # Parse unit and determine scale factor
                unit_str = reg_data.get("unit")
                unit, scale = self._parse_unit(unit_str)
                
                # Use name_en from JSON if provided, otherwise translate
                name_en = reg_data.get("name_en")
                if not name_en:
                    name_en = self._translate_name(reg_data["name"], reg_data["type"])
                
                # Convert enum values from string keys to int keys
                # JSON loads {"0": "value"} as string keys, but we need int keys
                # Also translate Slovenian values to English keys for HA
                enum_values = reg_data.get("values")
                if enum_values and reg_data["type"] == "Enum":
                    enum_values = {int(k): self._translate_enum_value(v) for k, v in enum_values.items()}
                
                reg_def = RegisterDefinition(
                    address=address,
                    name=reg_data["name"],
                    name_en=name_en,
                    type=reg_data["type"],
                    access=reg_data["access"],
                    unit=unit,
                    scale=scale,
                    values=enum_values,
                    bit_definitions=reg_data.get("bit_definitions"),
                    source=reg_data.get("source", ""),
                    range=reg_data.get("range"),
                    note=reg_data.get("note"),
                    register32_high=reg_data.get("register32_high"),
                    register32_low=reg_data.get("register32_low"),
                    disabled=reg_data.get("disabled", False),
                )
                self._registers[address] = reg_def
                
            _LOGGER.info("Loaded %d register definitions", len(self._registers))
            
        except Exception as e:
            _LOGGER.error("Failed to load register map from %s: %s", json_path, e)
            raise

    def _parse_unit(self, unit_str: Optional[str]) -> tuple[Optional[str], float]:
        """Parse unit string and extract HA unit + scale factor.
        
        Examples:
            "x 0.1°C" -> ("°C", 0.1)
            "x 1 W" -> ("W", 1.0)
            "ure" -> ("h", 1.0)
            "day" -> ("d", 1.0)
        """
        if not unit_str:
            return None, 1.0
        
        # Extract scale factor (e.g., "x 0.1°C" -> 0.1, "°C")
        if unit_str.startswith("x "):
            # Remove "x " prefix
            remainder = unit_str[2:]
            
            # Split on first space to separate scale from unit
            # But handle cases like "0.1°C" where unit is attached to number
            parts = remainder.split(None, 1)  # Split on first whitespace
            
            try:
                # First part should be the scale number
                # But it might have the unit attached (e.g., "0.1°C")
                first_part = parts[0]
                
                # Try to extract numeric part
                numeric_str = ""
                unit_str_part = ""
                for char in first_part:
                    if char.isdigit() or char == "." or char == "-":
                        numeric_str += char
                    else:
                        # Rest is unit
                        unit_str_part = first_part[len(numeric_str):]
                        break
                
                scale = float(numeric_str) if numeric_str else 1.0
                
                # Unit is either attached or in parts[1]
                if unit_str_part:
                    unit = unit_str_part
                elif len(parts) > 1:
                    unit = parts[1]
                else:
                    unit = None
                    
            except (ValueError, IndexError):
                scale = 1.0
                unit = remainder
        else:
            scale = 1.0
            unit = unit_str
        
        # Translate Slovenian units to HA standard
        unit_map = {
            "ure": "h",
            "day": "d",
            "bar": "bar",
            "kWh": "kWh",
            "minute": "min",
            "m3": "m³",
        }
        
        if unit in unit_map:
            unit = unit_map[unit]
        
        return unit, scale

    def _translate_enum_value(self, slovenian_value: str) -> str:
        """Translate Slovenian enum value to English key for HA.
        
        Maps Slovenian state values to English keys that match translation files.
        """
        # Comprehensive enum value translations
        enum_translations = {
            # Working function (2001)
            "Ogrevanje": "heating",
            "Sanitarna voda": "dhw",
            "Hlajenje": "cooling",
            "Ogrevanje bazena": "pool_heating",
            "Pregrevanje sanitarne vode": "thermal_disinfection",
            "Mirovanje": "standby",
            "Daljinski izklop": "remote_deactivation",
            
            # Error status (2006)
            "Ni napake": "no_error",
            "Opozorilo": "warning",
            "Alarm": "alarm",
            "Obvestilo": "notice",
            
            # Operation mode (2007)
            "Ogrevanje in hlajenje off": "heating_and_cooling_off",
            
            # Operation program (2008)
            "Normalno delovanje": "normal_operation",
            "Generalno delovanje v ECO režimu": "eco_mode",
            "Generalno delovanje v COM režimu": "comfort_mode",
            "Program sušenja estrihov je aktiven": "screed_drying_active",
            
            # Operation modes (generic)
            "Izklop": "off",
            "Izklopljeno": "off",
            "Izklopljen": "off",
            "Vklop": "on",
            "Vklopljeno": "on",
            "Vklopljen": "on",
            
            # Schedule modes
            "Normal": "normal",
            "ECO": "eco",
            "COM": "comfort",
            
            # Mode selections
            "Normalni režim": "normal_mode",
            "Delovanje po urniku": "schedule_mode",
            "Auto režim": "auto",
            "Off režim": "off_mode",
            
            # Boolean states
            "Ni": "no",
            "Da": "yes",
        }
        
        # Try direct translation
        if slovenian_value in enum_translations:
            return enum_translations[slovenian_value]
        
        # Fallback: convert to snake_case
        english = slovenian_value.lower()
        english = english.replace("č", "c").replace("š", "s").replace("ž", "z")
        english = "".join(c if c.isalnum() or c == " " else "" for c in english)
        english = "_".join(english.split())
        
        return english

    def _translate_name(self, slovenian_name: str, reg_type: str) -> str:
        """Translate Slovenian name to English snake_case.
        
        Comprehensive translation dictionary for all Kronoterm registers.
        """
        # Comprehensive translations
        translations = {
            # System Status (2000-2020)
            "Delovanje sistema": "system_operation",
            "Funkcija delovanja": "working_function",
            "Dodatni vklopi": "additional_activations",
            "Rezervni vir": "reserve_source",
            "Alternativni vir": "alternative_source",
            "Status napake": "error_warning",      # Cloud API key for consistency
            "Režim delovanja": "operation_regime",  # Cloud API key for consistency
            "Program delovanja": "operation_program",
            "Hitro segrevanje sanitarne vode": "dhw_quick_heating",
            "Odtaljevanje": "defrost_status",
            "Vklop sistema": "system_on",
            "Izbira programa delovanja": "operation_program_select",
            "Korekcija temperature sistema": "system_temperature_correction",
            "Vklop hitrega segrevanja sanitarne vode": "dhw_quick_heating_enable",
            "Vklop dodatnega vira": "additional_source_enable",
            "Preklop režima": "mode_switch",
            "Vklop rezervnega vira": "reserve_source_enable",
            "Dopust": "vacation_mode",
            
            # DHW (2023-2031)
            "Želena temperatura sanitarne vode": "dhw_setpoint",
            "Trenutna želena temperatura sanitarne vode": "dhw_current_setpoint",
            "Izbira delovanja sanitarna voda": "dhw_operation_mode",
            "Status delovanja sanitarne vode po urniku": "dhw_schedule_status",
            "Status cirkulacijskih črpalk": "circulation_pump_status",
            "Odmik v eco načinu sanitarna voda": "dhw_eco_offset",
            "Odmik v comfortnem načinu sanitarna voda": "dhw_comfort_offset",
            
            # Reservoir/Buffer (2034-2041)
            "Trenutna želena temperatura zalogovnika/sistema": "reservoir_current_setpoint",
            "Izbira delovanja zalogovnika": "reservoir_operation_mode",
            "Status delovanja zalogovnika po urniku": "reservoir_schedule_status",
            "Status glavne obtočne črpalke": "main_pump_status",
            "Status daljinskega vklopa": "remote_control_status",
            "Odmik v eco načinu toplotne črpalke": "hp_eco_offset",
            "Odmik v comfortnem načinu toplotne črpalke": "hp_comfort_offset",
            
            # Loop 1 (2042-2048)
            "Izbira delovanja krog 1": "loop_1_operation_mode",
            "Status delovanja kroga 1 po urniku": "loop_1_schedule_status",
            "Status obtočne črpalke krog 1": "loop_1_pump_status",
            "Status termostata krog 1 in status regulacije": "loop_1_thermostat_regulation_status",
            "Odmik v eco načinu ogrevalni krog 1": "loop_1_eco_offset",
            "Odmik v comfortnem načinu ogrevalni krog 1": "loop_1_comfort_offset",
            
            # Loop 2 (2049-2058)
            "Želena temperatura ogrevalnega kroga 2 / Prostor 2": "loop_2_setpoint",
            "Trenutna želena temperatura ogrevalnega kroga 2 / temperatura prostor 2": "loop_2_current_setpoint",
            "Izbira delovanja ogrevalni krog 2": "loop_2_operation_mode",
            "Status delovanja kroga 2 po urniku": "loop_2_schedule_status",
            "Status obtočne črpalke krog 2": "loop_2_pump_status",
            "Status termostata krog 2": "loop_2_thermostat_status",
            "Odmik v eco načinu ogrevalni krog 2": "loop_2_eco_offset",
            "Odmik v comfortnem načinu ogrevalni krog 2": "loop_2_comfort_offset",
            
            # Loop 3 (2059-2068)
            "Želena temperatura ogrevalnega kroga 3 / Prostor 3": "loop_3_setpoint",
            "Trenutna želena temperatura ogrevalnega kroga 3 / temperatura prostor 3": "loop_3_current_setpoint",
            "Izbira delovanja ogrevalni krog 3": "loop_3_operation_mode",
            "Status delovanja kroga 3 po urniku": "loop_3_schedule_status",
            "Status obtočne črpalke krog 3": "loop_3_pump_status",
            "Status termostata krog 3": "loop_3_thermostat_status",
            "Odmik v eco načinu ogrevalni krog 3": "loop_3_eco_offset",
            "Odmik v comfortnem načinu ogrevalni krog 3": "loop_3_comfort_offset",
            
            # Loop 4 (2069-2078)
            "Želena temperatura ogrevalnega kroga 4 / Prostor 4": "loop_4_setpoint",
            "Trenutna želena temperatura ogrevalnega kroga 4 / temperatura prostor 4": "loop_4_current_setpoint",
            "Izbira delovanja ogrevalni krog 4": "loop_4_operation_mode",
            "Status delovanja kroga 4 po urniku": "loop_4_schedule_status",
            "Status obtočne črpalke krog 4": "loop_4_pump_status",
            "Status termostata krog 4": "loop_4_thermostat_status",
            "Odmik v eco načinu ogrevalni krog 4": "loop_4_eco_offset",
            "Odmik v comfortnem načinu ogrevalni krog 4": "loop_4_comfort_offset",
            
            # Pool (2079-2087)
            "Želena temperatura bazen": "pool_setpoint",
            "Trenutna želena temperatura bazen": "pool_current_setpoint",
            "Izbira delovanja bazen": "pool_operation_mode",
            "Status delovanja bazena po urniku": "pool_schedule_status",
            "Status obtočne črpalke bazena": "pool_pump_status",
            "Status termostata bazena": "pool_thermostat_status",
            "Odmik v eco načinu bazen": "pool_eco_offset",
            "Odmik v comfortnem načinu bazen": "pool_comfort_offset",
            "Obtočna črpalka alternativni vir": "alternative_source_pump",
            
            # Operating Hours (2089-2099)
            "Obratovalne ure kompresor v režimu hlajenja": "operating_hours_cooling",
            "Obratovalne ure kompresor v režimu ogrevanja": "operating_hours_compressor_heating",  # Cloud API key
            "Obratovalne ure kompresor v režimu segrevanja sanitarne vode": "operating_hours_compressor_dhw",  # Cloud API key
            "Obratovalne ure glavna obtočne črpalke": "operating_hours_main_pump",
            "Obratovalne ure sanitarna obtočna črpalka": "operating_hours_dhw_pump",
            "Obratovalne ure dodatnega grela 1": "operating_hours_additional_source_1",  # Cloud API key
            "Obratovalne ure dodatnega grela 2": "operating_hours_heater_2",
            "Obratovalne ure alternativni vir": "operating_hours_alternative_source",
            "Obratovalne ure toplotni vir": "operating_hours_heat_source",
            "Obratovalne ure pasiva": "operating_hours_passive",
            
            # Temperatures (2101-2130)
            # NOTE: Using Cloud API keys for backward compatibility (historical data)
            "Temperatura povratnega voda": "hp_inlet_temperature",  # 2101 - Cloud API key
            "Temperatura sanitarne vode": "temperature_outside",     # 2102 - Cloud API key (MISLABELED!)
            "Zunanja temperatura": "outdoor_temperature",            # 2103 - True outdoor temp
            "Temperatura dvižnega voda": "hp_outlet_temperature",    # 2104 - Cloud API key
            "Temperatura uparjanja": "temperature_compressor_inlet", # 2105 - Cloud API key
            "Temperatura kompresorja": "temperature_compressor_outlet", # 2106 - Cloud API key
            "Temperatura alternativnega vira": "alternative_source_temperature",
            "Temperatura bazena": "pool_temperature",
            "Temperatura 2. kroga": "loop_2_temperature",
            "Temperatura 3. kroga": "loop_3_temperature",
            "Temperatura 4. kroga": "loop_4_temperature",
            "Trenutna želena temperatura ogrevalnega kroga 1": "loop_1_current_setpoint",
            "Trenutna električna poraba": "current_heating_cooling_capacity", # 2129 - Cloud API key
            "Temperatura 1. kroga": "loop_1_temperature",
            
            # Misc Status (2139-2191)
            "Dopust število dni": "vacation_days",
            "Temperatura termostata 1. ogrevalnega kroga": "loop_1_thermostat_temperature",
            "Temperatura termostata 2. ogrevalnega kroga": "loop_2_thermostat_temperature",
            "Temperatura termostata 3. ogrevalnega kroga": "loop_3_thermostat_temperature",
            "Temperatura termostata 4. ogrevalnega kroga": "loop_4_thermostat_temperature",
            "Izpad termostata": "thermostat_failure",
            "Želena temperatura prostor 1": "loop_1_room_setpoint",
            "Trenutna želena temperatura ogrevalnega kroga 2": "loop_2_current_setpoint",
            "Trenutna želena temperatura ogrevalnega kroga 3": "loop_3_current_setpoint",
            "Trenutna želena temperatura ogrevalnega kroga 4": "loop_4_current_setpoint",
            "Trenutna želena temperatura prostor 1": "loop_1_room_current_setpoint",
            "Oddaljen vklop funkcij": "remote_function_control",
            
            # Thermal Disinfection (2301-2304)
            "Termična dezinfekcija": "thermal_disinfection",
            "Termična dezinfekcija: Želena temperatura": "thermal_disinfection_setpoint",
            "Termična dezinfekcija: Perioda dezinfekcije": "thermal_disinfection_period",
            "Termična dezinfekcija: Začetek dezinfekcije": "thermal_disinfection_start_time",
            
            # Solar/Biomass (2305-2306)
            "Solar/biomasa: Želena temperatura zalogovnika": "solar_reservoir_setpoint",
            "Solar/biomasa: Želena temperatura bojlerja": "solar_boiler_setpoint",
            
            # Advanced (2307-2327)
            "Sušenje estrihov": "screed_drying",
            "Status kompresorjev": "compressor_status",
            "Status kompresorja (Varovanje)": "compressor_protection_status",
            "Polnjenje ogrevalnega sistema": "system_filling",
            "Nastavitev tlaka ogrevalnega sistema": "system_pressure_setting",
            "Tlak ogrevalnega sistema": "heating_system_pressure",
            "Trenutna obremenitev TČ": "hp_load",
            "Trenutna grelna/hladilna moč": "current_heating_cooling_power",
            
            # Energy/COP (2361-2372)
            "Električna energija ogrevanje + sanitarna voda (high)": "electrical_energy_high",
            "Električna energija ogrevanje + sanitarna voda (low)": "electrical_energy_low",
            "Toplotna energija ogrevanje + sanitarna voda (high)": "thermal_energy_high",
            "Toplotna energija ogrevanje + sanitarna voda (low)": "thermal_energy_low",
            "COP": "cop_value",      # Cloud API key for historical data
            "SCOP": "scop_value",    # Cloud API key for historical data
        }
        
        # Try direct translation
        if slovenian_name in translations:
            return translations[slovenian_name]
        
        # Fallback: simple snake_case conversion
        # Remove special chars, lowercase, replace spaces with underscores
        name = slovenian_name.lower()
        name = name.replace("č", "c").replace("š", "s").replace("ž", "z")
        name = "".join(c if c.isalnum() or c == " " else "" for c in name)
        name = "_".join(name.split())
        
        return name

    def get(self, address: int) -> Optional[RegisterDefinition]:
        """Get register definition by address."""
        return self._registers.get(address)

    def get_by_name(self, name_en: str) -> Optional[RegisterDefinition]:
        """Get register definition by English name.
        
        Args:
            name_en: English name (snake_case) from name_en field
            
        Returns:
            RegisterDefinition if found, None otherwise
            
        Example:
            reg = register_map.get_by_name("system_on")
            # Returns register 2012 (Vklop sistema)
        """
        for reg in self._registers.values():
            if reg.name_en == name_en:
                return reg
        return None

    def get_all(self) -> List[RegisterDefinition]:
        """Get all register definitions."""
        return list(self._registers.values())

    def get_sensors(self) -> List[RegisterDefinition]:
        """Get all readable registers suitable for sensors."""
        return [
            reg for reg in self._registers.values()
            if "Read" in reg.access 
            and reg.type in ("Value", "Value32", "Status", "Enum")
            and not reg.disabled
        ]

    def get_controls(self) -> List[RegisterDefinition]:
        """Get all writable control registers."""
        return [
            reg for reg in self._registers.values()
            if "Write" in reg.access and reg.type == "Control" and not reg.disabled
        ]
    
    def get_writable(self) -> List[RegisterDefinition]:
        """Get all writable registers (Read/Write or W access)."""
        return [
            reg for reg in self._registers.values()
            if "Write" in reg.access and not reg.disabled
        ]

    def get_bitmasks(self) -> List[RegisterDefinition]:
        """Get all bitmask registers."""
        return [
            reg for reg in self._registers.values()
            if reg.type == "Bitmask"
        ]

    @property
    def meta_info(self) -> Dict[str, Any]:
        """Get metadata about the register map."""
        return self._meta_info
