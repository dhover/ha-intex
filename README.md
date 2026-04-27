# Home Assistant Intex Pool Integration via Tuya (Local)

A custom Home Assistant integration for controlling an Intex spa or pool device over the local Tuya protocol.

## Features

- Local communication only, no Tuya cloud dependency for normal control
- Tuya protocol `3.4` via `tinytuya`
- Climate entity for the spa thermostat
- Separate switches for `Power`, `Filter`, `Bubbles`, and `Heat`
- Sensors for current temperature, target temperature, heat state, and error code
- Config flow with reconfigure support from the integration menu

## Installation

1. Copy the `intex-tuya` folder to your Home Assistant `custom_components` directory:

   ```text
   custom_components/intex-tuya/
   ```

2. Restart Home Assistant.
3. Go to **Settings > Devices & Services**.
4. Add **Intex Pool via Tuya (Local)**.

## Configuration

The config flow asks for:

- `Device Name`: used as the Home Assistant device name
- `Device IP Address`: used as the integration entry title
- `Device ID`
- `Local Key`

You can change these later from the integration's reconfigure action.

### Finding your device information

1. Find the IP address in your router or DHCP lease table.
2. Find the `Device ID` and `Local Key` from your Tuya app or Tuya developer tooling.

## Entities

### Climate

- `climate.<device_name>_thermostat`

This thermostat uses Fahrenheit and follows the current device mapping:

- target temperature DP: `109`
- current temperature DP: `110`
- HVAC mode DP: `108`
- HVAC action DP: `117`
- min/max temperature: `50-104 F`

### Switches

- `switch.<device_name>_power`
- `switch.<device_name>_filter`
- `switch.<device_name>_bubbles`
- `switch.<device_name>_heat`

### Sensors

- `sensor.<device_name>_current_temperature`
- `sensor.<device_name>_target_temperature`
- `sensor.<device_name>_heat_indicator`
- `sensor.<device_name>_error_code`

## Device Data Points

This integration is currently mapped for the following Intex/Tuya spa layout:

| DP | Purpose |
|----|---------|
| `104` | Power |
| `106` | Filter |
| `107` | Bubbles |
| `108` | Heat / HVAC mode |
| `109` | Target temperature |
| `110` | Current temperature |
| `114` | Error code |
| `117` | HVAC action |

If your device exposes different DPs, update [const.py](D:/git/ha-intex/custom_components/intex-tuya/const.py).

## Protocol Notes

- Port: `6668/TCP`
- Protocol version: `3.4`
- Library: `tinytuya`

## Logging and Debugging

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.intex_tuya: debug
    custom_components.intex_tuya.tuya_local: debug
```

With debug logging enabled, the integration logs:

- the full TinyTuya `status()` response
- the full TinyTuya `set_value()` response

That is useful when you want to inspect raw DPs or see whether your device exposes extra metadata.

## Known Behavior

- The configured `name` is used for the Home Assistant device name.
- The configured IP address is used as the integration entry title.
- There is currently no custom polling interval wired in code, even though `const.py` still contains a default interval constant.

## Troubleshooting

**Connection refused or unreachable**

- Verify the IP address is still correct.
- Make sure Home Assistant can reach the device on port `6668`.
- Check VLAN, guest network, and firewall rules.

**Connects but returns no data**

- Confirm the device really uses local Tuya protocol `3.4`.
- Re-check the `Local Key`.

**Wrong DPs or missing entities**

- Enable debug logging and inspect the full TinyTuya response.
- Update the DP constants to match your device.

## License

MIT License
