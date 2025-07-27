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
        async with self._lock:
            stored_data = await self.store.async_load()
            if stored_data:
                self._data = stored_data
            return self._data

    async def async_add_metrics(self, metrics_data: List[Dict[str, Any]]) -> bool:
        """Add or update energy metrics data."""
        async with self._lock:
            try:
                # Load existing data
                stored_data = await self.store.async_load() or {}
                metrics = stored_data.get("metrics", {})
                
                updated = False
                for metric in metrics_data:
                    timestamp = metric.get("timestamp")
                    if not timestamp:
                        _LOGGER.warning("Metric missing timestamp: %s", metric)
                        continue
                    
                    # Parse timestamp if it's a string
                    if isinstance(timestamp, str):
                        try:
                            timestamp = dt_util.parse_datetime(timestamp)
                        except Exception as err:
                            _LOGGER.error("Invalid timestamp format %s: %s", timestamp, err)
                            continue
                    
                    # Convert to ISO string for consistent storage
                    timestamp_key = timestamp.isoformat()
                    
                    # Store or update the metric
                    if timestamp_key not in metrics or metrics[timestamp_key] != metric:
                        metrics[timestamp_key] = {
                            "timestamp": timestamp_key,
                            "meter_value": metric.get("meter_value"),
                            "average_value": metric.get("average_value"), 
                            "temperature": metric.get("temperature"),
                            "created_at": dt_util.utcnow().isoformat(),
                        }
                        updated = True
                
                if updated:
                    # Save updated data
                    stored_data["metrics"] = metrics
                    stored_data["last_updated"] = dt_util.utcnow().isoformat()
                    await self.store.async_save(stored_data)
                    
                    # Update coordinator data
                    self._data = stored_data
                    
                    # Notify listeners
                    self.async_set_updated_data(self._data)
                
                return updated
                
            except Exception as err:
                _LOGGER.error("Error adding metrics: %s", err)
                return False

    async def async_get_latest_metrics(self) -> Optional[Dict[str, Any]]:
        """Get the latest metric entry."""
        async with self._lock:
            stored_data = await self.store.async_load() or {}
            metrics = stored_data.get("metrics", {})
            
            if not metrics:
                return None
            
            # Get the most recent entry
            latest_timestamp = max(metrics.keys())
            return metrics[latest_timestamp]

    async def async_get_metrics_range(
        self, start_time: datetime, end_time: datetime
    ) -> List[Dict[str, Any]]:
        """Get metrics within a time range."""
        async with self._lock:
            stored_data = await self.store.async_load() or {}
            metrics = stored_data.get("metrics", {})
            
            filtered_metrics = []
            for timestamp_str, metric in metrics.items():
                try:
                    metric_time = dt_util.parse_datetime(timestamp_str)
                    if start_time <= metric_time <= end_time:
                        filtered_metrics.append(metric)
                except Exception as err:
                    _LOGGER.error("Error parsing timestamp %s: %s", timestamp_str, err)
            
            # Sort by timestamp
            filtered_metrics.sort(key=lambda x: x["timestamp"])
            return filtered_metrics