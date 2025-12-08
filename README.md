# ESPHome Thermatik Integration

Expose your **S-Thermatik NEO controller** to **Home Assistant** (or any other MQTT-enabled system) using ESPHome.  
This package provides a simple way to integrate the controller without custom firmware modifications, just import the package into your ESPHome configuration.

---

## ✨ Features
- Seamless integration of **S-Thermatik NEO** with ESPHome.
- MQTT support for Home Assistant or other automation platforms.
- Easy setup via `packages` in ESPHome.
- Optional PIN code support if default one was changed.

---


## 📷 Sensors and controls
![](images/webserver_esphome.png)

## 📦 Installation

1. Ensure you have a working ESPHome environment.
2. Add the following snippet to your ESPHome configuration:

```yaml
packages:
  thermatik:
    url: https://github.com/vk496/esphome-thermatik
    files:
      - path: package.yaml
        vars:
          mac_address: "3C:E0:64:XX:XX:XX"
          # pincode: 000000 # Not required unless you changed it from default
```

- Replace `mac_address` with the MAC address of your S-Thermatik NEO controller.
- Add `pincode` if your device requires a different from the default.

3. Compile and flash your ESP device with ESPHome.

---

## ⚙️ Requirements
- An device running ESPHome that supports BLE.

---

## 🛠️ Usage
Once flashed:
- ESPHome will connect to the S-Thermatik NEO controller via BLE.
- Sensor data and controls will be exposed through MQTT.
- Home Assistant will automatically discover entities if MQTT discovery is enabled.

---

## 📚 Notes
- The integration is designed to be **plug-and-play**: no manual component coding required.
- For advanced customization, you can edit `package.yaml` directly in your ESPHome configuration with extension and overriding.
- The status of the project is in early stages; use at your own risk and report any issues you encounter.

---

## 🤝 Contributing
Pull requests and issues are welcome!  
If you encounter problems or have feature requests, please open an issue in the [GitHub repository](https://github.com/vk496/esphome-thermatik).

---

## 📄 License
This project is licensed under the GPLv3. See the [LICENSE](LICENSE) file for details.
