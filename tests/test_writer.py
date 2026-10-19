"""Exercise the real GATT writer with injected transport outcomes; no device IO."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class WriterTests(unittest.TestCase):
    def test_acknowledgements_and_failures(self):
        source = r'''
#include <cassert>
#include "thermatik_writer.h"
int main() {
  esphome::ble_client::BLEClient client;
  thermatik::GattWriter writer;
  esp_ble_gattc_cb_param_t event;
  auto dispatch=[&](int type,int handle=10,int status=0,int conn=7) {
    event.write={conn,static_cast<uint16_t>(handle),status};
    writer.gattc_event_handler(type,1,&event);
  };
  writer.configure(&client,"service","address","data");
  assert(!writer.write_address({1,0}) && mock_calls==0);
  dispatch(ESP_GATTC_SEARCH_CMPL_EVT);
  assert(!writer.write_data({1,0}) && mock_calls==0);
  assert(writer.write_address({1,0}) && !writer.done());
  dispatch(ESP_GATTC_WRITE_CHAR_EVT,20); assert(!writer.done()); // Other handle
  dispatch(ESP_GATTC_WRITE_CHAR_EVT,10,0,8); assert(!writer.done()); // Other connection
  dispatch(ESP_GATTC_WRITE_CHAR_EVT,10,5); assert(writer.done() && !writer.success());
  int calls=mock_calls;
  assert(!writer.write_data({1,0}) && mock_calls==calls);
  mock_result=-1;
  assert(!writer.write_address({1,0}) && !writer.success());
  calls=mock_calls; assert(!writer.write_data({1,0}) && mock_calls==calls);
  mock_result=0;
  assert(writer.write_address({1,0})); writer.timeout();
  dispatch(ESP_GATTC_WRITE_CHAR_EVT); assert(!writer.success()); // Late acknowledgement
  calls=mock_calls; assert(!writer.write_data({1,0}) && mock_calls==calls);
  assert(writer.write_address({1,0})); dispatch(ESP_GATTC_WRITE_CHAR_EVT);
  assert(writer.success() && writer.write_data({42,0}) && mock_handle==20);
  dispatch(ESP_GATTC_WRITE_CHAR_EVT,20); assert(writer.success());
  calls=mock_calls; assert(!writer.write_data({1,0}) && mock_calls==calls); // Single use
  assert(writer.write_address({1,0})); dispatch(ESP_GATTC_DISCONNECT_EVT);
  assert(writer.done() && !writer.success());
  calls=mock_calls; assert(!writer.write_data({1,0}) && mock_calls==calls);
  writer.configure(&client,"service","address","data");
  // Characteristics that only support writes without response are rejected.
  client.address.properties=4; dispatch(ESP_GATTC_SEARCH_CMPL_EVT);
  assert(!writer.write_address({1,0}) && mock_calls==calls);
}
'''
        with tempfile.TemporaryDirectory() as folder:
            cpp = pathlib.Path(folder) / "writer.cpp"
            binary = pathlib.Path(folder) / "writer"
            cpp.write_text(source)
            subprocess.run(["g++", "-std=c++17", "-DUSE_ESP32", "-Wall", "-Wextra", "-Werror",
                            "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                            "-I" + str(ROOT / "tests/stubs"), "-I" + str(ROOT / "src"),
                            str(cpp), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
