"""Energy Metrics Importer integration for Home Assistant."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION
from .coordinator import EnergyMetricsCoordinator
from .api import EnergyMetricsAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Energy Metrics Importer from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Create storage for historical data
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")
    
    # Create coordinator for managing data
    coordinator = EnergyMetricsCoordinator(hass, store)
    
    # Create API endpoint handler
    api = EnergyMetricsAPI(hass, coordinator)
    
    # Store coordinator and API in hass data
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
        "store": store,
    }
    
    # Register API endpoints
    await api.async_setup()
    
    # Forward setup to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Clean up API endpoints
        if entry.entry_id in hass.data[DOMAIN]:
            api = hass.data[DOMAIN][entry.entry_id]["api"]
            await api.async_cleanup()
        
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok