import logging
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from aiohttp.client_exceptions import ClientError, ClientResponseError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    BASE_URL,
    BASE_URL_DHW,
    API_QUERIES_GET,
    API_QUERIES_GET_DHW,
    API_QUERIES_SET,
    API_QUERIES_SET_DHW,
    PAGE_TO_SET_QUERY_KEY,
    API_PARAM_KEYS,
    CONSUMPTION_FORM_DATA_STATIC,
    DEFAULT_SCAN_INTERVAL,
    REQUEST_TIMEOUT,
    MAX_RETRY_ATTEMPTS,
    RETRY_DELAY_BASE,
    SHORTCUT_DELAY_DEFAULT,
    SHORTCUT_DELAY_STATE,
)

_LOGGER = logging.getLogger(__name__)


class KronotermBaseCoordinator(DataUpdateCoordinator):
    """Base class for Kronoterm coordinators."""
    
    def __init__(self, hass: HomeAssistant, session: aiohttp.ClientSession, config_entry, base_url, api_queries_get, api_queries_set):
        self.hass = hass
        self.session = session
        self.config_entry = config_entry
        self.base_url = base_url
        self.api_queries_get = api_queries_get
        self.api_queries_set = api_queries_set
        
        # Extract credentials
        self.username = config_entry.options.get("username", config_entry.data.get("username", ""))
        self.password = config_entry.options.get("password", config_entry.data.get("password", ""))
        
        if not self.username or not self.password:
            _LOGGER.error("No username/password found in config entry! Authentication will fail.")
        
        # Store Basic Auth object to send with EVERY request
        self.auth = aiohttp.BasicAuth(self.username, self.password)

        # Scan interval
        scan_interval_seconds = config_entry.options.get("scan_interval_seconds")
        if scan_interval_seconds is not None:
            scan_interval_seconds = max(scan_interval_seconds, 30)
            interval = timedelta(seconds=scan_interval_seconds)
        else:
            scan_interval_minutes = config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
            scan_interval_minutes = max(scan_interval_minutes, 1)
            interval = timedelta(minutes=scan_interval_minutes)

        super().__init__(
            hass,
            _LOGGER,
            name=f"kronoterm_coordinator_{config_entry.entry_id}",
            update_method=self._async_update_data,
            update_interval=interval,
        )

        self._session_valid = False
        self.shared_device_info: Dict[str, Any] = {}
        # Feature flags
        self.reservoir_installed = False
        self.pool_installed = False
        self.alt_source_installed = False
        self.loop1_installed = False
        self.loop2_installed = False
        self.loop3_installed = False
        self.loop4_installed = False
        self.tap_water_installed = False
        self.system_type = config_entry.data.get("system_type", "cloud")

    async def async_initialize(self) -> None:
        """Initialize: Verify auth, then fetch info."""
        await self._perform_login()
        await self.async_config_entry_first_refresh()
        await self._async_fetch_info_once()
        _LOGGER.info("Kronoterm coordinator initialized successfully")

    async def _perform_login(self) -> None:
        """Perform initial handshake (Menu=1)."""
        _LOGGER.debug("Performing initial handshake (Menu=1)...")
        try:
            query_params = self.api_queries_get["menu"]
            async with self.session.get(
                self.base_url, 
                auth=self.auth, 
                params=query_params,
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                if response.status == 200:
                    try:
                        data = await response.json()
                        if "hp_id" in data:
                            _LOGGER.info("Handshake successful. Session primed for HP ID: %s", data.get("hp_id"))
                            self._session_valid = True
                            return
                        else:
                            _LOGGER.warning("Handshake returned 200 but missing 'hp_id'. Response: %s", data)
                    except Exception:
                        _LOGGER.warning("Handshake returned 200 but invalid JSON.")
                    self._session_valid = True 
                else:
                    _LOGGER.error("Handshake failed. Status: %s", response.status)
                    self._session_valid = False
        except Exception as e:
            _LOGGER.error("Error during handshake: %s", e)
            self._session_valid = False

    def _get_headers(self) -> Dict[str, str]:
        """Generate headers. Overridden by subclasses."""
        raise NotImplementedError

    async def _async_fetch_info_once(self) -> None:
        """Fetch system info. Overridden by subclasses."""
        pass

    async def _request_with_retries(self, method: str, query_params: Dict[str, str], form_data=None, attempts=MAX_RETRY_ATTEMPTS) -> Optional[Dict[str, Any]]:
        """HTTP request with retries."""
        for attempt_idx in range(attempts):
            try:
                timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                page_cookies = self._get_page_cookies(query_params)
                
                if method.upper() == "GET":
                    async with self.session.get(
                        self.base_url, auth=self.auth, params=query_params, 
                        headers=self._get_headers(), cookies=page_cookies, timeout=timeout
                    ) as response:
                        return await self._process_response(response, "GET", query_params)
                else:
                    async with self.session.post(
                        self.base_url, auth=self.auth, params=query_params, data=form_data,
                        headers=self._get_headers(), cookies=page_cookies, timeout=timeout
                    ) as response:
                        return await self._process_response(response, "POST", query_params)
                        
            except (ClientResponseError, ClientError) as e:
                _LOGGER.warning("%s attempt %d failed: %s", method.upper(), attempt_idx + 1, e)
                if isinstance(e, ClientResponseError) and e.status in (401, 403):
                    _LOGGER.warning("Auth failure. Re-initializing connection.")
                    await self._perform_login()
                    continue
                if attempt_idx < attempts - 1:
                    await asyncio.sleep(RETRY_DELAY_BASE ** attempt_idx)
                else:
                    raise UpdateFailed(f"Max {method} retries reached for {query_params}: {e}")
        return None

    def _get_page_cookies(self, query_params: Dict[str, str]) -> Dict[str, str]:
        cookies = {"lang": "en"}
        if "TopPage" in query_params:
            cookies["CurrentTopPage"] = query_params["TopPage"]
        if "Subpage" in query_params:
            cookies["CurrentSubPage"] = query_params["Subpage"]
        return cookies

    async def _process_response(self, response, method, query_params) -> Optional[Dict[str, Any]]:
        if response.status == 401:
             raise ClientResponseError(response.request_info, response.history, status=401, message="Unauthorized")
        if response.status != 200:
            raise UpdateFailed(f"HTTP {response.status} for {method} {query_params}")
        
        raw_text = await response.text()
        _LOGGER.debug("Raw response %s %s: %s", method, query_params, raw_text)
        
        try:
            data = json.loads(raw_text)
            if data.get("result") == "action" and "window.location" in data.get("js", ""):
                 raise ClientResponseError(response.request_info, response.history, status=401, message="Session Redirect")
            return data
        except json.JSONDecodeError as e:
            raise UpdateFailed(f"Invalid JSON response for {method} {query_params}") from e
            
    async def _async_update_data(self) -> Dict[str, Any]:
        """Main update loop. Overridden by subclasses."""
        raise NotImplementedError


class KronotermMainCoordinator(KronotermBaseCoordinator):
    """Coordinator for standard Heat Pumps (Main Cloud)."""

    def __init__(self, hass, session, config_entry):
        super().__init__(hass, session, config_entry, BASE_URL, API_QUERIES_GET, API_QUERIES_SET)
        _LOGGER.info("Initializing Kronoterm Main Coordinator")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "phonegap": "1.5.0",
            "Accept": "*/*", 
            "Accept-Language": "en-US,en;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": self.base_url,
            "Origin": "https://cloud.kronoterm.com",
            "Connection": "keep-alive",
        }

    async def _async_fetch_info_once(self) -> None:
        try:
            info_data = await self._request_with_retries("GET", self.api_queries_get["info"])
            if info_data is None:
                raise UpdateFailed("No 'info' data returned from API")
            if not self.data:
                self.data = {}
            self.data["info"] = info_data
            
            self._parse_device_info(info_data)
            
            temp_config = info_data.get("TemperaturesAndConfig", {})
            self.pool_installed = bool(temp_config.get("pool_active", 0))
            self.reservoir_installed = True
            self.alt_source_installed = bool(temp_config.get("alt_source_temp_visible", 0))
            self.loop1_installed = bool(temp_config.get("circle_1_installed", 0))
            self.loop2_installed = bool(temp_config.get("circle_2_installed", 0))
            self.loop3_installed = bool(temp_config.get("circle_3_installed", 0))
            self.loop4_installed = bool(temp_config.get("circle_4_installed", 0))
            self.tap_water_installed = bool(temp_config.get("tap_water_installed", 0))
        except Exception as e:
            _LOGGER.error("Failed to fetch 'info' data: %s", e)
            raise

    def _parse_device_info(self, info_data: Dict[str, Any]) -> None:
        info_data_section = info_data.get("InfoData", {})
        self.shared_device_info = {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": "Kronoterm Heat Pump",
            "manufacturer": "Kronoterm",
            "model": info_data_section.get("pumpModel", "Unknown Model"),
            "sw_version": info_data_section.get("firmware", "Unknown Firmware"),
        }

    async def _async_update_data(self) -> Dict[str, Any]:
        if not self._session_valid:
            await self._perform_login()

        try:
            data = {}
            # 1. Main & Shortcuts
            results = await asyncio.gather(
                self._request_with_retries("GET", self.api_queries_get["main"]),
                self._request_with_retries("GET", self.api_queries_get["shortcuts"]),
                return_exceptions=True
            )
            data["main"] = results[0] if not isinstance(results[0], Exception) else None
            data["shortcuts"] = results[1] if not isinstance(results[1], Exception) else None

            # 2. Loops/DHW/Reservoir
            try:
                loop_results = await asyncio.gather(
                    self._request_with_retries("GET", self.api_queries_get["loop1"]),
                    self._request_with_retries("GET", self.api_queries_get["loop2"]),
                    self._request_with_retries("GET", self.api_queries_get["dhw"]),
                    self._request_with_retries("GET", self.api_queries_get["reservoir"]),
                    self._request_with_retries("GET", self.api_queries_get["loop3"]),
                    self._request_with_retries("GET", self.api_queries_get["loop4"]),
                    self._request_with_retries("GET", self.api_queries_get["main_settings"]),
                    self._request_with_retries("GET", self.api_queries_get["system_data"]),
                )
                data["loop1"] = loop_results[0]
                data["loop2"] = loop_results[1]
                data["dhw"] = loop_results[2]
                data["reservoir"] = loop_results[3]
                data["loop3"] = loop_results[4]
                data["loop4"] = loop_results[5]
                data["main_settings"] = loop_results[6]
                data["system_data"] = loop_results[7]
            except Exception as e:
                _LOGGER.error("Error fetching loops: %s", e)
            
            if self.data and "info" in self.data:
                data["info"] = self.data["info"]
                
            return data
        except Exception as err:
            raise UpdateFailed(f"Main update failed: {err}") from err

    # Setter methods for Main Cloud (kept from original class)
    async def _async_set_page_parameter(self, page: int, param_name: str, param_value: str) -> bool:
        query_key = PAGE_TO_SET_QUERY_KEY.get(page)
        if not query_key: return False
        form_data = [("param_name", param_name), ("param_value", param_value), ("page", str(page))]
        return await self._send_set_request(query_key, form_data)

    async def _async_set_shortcut(self, param_name: str, enable: bool) -> bool:
        form_data = [("param_name", param_name), ("param_value", "1" if enable else "0"), ("page", "-1")]
        return await self._send_set_request("switch", form_data)

    async def _send_set_request(self, query_key, form_data):
        try:
            result = await self._request_with_retries("POST", self.api_queries_set[query_key], form_data)
            if result and result.get("result") == "success":
                await self.async_request_refresh()
                return True
            return False
        except UpdateFailed:
            return False

    # (Add other specific setters here if needed, keeping it minimal for now)
    async def async_set_temperature(self, page: int, new_temp: float) -> bool:
        return await self._async_set_page_parameter(page, API_PARAM_KEYS["TEMP"], str(round(new_temp, 1)))

    async def async_set_loop_mode_by_page(self, page: int, new_mode: int) -> bool:
        return await self._async_set_page_parameter(page, API_PARAM_KEYS["MODE"], str(new_mode))


class KronotermDHWCoordinator(KronotermBaseCoordinator):
    """Coordinator for DHW Heat Pumps (Water Cloud)."""

    def __init__(self, hass, session, config_entry):
        super().__init__(hass, session, config_entry, BASE_URL_DHW, API_QUERIES_GET_DHW, API_QUERIES_SET_DHW)
        _LOGGER.info("Initializing Kronoterm DHW Coordinator")
        # Ensure we don't accidentally check flags that don't exist
        self.tap_water_installed = True 

    def _get_headers(self) -> Dict[str, str]:
        return {
            "phonegap": "1.0.7",
            "Accept": "*/*", 
            "Accept-Language": "en-US,en;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": self.base_url,
            "Origin": "https://cloud.kronoterm.com",
            "Connection": "keep-alive",
        }

    async def _async_fetch_info_once(self) -> None:
        # DHW doesn't have an "info" page like Main. 
        # We fetch "main" to get basic info if needed.
        # Just set device info manually for now based on what we know.
        self.shared_device_info = {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": "Kronoterm DHW",
            "manufacturer": "Kronoterm",
            "model": "DHW Heat Pump",
            "sw_version": "Unknown",
        }

    async def _async_update_data(self) -> Dict[str, Any]:
        if not self._session_valid:
            await self._perform_login()

        try:
            data = {}
            # Fetch Main (Basic Data) and Shortcuts
            results = await asyncio.gather(
                self._request_with_retries("GET", self.api_queries_get["main"]),
                self._request_with_retries("GET", self.api_queries_get["shortcuts"]),
                return_exceptions=True
            )
            
            data["main"] = results[0] if not isinstance(results[0], Exception) else None
            data["shortcuts"] = results[1] if not isinstance(results[1], Exception) else None
            
            # Nullify others to be safe
            for key in ["loop1", "loop2", "dhw", "reservoir", "loop3", "loop4", "main_settings", "system_data", "info", "consumption"]:
                data[key] = None
                
            return data
        except Exception as err:
            raise UpdateFailed(f"DHW update failed: {err}") from err

    # Setter methods for DHW
    async def async_set_temperature(self, page: int, new_temp: float) -> bool:
        # DHW Temp is usually on page 1 ("main")
        form_data = [
            ("param_name", "boiler_setpoint"),
            ("param_value", str(round(new_temp, 1))),
            ("page", "1"),
        ]
        return await self._send_set_request("main", form_data)

    async def async_set_luxury_shower(self, enable: bool) -> bool:
        return await self._send_shortcut("shrtct_luxury_shower", enable)

    async def async_set_antilegionella(self, enable: bool) -> bool:
        return await self._send_shortcut("shrtct_antilegionela", enable)

    async def async_set_reserve_source(self, enable: bool) -> bool:
        return await self._send_shortcut("shrtct_reserve_source", enable)

    async def async_set_holiday(self, enable: bool) -> bool:
        # Use current holiday_days if available
        days = 0
        try:
            days = int(
                self.data.get("shortcuts", {})
                .get("ShortcutsData", {})
                .get("holiday_days", 0)
            )
        except Exception:
            days = 0
        return await self._send_shortcut("shrtct_holiday", enable, additional_value=days)

    async def async_set_dhw_eco_offset(self, value: float) -> bool:
        form_data = [
            ("param_name", "boiler_eco_offset"),
            ("param_value", str(round(value, 1))),
            ("page", "1"),
        ]
        return await self._send_set_request("main", form_data)

    async def async_set_dhw_comfort_offset(self, value: float) -> bool:
        form_data = [
            ("param_name", "boiler_comfort_offset"),
            ("param_value", str(round(value, 1))),
            ("page", "1"),
        ]
        return await self._send_set_request("main", form_data)

    async def async_set_dhw_default_mode(self, mode: int) -> bool:
        form_data = [
            ("param_name", "default_mode"),
            ("param_value", str(int(mode))),
            ("page", "1"),
        ]
        return await self._send_set_request("main", form_data)

    async def _send_shortcut(self, param_name: str, enable: bool, additional_value: Optional[int] = None) -> bool:
        form_data = [
            ("param_name", param_name),
            ("param_value", "1" if enable else "0"),
            ("page", "2"),
        ]
        if additional_value is not None:
            form_data.append(("additional_value", str(additional_value)))
        return await self._send_set_request("shortcuts", form_data)

    async def _send_set_request(self, query_key, form_data):
        try:
            result = await self._request_with_retries("POST", self.api_queries_set[query_key], form_data)
            if result and result.get("result") == "success":
                await self.async_request_refresh()
                return True
            return False
        except UpdateFailed:
            return False

# Compatibility alias for existing code
KronotermCoordinator = KronotermMainCoordinator
