#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <string>

// Protocol behavior recovered from S-Thermatik NEO PROD-2025.11.26.
// See docs/protocol-audit.md for native function addresses and limitations.
namespace thermatik {

enum DiagnosticIndex : size_t {
  DIAG_SEQUENCE,
  DIAG_STARTED_MS,
  DIAG_REPLIES,
  DIAG_MALFORMED,
  DIAG_UNSOLICITED,
  DIAG_TIMEOUTS,
  DIAG_DISCONNECTS,
};
using Diagnostics = std::array<uint32_t, 7>;

inline void begin_transaction(Diagnostics &stats, uint32_t now) {
  ++stats[DIAG_SEQUENCE];
  stats[DIAG_STARTED_MS] = now;
}

struct FirmwareVersion {
  uint8_t major;
  uint8_t minor;
  uint8_t patch;
  uint8_t flags;

  bool valid() const { return major != 0 && major != 0xFF; }
  bool modern_registers() const {
    return major > 1 || (major == 1 && minor >= 15);
  }
  std::string text() const {
    char buffer[40];
    std::snprintf(buffer, sizeof(buffer), "%u.%u.%u", major, minor, patch);
    return buffer;
  }
};

inline FirmwareVersion firmware_version(uint16_t low, uint16_t high) {
  return {static_cast<uint8_t>(high), static_cast<uint8_t>(low >> 8),
          static_cast<uint8_t>(low), static_cast<uint8_t>(high >> 8)};
}

inline int32_t signed_word(uint16_t value) {
  return value < 0x8000U ? value : static_cast<int32_t>(value) - 0x10000;
}

inline const char *controller_status_text(uint16_t value) {
  static const char *const states[] = {
      "Standby", "Ignition", "Rising", "Falling", "Glowing",
      "Chamber flush", "No ignition", "Overheated", "Reducing glow"};
  return value < sizeof(states) / sizeof(states[0]) ? states[value] : "Unknown";
}

inline bool sensor_available(uint16_t status, unsigned channel) {
  return channel < 8 && (status & ((1U << channel) | (1U << (channel + 8)))) == 0;
}

inline const char *relay_function_text(uint16_t value) {
  static const char *const functions[] = {"Off", "Combustion", "Hot thermostat", "Cold thermostat",
      "Differential thermostat", "Timer", "Sezam"};
  return value < 7 ? functions[value] : "Unknown";
}

struct ErrorFlag {
  uint16_t mask;
  const char *text;
};

template<size_t N>
inline std::string describe_flags(uint16_t value, const ErrorFlag (&flags)[N]) {
  std::string result;
  uint16_t unknown = value;
  for (const auto &flag : flags) {
    if ((value & flag.mask) != 0) {
      if (!result.empty()) result += "; ";
      result += flag.text;
      unknown &= static_cast<uint16_t>(~flag.mask);
    }
  }
  if (unknown != 0) {
    char buffer[32];
    std::snprintf(buffer, sizeof(buffer), "Unknown flags 0x%04X", unknown);
    if (!result.empty()) result += "; ";
    result += buffer;
  }
  return result.empty() ? "OK" : result;
}

inline std::string motor_status_text(uint16_t value) {
  static constexpr ErrorFlag flags[] = {
      {0x0001, "Motor configuration wrong"},
      {0x0002, "Motor undercurrent"},
      {0x0004, "Motor overcurrent"},
      {0x0040, "Motor runtime test failed"},
      {0x0080, "Motor runtime test passed"},
  };
  return describe_flags(static_cast<uint16_t>(value & 0x00C7), flags);
}

inline std::string sensor_error_text(uint16_t value) {
  static constexpr ErrorFlag flags[] = {
      {0x0008, "Thermocouple open"},
      {0x0010, "Ambient sensor open"},
      {0x0020, "Board sensor open"},
      {0x0800, "Thermocouple shorted"},
      {0x1000, "Ambient sensor shorted"},
      {0x2000, "Board sensor shorted"},
      {0x4000, "Thermocouple shorted"},
  };
  // Other bits carry controller diagnostics, not app-reported sensor faults.
  return describe_flags(static_cast<uint16_t>(value & 0x7838), flags);
}

}  // namespace thermatik
