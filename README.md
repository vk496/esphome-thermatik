<div align="center">

# 🔥 ESPHome Thermatik

### Your fireplace, connected to Home Assistant.

Follow the fire, monitor temperatures and access your S-Thermatik NEO controls through an ESP32 and a local Bluetooth connection.

[![Version](https://img.shields.io/badge/version-v1.2.0-e87524)](https://github.com/vk496/esphome-thermatik/tree/v1.2.0)
[![ESPHome](https://img.shields.io/badge/ESPHome-2026.9.0%2B-18bcf2)](https://esphome.io/)
![Hardware](https://img.shields.io/badge/hardware-ESP32%20%2B%20BLE-555555)
[![License: GPL v3](https://img.shields.io/badge/license-GPLv3-blue)](LICENSE)

**Local connection · Actual controller readback · Runtime diagnostics**

[Get started](#quick-start) · [See it in action](#screenshots) · [What's new](#whats-new) · [Troubleshooting](#diagnostics)

</div>

---

## ✨ Bring your fireplace into your smart home

See whether the fire is rising, glowing or ready for a refill. Track exhaust, ambient and board temperatures alongside your other Home Assistant sensors. Access heating and air-slider controls, with their displayed values updated from the controller's response.

```text
S-Thermatik NEO  ← Bluetooth →  ESP32  ← Wi-Fi →  Home Assistant
```

The integration runs locally. Choose ESPHome's native API or add MQTT to your device configuration to suit your setup.

| | What you get |
| --- | --- |
| 🌡️ **Temperatures at a glance** | Exhaust, ambient and board temperatures, plus optional PT1–PT3 inputs for installed water/tank probes. |
| 🔥 **Follow the fire** | Controller state, door and refill status, heating level and air-slider position. |
| 🎛️ **Controls with feedback** | Low/Mid/High heating and manual air-slider control, with acknowledged BLE writes and fresh register readback. |
| 💧 **More of your installation** | Individual relay states, configured relay functions, operating hours and optional diagnostic flags. |
| 🔎 **Useful answers when debugging** | Controller and Bluetooth firmware versions, decoded errors, transaction counters and adjustable log verbosity. |
| 🏠 **Fits your ESPHome setup** | One package import, icons for every entity and configuration through Device Builder. |

<a id="screenshots"></a>

## 📷 See it in action

<div align="center">

<img src="images/webserver_esphome.png" alt="ESPHome web interface showing fireplace temperatures, controls and firmware diagnostics" width="560">

<em>Live readings, familiar controls and diagnostics in the ESPHome web interface.</em>

</div>

<details>
<summary>📱 More views of the controller and integration</summary>

<p align="center">
  <img src="images/thermatik_controller.png" alt="S-Thermatik controller" width="360">
  <img src="images/thermatik_panel.png" alt="Thermatik integration panel" width="360">
</p>

</details>

<a id="quick-start"></a>

## 🚀 Quick start

You'll need an **ESP32 with BLE**, **ESPHome 2026.9.0 or newer**, and your controller's **Bluetooth MAC address**. Add this package to an existing ESPHome device, or create an ESP32 device with the Device Builder wizard first.

### 1. Add the package

Open your device configuration and add:

```yaml
packages:
  thermatik:
    url: https://github.com/vk496/esphome-thermatik
    ref: v1.2.0
    files:
      - path: package.yaml
        vars:
          mac_address: "3C:E0:64:XX:XX:XX"
          # pincode: "000000"   # Set this if you changed the default PIN.
          # fetch_interval: 7s
          # FiringModeAttr: "auto"
```

Replace the MAC address with your controller's address. Keep your board, Wi-Fi, API/MQTT and OTA settings in the device configuration; the package provides the BLE integration.

### 2. Build and install

In **ESPHome Device Builder**, choose **Validate → Install → Wirelessly** for an ESP32 already configured for OTA. For a first installation, use a USB option offered by Device Builder, or **Manual download** with your usual flashing method. Browser USB installation needs a supported browser and a secure page.

### 3. Check the connection

Open **Logs** and look for the controller/Bluetooth firmware versions and selected heating register. Then add the device through Home Assistant's ESPHome integration if it has not already been discovered.

> 💡 **Optional sensors:** Enable PT and relay entities in Home Assistant's device entity settings. PT channels are physical inputs: give them names matching the probes installed in your system.

<details>
<summary>🛠️ Using a local checkout instead?</summary>

Keep `package.yaml` and its complete `src` directory together, then import the package relative to your device configuration:

```yaml
packages:
  thermatik: !include path/to/esphome-thermatik/package.yaml

substitutions:
  mac_address: "3C:E0:64:XX:XX:XX"
```

All three headers load relative to the package. No extra Git library or manual header copies are needed.

</details>

## 🎛️ Make it yours

| Setting or entity | How it works |
| --- | --- |
| **Heating** | Low/Mid/High in normal, automatic operation. The firmware determines the correct register automatically. |
| **Air Slider Manual mode / value** | Enable manual control before requesting a slider position. Values update from controller readback. |
| **PT1–PT3 temperature** | Signed temperature readings scaled to °C. Unavailable inputs display unavailable rather than a numeric sentinel. |
| **Relay 1/2/3 active / function** | See each output's state and configured function. Map your pump to the relay to which it is wired. |
| **Door Remote** | Optional Sezam pulse button, disabled by default. Enable it for configured Sezam hardware. |
| **Save user settings** | Optional persistence command, disabled by default. Ordinary control changes do not automatically save settings. |

Automatic register selection uses `1C5C` before controller firmware 1.15.0 and `1CBE` from 1.15.0 onward. If needed, override `FiringModeAttr` with `FiringMode_0x1C5C` or `FiringMode_0x1CBE`.

Heating changes require a known operating mode and confirmed automatic slider control. TUV/Blue Angel controls are not implemented. Normal control writes require a request through an entity; the integration keeps GATT acknowledgement, serialization and fresh readback checks active.

<a id="whats-new"></a>

## 🆕 What's new in v1.2.0

- **More responsive requests:** Controls enter their own transaction queue instead of waiting for the next polling tick. Writes use the official app's settling delays and a fresh readback.
- **Better temperature handling:** Signed decoding fixes wraparound such as `65511` becoming `-25`. Missing ambient inputs, including those reported on Basic models, remain unavailable.
- **More visibility:** Firmware diagnostics, PT inputs, individual relay monitoring, decoded errors and icons for all 39 exposed entities.
- **Debug without another upload:** Switch between INFO, DEBUG and VERBOSE at runtime, or print a diagnostic summary on demand.
- **Simpler package loading:** Uses ESPHome's upstream header fix. The extra Git-library workaround is gone.

<details>
<summary>⬆️ Upgrading from an older version</summary>

- Update to **ESPHome 2026.9.0 or newer** before using this release.
- Remove manually copied headers, their device-level `includes`, and the old `EsphomeThermatik` Git-library override. Old local headers can shadow the packaged versions.
- Set the package reference to `v1.2.0`. Keep existing network, API and OTA settings.
- The old Sezam cover is replaced by **Door Remote**, a pulse button; separate open/close/stop operations were not established.
- **Sensor Error Count** is now **Sensor Error Flags**. It is a bitfield; `7` alone is not a home-screen sensor fault in the official app.
- Controller states 4 and 5 now display **Glowing** and **Chamber flush**.
- Remove any `thermatik_read_only` substitution left over from pre-release testing. That temporary override was removed in v1.2.0.

</details>

<a id="diagnostics"></a>

## 🔎 Diagnostics that help

Use **Thermatik log level** to change detail without rebuilding firmware:

| Level | What you'll see |
| --- | --- |
| **INFO** | Connection and firmware information, warnings and periodic diagnostic summaries. |
| **DEBUG** | Transaction IDs, GATT acknowledgements, elapsed times, raw register words and decoded values. |
| **VERBOSE** | Everything above, plus raw BLE frames. |

Press **Thermatik diagnostics** for current firmware, operating mode, transaction flags and counters. The same summary runs about once a minute. Read logs through Device Builder or `esphome logs device.yaml`.

**Reporting an issue?** Include **Controller firmware**, **Bluetooth firmware**, your ESPHome version and the diagnostic summary. Add a DEBUG log covering the behavior you observed.

<details>
<summary>⏱️ Polling, timing and reconnects</summary>

- `fetch_interval` triggers complete polling cycles. A trigger is skipped quietly while a cycle is still running.
- Relay states refresh with normal polling. Extended diagnostics refresh about once per minute.
- `ble_write_settle: 1200ms` matches the app's delay after ADDRESS and DATA writes.
- `ble_read_settle: 2s` retains the observed delay for polling and developer reads.
- `ble_response_timeout: 3s` bounds GATT acknowledgements and reads. Failed transactions disconnect; control commands are not automatically retried.
- A control may wait for an in-flight BLE operation, but does not wait for the next polling tick.
- **Reboot BLE** disconnects for ten seconds before restarting, leaving a connection window for the official app.

</details>

## 🧪 Built from the official app's behavior

The protocol audit covers the supplied **PROD-2025.11.26** Android bundles. All **503 distinct register name/address pairs** already matched the integration; 523 property initializers include 20 aliases. The work corrected decoding and transaction behavior and added monitoring features.

**v1.2.0 was fetched from its published GitHub tag, compiled and installed wirelessly through ESPHome Device Builder 2026.9.1.** Local/remote package imports and offline receiver/writer tests passed. Live monitoring was checked on controller firmware **1.20.1**, with Bluetooth firmware **1.2.0**.

**Validation limits:** No actuator commands were sent during live checks. Write acceptance and mechanical behavior remain unverified on hardware, as does hydronic monitoring on a system with connected PT probes. Advanced service parameters, relay configuration, certification controls and SUSI configuration remain outside the UI.

📚 [Read the protocol audit](docs/protocol-audit.md) · [Explore the register inventory](docs/app-registers.json)

<details>
<summary>🧰 Run the offline checks</summary>

Requires Python, `g++` and the packages below:

```sh
python3 -m pip install -r tests/requirements.txt
python3 -m unittest discover -s tests -v
python3 tools/audit_xapk.py sthermatik_arm64.xapk
```

Tests exercise the actual receiver/control lambdas and GATT writer with address/undefined-behavior sanitizers. The remote-package fixture uses a temporary local Git repository and does not contact a device. The audit tool verifies artifact identity and compares the retained inventory with the header; another payload requires fresh decompilation.

To extract the audited native payload:

```sh
python3 tools/audit_xapk.py sthermatik_arm64.xapk --extract-dir .analysis/re-audit
# With a separately installed dae v0.1.13:
dae .analysis/re-audit/libapp-arm64-v8a.so .analysis/re-audit/decompiled --app --decompile
```

</details>

---

## 🤝 Help improve the integration

Have a controller variant, connected tank probes or a useful finding to share? [Open an issue](https://github.com/vk496/esphome-thermatik/issues) with your firmware versions and diagnostics. Contributions and pull requests are welcome.

<div align="center">

Made for local fireplace monitoring with ESPHome and Home Assistant.

**[GPLv3](LICENSE)** · **[Source](https://github.com/vk496/esphome-thermatik)** · **[Issues](https://github.com/vk496/esphome-thermatik/issues)**

</div>
