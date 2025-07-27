"""Config flow for Energy Metrics Importer integration."""
from __future__ import annotations

import logging
from typing import Any, Dict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("name", default="Energy Metrics"): str,
        vol.Optional("description", default="Energy metrics from vendor export"): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Energy Metrics Importer."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            _LOGGER.info("Processing config flow input: %s", {k: v for k, v in user_input.items() if k != "password"})
            
            try:
                info = await validate_input(self.hass, user_input)
                _LOGGER.info("Config validation successful for: %s", info["title"])
            except CannotConnect as err:
                _LOGGER.error("Cannot connect during config flow: %s", err)
                errors["base"] = "cannot_connect"
            except InvalidAuth as err:
                _LOGGER.error("Invalid auth during config flow: %s", err)
                errors["base"] = "invalid_auth"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during config flow: %s", err)
                errors["base"] = "unknown"
            else:
                _LOGGER.info("Creating config entry for Energy Metrics: %s", info["title"])
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_info: Dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_info)


async def validate_input(hass: HomeAssistant, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the user input allows us to connect.
    
    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    _LOGGER.debug("Validating config input: %s", data)
    
    try:
        # Validate that the name is not empty
        name = data.get("name", "").strip()
        if not name:
            _LOGGER.error("Config validation failed: name is empty")
            raise InvalidAuth("Name cannot be empty")
        
        # Validate name length
        if len(name) > 100:
            _LOGGER.error("Config validation failed: name too long (%d characters)", len(name))
            raise InvalidAuth("Name cannot be longer than 100 characters")
        
        # Validate description if provided
        description = data.get("description", "").strip()
        if description and len(description) > 500:
            _LOGGER.error("Config validation failed: description too long (%d characters)", len(description))
            raise InvalidAuth("Description cannot be longer than 500 characters")

        # For this integration, we don't need to connect to external services
        # The validation is mainly for ensuring required fields are present
        
        _LOGGER.debug("Config validation successful for name: %s", name)
        return {"title": name}
        
    except (InvalidAuth, CannotConnect):
        # Re-raise known validation errors
        raise
    except Exception as err:
        _LOGGER.error("Unexpected error during config validation: %s", err)
        raise InvalidAuth(f"Validation failed: {str(err)}")


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""