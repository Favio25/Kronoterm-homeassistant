import logging
import asyncio
from datetime import timedelta
import aiohttp
from aiohttp.client_exceptions import ClientError, ClientResponseError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, API_URL_MAIN, API_URL_DHW, API_URL_INFO, API_URL_LOOP1, API_URL_LOOP2, API_URL_SWITCH

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = 5  # Default to 5 minutes if not set by user

class KronotermCoordinator:
    """Handles API communication and data updates for Kronoterm integration."""

    def __init__(self, hass, session, config_entry):
        """Initialize the Kronoterm data coordinator."""
        self.hass = hass
        self.session = session
        self.config_entry = config_entry

        self.username = config_entry.options.get("username", config_entry.data.get("username", ""))
        self.password = config_entry.options.get("password", config_entry.data.get("password", ""))

        if not self.username or not self.password:
            _LOGGER.error("❌ No username/password found in config entry! Authentication will fail.")

        self.auth = aiohttp.BasicAuth(self.username, self.password)

        # Fetch scan interval from options; default to 5 minutes if not set
        scan_interval = config_entry.options.get("scan_interval", config_entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL))
        scan_interval = max(scan_interval, 1)  # Ensure it's at least 1 minute

        _LOGGER.info("Kronoterm main coordinator update interval set to %d minutes", scan_interval)

        # Main data update coordinator
        self.main_coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="kronoterm_main",
            update_method=lambda: self.async_update_data(API_URL_MAIN),
            update_interval=timedelta(minutes=scan_interval),
        )

        # Info data update coordinator (fixed to 24 hours)
        self.info_coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="kronoterm_info",
            update_method=lambda: self.async_update_data(API_URL_INFO),
            update_interval=timedelta(hours=24),
        )

        self.shared_device_info = {}

    async def async_update_data(self, url):
        """Fetch data from the Kronoterm API with retry logic."""
        for attempt in range(3):
            try:
                _LOGGER.info("Attempt %d: Making API request to %s", attempt + 1, url)
                async with self.session.get(url, auth=self.auth) as response:
                    if response.status == 401:
                        _LOGGER.error("❌ Unauthorized! Check username and password in Home Assistant options.")
                        return None  # Stop retries if credentials are wrong
                    if response.status != 200:
                        raise UpdateFailed(f"HTTP error: {response.status}")
                    return await response.json()
            except (ClientResponseError, ClientError) as e:
                _LOGGER.warning("Attempt %d failed: %s", attempt + 1, e)
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    _LOGGER.error("Max retries reached for %s", url)
                    raise UpdateFailed(f"Error while communicating with {url}: {e}")

    async def async_set_temperature(self, page, new_temp):
        """Send a POST request to change the temperature for DHW, Loop 1, or Loop 2."""
        
        # ✅ Select the correct API URL
        if page == 9:
            api_url = API_URL_DHW
        elif page == 5:
            api_url = API_URL_LOOP1
        elif page == 6:
            api_url = API_URL_LOOP2
        else:
            _LOGGER.error(f"❌ Invalid page number {page} for temperature update.")
            return False

        payload = {
            "param_name": "circle_temp",
            "param_value": str(round(new_temp, 1)),  # ✅ Ensure correct formatting
            "page": str(page)
        }

        _LOGGER.info(f"🔄 Sending API request to {api_url} (Page: {page}, Value: {new_temp}°C)")

        try:
            async with self.session.post(api_url, auth=self.auth, data=payload) as response:
                response_text = await response.text()
                if response.status == 200:
                    _LOGGER.info(f"✅ API confirmed temperature update. Response: {response_text}")
                    await self.main_coordinator.async_request_refresh()
                    return True
                else:
                    _LOGGER.error(f"❌ API failed. HTTP {response.status}. Response: {response_text}")
                    return False
        except aiohttp.ClientError as err:
            _LOGGER.error(f"❌ API request error: {err}")
            return False



    async def async_set_heatpump_state(self, turn_on: bool):
        """Set heat pump ON/OFF using the correct API URL."""
        payload = {
            "param_name": "heatpump_on",
            "param_value": "1" if turn_on else "0",
            "page": "-1"
        }

        try:
            async with self.session.post(API_URL_SWITCH, auth=self.auth, data=payload) as response:
                if response.status == 200:
                    _LOGGER.info("Heat pump state changed successfully to %s", "ON" if turn_on else "OFF")
                    return True
                _LOGGER.error("Failed to change heat pump state, HTTP %s", response.status)
        except aiohttp.ClientError as err:
            _LOGGER.error("Error updating heat pump state: %s", err)
        return False

    async def async_initialize(self):
        """Fetch initial data on startup and set up device info."""
        await self.main_coordinator.async_config_entry_first_refresh()
        await self.info_coordinator.async_config_entry_first_refresh()

        info_data = self.info_coordinator.data or {}
        info_data_section = info_data.get("InfoData", {})  # ✅ Correctly accessing "InfoData"

        _LOGGER.debug("Full Device Info Response: %s", info_data)
        
        self.shared_device_info = {
            "identifiers": {(DOMAIN, info_data_section.get("device_id", "kronoterm_heat_pump"))},
            "name": "Kronoterm Heat Pump",
            "manufacturer": "Kronoterm",
            "model": info_data_section.get("pumpModel", "Unknown Model"),  # ✅ Fixed
            "sw_version": info_data_section.get("firmware", "Unknown Firmware"),  # ✅ Fixed
        }
        _LOGGER.info("Final Parsed Device Info: %s", self.shared_device_info)
        _LOGGER.info("Kronoterm integration initialized successfully.")
