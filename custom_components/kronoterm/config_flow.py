import voluptuous as vol
import logging
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSITIVE_KEYS = ["username", "password"]

def sanitize_user_input(user_input: dict) -> dict:
    """
    Sanitizes user input by redacting sensitive information for logging purposes.
    """
    return {
        key: ("[REDACTED]" if key in SENSITIVE_KEYS else value)
        for key, value in user_input.items()
    }

class KronotermConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Handles the configuration flow for the Kronoterm integration.
    """
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Handle a flow initialized by the user."""
        _LOGGER.debug("Starting user step in KronotermConfigFlow")
        if user_input is not None:
            sanitized_input = sanitize_user_input(user_input)
            _LOGGER.debug("User input received: %s", sanitized_input)
            return self.async_create_entry(title="Kronoterm Heat Pump", data=user_input)

        user_schema = vol.Schema({
            vol.Required("username"): str,
            vol.Required("password"): str,
        })
        return self.async_show_form(step_id="user", data_schema=user_schema)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry
    ) -> "KronotermOptionsFlowHandler":
        """Get the options flow for this integration."""
        return KronotermOptionsFlowHandler(config_entry)

class KronotermOptionsFlowHandler(config_entries.OptionsFlow):
    """
    Handles the options flow for the Kronoterm integration.
    """
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow handler."""
        self.config_entry = config_entry
        _LOGGER.info("KronotermOptionsFlowHandler initialized with entry: %s", config_entry.entry_id)

    async def async_step_init(self, user_input: dict | None = None):
        """Handle the initial step of the options flow."""
        _LOGGER.debug("Starting options flow init step")
        if user_input is not None:
            _LOGGER.debug("User input received in options flow: %s", sanitize_user_input(user_input))
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema({})
        return self.async_show_form(step_id="init", data_schema=options_schema)
