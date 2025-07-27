# Energy Metrics Importer - Troubleshooting Guide

This guide helps you identify and resolve common issues with the Energy Metrics Importer integration.

## Checking Logs

All error information is logged to Home Assistant's log files. To enable debug logging for this integration:

1. Add to your `configuration.yaml`:
```yaml
logger:
  default: warning
  logs:
    custom_components.energy_metrics: debug
```

2. Restart Home Assistant
3. Check logs at: Settings → System → Logs

## Common Issues

### 1. Integration Setup Issues

#### Problem: Integration fails to load
**Symptoms:**
- Integration shows as "Failed to load" in Settings → Devices & Services
- Error in logs: "Failed to set up Energy Metrics Importer"

**Solutions:**
- Check that all files are in the correct directory: `custom_components/energy_metrics/`
- Verify file permissions are readable by Home Assistant
- Check logs for specific error messages
- Restart Home Assistant after installation

#### Problem: API endpoints not registering
**Symptoms:**
- Error in logs: "Failed to register API endpoints"
- HTTP 404 when accessing `/api/energy_metrics`

**Solutions:**
- Ensure Home Assistant's HTTP integration is enabled
- Check for port conflicts
- Verify authentication is configured correctly

### 2. Data Ingestion Issues

#### Problem: API returns 400 Bad Request
**Symptoms:**
- POST requests to `/api/energy_metrics` return 400 status
- Error message about invalid data format

**Solutions:**
- Verify JSON format is correct
- Check that `timestamp` field is present
- Ensure at least one data field (meter_value, average_value, temperature) is provided
- Validate timestamp format (ISO 8601): `2024-01-01T10:00:00Z`

**Example valid request:**
```json
{
  "timestamp": "2024-01-01T10:00:00Z",
  "meter_value": 1234.567,
  "average_value": 12.34,
  "temperature": 72.5
}
```

#### Problem: API returns 401 Unauthorized
**Symptoms:**
- All API requests return 401 status
- Error about missing or invalid authentication

**Solutions:**
- Generate a long-lived access token in Home Assistant
- Include token in Authorization header: `Bearer YOUR_TOKEN`
- Verify token is not expired
- Check that the token has the necessary permissions

#### Problem: Data not appearing in sensors
**Symptoms:**
- API returns 200 success
- No data shows in sensor entities

**Solutions:**
- Check coordinator logs for storage errors
- Verify sensor entities are enabled
- Check that data contains valid numeric values
- Restart integration: Settings → Devices & Services → Energy Metrics → Reload

### 3. Sensor Issues

#### Problem: Sensors show "Unknown" or "Unavailable"
**Symptoms:**
- Energy meter sensor state is "Unknown"
- No recent data in sensor attributes

**Solutions:**
- Check if any data has been sent to the API
- Verify data contains the expected field (meter_value, average_value, temperature)
- Check sensor attributes for error messages
- Look for data type conversion errors in logs

#### Problem: Energy sensor not appearing in Energy dashboard
**Symptoms:**
- Sensor exists but not available for Energy configuration

**Solutions:**
- Verify sensor has `device_class: energy` and `state_class: total_increasing`
- Ensure unit is `kWh`
- Check that sensor has numerical values (not None/null)
- The energy meter sensor specifically should appear in Energy dashboard

### 4. Storage Issues

#### Problem: Data not persisting across restarts
**Symptoms:**
- Data disappears after Home Assistant restart
- Storage errors in logs

**Solutions:**
- Check Home Assistant storage directory permissions
- Verify sufficient disk space
- Look for storage-related errors in logs
- Check if storage file is being created in Home Assistant's storage directory

#### Problem: Large amounts of data causing performance issues
**Symptoms:**
- Slow API responses
- High memory usage
- Timeout errors

**Solutions:**
- Consider data retention policies
- Monitor API payload sizes (10MB limit)
- Implement data cleanup if needed

## Error Status Indicators

The sensors provide status information in their attributes:

- `"status": "connected"` - Normal operation
- `"status": "disconnected"` - No coordinator data
- `"status": "no_data"` - No metrics in storage
- `"status": "data_error"` - Invalid timestamps
- `"status": "error"` - General error (check logs)

## Performance Monitoring

Monitor these metrics for optimal performance:

1. **API Response Times**: Should be < 1 second for normal payloads
2. **Storage Size**: Monitor growth of storage files
3. **Memory Usage**: Check if integration memory usage grows over time
4. **Log Volume**: Enable debug logging only when troubleshooting

## Debug Information Collection

When reporting issues, include:

1. Home Assistant version
2. Integration version
3. Full error logs with debug enabled
4. Example API request that's failing
5. Sensor attribute values showing status
6. Storage file size (if accessible)

## API Testing

Use the included `example_usage.py` script to test API functionality:

```bash
python3 example_usage.py
```

Update the script with your Home Assistant URL and access token.

## Getting Help

1. Enable debug logging
2. Reproduce the issue
3. Collect relevant log entries
4. Check this troubleshooting guide
5. Report issues with full details

## Log Message Examples

**Normal Operation:**
```
INFO: Successfully processed 24 metrics from 192.168.1.100
DEBUG: Storage updated successfully. Metrics count: 120 -> 144
```

**Data Issues:**
```
WARNING: Metric at index 5 missing timestamp
ERROR: Invalid timestamp format at index 2 (not-a-date): Invalid isoformat string
ERROR: Invalid meter_value type: could not convert string to float: 'invalid'
```

**Storage Issues:**
```
ERROR: Failed to save metrics to storage: [Errno 28] No space left on device
ERROR: Failed to load data from storage: Permission denied
```

**API Issues:**
```
WARNING: Request from 192.168.1.100 rejected: payload too large (15728640 bytes)
ERROR: Unexpected error processing metrics from 192.168.1.100: 'NoneType' object has no attribute 'get'
```