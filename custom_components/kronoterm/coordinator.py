import logging
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import aiohttp
from aiohttp.client_exceptions import ClientError, ClientResponseError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

from .const import (
    DOMAIN,
    API_QUERIES,
    BASE_URL,
    DEFAULT_SCAN_INTERVAL,
    REQUEST_TIMEOUT,
    MAX_RETRY_ATTEMPTS,
    RETRY_DELAY_BASE
)

class KronotermCoordinator(DataUpdateCoordinator):
    """Coordinator that fetches and manages Kronoterm heat pump data."""

    def __init__(self, hass: HomeAssistant, session: aiohttp.ClientSession, config_entry):
        """Initialize the coordinator with the Home Assistant instance and session."""
        self.hass = hass
        self.session = session
        self.config_entry = config_entry
        
        # Extract credentials
        self.username = config_entry.options.get("username", config_entry.data.get("username", ""))
        self.password = config_entry.options.get("password", config_entry.data.get("password", ""))
        if not self.username or not self.password:
            _LOGGER.error("No username/password found in config entry! Authentication will fail.")
        self.auth = aiohttp.BasicAuth(self.username, self.password)

        # Determine scan interval from config, with minimum of 1 minute
        scan_interval = config_entry.options.get(
            "scan_interval", 
            config_entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        )
        scan_interval = max(scan_interval, 1)
        _LOGGER.info("Kronoterm coordinator update interval set to %d minutes", scan_interval)

        super().__init__(
            hass,
            _LOGGER,
            name="kronoterm_unified_coordinator",
            update_method=self._async_update_data,
            update_interval=timedelta(minutes=scan_interval),
        )

        # Shared information across entities
        self.shared_device_info: Dict[str, Any] = {}
        self.reservoir_installed: bool = False

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch all required data in parallel and merge into a single dictionary."""
        try:
            results = await asyncio.gather(
                self._fetch_main(),
                self._fetch_consumption(),
                self._fetch_shortcuts(),
                return_exceptions=True
            )
            
            # Handle any exceptions from gather
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    _LOGGER.error("Error in gather item %d: %s", i, result)
                    results[i] = None
            
            # Combine results into a single dictionary
            data = {
                "main": results[0],
                "consumption": results[1],
                "shortcuts": results[2],
            }
            
            # Preserve previously-fetched 'info' data if it exists
            if self.data and "info" in self.data:
                data["info"] = self.data["info"]

            return data
        except Exception as err:
            raise UpdateFailed(f"Unified update failed: {err}") from err

    async def async_initialize(self) -> None:
        """
        Initialize the coordinator with:
        1) First data refresh
        2) One-time info fetch
        3) System configuration parsing
        """
        # 1) Initial data refresh
        await self.async_config_entry_first_refresh()

        # 2) Fetch info data once
        await self._async_fetch_info_once()

        # 3) Parse system configuration
        await self._parse_system_config()
        
        _LOGGER.info("Kronoterm coordinator initialized successfully")

    async def _parse_system_config(self) -> None:
        """Parse system configuration from main data."""
        main_data = (self.data or {}).get("main") or {}
        system_config = main_data.get("SystemConfiguration", {})
        self.reservoir_installed = bool(system_config.get("reservoir_installed", 0))
        _LOGGER.info("Reservoir installed: %s", self.reservoir_installed)

    async def _async_fetch_info_once(self) -> None:
        """Fetch 'info' data exactly once and parse device information."""
        try:
            info_data = await self._fetch_info()
            if info_data is None:
                _LOGGER.warning("No 'info' data returned.")
                return

            # Merge into self.data
            if not self.data:
                self.data = {}
            self.data["info"] = info_data

            # Extract device info from the response
            self._parse_device_info(info_data)
        except Exception as e:
            _LOGGER.warning("Failed to fetch 'info' data once: %s", e)

    def _parse_device_info(self, info_data: Dict[str, Any]) -> None:
        """Extract device information from info data response."""
        info_data_section = info_data.get("InfoData", {})
        device_id = info_data_section.get("device_id", "kronoterm_heat_pump")
        pump_model = info_data_section.get("pumpModel", "Unknown Model")
        firmware_version = info_data_section.get("firmware", "Unknown Firmware")

        self.shared_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": "Kronoterm Heat Pump",
            "manufacturer": "Kronoterm",
            "model": pump_model,
            "sw_version": firmware_version,
        }
        _LOGGER.info("Device info parsed - ID: %s, model: %s", device_id, pump_model)

    # ------------------------------------------------------------------
    #  API Fetch Methods
    # ------------------------------------------------------------------
    async def _fetch_main(self) -> Optional[Dict[str, Any]]:
        """Fetch main system data."""
        return await self._request_with_retries("GET", API_QUERIES["main"])

    async def _fetch_info(self) -> Optional[Dict[str, Any]]:
        """Fetch device information data."""
        return await self._request_with_retries("GET", API_QUERIES["info"])

    async def _fetch_shortcuts(self) -> Optional[Dict[str, Any]]:
        """Fetch shortcuts data."""
        return await self._request_with_retries("GET", API_QUERIES["shortcuts"])

    async def _fetch_consumption(self) -> Optional[Dict[str, Any]]:
        """Fetch consumption statistics data."""
        # Get current year and day, or use configured values
        now = datetime.now()
        year = now.year
        d1 = now.timetuple().tm_yday

        # Override with configured values if available
        if (custom_year := self.config_entry.options.get("consumption_year")):
            try:
                year = int(custom_year)
            except ValueError:
                _LOGGER.warning("Invalid consumption_year in options, ignoring.")

        if (custom_d1 := self.config_entry.options.get("consumption_d1")):
            try:
                d1 = int(custom_d1)
            except ValueError:
                _LOGGER.warning("Invalid consumption_d1 in options, ignoring.")

        # Construct consumption query
        query_params = {
            "TopPage": "4",
            "Subpage": "4",
            "Action": "4"
        }
        
        # Consumption requires specific form data
        form_data = [
            ("year", str(year)),
            ("d1", str(d1)),
            ("d2", "0"),
            ("type", "day"),
            ("aValues[]", "17"),
            ("dValues[]", "90"),
            ("dValues[]", "0"),
            ("dValues[]", "91"),
            ("dValues[]", "92"),
            ("dValues[]", "1"),
            ("dValues[]", "2"),
            ("dValues[]", "24"),
            ("dValues[]", "71"),
        ]
        
        return await self._request_with_retries("POST", query_params, form_data)

    # ------------------------------------------------------------------
    #  HTTP Request Helpers
    # ------------------------------------------------------------------
    async def _request_with_retries(
        self, 
        method: str, 
        query_params: Dict[str, str], 
        form_data: Optional[List[Tuple[str, str]]] = None, 
        attempts: int = MAX_RETRY_ATTEMPTS
    ) -> Optional[Dict[str, Any]]:
        """Make an HTTP request with automatic retries on failure."""
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        
        for attempt_idx in range(attempts):
            try:
                if method.upper() == "GET":
                    return await self._perform_get(query_params, timeout)
                else:
                    return await self._perform_post(query_params, form_data, timeout)
            except (ClientResponseError, ClientError) as e:
                _LOGGER.warning("%s attempt %d failed: %s", method.upper(), attempt_idx + 1, e)
                if attempt_idx < attempts - 1:
                    # Exponential backoff for retries
                    await asyncio.sleep(RETRY_DELAY_BASE ** attempt_idx)
                else:
                    raise UpdateFailed(f"Max {method} retries reached for {query_params}: {e}")
        
        return None

    async def _perform_get(
        self, 
        query_params: Dict[str, str], 
        timeout: aiohttp.ClientTimeout
    ) -> Optional[Dict[str, Any]]:
        """Perform a GET request and validate the response."""
        async with self.session.get(
            BASE_URL,
            auth=self.auth,
            params=query_params,
            timeout=timeout
        ) as response:
            return await self._process_response(response, "GET", query_params)

    async def _perform_post(
        self, 
        query_params: Dict[str, str], 
        form_data: Optional[List[Tuple[str, str]]], 
        timeout: aiohttp.ClientTimeout
    ) -> Optional[Dict[str, Any]]:
        """Perform a POST request and validate the response."""
        async with self.session.post(
            BASE_URL,
            auth=self.auth,
            params=query_params,
            data=form_data,
            timeout=timeout
        ) as response:
            return await self._process_response(response, "POST", query_params)

    async def _process_response(
        self, 
        response: aiohttp.ClientResponse, 
        method: str, 
        query_params: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """Process HTTP response, handle errors, and return JSON data."""
        if response.status == 401:
            _LOGGER.error("Unauthorized! Check credentials.")
            return None
        
        if response.status != 200:
            body = await response.text()
            _LOGGER.error("HTTP %s on %s: %s", response.status, method, body)
            raise UpdateFailed(f"HTTP {response.status} for {method} {query_params}")
        
        # Validate response is JSON
        try:
            return await response.json()
        except aiohttp.ContentTypeError as e:
            text = await response.text()
            _LOGGER.error("Invalid JSON response: %s", text[:200])
            raise UpdateFailed(f"Invalid JSON response for {method} {query_params}") from e

    # -------------------------------------
    # Command/Control Methods
    # -------------------------------------
    async def async_set_temperature(self, page: int, new_temp: float) -> bool:
        """Set temperature for a specific page/circle."""
        # Validate input
        if not isinstance(new_temp, (int, float)) or new_temp < 0 or new_temp > 60:
            _LOGGER.error("Invalid temperature value: %s", new_temp)
            return False
            
        # Map page number to the appropriate query
        query = self._get_query_for_page(page)
        if query is None:
            return False
        
        payload = self._create_payload("circle_temp", str(round(new_temp, 1)), page)
        return await self._execute_command(query, payload)

    async def async_set_heatpump_state(self, turn_on: bool) -> bool:
        """Turn the heat pump on or off."""
        payload = self._create_payload("heatpump_on", "1" if turn_on else "0", -1)
        return await self._execute_command(API_QUERIES["switch"], payload)

    async def async_set_dhw_circulation(self, turn_on: bool) -> bool:
        """Turn DHW circulation on or off."""
        payload = self._create_payload("circulation_on", "1" if turn_on else "0", -1) 
        return await self._execute_command(API_QUERIES["switch"], payload)

    async def async_set_fast_water_heating(self, turn_on: bool) -> bool:
        """Turn fast water heating on or off."""
        payload = self._create_payload("water_heating_on", "1" if turn_on else "0", -1)
        return await self._execute_command(API_QUERIES["switch"], payload)

    async def async_set_antilegionella(self, turn_on: bool) -> bool:
        """Turn antilegionella function on or off."""
        payload = self._create_payload("antilegionella", "1" if turn_on else "0", -1)
        return await self._execute_command(API_QUERIES["switch"], payload)

    async def async_set_loop_mode_by_page(self, page: int, new_mode: int) -> bool:
        """Set operating mode for a specific loop/circuit."""
        # Validate input
        if not isinstance(new_mode, int) or new_mode < 0 or new_mode > 5:
            _LOGGER.error("Invalid mode value: %s", new_mode)
            return False
            
        # Map page number to the appropriate query
        query = self._get_query_for_page(page)
        if query is None:
            return False
        
        payload = self._create_payload("circle_status", str(new_mode), page)
        return await self._execute_command(query, payload)

    async def async_set_offset(self, page: int, param_name: str, new_value: float) -> bool:
        """Set offset parameter for a specific page."""
        # Validate inputs
        if not param_name or not isinstance(new_value, (int, float)):
            _LOGGER.error("Invalid parameter name or value: %s=%s", param_name, new_value)
            return False
            
        query_params = {
            "TopPage": "1",
            "Subpage": str(page),
            "Action": "1"
        }
        
        payload = self._create_payload(param_name, str(new_value), page)
        return await self._execute_command(query_params, payload)

    # -------------------------------------
    # Helper Methods
    # -------------------------------------
    def _get_query_for_page(self, page: int) -> Optional[Dict[str, str]]:
        """Map page number to appropriate query parameters."""
        page_mapping = {
            9: API_QUERIES["dhw"],
            5: API_QUERIES["loop1"],
            6: API_QUERIES["loop2"],
            4: API_QUERIES["reservoir"]
        }
        
        if page not in page_mapping:
            _LOGGER.error("Invalid page number %s", page)
            return None
            
        return page_mapping[page]
        
    def _create_payload(self, param_name: str, param_value: str, page: int) -> List[Tuple[str, str]]:
        """Create a standardized payload for API commands."""
        return [
            ("param_name", param_name),
            ("param_value", param_value),
            ("page", str(page))
        ]
        
    async def _execute_command(
        self, 
        query: Dict[str, str], 
        payload: List[Tuple[str, str]]
    ) -> bool:
        """Execute a command and handle response."""
        try:
            resp = await self._request_with_retries("POST", query, payload)
            if resp is not None:
                _LOGGER.info("Command executed successfully: %s", resp)
                await self.async_request_refresh()
                return True
            return False
        except UpdateFailed as err:
            _LOGGER.error("Error executing command: %s", err)
            return False