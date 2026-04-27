# Debugging Guide for Intex Tuya Integration

This guide explains how to debug and analyze the data being returned from your Intex pool device.

## Enable Debug Logging

To see detailed debug logs from the integration, add this to your Home Assistant `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.intex_localtuya: debug
    custom_components.intex_localtuya.tuya_local: debug
```

Then restart Home Assistant and check the logs.

## Log Analysis

### Device Communication Protocol

Look for these log messages to understand the protocol flow:

#### Sending Messages
```
Creating status message with payload: {"gwId": "...", "devId": "...", ...}
Encrypted payload (X bytes): 1a2b3c4d...
Message header - Session: 1, Type: 10, PayloadLen: 32
MD5 checksum: 5d41402abc4b2a76b9719d911017c592
Sending status request message: 000055aa00000001000a00201a2b3c4d...
```

**What it means:**
- **Session**: Increments with each message (0-255)
- **Type**: 10 = status request, 7 = control, 9 = heartbeat
- **PayloadLen**: Size of encrypted data
- **Message format**: Prefix (4B) + Session (4B) + Type (4B) + Len (4B) + Encrypted payload + MD5 (16B) + Suffix (4B)

#### Receiving Responses
```
Raw response from device: 000055aa00000001000a003c1a2b3c4d...
Response length: 72 bytes
Response header - Prefix: 0x000055aa, Session: 1, Type: 10, PayloadLen: 60
Encrypted payload (60 bytes): 1a2b3c4d...
Decrypted payload (60 bytes): 7b226470...
JSON payload: {"dps":{"1":true,"4":230,"5":300,"6":45},...}
Device status - DPs: {'1': true, '4': 230, '5': 300, '6': 45}
```

**What it means:**
- **Raw response**: Complete binary message from device
- **Prefix 0x000055aa**: Valid Tuya protocol frame
- **DPs**: Data Point values - these are your device values

### Entity Updates

#### Climate (Heater) Entity
```
Climate update - Available DPs: {'1': true, '4': 230, '5': 300, '6': 45}
Updated current temp from DP 4: 230 -> 23.0°C
Updated target temp from DP 5: 300 -> 30.0°C
Updated heater state from DP 3: true
```

**Interpreting the data:**
- DP 4 (Temperature) = 230 → 23.0°C (divided by 10)
- DP 5 (Target Temp) = 300 → 30.0°C (divided by 10)  
- DP 3 (Heater) = true → Heater is ON

#### Switch Entities
```
Switch 1 update - Available DPs: {'1': true, '2': false, '3': true, ...}
Switch 1 state updated: true
Switch 2 update - Available DPs: {'1': true, '2': false, '3': true, ...}
Switch 2 state updated: false
```

**Interpreting the data:**
- DP 1 (Power) = true → Power ON
- DP 2 (Pump) = false → Pump OFF

#### Sensor Entities
```
Sensor Water Temperature (4) update - Available DPs: {'1': true, '4': 230, ...}
Sensor Water Temperature updated: raw=230, scaled=23.0 °C
Sensor Air Humidity (6) update - Available DPs: {'1': true, '6': 45, ...}
Sensor Air Humidity updated: raw=45, scaled=45.0 %
```

## Common Issues & Solutions

### Issue: "Response length: 0 bytes" or "Response too short"

This usually means the device closed the connection without sending data.

**Possible causes:**
1. Device doesn't support local key protocol
2. Local key is incorrect
3. Device firmware doesn't support the Tuya local protocol version
4. Device is offline or not responding

**Solutions:**
1. **Verify device is online**: Check Tuya app to confirm device is connected
2. **Check Local Key**: Get it from Tuya app device settings
3. **Check network connectivity**: Ping the device IP from Home Assistant host
4. **Check firewall**: Ensure port 6668 is not blocked
5. **Check device logs**: Look for additional error messages in Home Assistant logs

**Debug output to look for:**
```
Successfully connected to device at 192.168.1.100
Socket info: ('192.168.1.100', 6668)  # Good - connected successfully
Timeout reading message from device  # Device not responding
```

If you see "Successfully connected" but then "Response length: 0 bytes", the device connected but didn't respond. This could mean:
- Wrong protocol/version
- Device doesn't support local key encryption
- Device is busy or crashed

### Issue: "DP X not found in response"

This means the device is not returning data for that data point.

**Solution:**
1. Check if the device actually has that feature
2. Update the DP number in `const.py` to match your device
3. Look at "Available DPs" to see what your device actually returns

Example:
```python
# In const.py - if your device returns different DPs
DP_POWER = "1"           # Correct
DP_PUMP = "2"            # Correct  
DP_HEATER = "3"          # Change if needed
DP_TEMPERATURE = "4"     # Change if needed
```

### Issue: "Response too short: X bytes"

The device sent an incomplete or invalid response.

**Possible causes:**
- Device is not responding properly
- Local key is incorrect (encrypted data won't decrypt)
- Network issue causing packet loss

**Solution:**
1. Check your Local Key is correct
2. Verify device is online and responding
3. Try increasing socket timeout in code

### Issue: Values are wrong (e.g., temperature showing 45 instead of 24)

The scaling factor might be incorrect.

**Solution:**
1. Check raw value vs scaled value in logs
2. Adjust the scale in sensor initialization if needed

Example in `sensor.py`:
```python
# Current scaling (divide by 10)
IntexPoolSensor(..., scale=0.1)  # raw=230 → 23.0

# For different scaling:
IntexPoolSensor(..., scale=1.0)  # raw=230 → 230
```

### Issue: Connection drops or slow updates

**Solutions:**
1. Ensure device and Home Assistant are on same network
2. Check WiFi signal strength on device
3. Reduce scan interval in `const.py` if device is overwhelming
4. Increase it if device is disconnecting

### Issue: Encrypted payload won't decrypt

This usually means wrong Local Key.

**Solution:**
1. Verify Local Key from Tuya app
2. Some devices require regenerating it in app settings
3. Try restarting the device

## Finding Your Device's Data Point Mapping

If your device is different from standard Intex:

1. Look at "Available DPs" in Climate/Switch/Sensor logs
2. Identify which DP corresponds to what feature:
   - Usually DP 1, 2, 3 are switches (on/off)
   - Usually DP 4, 5, 6 are values (temp, humidity, etc.)
3. Update `const.py` with correct mappings
4. Update entity scaling if needed

Example device response mapping:
```
Available DPs: {'1': true, '2': false, '3': 0, '4': 235, '5': 280, '6': 52, '8': 'test'}

DP 1 = Power switch (bool)
DP 2 = Pump switch (bool)  
DP 3 = Heater switch or value (int)
DP 4 = Temperature (int, scale by 0.1)
DP 5 = Target temperature (int, scale by 0.1)
DP 6 = Humidity (int, scale by 1.0)
DP 8 = String value (firmware version?)
```

## Enabling Protocol-Level Debugging

For very detailed protocol debugging, check Home Assistant logs for:

```
Sending control message: 000055aa...
Control response from device: 000055aa...
```

These show the exact bytes being sent and received, useful for protocol analysis.

## Submitting a Bug Report

If you need to report a bug, include:

1. Your device type and firmware version
2. Relevant log section showing the issue
3. What you expected vs. what happened
4. The DPs your device returns (from "Available DPs" logs)
