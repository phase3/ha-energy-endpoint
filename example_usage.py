#!/usr/bin/env python3
"""Example script for testing Energy Metrics Importer API."""

from datetime import datetime, timedelta

try:
    import requests
except ImportError:
    print("Error: 'requests' library not found. Install with: pip install requests")
    exit(1)

# Configuration
HA_URL = "http://localhost:8123"  # Change to your Home Assistant URL
API_TOKEN = "YOUR_API_TOKEN_HERE"  # Replace with your long-lived access token
API_ENDPOINT = f"{HA_URL}/api/energy_metrics"

def send_metrics(metrics_data):
    """Send metrics data to Home Assistant."""
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(API_ENDPOINT, headers=headers, json=metrics_data)
    
    if response.status_code == 200:
        print(f"✅ Successfully sent {len(metrics_data.get('metrics', [metrics_data]))} metrics")
        print(f"Response: {response.json()}")
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")

def generate_sample_data():
    """Generate sample energy metrics data."""
    now = datetime.now()
    metrics = []
    
    # Generate 24 hours of hourly data
    for i in range(24):
        timestamp = now - timedelta(hours=i)
        metrics.append({
            "timestamp": timestamp.isoformat(),
            "meter_value": 1000.0 + (i * 0.5),  # kWh reading
            "average_value": 0.5,  # Average consumption per hour
            "temperature": 72.0 + (i * 0.1)  # Temperature in Fahrenheit
        })
    
    return {"metrics": metrics}

if __name__ == "__main__":
    # Example 1: Send single metric
    single_metric = {
        "timestamp": datetime.now().isoformat(),
        "meter_value": 1234.567,
        "average_value": 12.34,
        "temperature": 72.5
    }
    
    print("Sending single metric...")
    send_metrics(single_metric)
    
    # Example 2: Send bulk metrics
    print("\nSending bulk metrics...")
    bulk_data = generate_sample_data()
    send_metrics(bulk_data)