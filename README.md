# Energy Metrics Importer

A Home Assistant custom component for importing historical energy metrics from energy vendor exports. This integration allows you to add bulk historical energy data that can be used with Home Assistant's Energy feature.

## Features

- Import historical energy meter readings
- Support for average energy consumption values
- Temperature data correlation
- REST API endpoint for bulk data ingestion
- Data overwriting capability for existing timestamps
- Energy sensor compatible with Home Assistant Energy feature
- HACS 2.0.5 compatible

## Installation

### Via HACS (Recommended)

1. Add this repository to HACS as a custom repository
2. Install the "Energy Metrics Importer" integration
3. Restart Home Assistant
4. Configure the integration via UI

### Manual Installation

1. Copy the `custom_components/energy_metrics` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Configure the integration via the UI

## Configuration

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "Energy Metrics Importer"
4. Follow the configuration steps

## API Usage

The integration provides a REST API endpoint at `/api/energy_metrics` for importing data.

### Authentication

All API requests require a valid Home Assistant authentication token in the Authorization header:

```
Authorization: Bearer YOUR_TOKEN
```

### Data Format

#### Single Metric

```json
{
  "timestamp": "2024-01-01T10:00:00Z",
  "meter_value": 1234.567,
  "average_value": 12.34,
  "temperature": 72.5
}
```

#### Bulk Metrics

```json
{
  "metrics": [
    {
      "timestamp": "2024-01-01T10:00:00Z",
      "meter_value": 1234.567,
      "average_value": 12.34,
      "temperature": 72.5
    },
    {
      "timestamp": "2024-01-01T11:00:00Z",
      "meter_value": 1246.891,
      "average_value": 13.45,
      "temperature": 73.6
    }
  ]
}
```

### Example Usage

```bash
curl -X POST \
  http://your-ha-instance:8123/api/energy_metrics \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "metrics": [
      {
        "timestamp": "2024-01-01T10:00:00Z",
        "meter_value": 1234.567,
        "average_value": 12.34,
        "temperature": 72.5
      }
    ]
  }'
```

## Sensors

The integration creates three sensors:

1. **Energy Meter** (`sensor.energy_meter`)
   - Device Class: `energy`
   - State Class: `total_increasing`
   - Unit: `kWh`
   - Compatible with Home Assistant Energy feature

2. **Energy Average** (`sensor.energy_average`)
   - Device Class: `energy`
   - State Class: `measurement`
   - Unit: `kWh`

3. **Temperature** (`sensor.temperature`)
   - Device Class: `temperature`
   - State Class: `measurement`
   - Unit: `°F`

## Data Storage

- Historical data is stored persistently and survives Home Assistant restarts
- Existing data with the same timestamp will be overwritten
- Data is stored in Home Assistant's storage system

## Requirements

- Home Assistant 2025.7 or later
- HACS 2.0.5 or later (if installing via HACS)

## Support

For issues and feature requests, please use the GitHub repository issue tracker.