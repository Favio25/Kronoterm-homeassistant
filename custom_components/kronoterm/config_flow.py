import voluptuous as vol
import logging
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = 5
SENSITIVE_KEYS = ["username", "password"]

def sanitize_user_input(user_input: dict) -> dict:
    """
    Sanitizes user input by redacting sensitive information for logging purposes.

    Args:
        user_input (dict): The original user input dictionary.
    
    Returns:
        dict: A new dictionary with sensitive keys redacted.
    """
    return {
        key: ("[REDACTED]" if key in SENSITIVE_KEYS else value)
        for key, value in user_input.items()
    }

class KronotermConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Handles the configuration flow for the Kronoterm integration.

    Manages the user interactions required to set up and configure
    the Kronoterm Heat Pump within Home Assistant.
    """
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Handle a flow initialized by the user."""
        _LOGGER.debug("Starting user step in KronotermConfigFlow")
        if user_input is not None:
            # Log sanitized input for debugging without exposing sensitive data.
            sanitized_input = sanitize_user_input(user_input)
            _LOGGER.debug("User input received: %s", sanitized_input)
            return self.async_create_entry(title="Kronoterm Heat Pump", data=user_input)

        # Define the configuration schema.
        user_schema = vol.Schema(
            {
                vol.Required("username"): str,
                vol.Required("password"): str,
                vol.Optional("scan_interval", default=DEFAULT_SCAN_INTERVAL): int,
            }
        )
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

    Allows users to modify configuration options after the initial setup
    of the Kronoterm Heat Pump integration.
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

        # Define the options schema.
        options_schema = vol.Schema(
            {
                vol.Optional(
                    "scan_interval",
                    default=self.config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL),
                ): vol.All(int, vol.Range(min=1, max=60)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=options_schema)
