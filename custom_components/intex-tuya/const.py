"""Constants for the Intex Tuya integration."""

DOMAIN = "intex_tuya"

# Configuration keys
CONF_HOST = "host"
CONF_DEVICE_ID = "device_id"
CONF_LOCAL_KEY = "local_key"

# Tuya device DPs (Data Points)
# These are the function codes for pool-specific controls
DP_POWER = "104"           # Power switch
DP_PUMP = "2"            # Pump control
DP_HEATER = "108"          # Heater control
DP_TEMPERATURE = "110"     # Current water temperature
DP_TARGET_TEMP = "109"     # Target temperature
DP_HUMIDITY = "6"        # Humidity

# Entity platforms
PLATFORMS = [
    "climate",
    "switch",
    "sensor",
]

# Update interval
DEFAULT_SCAN_INTERVAL = 10  # 10 seconds for local polling
DEVICE_TIMEOUT = 5  # Timeout for device communication in seconds
