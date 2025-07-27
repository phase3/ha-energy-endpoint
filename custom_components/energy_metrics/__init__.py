"""Energy Metrics Importer integration for Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION
from .coordinator import EnergyMetricsCoordinator
from .api import EnergyMetricsAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Energy Metrics Importer from a config entry."""
    _LOGGER.info("Setting up Energy Metrics Importer integration for entry %s", entry.entry_id)
    
    try:
        hass.data.setdefault(DOMAIN, {})
        
        # Create storage for historical data
        _LOGGER.debug("Creating storage for entry %s", entry.entry_id)
        store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")
        
        # Create coordinator for managing data
        _LOGGER.debug("Initializing coordinator for entry %s", entry.entry_id)
        coordinator = EnergyMetricsCoordinator(hass, store)
        
        # Initialize coordinator data
        await coordinator.async_config_entry_first_refresh()
        
        # Create API endpoint handler
        _LOGGER.debug("Setting up API handler for entry %s", entry.entry_id)
        api = EnergyMetricsAPI(hass, coordinator)
        
        # Store coordinator and API in hass data
        hass.data[DOMAIN][entry.entry_id] = {
            "coordinator": coordinator,
            "api": api,
            "store": store,
        }
        
        # Register API endpoints
        try:
            await api.async_setup()
            _LOGGER.info("API endpoints successfully registered for entry %s", entry.entry_id)
        except Exception as err:
            _LOGGER.error("Failed to register API endpoints for entry %s: %s", entry.entry_id, err)
            raise
        
        # Forward setup to sensor platform
        try:
            await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
            _LOGGER.info("Sensor platform setup completed for entry %s", entry.entry_id)
        except Exception as err:
            _LOGGER.error("Failed to set up sensor platform for entry %s: %s", entry.entry_id, err)
            # Clean up API if sensor setup fails
            await api.async_cleanup()
            raise
        
        _LOGGER.info("Energy Metrics Importer integration successfully set up for entry %s", entry.entry_id)
        return True
        
    except Exception as err:
        _LOGGER.error("Failed to set up Energy Metrics Importer for entry %s: %s", entry.entry_id, err)
        # Clean up any partial setup
        if entry.entry_id in hass.data.get(DOMAIN, {}):
            hass.data[DOMAIN].pop(entry.entry_id)
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Energy Metrics Importer integration for entry %s", entry.entry_id)
    
    try:
        # Unload platforms first
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        
        if unload_ok:
            # Clean up API endpoints and data
            if entry.entry_id in hass.data.get(DOMAIN, {}):
                try:
                    api = hass.data[DOMAIN][entry.entry_id]["api"]
                    await api.async_cleanup()
                    _LOGGER.debug("API cleanup completed for entry %s", entry.entry_id)
                except Exception as err:
                    _LOGGER.error("Error during API cleanup for entry %s: %s", entry.entry_id, err)
                    # Continue with cleanup even if API cleanup fails
                
                # Remove from hass data
                hass.data[DOMAIN].pop(entry.entry_id)
                _LOGGER.debug("Data cleanup completed for entry %s", entry.entry_id)
            
            _LOGGER.info("Energy Metrics Importer integration successfully unloaded for entry %s", entry.entry_id)
        else:
            _LOGGER.error("Failed to unload platforms for entry %s", entry.entry_id)
        
        return unload_ok
        
    except Exception as err:
        _LOGGER.error("Error unloading Energy Metrics Importer for entry %s: %s", entry.entry_id, err)
        return False