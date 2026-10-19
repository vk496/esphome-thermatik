# S-Thermatik NEO protocol audit

Audited on 20 October 2026 against the two supplied Android bundles. The integration's **503 register name/address pairs match all 503 distinct `DeviceProperty` name/address pairs recovered from the official app**. This establishes register-table coverage for this build; it does not establish full app parity or hardware validation of every command.

## Artifacts and evidence

Both XAPK manifests identify `com.spartherm.thermatikneo`, version code **450**, version name **PROD-2025.11.26**. The [official Google Play listing](https://play.google.com/store/apps/details?id=com.spartherm.thermatikneo) reports an update on **3 December 2025**, consistent with the supplied release. The store date alone cannot prove that a supplied bundle is the latest binary distributed to every device.

SHA-256 fingerprints:

| Artifact | SHA-256 |
| --- | --- |
| `sthermatik.xapk` (ARM32) | `197d4cbcf84b80bf875abda56f68125729e11a7d8775e1f767140f90694a3c76` |
| `sthermatik_arm64.xapk` (ARM64) | `3b53b22190caa9396e78ca38defb6d1e3e3b8222c3307206738cb83656579d65` |
| ARM32 `libapp.so` | `80e6cd63ce180cad5718190086ed134568b3a1eb462985ceb08e1252405419b2` |
| ARM64 `libapp.so` | `cdaa4bc54e248dddfc78ba92daecd9258f78b01c54c516fc740ef30949e714e2` |

The Dart snapshot fingerprint is `f956f595844a2f845a55707faaaa51e4` (Dart 3.6 snapshot family). ARM64 AOT metadata, object-pool constants and native instructions provided the behavioral evidence below. Addresses refer to the fingerprinted ARM64 `libapp.so`, not controller registers or addresses stable across future app builds. Decompiled output is approximate; the findings were checked against instructions and constants rather than treating generated pseudocode as original source.

A direct ARM64 instruction/object-pool cross-check found 523 property initializer functions producing 503 distinct name/address pairs; the other 20 functions are aliases of existing pairs. All 539 functions in the BLE property library were accounted for: 523 initializers and 16 transport/list/format helpers. This also checked initializer functions omitted from the decompiler’s duplicate-body assembly exports.

The normalized inventory is [app-registers.json](app-registers.json). Register names, addresses and value formats are retained; decompiled app source is not included in this documentation. Implementations are in [the package](../package.yaml), [protocol helpers](../src/thermatik_protocol.h) and [the register table](../src/ble_values.h).

## Transport and value formats

The app uses BLE service `FFF0`, address characteristic `FFF1`, and data characteristic `FFF2`, under the standard Bluetooth base UUID. An address is sent least-significant byte first; the corresponding returned value occupies a two-byte little-endian slot. The package pads polling requests to five registers and waits two seconds before reading. Developer reads and control transactions share a queue with polling so their address and response ownership cannot overlap.

The receiver consumes only an explicitly pending read, checks that the response contains every requested slot, and reconnects after a response timeout to discard an unidentifiable late reply. Disconnecting clears transaction and firmware state. These are integration safeguards, not claims that the controller includes transaction identifiers. A requested manual-mode change invalidates the cached mode until immediate readback confirms it; controls are also blocked while a user transaction is running.

`BluetoothRepository.readData` at `0x53e0a4` reads the raw characteristic. Conversion occurs in its callers: the generic response decoder uses signed halfword loads at `0x540e48`, unsigned halfword loads at `0x540e94`, and byte loads for the byte-valued format. Property initializers identify these formats:

| Format | Properties |
| --- | --- |
| Signed 16-bit | `vPtTempDec1/2/3`, `vTcTemp1`, `BoardTemp`, `cAmbientTemp`, `cSensorError`, `cMotorError`, `cSusiValue` |
| Unsigned 8-bit | `cControllerReset` |
| Unsigned 16-bit | All other recovered properties |

Ambient, board and exhaust temperatures are signed integer °C. PT temperatures are signed tenths of °C: `OverviewPageCubit.updateState` divides the three readings by ten at `0x55626c`, `0x55630c` and `0x5563ac`. The package applies that scaling only to PT channels. Error registers remain exposed as raw diagnostic words while their app-reported flags receive text descriptions.

## Firmware and heating controls

`readFirmwareVersion` (`0x53cd64`, response closure `0x53d310`) requests controller registers `1ED6` and `1ED8` in that order. The first is the low word:

```text
word  = (controllerVersion2 << 16) | controllerVersion
major = (word >> 16) & 0xFF
minor = (word >> 8) & 0xFF
patch = word & 0xFF
flags = (word >> 24) & 0xFF
```

The app selects the modern register layout at **1.15.0 or later**, independently of prerelease flags. `get_flameProp` (`0x53db64`) selects `FiringMode=1CBE` for modern firmware and `1C5C` for older firmware; their initializers are `0x53dc20` and `0x53dbe4`. Many relay, motor, door-switch and parameter addresses also vary by firmware; explicit inventory variants must be used rather than assuming a universal offset.

`FiringModeAttr` defaults to `auto`. The package first reads both controller-version words, then selects the appropriate power register. Explicit `FiringMode_0x1C5C` and `FiringMode_0x1CBE` overrides remain available. Invalid major bytes (`0` or `255`) leave firmware unknown; the current version text shows the numeric release and does not render the app's prerelease labels.

**Power stage and burning mode are separate values.** `updatePowerStage` (`0x5f9cf4`) writes the normal power levels `1=Low`, `2=Mid`, `3=High` to the firmware-selected FiringMode register. Modern `Mode=1CD4` selects `0=TUV part load`, `1=TUV full load`, `2=Blue Angel`, `3=Normal/Spartherm`. `fetchBurningMode` (`0x53dc5c`) and `get_burningMode` (`0x544280`) decode Mode; the official app blocks Blue Angel power changes and handles TUV modes through a separate Mode-toggle path.

The package permits heating changes only while connected, with a resolved power register, a confirmed automatic air-slider state and normal burning mode. It blocks certification-mode heating changes instead of implementing the TUV toggle. Older firmware skips the modern Mode register and uses normal mode. Manual slider percentage changes require confirmed manual control. Readback updates the control entities.

`cBurningModeCount=1E22` bit 15 identifies the app's product prefix 4; it is not the selected burning mode (`fetchVersionPrefix`, `0x53de6c`). A raw value of four does not set that flag.

## Status, errors and sensor availability

`HomeState.fromValueCache` (`0x543378`, status switch at `0x543d74–0x543e20`) maps `cControllerStatus` as follows:

| Raw | Status | Raw | Status | Raw | Status |
| --- | --- | --- | --- | --- | --- |
| 0 | Standby | 1 | Ignition | 2 | Rising |
| 3 | Falling | 4 | Glowing | 5 | Chamber flush |
| 6 | No ignition | 7 | Overheated | 8 | Reducing glow |

Other values display Unknown while the raw diagnostic remains available. Motor and sensor diagnostics are bit fields, so simultaneous conditions must be combined rather than treated as enum values. The same native function reads motor errors through Dart static-table offset `0x1D18` and sensor errors through offset `0x1CD0`. These are application metadata locations, distinct from controller registers `1E2A` and `1D4E`.

| Register | Mask | Meaning |
| --- | --- | --- |
| `cMotorError` | `0001`, `0002`, `0004` | Wrong motor configuration, undercurrent, overcurrent |
| `cMotorError` | `0040`, `0080` | Runtime test failed, runtime test passed |
| `cSensorError` | `0008`, `0010`, `0020` | Thermocouple, ambient sensor, board sensor open |
| `cSensorError` | `0800`, `1000`, `2000` | Thermocouple, ambient sensor, board sensor shorted |
| `cSensorError` | `4000` | Also labeled thermocouple shorted by the app |

Masks are hexadecimal. `DeviceError.getLabel` (`0x5f7eac`) deliberately maps both thermocouple-short conditions to the same label. Text helpers consider only the app-reported masks `00C7` and `7838`; other diagnostic bits are preserved in the raw sensors and are not presented as inferred faults. In particular, `cSensorError=0007` alone is not an app-reported sensor failure.

Sensor availability is a separate register, `cSensorStatus=1EA2`. `isAmbientSensorConnected` (`0x5441c8`) checks bits 4 and 12. The ambient reading is published only when both of its availability bits are clear, including when the flags follow the temperature in the same response. Unknown availability remains unavailable. PT availability uses pairs `(0,8)`, `(1,9)`, `(2,10)` for PT1–PT3 (`SchemePageCubit.updateState`, `0x5f323c–0x5f35fc`). The package publishes unavailable PT temperatures as unavailable rather than exposing their numeric sentinel as a temperature.

The app also conditions settings availability on relay configuration, sensor availability and `cFeatureConfig=1F10` (`createSettingsAvailabilityState`, `0x5421b8`). Feature configuration is exposed as a raw diagnostic; it is not treated as a universal capability bitmask. Register-table presence alone does not establish that a particular controller has the corresponding hardware.

## Commands and coverage limits

`openSesam` (`0x5f6e88`, write closure `0x5f6fc8`) uses `cSezam=1ECA` with little-endian value one (`01 00`). The package exposes a disabled-by-default **Door Remote pulse button**. The former cover abstraction was removed: open, close and stop positions are not established protocol operations for this command. `saveUserData` (`0x5e3068`, shared closure `0x5e2890`) likewise writes value one to `cSaveUserData=1EFA`; the optional save button is disabled by default.

The integration covers its existing temperature, status, air-slider and normal heating functions and adds firmware, sensor errors, PT availability, initialization, operating-hours, relay-status and feature diagnostics. It does not reproduce the app's advanced parameter editor, relay configuration, burning-mode configuration, SUSI configuration, statistics or all service/test functions. The inventory supports further investigation; it does not automatically expose those features as controls.

`BLE.writeDelay` (`0x48bdb4`, pool entry `0x155f0`) constructs a Duration of `0x124f80` microseconds: **1.2 seconds**. `writeAddresses` (`0x499794`) and `writeData` (`0x48bc04`) each await a write with response, followed by that delay. The operation timeout uses `0x2dc6c0` microseconds: **3 seconds**. The package uses these write/timeout defaults and retains the observed two-second delay for polling and developer reads.

User commands execute from their own serialized queue as soon as the active transaction finishes; they do not depend on a future polling tick. `src/thermatik_writer.h` uses write-with-response and checks both immediate initiation errors and matching GATT completion status. DATA requires a successful, single-use ADDRESS acknowledgement. A failure or timeout aborts the transaction, clears queued commands and disconnects; commands are not retried. Heating, manual-mode and slider writes reselect ADDRESS after settling, wait for a fresh register read and compare the requested value before publishing the returned state. This confirmation runs within the user transaction rather than waiting for a polling tick. A GATT acknowledgement alone does not establish that a controller applied the requested value. Pulse/save commands have no invented state confirmation.

No control write was hardware-tested during this audit. The heater was active, so initial test firmware used a temporary read-only override, blocking all controller DATA writes at three layers. That override was removed for v1.2.0 after read-only validation; normal controls require an explicit user request. Offline tests inject GATT failures, late/wrong acknowledgements, disconnects, successful writes and matching/mismatching readback. They do not establish mechanical behavior, controller acceptance or compatibility with every controller.

## Controller firmware download/update investigation

No controller firmware image, firmware-download URL, BLE DFU/update client or established flash-readback routine was found in the supplied PROD-2025.11.26 APK. The recovered app firmware routine is `readFirmwareVersion` (`0x53cd64`), which reads version registers, not firmware bytes. Inspection covered the native Dart function/library inventories and strings, the base APK's 90 asset files, split APK contents and DEX strings. The only similarly named bundled binaries are Flutter asset metadata and Android debug metadata. The `bootloader` string is read by `device_info_plus` for Android phone information; the DEX `Firmware Revision String` is a generic Bluetooth attribute label.

This is an absence-of-evidence result for the inspected app build, not proof that the controller has no programming interface. No supported app-based firmware extraction or upload procedure can be derived from these findings. The [vendor's public downloads page](https://www.spartherm.com/de/service/downloads/) did not provide a controller firmware binary during this check. No controller firmware file was obtained, and no reset, bootloader entry, flash readout or update was attempted on the active heater.

## Open issue coverage

| Issue | Changes and remaining validation |
| --- | --- |
| [#11 — unsigned temperatures](https://github.com/vk496/esphome-thermatik/issues/11) | The exact `FFE7` payload decodes to `-25` for exhaust and ambient temperatures. Ambient availability additionally follows the official app's status bits 4/12, covering the reported Basic model without ambient hardware. No evidence establishes `-25` as a universal sentinel. Tests cover both missing and connected inputs; validation on an affected Basic model remains outstanding. |
| [#5 — pump/relay/tank monitoring](https://github.com/vk496/esphome-thermatik/issues/5) | PT1–PT3 expose installed temperature probes with scaling/availability. Relay 1/2/3 active expose status bits 0/1/2, and relay function sensors decode the firmware-dependent configuration. A pump must be mapped to its wired relay; no universal pump channel is inferred. The active test controller lacks connected PT probes, so hydronic hardware validation remains outstanding. |

`RelayInfo.forRelay` (`0x542bac`, bit tests `0x542db8–0x542de4`) reads `_RelayStatus=1EAE` and maps bits 0/1/2 to the three outputs. The pool constants `0x16308` and `0x16310` identify the true/false results as `on`/`off`. `get_relayFunct1/2/3` (`0x541d28`, `0x541ca8`, `0x541c28`) select `1C78/1C7A/1C7C` before 1.15.0 and `1CDA/1CDC/1CDE` from 1.15.0. `RelayFunction` constants at pool `0x19360–0x193c0` map values 0–6 to Off, Combustion, Hot thermostat, Cold thermostat, Differential thermostat, Timer and Sezam. These are read-only monitoring entities, not relay controls. Scheme sensor selection is a separate packed configuration and must not be confused with relay on/off status.

## Observations and build requirement

A read-only image was uploaded to the test ESP32 using ESPHome 2026.9.1. Live firmware discovery confirmed **controller 1.20.1** (low `1401`, high `0101`, prerelease flags `01`) and **Bluetooth 1.2.0**. This controller uses `FiringMode=1CBE`. Other observations included Mode `0003`, feature configuration `0000`, burning-mode count `0004`, motor error `0000`, sensor error/status `0007`, initialization `0001`, relay status `0002`, and operating hours `0B6D` (2925). PT words `0A61` were accompanied by unavailable-channel status and were correctly published as unavailable. Native API logs expose decoded registers and can change verbosity at runtime. All 39 exposed entities reported icons on the final image. Live relay function values were 0/1/5 (Off/Combustion/Timer); status `0002` correctly yielded relay states off/on/off. Ambient temperature was 28 °C with flags `0007`, and the three unavailable PT inputs remained unavailable. During one observation window, two developer reads acquired the connection in 0.64 and 1.69 seconds and completed approximately 3.1 seconds after acquiring it; the configured polling interval was ten seconds. The window had zero malformed replies, timeouts or disconnects, and no polling reentry warning. No heating, slider, manual-mode, Sezam or save-settings command was sent. These observations validate specific decoding and read transactions; they do not validate actuator writes.

The package requires **ESPHome 2026.9.0 or newer** and uses package-relative includes. This addresses the external-header resolution problem in [project issue #9](https://github.com/vk496/esphome-thermatik/issues/9), following [ESPHome change #19259](https://github.com/esphome/esphome/pull/19259) and the [upstream confirmation of the 2026.9.0 fix](https://github.com/esphome/esphome/issues/14583#issuecomment-6173385014). This minimum version concerns package loading; it is separate from controller firmware compatibility.

Validation passed on ESPHome **2026.9.1**: a full ESP32/ESP-IDF firmware compile, C++ generation through local and remote package imports, and the actual receiver/control lambdas and GATT writer exercised with ASan/UBSan. Tests cover malformed and unsolicited replies, signed temperatures, firmware selection, combined error flags, unavailable PT channels, and control preconditions. The artifact-identity/inventory check finds zero missing or extra register pairs. See the README for reproducible commands. The staged package was additionally compiled and uploaded to the test ESP32 through the existing ESPHome Device Builder, with both jobs completing successfully (exit code 0). Initial validation used staged package/header copies with a temporary read-only override. That override was removed in v1.2.0; acknowledgement, serialization and readback checks remain active. The remote-import regression covers package-relative headers using a temporary Git repository; the release installation uses the published `v1.2.0` package reference.

Release validation: the standard Device Builder configuration fetched `ref: v1.2.0` directly from GitHub, validated successfully, compiled with ESPHome 2026.9.1 and completed a wireless OTA upload to the test ESP32. The temporary write blocks are absent from this release. Live verification continues to use diagnostic requests and register reads only.
