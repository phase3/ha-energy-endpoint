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

### Energy Dashboard Integration

After importing data, the historical energy readings will be available in:

1. **Home Assistant Energy Dashboard** - Use `energy_metrics:energy_total` as the energy source
2. **Statistics graphs** - View long-term trends and analytics
3. **History panel** - See all imported historical data points

## Sensors and Statistics

The integration creates three sensors and imports historical data to Home Assistant's statistics system:

### Sensors

1. **Energy Meter** (`sensor.energy_meter`)
   - Device Class: `energy`
   - State Class: `total_increasing`
   - Unit: `kWh`
   - Shows current meter reading

2. **Energy Average** (`sensor.energy_average`)
   - Device Class: `energy`
   - State Class: `measurement`
   - Unit: `kWh`
   - Shows current average consumption

3. **Temperature** (`sensor.temperature`)
   - Device Class: `temperature`
   - State Class: `measurement`
   - Unit: `°F`
   - Shows current temperature

### Statistics (Energy Dashboard Integration)

Historical data is automatically imported to Home Assistant's statistics system:

1. **Energy Total** (`energy_metrics:energy_total`)
   - External statistic for cumulative energy consumption
   - Appears in Home Assistant Energy dashboard
   - All historical meter readings are imported

2. **Temperature** (`energy_metrics:temperature`)
   - External statistic for temperature data
   - Historical temperature readings are imported

## Data Storage

- Historical data is stored in two places:
  1. **Component storage**: For sensor state management and API queries
  2. **Home Assistant statistics**: For Energy dashboard and long-term analytics
- Existing data with the same timestamp will be overwritten in both systems
- Data survives Home Assistant restarts
- Statistics are automatically imported to Home Assistant's recorder database
- Historical data appears immediately in the Energy dashboard after import

## Requirements

- Home Assistant 2025.7 or later
- HACS 2.0.5 or later (if installing via HACS)

## Support

For issues and feature requests, please use the GitHub repository issue tracker.
