# Home Assistant Intex Pool Integration via Tuya (Local)

A custom Home Assistant integration for controlling Intex pool devices via the Tuya protocol using **local network communication** (no cloud dependencies).

## Features

- **Local Communication Only**: Direct connection to device via IP address - no cloud dependency
- **Climate Control**: Manage heater temperature settings (20-40°C)
- **Switches**: Control pump and power states
- **Sensors**: Monitor water temperature and air humidity
- **Real-time Updates**: Periodic polling of device status (10 second intervals)
- **Low Latency**: Direct local network communication for faster response times

## Installation

1. Copy the `intex-tuya` folder to your Home Assistant `custom_components` directory:
   ```
   custom_components/intex-tuya/
   ```

2. Restart Home Assistant

3. Go to Settings → Devices & Services → Create Integration

4. Search for "Intex Pool via Tuya (Local)" and add the integration

## Configuration

You'll need the following information from your Tuya device:

- **Device Name**: A friendly name for your pool device (e.g., "Pool")
- **Device IP Address**: The local IP address of your pool device (e.g., 192.168.1.100)
- **Device ID**: Found in the Tuya Smart Home app or device settings
- **Local Key**: The local encryption key for your device

### Finding Your Device Information

1. **IP Address**: 
   - Check your router's DHCP client list for the device IP
   - Or use network scanning tools like arp-scan or nmap

2. **Device ID & Local Key**:
   - Open the Tuya Smart Home app
   - Long-press on your pool device
   - Go to Device Information or Settings
   - Find "Device ID" and "Local Key" values
   - Note: Some devices store this in the app's cached data

## Entities

### Climate
- `climate.intex_pool_heater` - Control pool heater temperature (20-40°C)

### Switches
- `switch.intex_pool_power` - Main power control
- `switch.intex_pool_pump` - Pump control

### Sensors
- `sensor.intex_pool_water_temperature` - Current water temperature (°C)
- `sensor.intex_pool_air_humidity` - Current air humidity (%)

## Device Data Points (DPs)

The integration uses the following Tuya data points:

| DP | Name | Type | Description |
|----|------|------|-------------|
| 1 | Power | Bool | Main power switch |
| 2 | Pump | Bool | Pump control |
| 3 | Heater | Bool | Heater on/off |
| 4 | Temperature | Int | Current water temperature (×10) |
| 5 | Target Temp | Int | Target water temperature (×10) |
| 6 | Humidity | Int | Air humidity percentage |

*Note: If your device uses different DPs, modify the values in `const.py`*

## Protocol Details

This integration uses the **Tuya Local Protocol** with the following specifications:

- **Port**: 6668 (TCP)
- **Encryption**: AES-128-ECB with PKCS7 padding
- **Authentication**: Device ID + Protocol Version + Local Key
- **Message Format**: Binary protocol with MD5 checksums

## Development

To further develop this integration:

1. The `tuya_local.py` module contains the Tuya local protocol client
2. Entities are in `climate.py`, `switch.py`, and `sensor.py`
3. Update `const.py` if your device uses different data points

## Troubleshooting

**Device not found / Connection refused**:
- Verify the IP address is correct and reachable
- Ensure the device is on the same network as Home Assistant
- Check firewall rules allow port 6668

**Invalid Device ID or Local Key**:
- Double-check the values from the Tuya app
- Some devices require regenerating the Local Key in the app settings
- Restart the device and try again

**Incorrect sensor readings**:
- Check if your device uses different data point scaling
- Modify the scaling factors in `const.py` if needed

**Frequent disconnections**:
- Some devices have unstable local connections
- Try increasing the scan interval in configuration
- Ensure good WiFi signal strength on the device

## License

MIT License

## Contributing

Contributions are welcome! Please submit pull requests or open issues for bugs and feature requests.
