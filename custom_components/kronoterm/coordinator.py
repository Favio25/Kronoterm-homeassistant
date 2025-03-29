import logging
import asyncio
from datetime import datetime, timedelta

import aiohttp
from aiohttp.client_exceptions import ClientError, ClientResponseError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Single base URL
BASE_URL = "https://cloud.kronoterm.com/jsoncgi.php"

# Default intervals/timeouts
DEFAULT_SCAN_INTERVAL = 5  # 5 minutes
REQUEST_TIMEOUT = 10       # 10 seconds

# Query param presets for main info
QUERY_MAIN = {"TopPage": "5", "Subpage": "3"}
QUERY_INFO = {"TopPage": "1", "Subpage": "1"}

# Query param presets for sending commands
QUERY_DHW   = {"TopPage": "1", "Subpage": "9", "Action": "1"}
QUERY_LOOP1 = {"TopPage": "1", "Subpage": "5", "Action": "1"}
QUERY_LOOP2 = {"TopPage": "1", "Subpage": "6", "Action": "1"}
QUERY_SWITCH = {"TopPage": "1", "Subpage": "3", "Action": "1"}
QUERY_RESERVOIR = {"TopPage": "1", "Subpage": "4", "Action": "1"}



class KronotermCoordinator:
    """Handles API communication and data updates for Kronoterm integration, using a single base URL."""

    def __init__(self, hass: HomeAssistant, session: aiohttp.ClientSession, config_entry):
        """Initialize the Kronoterm data coordinator."""
        self.hass = hass
        self.session = session
        self.config_entry = config_entry

        # Credentials
        self.username = config_entry.options.get("username", config_entry.data.get("username", ""))
        self.password = config_entry.options.get("password", config_entry.data.get("password", ""))

        if not self.username or not self.password:
            _LOGGER.error("❌ No username/password found in config entry! Authentication will fail.")

        self.auth = aiohttp.BasicAuth(self.username, self.password)

        # Determine scan interval
        scan_interval = config_entry.options.get(
            "scan_interval", config_entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        )
        scan_interval = max(scan_interval, 1)  # at least 1 minute
        _LOGGER.info("Kronoterm main coordinator update interval set to %d minutes", scan_interval)

        # Main data update coordinator
        self.main_coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="kronoterm_main",
            update_method=lambda: self.async_update_data(QUERY_MAIN),
            update_interval=timedelta(minutes=scan_interval),
        )

        # Info data update coordinator (24-hour interval)
        self.info_coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="kronoterm_info",
            update_method=lambda: self.async_update_data(QUERY_INFO),
            update_interval=timedelta(hours=24),
        )

        # Consumption coordinator (POST with query + form-data)
        # Update every hour (arbitrary; adjust as needed)
        self.consumption_coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="kronoterm_consumption",
            update_method=self.async_update_consumption_data,
            update_interval=timedelta(minutes=5),
        )

        # Will be set after fetching device info
        self.shared_device_info = {}

    async def async_initialize(self):
        # Refresh all coordinators.
        await self.main_coordinator.async_config_entry_first_refresh()
        await self.info_coordinator.async_config_entry_first_refresh()
        await self.consumption_coordinator.async_config_entry_first_refresh()

        # Extract device info as before...
        info_data = self.info_coordinator.data or {}
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

        # --- New: Extract reservoir installation status ---
        main_data = self.main_coordinator.data or {}
        system_config = main_data.get("SystemConfiguration", {})
        # Adjust the key name if your JSON uses a different one.
        self.reservoir_installed = bool(system_config.get("reservoir_installed", 0))
        _LOGGER.info("Reservoir installed: %s", self.reservoir_installed)

        _LOGGER.info("Kronoterm integration initialized successfully.")

    # -------------------------
    #  Helpers for GET / POST
    # -------------------------
    async def async_update_data(self, query_params: dict):
        """
        Generic GET request with retries.
        Example usage: self.async_update_data({"TopPage":"5","Subpage":"3"})
        """
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

        for attempt in range(3):
            try:
                _LOGGER.debug("Attempt %d: GET %s params=%s", attempt + 1, BASE_URL, query_params)
                async with self.session.get(
                    BASE_URL,
                    auth=self.auth,
                    params=query_params,
                    timeout=timeout,
                ) as response:
                    if response.status == 401:
                        _LOGGER.error("❌ Unauthorized! Check username/password in HA options.")
                        return None
                    if response.status != 200:
                        body = await response.text()
                        _LOGGER.error(
                            "HTTP error %s on GET. Params=%s\nResponse:\n%s",
                            response.status, query_params, body
                        )
                        raise UpdateFailed(f"HTTP {response.status} for {query_params}")

                    return await response.json()

            except (ClientResponseError, ClientError) as e:
                _LOGGER.warning("Attempt %d failed on GET: %s", attempt + 1, e)
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)  # e.g. 1s, then 2s
                else:
                    _LOGGER.error("Max GET retries reached for query=%s", query_params)
                    raise UpdateFailed(f"Error GET {query_params}: {e}")

    async def async_post_data(self, query_params: dict, form_data: list):
        """
        Generic POST request with retries.
        Takes query_params (dict) for the URL (e.g. ?TopPage=4&Subpage=4&Action=4)
        and form_data (list of tuples) for repeated fields like dValues[] or aValues[].
        Returns parsed JSON or None if 401; raises UpdateFailed on error.
        """
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

        for attempt in range(3):
            try:
                _LOGGER.debug(
                    "Attempt %d: POST %s params=%s, data=%s",
                    attempt + 1, BASE_URL, query_params, form_data
                )

                async with self.session.post(
                    BASE_URL,
                    auth=self.auth,
                    params=query_params,   # e.g. ?TopPage=4&Subpage=4&Action=4
                    data=form_data,        # repeated keys => multiple dValues[]
                    timeout=timeout,
                ) as response:

                    if response.status == 401:
                        _LOGGER.error("❌ Unauthorized! Check username/password in HA options.")
                        return None

                    text = await response.text()
                    if response.status != 200:
                        _LOGGER.error(
                            "HTTP error %s on POST. params=%s\nResponse:\n%s",
                            response.status, query_params, text
                        )
                        raise UpdateFailed(f"HTTP {response.status} for {query_params}")

                    return await response.json()

            except (ClientResponseError, ClientError) as e:
                _LOGGER.warning("Attempt %d failed on POST: %s", attempt + 1, e)
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    _LOGGER.error("Max POST retries reached for query=%s", query_params)
                    raise UpdateFailed(f"Error POST {query_params}: {e}")

    # -----------------------------------
    #  Example for consumption data (POST)
    # -----------------------------------
    async def async_update_consumption_data(self):
        """
        Build dynamic day-of-year + year, then send a POST to Kronoterm
        with repeated form data (like dValues[] or aValues[]).
        """
        # 1) Query string params
        query_params = {
            "TopPage": "4",
            "Subpage": "4",
            "Action": "4",
        }

        # 2) Prepare dynamic year/d1:
        now = datetime.now()
        year = now.year
        d1 = now.timetuple().tm_yday  # day of the year

        # Optional: check config entries for overrides
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

        # 3) Build form data. This matches your screenshot's structure:
        #    year=2025, d1=44, etc. plus repeated dValues[] or aValues[]
        #    For demonstration, we hardcode a few. Make them dynamic if needed.
        form_data = [
            ("year", str(year)),
            ("d1", str(d1)),
            ("d2", "0"),   # fixed in your screenshot
            ("type", "day"),
            # aValues[] repeated once:
            ("aValues[]", "17"),
            # multiple dValues[]:
            ("dValues[]", "90"),
            ("dValues[]", "0"),
            ("dValues[]", "91"),
            ("dValues[]", "92"),
            ("dValues[]", "1"),
            ("dValues[]", "2"),
            ("dValues[]", "24"),
            ("dValues[]", "71"),
        ]

        # If you wanted to store them in config options:
        # for val in self.config_entry.options.get("dValues_list", []):
        #     form_data.append(("dValues[]", str(val)))

        _LOGGER.debug("Posting consumption data: year=%s, d1=%s", year, d1)
        return await self.async_post_data(query_params, form_data)

    # ---------------------------------------
    #  Example for set_temperature (POST)
    # ---------------------------------------
    async def async_set_temperature(self, page: int, new_temp: float):
        """POST request to change the temperature for DHW (page=9), Loop 1 (page=5), Loop 2 (page=6), or Reservoir (page=4)."""
        if page == 9:
            query = QUERY_DHW
        elif page == 5:
            query = QUERY_LOOP1
        elif page == 6:
            query = QUERY_LOOP2
        elif page == 4:
            query = QUERY_RESERVOIR
        else:
            _LOGGER.error("❌ Invalid page number %s for set_temperature", page)
            return False

        payload = {
            "param_name": "circle_temp",
            "param_value": str(round(new_temp, 1)),
            "page": str(page),
        }

        _LOGGER.info("🔄 Setting temperature (page=%s) to %.1f°C", page, new_temp)
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        try:
            async with self.session.post(
                BASE_URL,
                auth=self.auth,
                params=query,
                data=payload,
                timeout=timeout,
            ) as response:
                text = await response.text()
                if response.status == 200:
                    _LOGGER.info("✅ Temperature update success. Response: %s", text)
                    await self.main_coordinator.async_request_refresh()
                    return True
                else:
                    _LOGGER.error("❌ Temperature update failed (HTTP %s). Body: %s", response.status, text)
                    return False
        except aiohttp.ClientError as err:
            _LOGGER.error("❌ API request error while setting temperature: %s", err)
            return False


    # ---------------------------------------
    #  Example for set_heatpump_state (POST)
    # ---------------------------------------
    async def async_set_heatpump_state(self, turn_on: bool):
        """Turn the heat pump ON/OFF with a single base URL + query=QUERY_SWITCH."""
        payload = {
            "param_name": "heatpump_on",
            "param_value": "1" if turn_on else "0",
            "page": "-1",
        }

        _LOGGER.info("🔄 Setting heat pump state to %s", "ON" if turn_on else "OFF")

        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        try:
            async with self.session.post(
                BASE_URL,
                auth=self.auth,
                params=QUERY_SWITCH,
                data=payload,
                timeout=timeout,
            ) as response:
                text = await response.text()
                if response.status == 200:
                    _LOGGER.info("✅ Heat pump state changed successfully. Body: %s", text)
                    await self.main_coordinator.async_request_refresh()
                    return True
                else:
                    _LOGGER.error("Failed to change heat pump state (HTTP %s). Body: %s", response.status, text)
        except aiohttp.ClientError as err:
            _LOGGER.error("Error updating heat pump state: %s", err)

        return False

    # ---------------------------------------
    #  Example for set_dhw_circulation (POST)
    # ---------------------------------------
    async def async_set_dhw_circulation(self, turn_on: bool):
        """Turn the DHW circulation ON/OFF with a single base URL + query=QUERY_SWITCH."""
        payload = {
            "param_name": "circulation_on",
            "param_value": "1" if turn_on else "0",
            "page": "-1",
        }

        _LOGGER.info("🔄 Setting DHW circulation to %s", "ON" if turn_on else "OFF")

        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        try:
            async with self.session.post(
                BASE_URL,
                auth=self.auth,
                params=QUERY_SWITCH,
                data=payload,
                timeout=timeout,
            ) as response:
                text = await response.text()
                if response.status == 200:
                    _LOGGER.info("✅ DHW circulation state changed successfully. Body: %s", text)
                    await self.main_coordinator.async_request_refresh()
                    return True
                else:
                    _LOGGER.error("Failed to change DHW circulation state (HTTP %s). Body: %s", response.status, text)
        except aiohttp.ClientError as err:
            _LOGGER.error("Error updating DHW circulation state: %s", err)

        return False
