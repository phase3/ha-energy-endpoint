"""Constants for the Energy Metrics Importer integration."""

DOMAIN = "energy_metrics"
STORAGE_KEY = "energy_metrics_data"
STORAGE_VERSION = 1

# API endpoint paths
API_ENDPOINT = "/api/energy_metrics"

# Default configuration
DEFAULT_NAME = "Energy Metrics"
DEFAULT_SCAN_INTERVAL = 300  # 5 minutes

# Energy sensor configuration
ENERGY_DEVICE_CLASS = "energy"
ENERGY_STATE_CLASS = "total_increasing"
ENERGY_UNIT = "kWh"

# Temperature sensor configuration  
TEMPERATURE_DEVICE_CLASS = "temperature"
TEMPERATURE_STATE_CLASS = "measurement"
TEMPERATURE_UNIT = "°F"