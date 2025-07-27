"""Data coordinator for Energy Metrics Importer."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.components.recorder.statistics import async_add_external_statistics

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class EnergyMetricsCoordinator(DataUpdateCoordinator):
    """Class to manage fetching and storing energy metrics data."""

    def __init__(self, hass: HomeAssistant, store: Store) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.store = store
        self._data: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data from storage."""
        try:
            async with self._lock:
                _LOGGER.debug("Loading data from storage")
                stored_data = await self.store.async_load()
                if stored_data:
                    self._data = stored_data
                    metrics_count = len(stored_data.get("metrics", {}))
                    _LOGGER.debug("Loaded %d metrics from storage", metrics_count)
                else:
                    _LOGGER.debug("No stored data found, initializing empty dataset")
                    self._data = {}
                return self._data
        except Exception as err:
            _LOGGER.error("Failed to load data from storage: %s", err)
            self.last_update_success = False
            raise

    async def async_add_metrics(self, metrics_data: List[Dict[str, Any]]) -> bool:
        """Add or update energy metrics data."""
        if not metrics_data:
            _LOGGER.warning("No metrics data provided")
            return False
            
        _LOGGER.info("Processing %d metrics for storage", len(metrics_data))
        
        async with self._lock:
            try:
                # Load existing data
                stored_data = await self.store.async_load() or {}
                metrics = stored_data.get("metrics", {})
                initial_count = len(metrics)
                
                updated = False
                processed_count = 0
                error_count = 0
                
                for i, metric in enumerate(metrics_data):
                    try:
                        timestamp = metric.get("timestamp")
                        if not timestamp:
                            _LOGGER.warning("Metric at index %d missing timestamp: %s", i, metric)
                            error_count += 1
                            continue
                        
                        # Parse timestamp if it's a string
                        if isinstance(timestamp, str):
                            try:
                                timestamp = dt_util.parse_datetime(timestamp)
                                if not timestamp:
                                    _LOGGER.error("Failed to parse timestamp at index %d: %s", i, metric.get("timestamp"))
                                    error_count += 1
                                    continue
                            except Exception as parse_err:
                                _LOGGER.error("Invalid timestamp format at index %d (%s): %s", i, metric.get("timestamp"), parse_err)
                                error_count += 1
                                continue
                        
                        # Convert to ISO string for consistent storage
                        timestamp_key = timestamp.isoformat()
                        
                        # Validate data fields
                        meter_value = metric.get("meter_value")
                        average_value = metric.get("average_value")
                        temperature = metric.get("temperature")
                        
                        # Log if all data fields are None
                        if all(v is None for v in [meter_value, average_value, temperature]):
                            _LOGGER.warning("Metric at index %d has no data values (meter_value, average_value, temperature all None)", i)
                        
                        # Store or update the metric (check if different for efficiency)
                        new_metric_data = {
                            "timestamp": timestamp_key,
                            "meter_value": meter_value,
                            "average_value": average_value,
                            "temperature": temperature,
                            "created_at": dt_util.utcnow().isoformat(),
                        }
                        
                        # Check if this is a new entry or an update
                        is_new = timestamp_key not in metrics
                        is_different = not is_new and metrics[timestamp_key] != new_metric_data
                        
                        if is_new or is_different:
                            metrics[timestamp_key] = new_metric_data
                            updated = True
                            if is_new:
                                _LOGGER.debug("Added new metric for timestamp %s", timestamp_key)
                            else:
                                _LOGGER.debug("Updated existing metric for timestamp %s", timestamp_key)
                        
                        processed_count += 1
                        
                    except Exception as metric_err:
                        _LOGGER.error("Error processing metric at index %d: %s. Metric data: %s", i, metric_err, metric)
                        error_count += 1
                        continue
                
                if updated:
                    try:
                        # Save updated data
                        stored_data["metrics"] = metrics
                        stored_data["last_updated"] = dt_util.utcnow().isoformat()
                        await self.store.async_save(stored_data)
                        
                        final_count = len(metrics)
                        _LOGGER.info("Storage updated successfully. Metrics count: %d -> %d. Processed: %d, Errors: %d", 
                                   initial_count, final_count, processed_count, error_count)
                        
                        # Update coordinator data
                        self._data = stored_data
                        
                        # Import new/updated metrics to Home Assistant statistics system
                        await self._import_metrics_to_statistics(metrics_data)
                        
                        # Notify listeners
                        self.async_set_updated_data(self._data)
                        
                    except Exception as save_err:
                        _LOGGER.error("Failed to save metrics to storage: %s", save_err)
                        return False
                else:
                    _LOGGER.info("No metrics needed updating. Processed: %d, Errors: %d", processed_count, error_count)
                
                # Return True if we processed at least some metrics successfully
                return processed_count > 0
                
            except Exception as err:
                _LOGGER.error("Critical error in async_add_metrics: %s", err, exc_info=True)
                return False

    async def async_get_latest_metrics(self) -> Optional[Dict[str, Any]]:
        """Get the latest metric entry."""
        try:
            async with self._lock:
                stored_data = await self.store.async_load() or {}
                metrics = stored_data.get("metrics", {})
                
                if not metrics:
                    _LOGGER.debug("No metrics found in storage")
                    return None
                
                try:
                    # Get the most recent entry
                    latest_timestamp = max(metrics.keys())
                    latest_metric = metrics[latest_timestamp]
                    _LOGGER.debug("Retrieved latest metric for timestamp %s", latest_timestamp)
                    return latest_metric
                except ValueError as err:
                    _LOGGER.error("Error finding latest metric (empty metrics?): %s", err)
                    return None
                    
        except Exception as err:
            _LOGGER.error("Error retrieving latest metrics: %s", err)
            return None

    async def async_get_metrics_range(
        self, start_time: datetime, end_time: datetime
    ) -> List[Dict[str, Any]]:
        """Get metrics within a time range."""
        if start_time > end_time:
            _LOGGER.error("Invalid time range: start_time (%s) is after end_time (%s)", start_time, end_time)
            return []
            
        _LOGGER.debug("Retrieving metrics from %s to %s", start_time, end_time)
        
        try:
            async with self._lock:
                stored_data = await self.store.async_load() or {}
                metrics = stored_data.get("metrics", {})
                
                if not metrics:
                    _LOGGER.debug("No metrics found in storage for range query")
                    return []
                
                filtered_metrics = []
                parse_errors = 0
                
                for timestamp_str, metric in metrics.items():
                    try:
                        metric_time = dt_util.parse_datetime(timestamp_str)
                        if metric_time and start_time <= metric_time <= end_time:
                            filtered_metrics.append(metric)
                    except Exception as err:
                        _LOGGER.error("Error parsing timestamp %s: %s", timestamp_str, err)
                        parse_errors += 1
                        continue
                
                if parse_errors > 0:
                    _LOGGER.warning("Encountered %d timestamp parsing errors during range query", parse_errors)
                
                # Sort by timestamp
                try:
                    filtered_metrics.sort(key=lambda x: x["timestamp"])
                except KeyError as err:
                    _LOGGER.error("Error sorting metrics by timestamp: %s", err)
                
                _LOGGER.debug("Retrieved %d metrics in range %s to %s", len(filtered_metrics), start_time, end_time)
                return filtered_metrics
                
        except Exception as err:
            _LOGGER.error("Error retrieving metrics range: %s", err, exc_info=True)
            return []

    async def _import_metrics_to_statistics(self, metrics_data: List[Dict[str, Any]]) -> None:
        """Import metrics data to Home Assistant statistics system."""
        try:
            # Prepare statistics for energy meter (cumulative)
            energy_statistics = []
            temperature_statistics = []
            
            # Sort metrics by timestamp to ensure proper order
            def parse_timestamp_for_sorting(metric):
                timestamp = metric.get("timestamp")
                if isinstance(timestamp, str):
                    return dt_util.parse_datetime(timestamp)
                elif isinstance(timestamp, datetime):
                    return timestamp
                else:
                    return datetime.min  # Put invalid timestamps at the beginning
            
            sorted_metrics = sorted(metrics_data, key=parse_timestamp_for_sorting)
            
            for metric in sorted_metrics:
                timestamp = metric.get("timestamp")
                if isinstance(timestamp, str):
                    timestamp = dt_util.parse_datetime(timestamp)
                
                if not timestamp:
                    continue
                
                # Round timestamp to the hour (Home Assistant statistics requirement)
                timestamp = timestamp.replace(minute=0, second=0, microsecond=0)
                
                # Energy meter statistics (cumulative)
                meter_value = metric.get("meter_value")
                if meter_value is not None:
                    energy_stat = {
                        "start": timestamp,
                        "sum": float(meter_value),  # Cumulative energy reading
                        "state": float(meter_value),  # Current state
                    }
                    energy_statistics.append(energy_stat)
                
                # Temperature statistics
                temperature = metric.get("temperature")
                if temperature is not None:
                    temp_stat = {
                        "start": timestamp,
                        "mean": float(temperature),  # Average temperature
                        "min": float(temperature),   # Could be actual min if available
                        "max": float(temperature),   # Could be actual max if available
                    }
                    temperature_statistics.append(temp_stat)
            
            # Import energy statistics
            if energy_statistics:
                energy_metadata = {
                    "source": DOMAIN,
                    "statistic_id": f"{DOMAIN}:energy_total",
                    "unit_of_measurement": "kWh",
                    "has_mean": False,
                    "has_sum": True,
                    "name": "Energy Consumption Total",
                }
                
                _LOGGER.debug("Importing %d energy statistics to Home Assistant", len(energy_statistics))
                await async_add_external_statistics(self.hass, energy_metadata, energy_statistics)
                _LOGGER.info("Successfully imported %d energy statistics", len(energy_statistics))
            
            # Import temperature statistics
            if temperature_statistics:
                temp_metadata = {
                    "source": DOMAIN,
                    "statistic_id": f"{DOMAIN}:temperature",
                    "unit_of_measurement": "°F",
                    "has_mean": True,
                    "has_sum": False,
                    "name": "Temperature",
                }
                
                _LOGGER.debug("Importing %d temperature statistics to Home Assistant", len(temperature_statistics))
                await async_add_external_statistics(self.hass, temp_metadata, temperature_statistics)
                _LOGGER.info("Successfully imported %d temperature statistics", len(temperature_statistics))
                
        except Exception as err:
            _LOGGER.error("Failed to import metrics to statistics system: %s", err, exc_info=True)