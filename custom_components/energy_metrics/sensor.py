"""Energy sensor platform for Energy Metrics Importer."""
from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EnergyMetricsCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Energy Metrics sensors from a config entry."""
    _LOGGER.info("Setting up Energy Metrics sensors for entry %s", config_entry.entry_id)
    
    try:
        coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
        
        entities = [
            EnergyMeterSensor(coordinator, config_entry),
            EnergyAverageSensor(coordinator, config_entry),
            TemperatureSensor(coordinator, config_entry),
        ]
        
        _LOGGER.debug("Created %d sensor entities for entry %s", len(entities), config_entry.entry_id)
        async_add_entities(entities)
        _LOGGER.info("Successfully set up %d Energy Metrics sensors for entry %s", len(entities), config_entry.entry_id)
        
    except KeyError as err:
        _LOGGER.error("Failed to find coordinator for entry %s: %s", config_entry.entry_id, err)
        raise
    except Exception as err:
        _LOGGER.error("Error setting up Energy Metrics sensors for entry %s: %s", config_entry.entry_id, err)
        raise


class EnergyMetricsBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Energy Metrics sensors."""

    def __init__(
        self,
        coordinator: EnergyMetricsCoordinator,
        config_entry: ConfigEntry,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}"
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": "Energy Metrics Importer",
            "manufacturer": "Custom Integration",
            "model": "Energy Metrics",
            "sw_version": "1.0.0",
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class EnergyMeterSensor(EnergyMetricsBaseSensor):
    """Energy meter cumulative sensor for Home Assistant Energy feature."""

    def __init__(
        self,
        coordinator: EnergyMetricsCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the energy meter sensor."""
        super().__init__(coordinator, config_entry, "energy_meter")
        self._attr_name = "Energy Meter"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_suggested_display_precision = 3
        self._attr_icon = "mdi:flash"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        try:
            if not self.coordinator.data:
                _LOGGER.debug("No coordinator data available for energy meter sensor")
                return None
            
            # Get the latest metric data
            metrics = self.coordinator.data.get("metrics", {})
            if not metrics:
                _LOGGER.debug("No metrics data available for energy meter sensor")
                return None
            
            # Get the most recent entry
            try:
                latest_timestamp = max(metrics.keys())
            except ValueError:
                _LOGGER.warning("No valid timestamps found in metrics for energy meter sensor")
                return None
            
            latest_metric = metrics[latest_timestamp]
            meter_value = latest_metric.get("meter_value")
            
            if meter_value is not None:
                try:
                    return float(meter_value)
                except (ValueError, TypeError) as err:
                    _LOGGER.error("Invalid meter_value type for energy meter sensor: %s (value: %s)", err, meter_value)
                    return None
            else:
                _LOGGER.debug("No meter_value available in latest metric for energy meter sensor")
                return None
                
        except Exception as err:
            _LOGGER.error("Error getting native_value for energy meter sensor: %s", err)
            return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any] | None:
        """Return extra state attributes."""
        try:
            if not self.coordinator.data:
                return {"error": "No coordinator data", "status": "disconnected"}
            
            metrics = self.coordinator.data.get("metrics", {})
            if not metrics:
                return {"error": "No metrics data", "status": "no_data", "total_readings": 0}
            
            try:
                latest_timestamp = max(metrics.keys())
                latest_metric = metrics[latest_timestamp]
                
                attributes = {
                    "last_updated": latest_metric.get("timestamp"),
                    "total_readings": len(metrics),
                    "data_source": "energy_vendor_export",
                    "status": "connected",
                }
                
                # Add reading age if timestamp is available
                if latest_metric.get("timestamp"):
                    try:
                        last_reading_time = dt_util.parse_datetime(latest_metric.get("timestamp"))
                        if last_reading_time:
                            age_seconds = (dt_util.utcnow() - last_reading_time).total_seconds()
                            attributes["last_reading_age_seconds"] = age_seconds
                    except Exception as parse_err:
                        _LOGGER.debug("Could not parse timestamp for age calculation: %s", parse_err)
                
                return attributes
                
            except ValueError:
                return {"error": "No valid timestamps", "status": "data_error", "total_readings": len(metrics)}
                
        except Exception as err:
            _LOGGER.error("Error getting extra_state_attributes for energy meter sensor: %s", err)
            return {"error": str(err), "status": "error"}


class EnergyAverageSensor(EnergyMetricsBaseSensor):
    """Average energy consumption sensor."""

    def __init__(
        self,
        coordinator: EnergyMetricsCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the average energy sensor."""
        super().__init__(coordinator, config_entry, "energy_average")
        self._attr_name = "Energy Average"
        self._attr_device_class = None  # Generic sensor for average consumption
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_suggested_display_precision = 3
        self._attr_icon = "mdi:flash-outline"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        try:
            if not self.coordinator.data:
                return None
            
            metrics = self.coordinator.data.get("metrics", {})
            if not metrics:
                return None
            
            try:
                latest_timestamp = max(metrics.keys())
            except ValueError:
                return None
            
            latest_metric = metrics[latest_timestamp]
            average_value = latest_metric.get("average_value")
            
            if average_value is not None:
                try:
                    return float(average_value)
                except (ValueError, TypeError) as err:
                    _LOGGER.error("Invalid average_value type for energy average sensor: %s (value: %s)", err, average_value)
                    return None
            
            return None
            
        except Exception as err:
            _LOGGER.error("Error getting native_value for energy average sensor: %s", err)
            return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any] | None:
        """Return extra state attributes."""
        try:
            if not self.coordinator.data:
                return {"error": "No coordinator data", "status": "disconnected"}
            
            metrics = self.coordinator.data.get("metrics", {})
            if not metrics:
                return {"error": "No metrics data", "status": "no_data"}
            
            try:
                latest_timestamp = max(metrics.keys())
                latest_metric = metrics[latest_timestamp]
                
                return {
                    "last_updated": latest_metric.get("timestamp"),
                    "measurement_type": "average_consumption",
                    "status": "connected",
                }
            except ValueError:
                return {"error": "No valid timestamps", "status": "data_error"}
                
        except Exception as err:
            _LOGGER.error("Error getting extra_state_attributes for energy average sensor: %s", err)
            return {"error": str(err), "status": "error"}


class TemperatureSensor(EnergyMetricsBaseSensor):
    """Temperature sensor for environmental data."""

    def __init__(
        self,
        coordinator: EnergyMetricsCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(coordinator, config_entry, "temperature")
        self._attr_name = "Temperature"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
        self._attr_suggested_display_precision = 1
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        try:
            if not self.coordinator.data:
                return None
            
            metrics = self.coordinator.data.get("metrics", {})
            if not metrics:
                return None
            
            try:
                latest_timestamp = max(metrics.keys())
            except ValueError:
                return None
            
            latest_metric = metrics[latest_timestamp]
            temperature = latest_metric.get("temperature")
            
            if temperature is not None:
                try:
                    return float(temperature)
                except (ValueError, TypeError) as err:
                    _LOGGER.error("Invalid temperature type for temperature sensor: %s (value: %s)", err, temperature)
                    return None
            
            return None
            
        except Exception as err:
            _LOGGER.error("Error getting native_value for temperature sensor: %s", err)
            return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any] | None:
        """Return extra state attributes."""
        try:
            if not self.coordinator.data:
                return {"error": "No coordinator data", "status": "disconnected"}
            
            metrics = self.coordinator.data.get("metrics", {})
            if not metrics:
                return {"error": "No metrics data", "status": "no_data"}
            
            try:
                latest_timestamp = max(metrics.keys())
                latest_metric = metrics[latest_timestamp]
                
                return {
                    "last_updated": latest_metric.get("timestamp"),
                    "sensor_type": "environmental",
                    "status": "connected",
                    "unit": "°F",
                }
            except ValueError:
                return {"error": "No valid timestamps", "status": "data_error"}
                
        except Exception as err:
            _LOGGER.error("Error getting extra_state_attributes for temperature sensor: %s", err)
            return {"error": str(err), "status": "error"}