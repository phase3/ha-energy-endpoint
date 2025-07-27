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
        try:
            self._view = EnergyMetricsView(self.coordinator)
            self.hass.http.register_view(self._view)
            _LOGGER.info("Energy Metrics API endpoints registered at %s", API_ENDPOINT)
        except Exception as err:
            _LOGGER.error("Failed to register API endpoints at %s: %s", API_ENDPOINT, err)
            raise

    async def async_cleanup(self) -> None:
        """Clean up API endpoints."""
        try:
            if self._view:
                # Home Assistant doesn't have a direct way to unregister views
                # The view will be cleaned up when the component is unloaded
                _LOGGER.debug("Cleaning up API view reference")
                self._view = None
        except Exception as err:
            _LOGGER.error("Error during API cleanup: %s", err)


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
        client_ip = request.remote or "unknown"
        _LOGGER.info("Received POST request from %s to add energy metrics", client_ip)
        
        try:
            # Parse JSON data with size limit check
            content_length = request.content_length
            if content_length and content_length > 10 * 1024 * 1024:  # 10MB limit
                _LOGGER.warning("Request from %s rejected: payload too large (%d bytes)", client_ip, content_length)
                return web.json_response(
                    {"error": "Payload too large. Maximum size is 10MB."},
                    status=413
                )
            
            try:
                data = await request.json()
                _LOGGER.debug("Successfully parsed JSON data from %s", client_ip)
            except json.JSONDecodeError as json_err:
                _LOGGER.warning("Invalid JSON from %s: %s", client_ip, json_err)
                return web.json_response(
                    {"error": "Invalid JSON data", "details": str(json_err)},
                    status=400
                )
            
            # Validate data structure
            if not isinstance(data, dict):
                _LOGGER.warning("Invalid data format from %s: expected dict, got %s", client_ip, type(data).__name__)
                return web.json_response(
                    {"error": "Invalid data format. Expected JSON object."},
                    status=400
                )
            
            # Handle both single metric and bulk metrics
            metrics_data = []
            
            if "metrics" in data:
                # Bulk data format: {"metrics": [...]}
                if not isinstance(data["metrics"], list):
                    _LOGGER.warning("Invalid metrics format from %s: expected list, got %s", client_ip, type(data["metrics"]).__name__)
                    return web.json_response(
                        {"error": "Metrics must be a list."},
                        status=400
                    )
                metrics_data = data["metrics"]
                _LOGGER.debug("Processing %d bulk metrics from %s", len(metrics_data), client_ip)
            elif "timestamp" in data:
                # Single metric format
                metrics_data = [data]
                _LOGGER.debug("Processing single metric from %s", client_ip)
            else:
                _LOGGER.warning("Missing required fields from %s: no 'metrics' array or 'timestamp' field", client_ip)
                return web.json_response(
                    {"error": "Invalid data format. Expected 'metrics' array or single metric with 'timestamp'."},
                    status=400
                )
            
            # Validate each metric
            validated_metrics = []
            validation_errors = []
            
            for i, metric in enumerate(metrics_data):
                validation_result = self._validate_metric(metric, i)
                if validation_result["valid"]:
                    validated_metrics.append(validation_result["metric"])
                else:
                    error_msg = f"Invalid metric at index {i}: {validation_result['error']}"
                    validation_errors.append(error_msg)
                    _LOGGER.warning("Validation error from %s: %s", client_ip, error_msg)
            
            # If any validation errors, return them
            if validation_errors:
                return web.json_response(
                    {
                        "error": "Validation failed",
                        "validation_errors": validation_errors,
                        "total_metrics": len(metrics_data),
                        "valid_metrics": len(validated_metrics)
                    },
                    status=400
                )
            
            # Add metrics to coordinator
            _LOGGER.debug("Attempting to store %d validated metrics from %s", len(validated_metrics), client_ip)
            success = await self.coordinator.async_add_metrics(validated_metrics)
            
            if success:
                _LOGGER.info("Successfully processed %d metrics from %s", len(validated_metrics), client_ip)
                return web.json_response(
                    {
                        "success": True,
                        "message": f"Successfully processed {len(validated_metrics)} metrics",
                        "processed_count": len(validated_metrics),
                        "timestamp": dt_util.utcnow().isoformat()
                    },
                    status=200
                )
            else:
                _LOGGER.error("Failed to store metrics data from %s", client_ip)
                return web.json_response(
                    {
                        "error": "Failed to store metrics data",
                        "details": "See Home Assistant logs for more information"
                    },
                    status=500
                )
                
        except Exception as err:
            _LOGGER.error("Unexpected error processing metrics from %s: %s", client_ip, err, exc_info=True)
            return web.json_response(
                {
                    "error": "Internal server error",
                    "details": "An unexpected error occurred. Check Home Assistant logs.",
                    "timestamp": dt_util.utcnow().isoformat()
                },
                status=500
            )

    async def get(self, request: Request) -> Response:
        """Handle GET requests to retrieve metrics data."""
        client_ip = request.remote or "unknown"
        _LOGGER.debug("Received GET request from %s to retrieve metrics", client_ip)
        
        try:
            query_params = request.query
            
            # Get date range if specified
            start_time_str = query_params.get("start_time")
            end_time_str = query_params.get("end_time")
            
            if start_time_str and end_time_str:
                _LOGGER.debug("Range query from %s: %s to %s", client_ip, start_time_str, end_time_str)
                try:
                    start_time = dt_util.parse_datetime(start_time_str)
                    end_time = dt_util.parse_datetime(end_time_str)
                    
                    if not start_time or not end_time:
                        _LOGGER.warning("Invalid datetime format from %s: start=%s, end=%s", client_ip, start_time_str, end_time_str)
                        return web.json_response(
                            {
                                "error": "Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)",
                                "examples": [
                                    "2024-01-01T10:00:00Z",
                                    "2024-01-01T10:00:00",
                                    "2024-01-01T10:00:00+00:00"
                                ]
                            },
                            status=400
                        )
                    
                    metrics = await self.coordinator.async_get_metrics_range(start_time, end_time)
                    _LOGGER.debug("Retrieved %d metrics for range query from %s", len(metrics), client_ip)
                    
                except Exception as datetime_err:
                    _LOGGER.warning("Datetime parsing error from %s: %s", client_ip, datetime_err)
                    return web.json_response(
                        {
                            "error": "Invalid datetime format",
                            "details": str(datetime_err),
                            "provided_start": start_time_str,
                            "provided_end": end_time_str
                        },
                        status=400
                    )
            elif start_time_str or end_time_str:
                # Only one time parameter provided
                _LOGGER.warning("Incomplete time range from %s: start=%s, end=%s", client_ip, start_time_str, end_time_str)
                return web.json_response(
                    {
                        "error": "Both start_time and end_time must be provided for range queries",
                        "provided_start": start_time_str,
                        "provided_end": end_time_str
                    },
                    status=400
                )
            else:
                # Get latest metric
                _LOGGER.debug("Latest metric query from %s", client_ip)
                latest_metric = await self.coordinator.async_get_latest_metrics()
                metrics = [latest_metric] if latest_metric else []
                _LOGGER.debug("Retrieved %d metrics for latest query from %s", len(metrics), client_ip)
            
            response_data = {
                "success": True,
                "metrics": metrics,
                "count": len(metrics),
                "timestamp": dt_util.utcnow().isoformat()
            }
            
            # Add query info to response for debugging
            if start_time_str and end_time_str:
                response_data["query"] = {
                    "type": "range",
                    "start_time": start_time_str,
                    "end_time": end_time_str
                }
            else:
                response_data["query"] = {"type": "latest"}
            
            return web.json_response(response_data, status=200)
            
        except Exception as err:
            _LOGGER.error("Unexpected error retrieving metrics for %s: %s", client_ip, err, exc_info=True)
            return web.json_response(
                {
                    "error": "Internal server error",
                    "details": "An unexpected error occurred. Check Home Assistant logs.",
                    "timestamp": dt_util.utcnow().isoformat()
                },
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