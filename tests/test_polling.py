"""Polling schedule regressions: priority registers stay fast, nothing is starved or padded.

Run: python3 -m unittest discover -s tests -v (requires PyYAML and g++).
No network access or device operations are performed.
"""
import pathlib
import re
import subprocess
import tempfile
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHUNK = 5  # registers per controller read


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor("!lambda", lambda loader, node: loader.construct_scalar(node))


def load_package():
    return yaml.load((ROOT / "package.yaml").read_text(), Loader=Loader)


def keys_of(config, global_id):
    text = next(g for g in config["globals"] if g["id"] == global_id)["initial_value"]
    return [k.replace("${FiringModeAttr}", "auto") for k in re.findall(r'"([^"]+)"', text)]


class PollScheduleTests(unittest.TestCase):
    def test_scheduler(self):
        source = r'''
#include <cassert>
#include <set>
#include "thermatik_protocol.h"
using V = std::vector<std::string>;
int main() {
  const V priority{"p1", "p2", "p3"};
  const V rotating{"r1", "r2", "r3", "r4", "r5", "r6", "r7"};
  size_t offset = 0;
  // Priority registers are in every cycle; the rotating ones are covered in order, wrapping.
  auto a = thermatik::build_poll_cycle(priority, rotating, offset, 5);
  assert((a == V{"r1", "r2", "r3", "r4", "r5", "p1", "p2", "p3"}) && offset == 5);
  auto b = thermatik::build_poll_cycle(priority, rotating, offset, 5);
  assert((b == V{"r6", "r7", "r1", "r2", "r3", "p1", "p2", "p3"}) && offset == 3);
  std::set<std::string> seen;
  for (int i = 0; i < 4; ++i)
    for (const auto &k : thermatik::build_poll_cycle(priority, rotating, offset, 5)) seen.insert(k);
  assert(seen.size() == priority.size() + rotating.size());
  // Degenerate lists never loop, crash or duplicate.
  size_t o = 99;
  assert(thermatik::build_poll_cycle(priority, {}, o) == priority);
  o = 0; auto c = thermatik::build_poll_cycle({}, {"x", "y"}, o, 5);
  assert((c == V{"x", "y"}) && o == 0);  // slice larger than the list: each register once
  o = 99; c = thermatik::build_poll_cycle({}, {"x", "y"}, o, 5);
  assert((c == V{"y", "x"}) && o == 1);  // stale offsets are folded back into range
  o = 0; assert(thermatik::build_poll_cycle({}, {}, o).empty());
}
'''
        with tempfile.TemporaryDirectory() as folder:
            cpp = pathlib.Path(folder) / "poll.cpp"
            binary = pathlib.Path(folder) / "poll"
            cpp.write_text(source)
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
                            "-I" + str(ROOT / "src"), str(cpp), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)

    def test_package_register_lists(self):
        config = load_package()
        priority = keys_of(config, "priority_batches")
        rotating = keys_of(config, "rotating_batches")
        # A cycle of exactly two controller reads: the second would otherwise be padded with
        # unrelated registers, wasting a ~2 s round trip (and was how this regressed before).
        self.assertEqual(len(priority), CHUNK)
        self.assertEqual(len(rotating) % CHUNK, 0)
        self.assertEqual(len(priority + rotating) % CHUNK, 0)
        self.assertFalse(set(priority) & set(rotating), "a register must not be both priority and rotating")
        self.assertEqual(len(set(rotating)), len(rotating))
        self.assertEqual(rotating[0], "cSensorStatus", "availability flags must precede the temperatures")
        receive = next(s["lambda"] for s in config["sensor"] if s.get("id") == "read_ble_characteristic")
        header = (ROOT / "src/ble_values.h").read_text()
        for key in priority + rotating:
            self.assertIn('"%s" == target_batch' % key.replace("auto", "${FiringModeAttr}"), receive,
                          key + " is polled but never decoded")
            if key != "auto":
                self.assertIn('"%s"' % key, header, key + " has no register address")

    def test_scheduling_structure(self):
        config = load_package()
        scripts = {s["id"]: s for s in config["script"]}
        tick = next(i for i in config["interval"] if i["interval"] == "${fetch_interval}")
        self.assertIn("poll_due", yaml.dump(tick["then"]), "the tick must request a cycle, not be dropped")
        # One long-running loop paced by poll_due: a slow cycle is followed straight away.
        loop = scripts["process_batches"]["then"][0]["while"]
        self.assertIn("connected", yaml.dump(loop["condition"]))
        self.assertIn("poll_due", yaml.dump(loop["then"][0]))
        # A user write must interrupt the controller settle delay, not wait it out.
        read = scripts["read_batch_values"]["then"]
        settle = [s for s in read if "wait_until" in s and s["wait_until"].get("timeout") == "${ble_read_settle}"]
        self.assertEqual(len(settle), 1)
        self.assertIn("is_writing_user", yaml.dump(settle[0]["wait_until"]["condition"]))
        self.assertFalse([s for s in read if s.get("delay") == "${ble_read_settle}"], "settle must not be a fixed delay")
        # Optimistic controls are only safe if every failure path restores them.
        for name in ("abort_ble_transaction",):
            self.assertIn("revert_pending_write", yaml.dump(scripts[name]["then"]))
        self.assertIn("revert_pending_write", yaml.dump(config["ble_client"][0]["on_disconnect"]))


if __name__ == "__main__":
    unittest.main()
