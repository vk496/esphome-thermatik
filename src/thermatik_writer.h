#pragma once

#ifdef USE_ESP32
#include "esphome/components/ble_client/ble_client.h"
#include "esphome/components/esp32_ble_client/ble_characteristic.h"
#include "esphome/core/log.h"
#include <vector>

namespace thermatik {

// ESPHome's generic BLE action advances even on a failed GATT write. Keep the
// result here so an unsuccessful address selection can never lead to a DATA write.
class GattWriter final : public esphome::ble_client::BLEClientNode {
 public:
  void configure(esphome::ble_client::BLEClient *parent, const char *service,
                 const char *address, const char *data) {
    service_ = esphome::esp32_ble_tracker::ESPBTUUID::from_raw(service);
    address_ = esphome::esp32_ble_tracker::ESPBTUUID::from_raw(address);
    data_ = esphome::esp32_ble_tracker::ESPBTUUID::from_raw(data);
    node_state = esphome::esp32_ble_tracker::ClientState::INIT;
    parent->register_ble_node(this);
  }

  bool write_address(const std::vector<uint8_t> &value) { return start_(false, value); }
  bool write_data(const std::vector<uint8_t> &value) { return start_(true, value); }
  bool done() const { return state_ != PENDING; }
  bool success() const { return state_ == SUCCESS; }
  void timeout() {
    if (state_ == PENDING) {
      state_ = FAILED;
      address_ready_ = false;
      ESP_LOGW("thermatik", "GATT write acknowledgement timed out: handle=0x%04X", handle_);
    }
  }

  void gattc_event_handler(esp_gattc_cb_event_t event, esp_gatt_if_t,
                          esp_ble_gattc_cb_param_t *param) override {
    if (event == ESP_GATTC_SEARCH_CMPL_EVT) {
      auto *addr = parent()->get_characteristic(service_, address_);
      auto *data = parent()->get_characteristic(service_, data_);
      address_handle_ = addr && (addr->properties & ESP_GATT_CHAR_PROP_BIT_WRITE) ? addr->handle : 0;
      data_handle_ = data && (data->properties & ESP_GATT_CHAR_PROP_BIT_WRITE) ? data->handle : 0;
      node_state = esphome::esp32_ble_tracker::ClientState::ESTABLISHED;
      ESP_LOGI("thermatik", "GATT writer ready: ADDRESS=0x%04X DATA=0x%04X",
               address_handle_, data_handle_);
    } else if (event == ESP_GATTC_WRITE_CHAR_EVT && state_ == PENDING &&
               param->write.conn_id == parent()->get_conn_id() && param->write.handle == handle_) {
      state_ = param->write.status == ESP_GATT_OK ? SUCCESS : FAILED;
      address_ready_ = !writing_data_ && success();
      if (success()) {
        ESP_LOGD("thermatik", "GATT %s acknowledged: handle=0x%04X", writing_data_ ? "DATA" : "ADDRESS", handle_);
      } else {
        ESP_LOGW("thermatik", "GATT %s rejected: handle=0x%04X status=0x%02X",
                 writing_data_ ? "DATA" : "ADDRESS", handle_, static_cast<unsigned>(param->write.status));
      }
    } else if (event == ESP_GATTC_CLOSE_EVT || event == ESP_GATTC_DISCONNECT_EVT) {
      state_ = FAILED;
      address_handle_ = data_handle_ = 0;
      address_ready_ = false;
    }
  }

 protected:
  enum State { IDLE, PENDING, SUCCESS, FAILED } state_{IDLE};
  bool start_(bool data, const std::vector<uint8_t> &value) {
    if (state_ == PENDING) return false;
    state_ = FAILED;
    const bool selected = address_ready_;
    address_ready_ = false;
    if (data && !selected) {
      ESP_LOGW("thermatik", "DATA rejected: no acknowledged ADDRESS selection");
      return false;
    }
    handle_ = data ? data_handle_ : address_handle_;
    if (node_state != esphome::esp32_ble_tracker::ClientState::ESTABLISHED || handle_ == 0 || value.empty()) {
      ESP_LOGW("thermatik", "GATT %s unavailable; command not sent", data ? "DATA" : "ADDRESS");
      return false;
    }
    writing_data_ = data;
    state_ = PENDING;
    const auto status = esp_ble_gattc_write_char(parent()->get_gattc_if(), parent()->get_conn_id(), handle_,
        value.size(), const_cast<uint8_t *>(value.data()), ESP_GATT_WRITE_TYPE_RSP, ESP_GATT_AUTH_REQ_NONE);
    if (status != ESP_OK) {
      state_ = FAILED;
      ESP_LOGW("thermatik", "GATT %s initiation failed: status=%d", data ? "DATA" : "ADDRESS", status);
    }
    return state_ == PENDING;
  }
  esphome::esp32_ble_tracker::ESPBTUUID service_, address_, data_;
  uint16_t address_handle_{0}, data_handle_{0}, handle_{0};
  bool writing_data_{false}, address_ready_{false};
};

inline GattWriter &gatt_writer() {
  static GattWriter writer;
  return writer;
}
}  // namespace thermatik
#endif
