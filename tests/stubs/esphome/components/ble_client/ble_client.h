#pragma once
#include <cstdint>
#include <string>
using esp_gattc_cb_event_t = int;
using esp_gatt_if_t = int;
constexpr int ESP_GATTC_SEARCH_CMPL_EVT=1, ESP_GATTC_WRITE_CHAR_EVT=2, ESP_GATTC_CLOSE_EVT=3, ESP_GATTC_DISCONNECT_EVT=4;
constexpr int ESP_GATT_CHAR_PROP_BIT_WRITE=8, ESP_GATT_OK=0, ESP_OK=0;
constexpr int ESP_GATT_WRITE_TYPE_RSP=1, ESP_GATT_AUTH_REQ_NONE=0;
struct esp_ble_gattc_cb_param_t { struct { int conn_id=7; uint16_t handle=0; int status=0; } write; };
inline int mock_calls=0, mock_result=0;
inline uint16_t mock_handle=0;
inline int esp_ble_gattc_write_char(int,int,uint16_t handle,size_t,uint8_t*,int type,int) {
  ++mock_calls; mock_handle=handle; return type==ESP_GATT_WRITE_TYPE_RSP ? mock_result : -1;
}
namespace esphome {
namespace esp32_ble_tracker {
enum class ClientState { INIT, ESTABLISHED };
struct ESPBTUUID { std::string value; static ESPBTUUID from_raw(const char *v) { return {v}; } };
}
namespace esp32_ble_client { struct BLECharacteristic { uint16_t handle; int properties=8; }; }
namespace ble_client {
class BLEClient;
class BLEClientNode {
 public:
  virtual ~BLEClientNode() = default;
  virtual void gattc_event_handler(esp_gattc_cb_event_t,esp_gatt_if_t,esp_ble_gattc_cb_param_t*)=0;
  BLEClient *parent() { return parent_; }
  BLEClient *parent_=nullptr;
  esp32_ble_tracker::ClientState node_state=esp32_ble_tracker::ClientState::INIT;
};
class BLEClient {
 public:
  esp32_ble_client::BLECharacteristic address{10}, data{20};
  void register_ble_node(BLEClientNode *node) { node->parent_=this; }
  auto *get_characteristic(esp32_ble_tracker::ESPBTUUID, esp32_ble_tracker::ESPBTUUID uuid) {
    return uuid.value=="address" ? &address : &data;
  }
  int get_conn_id() { return 7; }
  int get_gattc_if() { return 1; }
};
}
}
