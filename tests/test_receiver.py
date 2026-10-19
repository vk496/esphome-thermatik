"""Exercise the actual package lambdas against recorded and malformed BLE replies.

Run: python3 -m unittest discover -s tests -v (requires PyYAML and g++).
No network access or device operations are performed.
"""
import pathlib
import subprocess
import tempfile
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor("!lambda", lambda loader, node: loader.construct_scalar(node))


class ReceiverTests(unittest.TestCase):
    def test_protocol_and_automation_lambdas(self):
        config = yaml.load((ROOT / "package.yaml").read_text(), Loader=Loader)
        receive = next(s["lambda"] for s in config["sensor"] if s.get("id") == "read_ble_characteristic")
        heating = config["select"][0]["set_action"][0]["lambda"]
        manual_on = config["switch"][0]["turn_on_action"][0]["lambda"]
        manual_off = config["switch"][0]["turn_off_action"][0]["lambda"]
        queue_write = next(s for s in config["script"] if s["id"] == "write_user_input")["then"][0]["lambda"]
        texts = [s["id"] for s in config["text_sensor"]] + ["DevSensorKeyText"]
        numbers = [s["id"] for s in config["sensor"] if s.get("id") != "read_ble_characteristic"]
        numbers += [s["id"] for s in config["binary_sensor"]] + ["cAirSliderPercentage", "cAirSliderAutoManual"]
        source = r'''
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <optional>
#include <string>
#include <vector>
#include "ble_values.h"
#define id(x) x
struct TextEntity { std::string state; int calls=0;
  void publish_state(const std::string &v) { state=v; ++calls; }
};
struct NumericEntity { double state=NAN; int calls=0;
  void publish_state(double v) { state=v; ++calls; }
};
struct SelectEntity:NumericEntity {
  std::optional<size_t> index_of(const std::string &s) {
    if(s=="Low") return 0; if(s=="Mid") return 1; if(s=="High") return 2;
    return {};
  }
} cPowerIcon;
struct WriteScript { int calls=0; std::vector<uint8_t> address, data;
  WriteScript *operator->() { return this; }
  void execute(std::vector<uint8_t> a, std::vector<uint8_t> d) { ++calls; address=a; data=d; }
} write_user_input;
struct Transaction {
  bool running=false; int calls=0;
  bool is_running() { return running; }
  void execute(std::vector<uint8_t>,std::vector<uint8_t>,std::string) { ++calls; }
} user_transaction;
thermatik::Diagnostics thermatik_diagnostics{};
bool connected=true,read_pending=false,is_polling=false;
bool confirming_write=false,write_readback_matches=false;
uint16_t expected_write_value=0;
bool device_info_read=false,firmware_modern=false,manual_mode_known=false;
uint16_t mode_value=65535,sensor_status_value=65535;
uint32_t last_ble_read=0;
uint32_t millis() { return 12345; }
std::vector<std::string> current_batch;
std::vector<uint8_t> firing_mode_bytes;
'''
        source += "\n".join("TextEntity " + name + ";" for name in texts)
        source += "\n" + "\n".join("NumericEntity " + name + ";" for name in numbers)
        source += "\nfloat receive(const std::vector<uint8_t> &x) {\n" + receive + "\n}\n"
        source += "void heat(const std::string &x) {\n" + heating + "\n}\n"
        source += "void manual_on() {\n" + manual_on + "\n}\n"
        source += "void manual_off() {\n" + manual_off + "\n}\n"
        source += "void queue_write(std::vector<uint8_t> address, std::vector<uint8_t> data) {\n" + queue_write + "\n}\n"
        source += r'''
void reply(std::vector<std::string> keys, std::vector<uint8_t> bytes) {
  current_batch=keys; read_pending=is_polling=true; receive(bytes);
}
int main() {
  // User commands dispatch immediately; invalid/disconnected requests never queue.
  for (const auto &key : {"cAirSlider", "cAirSliderAutoManual", "FiringMode_0x1CBE", "cSezam", "cSaveUserData"}) {
    queue_write(get_hex_bytes(key), {1,0});
  }
  assert(user_transaction.calls==5);
  queue_write({}, {1,0}); queue_write({0,0}, {1,0}); queue_write({1,0}, {});
  connected=false; queue_write(get_hex_bytes("cAirSlider"), {1,0}); connected=true;
  assert(user_transaction.calls==5);
  // ESPHome discovery and late replies cannot consume a stale batch.
  current_batch={"cAmbientTemp"}; receive({24,0});
  assert(cAmbientTemp.calls==0 && last_ble_read==0);
  reply({"cAmbientTemp","BoardTemp"},{24});
  assert(cAmbientTemp.calls==0 && !read_pending && !is_polling && last_ble_read==0);
  reply({},{}); assert(last_ble_read==0);
  reply({"a","b","c","d","e","f"},std::vector<uint8_t>(12)); assert(last_ble_read==0);
  reply({"cAmbientTemp"},{0xe7,0xff}); assert(std::isnan(cAmbientTemp.state)); // Unknown availability
  reply({"cAmbientTemp","cSensorStatus"},{0xe7,0xff,0x10,0}); assert(std::isnan(cAmbientTemp.state));
  reply({"cAmbientTemp","cSensorStatus"},{0xe7,0xff,0,0}); assert(cAmbientTemp.state==-25);
  reply({"vTcTemp1"},{0xe7,0xff}); assert(vTcTemp1.state==-25); // issue #11 exact payload
  reply({"cSensorStatus"},{0,0x10}); assert(std::isnan(cAmbientTemp.state));
  reply({"cSensorStatus"},{0,0});
  reply({"cAmbientTemp"},{0xfa,0xff});
  assert(cAmbientTemp.state==-6 && last_ble_read==12345);
  reply({"BoardTemp","vTcTemp1"},{0xff,0x7f,0,0x80});
  assert(BoardTemp.state==32767 && vTcTemp1.state==-32768);
  reply({"cControllerStatus"},{4,0}); assert(cControllerStatusText.state=="Glowing");
  reply({"cControllerStatus"},{5,0}); assert(cControllerStatusText.state=="Chamber flush");
  reply({"cControllerStatus"},{0,1}); assert(cControllerStatusText.state=="Unknown");
  reply({"cSensorError"},{7,0}); assert(sensor_error_description.state=="OK" && cSensorError.state==7);
  reply({"cSensorError"},{0x18,0x10});
  assert(sensor_error_description.state=="Thermocouple open; Ambient sensor open; Ambient sensor shorted");
  reply({"cMotorError"},{0x82,0});
  assert(cMotorErrorText.state=="Motor undercurrent; Motor runtime test passed");
  assert(thermatik::motor_status_text(0x100)=="OK"); // ignored by official home decoder
  reply({"auto"},{0,0}); assert(cPowerIcon.calls==0);
  reply({"auto"},{3,0}); assert(cPowerIcon.state==2);
  reply({"cControllerVersion","cControllerVersion2"},{1,20,1,0});
  assert(device_info_read && firmware_modern && controller_version_text.state=="1.20.1");
  assert(firing_mode_bytes==get_hex_bytes("FiringMode_0x1CBE"));
  reply({"cControllerVersion","cControllerVersion2"},{2,14,1,0});
  assert(!firmware_modern && controller_version_text.state=="1.14.2" && mode_value==3);
  assert(firing_mode_bytes==get_hex_bytes("FiringMode_0x1C5C"));
  device_info_read=false;
  reply({"cControllerVersion","cControllerVersion2"},{0,0,0,0}); assert(!device_info_read);
  reply({"cControllerVersion","cControllerVersion2"},{0xff,0xff,0xff,0xff}); assert(!device_info_read);
  assert(thermatik::firmware_version(0,2).valid()); // 2.0.0 is valid
  assert(thermatik::firmware_version(0x0f00,0xc001).modern_registers()); // prerelease flags ignored
  device_info_read=false;
  reply({"cControllerVersion"},{1,20});
  reply({"cControllerVersion2"},{1,0}); assert(!device_info_read); // no cross-response mix
  // The actual heater returned PT temperatures 2657 with status7: unavailable.
  reply({"cSensorStatus","vPtTempDec1"},{7,0,0x61,0x0a}); assert(std::isnan(pt_temperature_1.state));
  reply({"cSensorStatus","vPtTempDec2"},{0,0,0x85,0xff});
  assert(std::abs(pt_temperature_2.state-(-12.3))<0.001);
  // Control preconditions and pending-mode invalidation use the actual YAML code.
  firing_mode_bytes=get_hex_bytes("FiringMode_0x1CBE"); mode_value=3;
  cAirSliderAutoManual.state=0; manual_mode_known=false; heat("Low"); assert(write_user_input.calls==0);
  manual_mode_known=true; mode_value=2; heat("High"); assert(write_user_input.calls==0);
  mode_value=3; heat("Low"); assert(write_user_input.calls==1 && write_user_input.data[0]==1);
  manual_on(); assert(!manual_mode_known && write_user_input.calls==2);
  user_transaction.running=true;
  reply({"cAirSliderAutoManual"},{0,0}); assert(!manual_mode_known);
  heat("High"); assert(write_user_input.calls==2);
  user_transaction.running=false;
  reply({"cAirSliderAutoManual"},{1,0}); assert(manual_mode_known);
  heat("Low"); assert(write_user_input.calls==2);
  // Immediate readback accepts actual values while the user transaction owns the bus.
  user_transaction.running=true; confirming_write=true; expected_write_value=0;
  reply({"cAirSliderAutoManual"},{0,0});
  assert(write_readback_matches && manual_mode_known && !confirming_write);
  confirming_write=true; expected_write_value=50;
  reply({"cAirSlider"},{40,0});
  assert(!write_readback_matches && cAirSliderPercentage.state==40 && !confirming_write);
  confirming_write=true; reply({"cAirSlider"},{}); assert(!confirming_write);
  user_transaction.running=false;
  manual_off(); assert(!manual_mode_known);
  // Relay status is a bitfield, while the three function registers depend on firmware.
  reply({"_RelayStatus"},{5,0}); assert(relay_1_active.state==1 && relay_2_active.state==0 && relay_3_active.state==1);
  reply({"RelayFunct1","RelayFunct2","RelayFunct3"},{4,0,6,0,42,0});
  assert(relay_1_function.state=="Differential thermostat" && relay_2_function.state=="Sezam" && relay_3_function.state=="Unknown");
  assert(get_read_bytes("RelayFunct1",false,{},"auto")==get_hex_bytes("RelayFunct1_0x1C78"));
  assert(get_read_bytes("RelayFunct3",true,{},"auto")==get_hex_bytes("RelayFunct3_0x1CDE"));
  uint32_t before=0xfffffff0U,after=0x20U; assert(uint32_t(after-before)==48U);
  assert(get_hex_bytes("cSensorError")==std::vector<uint8_t>({0x4e,0x1d}));
}
'''
        source = source.replace("${FiringModeAttr}", "auto")
        with tempfile.TemporaryDirectory() as folder:
            cpp = pathlib.Path(folder) / "receiver.cpp"
            binary = pathlib.Path(folder) / "receiver"
            cpp.write_text(source)
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-unused-variable",
                            "-Wno-misleading-indentation", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                            "-I" + str(ROOT / "src"), "-I" + str(ROOT / "tests/stubs"), str(cpp), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    unittest.main()
