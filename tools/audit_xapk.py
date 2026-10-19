#!/usr/bin/env python3
"""Identify a supplied XAPK and compare a retained app inventory with the header.

Uses Python's standard library. Does not launch the app, download tools, or
contact a controller. --extract-dir writes only libapp-<ABI>.so and manifest.json.
The register inventory is retained analysis evidence, not an automatic decompiler.
"""
import argparse
import hashlib
import io
import json
import pathlib
import re
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xapk", type=pathlib.Path)
    parser.add_argument("--extract-dir", type=pathlib.Path)
    parser.add_argument("--inventory", type=pathlib.Path, default=ROOT / "docs/app-registers.json")
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text())
    header = (ROOT / "src/ble_values.h").read_text()
    header_pairs = {(re.sub(r"_0x[0-9A-Fa-f]+$", "", name), int(value, 16))
                    for name, value in re.findall(r'\{"([^"]+)", 0x([0-9A-Fa-f]+)\}', header)}
    app_pairs = {(r["name"], int(r["address"], 16)) for r in inventory["registers"]}
    report = {"xapk_sha256": hashlib.sha256(args.xapk.read_bytes()).hexdigest()}
    with zipfile.ZipFile(args.xapk) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        report["package"] = manifest["package_name"]
        report["version_name"] = manifest["version_name"]
        report["version_code"] = manifest["version_code"]
        report["native_payloads"] = []
        for member in archive.namelist():
            if not member.endswith(".apk"):
                continue
            with zipfile.ZipFile(io.BytesIO(archive.read(member))) as apk:
                for native in apk.namelist():
                    match = re.fullmatch(r"lib/([A-Za-z0-9_-]+)/libapp\.so", native)
                    if not match:
                        continue
                    data = apk.read(native)
                    report["native_payloads"].append({"abi": match[1], "sha256": hashlib.sha256(data).hexdigest()})
                    if args.extract_dir:
                        args.extract_dir.mkdir(parents=True, exist_ok=True)
                        (args.extract_dir / ("libapp-" + match[1] + ".so")).write_bytes(data)
        if args.extract_dir:
            (args.extract_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    report["retained_inventory_matches_artifact"] = any(
        p["sha256"] == inventory["libapp_arm64_sha256"] for p in report["native_payloads"])
    report["native_property_initializer_count"] = inventory.get("native_property_initializer_count")
    report["inventory_register_count"] = len(app_pairs)
    report["missing_from_header"] = sorted((n, hex(a)) for n, a in app_pairs - header_pairs)
    report["extra_in_header"] = sorted((n, hex(a)) for n, a in header_pairs - app_pairs)
    print(json.dumps(report, indent=2))
    # ARM32 identity is printed but requires separate analysis, not the ARM64 inventory.
    if not report["retained_inventory_matches_artifact"]:
        parser.exit(2, "This payload is not the audited ARM64 artifact; decompile it before claiming compatibility.\n")
    if app_pairs != header_pairs:
        parser.exit(1, "Register inventory differs from src/ble_values.h.\n")


if __name__ == "__main__":
    main()
