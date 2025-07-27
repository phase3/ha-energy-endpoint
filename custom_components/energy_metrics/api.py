"""REST API for Energy Metrics Importer."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import API_ENDPOINT, DOMAIN
from .coordinator import EnergyMetricsCoordinator

_LOGGER = logging.getLogger(__name__)


class EnergyMetricsAPI:
    """API handler for Energy Metrics endpoints."""

    def __init__(self, hass: HomeAssistant, coordinator: EnergyMetricsCoordinator) -> None:
        """Initialize the API handler."""
        self.hass = hass
        self.coordinator = coordinator
        self._view: EnergyMetricsView | None = None

    async def async_setup(self) -> None:
        """Set up the API endpoints."""
        self._view = EnergyMetricsView(self.coordinator)
        self.hass.http.register_view(self._view)
        _LOGGER.info("Energy Metrics API endpoints registered at %s", API_ENDPOINT)

    async def async_cleanup(self) -> None:
        """Clean up API endpoints."""
        if self._view:
            # Home Assistant doesn't have a direct way to unregister views
            # The view will be cleaned up when the component is unloaded
            self._view = None


class EnergyMetricsView(HomeAssistantView):
    """View for handling energy metrics API requests."""

    url = API_ENDPOINT
    name = "api:energy_metrics"
    requires_auth = True

    def __init__(self, coordinator: EnergyMetricsCoordinator) -> None:
        """Initialize the view."""
        self.coordinator = coordinator

    async def post(self, request: Request) -> Response:
        """Handle POST requests to add energy metrics data."""
        try:
            # Parse JSON data
            data = await request.json()
            
            # Validate data structure
            if not isinstance(data, dict):
                return web.json_response(
                    {"error": "Invalid data format. Expected JSON object."},
                    status=400
                )
            
            # Handle both single metric and bulk metrics
            metrics_data = []
            
            if "metrics" in data:
                # Bulk data format: {"metrics": [...]}
                if not isinstance(data["metrics"], list):
                    return web.json_response(
                        {"error": "Metrics must be a list."},
                        status=400
                    )
                metrics_data = data["metrics"]
            elif "timestamp" in data:
                # Single metric format
                metrics_data = [data]
            else:
                return web.json_response(
                    {"error": "Invalid data format. Expected 'metrics' array or single metric with 'timestamp'."},
                    status=400
                )
            
            # Validate each metric
            validated_metrics = []
            for i, metric in enumerate(metrics_data):
                validation_result = self._validate_metric(metric, i)
                if validation_result["valid"]:
                    validated_metrics.append(validation_result["metric"])
                else:
                    return web.json_response(
                        {"error": f"Invalid metric at index {i}: {validation_result['error']}"},
                        status=400
                    )
            
            # Add metrics to coordinator
            success = await self.coordinator.async_add_metrics(validated_metrics)
            
            if success:
                return web.json_response(
                    {
                        "success": True,
                        "message": f"Successfully processed {len(validated_metrics)} metrics",
                        "processed_count": len(validated_metrics)
                    },
                    status=200
                )
            else:
                return web.json_response(
                    {"error": "Failed to store metrics data"},
                    status=500
                )
                
        except json.JSONDecodeError:
            return web.json_response(
                {"error": "Invalid JSON data"},
                status=400
            )
        except Exception as err:
            _LOGGER.error("Error processing metrics data: %s", err)
            return web.json_response(
                {"error": f"Internal server error: {str(err)}"},
                status=500
            )

    async def get(self, request: Request) -> Response:
        """Handle GET requests to retrieve metrics data."""
        try:
            query_params = request.query
            
            # Get date range if specified
            start_time_str = query_params.get("start_time")
            end_time_str = query_params.get("end_time")
            
            if start_time_str and end_time_str:
                try:
                    start_time = dt_util.parse_datetime(start_time_str)
                    end_time = dt_util.parse_datetime(end_time_str)
                    
                    if not start_time or not end_time:
                        return web.json_response(
                            {"error": "Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"},
                            status=400
                        )
                    
                    metrics = await self.coordinator.async_get_metrics_range(start_time, end_time)
                    
                except Exception as err:
                    return web.json_response(
                        {"error": f"Invalid datetime format: {str(err)}"},
                        status=400
                    )
            else:
                # Get latest metric
                latest_metric = await self.coordinator.async_get_latest_metrics()
                metrics = [latest_metric] if latest_metric else []
            
            return web.json_response(
                {
                    "success": True,
                    "metrics": metrics,
                    "count": len(metrics)
                },
                status=200
            )
            
        except Exception as err:
            _LOGGER.error("Error retrieving metrics data: %s", err)
            return web.json_response(
                {"error": f"Internal server error: {str(err)}"},
                status=500
            )

    def _validate_metric(self, metric: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Validate a single metric entry."""
        if not isinstance(metric, dict):
            return {"valid": False, "error": "Metric must be an object"}
        
        required_fields = ["timestamp"]
        for field in required_fields:
            if field not in metric:
                return {"valid": False, "error": f"Missing required field: {field}"}
        
        # Validate timestamp
        timestamp = metric.get("timestamp")
        if isinstance(timestamp, str):
            try:
                parsed_timestamp = dt_util.parse_datetime(timestamp)
                if not parsed_timestamp:
                    return {"valid": False, "error": "Invalid timestamp format"}
                metric["timestamp"] = parsed_timestamp
            except Exception:
                return {"valid": False, "error": "Invalid timestamp format"}
        elif not isinstance(timestamp, datetime):
            return {"valid": False, "error": "Timestamp must be a datetime string or object"}
        
        # Validate numeric fields (optional but must be numeric if present)
        numeric_fields = ["meter_value", "average_value", "temperature"]
        for field in numeric_fields:
            if field in metric and metric[field] is not None:
                try:
                    metric[field] = float(metric[field])
                except (ValueError, TypeError):
                    return {"valid": False, "error": f"Field '{field}' must be numeric"}
        
        # Ensure at least one data field is present
        data_fields = ["meter_value", "average_value", "temperature"]
        if not any(field in metric and metric[field] is not None for field in data_fields):
            return {"valid": False, "error": "At least one data field (meter_value, average_value, temperature) must be provided"}
        
        return {"valid": True, "metric": metric}