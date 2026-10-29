#!/usr/bin/env python3
"""Read-only ADB inspection for the Orange/Kaon KSTB7259.

This tool deliberately contains no reboot, wipe, unlock, partition, or flashing
commands.  It writes reports only on the host computer.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

__version__ = "0.1.0"
TARGET_MODEL = "KSTB7259"

# An allowlist avoids publishing the complete getprop output, which can contain
# serial numbers, operator provisioning data, or network identifiers.
PROPERTY_KEYS = (
    "ro.product.manufacturer",
    "ro.product.brand",
    "ro.product.model",
    "ro.product.name",
    "ro.product.device",
    "ro.product.board",
    "ro.product.cpu.abi",
    "ro.product.cpu.abilist",
    "ro.product.characteristics",
    "ro.product.first_api_level",
    "ro.product.vendor.model",
    "ro.product.vendor.device",
    "ro.hardware",
    "ro.hardware.egl",
    "ro.board.platform",
    "ro.soc.model",
    "ro.build.fingerprint",
    "ro.build.id",
    "ro.build.display.id",
    "ro.build.version.release",
    "ro.build.version.sdk",
    "ro.build.version.security_patch",
    "ro.build.type",
    "ro.build.tags",
    "ro.build.ab_update",
    "ro.boot.dynamic_partitions",
    "ro.treble.enabled",
    "ro.vndk.version",
    "ro.debuggable",
    "ro.secure",
    "ro.boot.flash.locked",
    "ro.boot.verifiedbootstate",
    "ro.boot.vbmeta.device_state",
    "ro.boot.slot_suffix",
)

MODEL_PROPERTY_KEYS = (
    "ro.product.model",
    "ro.product.name",
    "ro.product.device",
    "ro.product.vendor.model",
    "ro.product.vendor.device",
)


class AdbError(RuntimeError):
    """An ADB invocation or device-selection problem with a readable message."""


def parse_adb_devices(output: str) -> list[dict[str, str]]:
    """Parse `adb devices` output without mistaking help text for a device."""
    devices: list[dict[str, str]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices") or line.startswith("*"):
            continue
        fields = line.split()
        if len(fields) >= 3 and fields[1:3] == ["no", "permissions"]:
            devices.append({"serial": fields[0], "state": "no permissions"})
        elif len(fields) >= 2 and fields[1] in {
            "device",
            "unauthorized",
            "offline",
            "recovery",
            "sideload",
            "bootloader",
            "authorizing",
            "connecting",
        }:
            devices.append({"serial": fields[0], "state": fields[1]})
    return devices


def parse_getprop(output: str) -> dict[str, str]:
    """Parse Android's [property]: [value] output."""
    properties: dict[str, str] = {}
    for line in output.splitlines():
        match = re.match(r"^\[([^]]+)\]: \[(.*)]$", line.strip())
        if match:
            properties[match.group(1)] = match.group(2)
    return properties


def parse_features(output: str) -> list[str]:
    """Return sorted feature names from `pm list features` output."""
    features = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("feature:"):
            features.append(line.removeprefix("feature:").strip())
    return sorted(set(features))


def tri_state(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "yes" if value else "no"


def property_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    return None


def target_model_detected(properties: dict[str, str | None]) -> bool:
    # Permit separators and surrounding descriptive words, but never match a
    # longer model such as KSTB72590 or an unrelated embedded alphanumeric ID.
    pattern = re.compile(r"(?<![a-z0-9])kstb[\s_-]*7259(?![a-z0-9])", re.IGNORECASE)
    for key in MODEL_PROPERTY_KEYS:
        value = properties.get(key)
        if value and pattern.search(value):
            return True
    return False


def build_observations(
    properties: dict[str, str | None], features: Sequence[str]
) -> dict[str, str]:
    """Describe observed indicators; never turn them into clearance to flash."""
    feature_set = set(features)
    characteristics = (properties.get("ro.product.characteristics") or "").lower()
    is_tv: bool | None
    if feature_set.intersection(
        {"android.software.leanback", "android.hardware.type.television"}
    ) or "television" in characteristics:
        is_tv = True
    elif features or characteristics:
        is_tv = False
    else:
        is_tv = None

    lock_indicator = "unknown"
    flash_locked = property_bool(properties.get("ro.boot.flash.locked"))
    vbmeta_state = (properties.get("ro.boot.vbmeta.device_state") or "").lower()
    if flash_locked is True or vbmeta_state == "locked":
        lock_indicator = "locked"
    elif flash_locked is False or vbmeta_state == "unlocked":
        lock_indicator = "unlocked"

    return {
        "target_model_detected": tri_state(target_model_detected(properties)),
        "android_tv_indicator": tri_state(is_tv),
        "treble_property": (properties.get("ro.treble.enabled") or "unknown"),
        "ab_update_property": (properties.get("ro.build.ab_update") or "unknown"),
        "dynamic_partitions_property": (
            properties.get("ro.boot.dynamic_partitions") or "unknown"
        ),
        "bootloader_lock_indicator": lock_indicator,
        "custom_os_clearance": "not established",
        "note": (
            "These runtime properties do not prove that an unlock method, "
            "recovery path, or compatible Android TV image exists. Do not flash "
            "based on this report."
        ),
    }


class AdbClient:
    """Small ADB wrapper restricted to the read-only commands used below."""

    def __init__(
        self, executable: str = "adb", serial: str | None = None, timeout: int = 30
    ) -> None:
        self.executable = executable
        self.serial = serial
        self.timeout = timeout

    def _run(self, arguments: Sequence[str], targeted: bool = True) -> str:
        command = [self.executable]
        if targeted and self.serial:
            command.extend(["-s", self.serial])
        command.extend(arguments)
        try:
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise AdbError(
                "ADB was not found. Install Google's Android SDK Platform-Tools "
                "and add adb to PATH, or pass --adb /path/to/adb."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"ADB command timed out: {' '.join(arguments)}") from exc
        except OSError as exc:
            raise AdbError(f"Could not execute ADB: {exc}") from exc

        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise AdbError(
                f"ADB command failed ({' '.join(arguments)}): "
                f"{detail or f'exit status {result.returncode}'}"
            )
        return result.stdout

    def select_device(self) -> str:
        devices = parse_adb_devices(self._run(["devices"], targeted=False))
        if self.serial:
            matches = [item for item in devices if item["serial"] == self.serial]
            if not matches:
                raise AdbError(f"The requested ADB device is not visible: {self.serial}")
            selected = matches[0]
            if selected["state"] != "device":
                raise AdbError(
                    f"Device {self.serial} is {selected['state']}, not ready. "
                    "Authorize ADB on the TV and reconnect."
                )
            return self.serial

        ready = [item for item in devices if item["state"] == "device"]
        if len(ready) == 1:
            self.serial = ready[0]["serial"]
            return self.serial
        if len(ready) > 1:
            raise AdbError(
                "More than one Android device is connected. Re-run with "
                "--serial SERIAL (see `adb devices`)."
            )
        if devices:
            states = ", ".join(
                f"{item['serial']}={item['state']}" for item in devices
            )
            raise AdbError(
                f"No device is ready ({states}). Accept the ADB authorization "
                "prompt on the TV, then try again."
            )
        raise AdbError(
            "No ADB device found. Enable ADB debugging on the TV and connect "
            "it before running the inspection."
        )

    def shell(self, *arguments: str) -> str:
        """Run a shell command assembled only from static arguments in this file."""
        return self._run(["shell", *arguments])


def _optional_shell(client: AdbClient, *arguments: str) -> dict[str, str | None]:
    try:
        return {"output": client.shell(*arguments).strip(), "error": None}
    except AdbError as exc:
        return {"output": None, "error": str(exc)}


def collect_report(client: AdbClient) -> dict[str, Any]:
    client.select_device()
    properties_all = parse_getprop(client.shell("getprop"))
    properties = {key: properties_all.get(key) for key in PROPERTY_KEYS}
    features_result = _optional_shell(client, "pm", "list", "features")
    features = parse_features(features_result["output"] or "")

    return {
        "schema_version": 1,
        "tool_version": __version__,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "target_model": TARGET_MODEL,
        "properties": properties,
        "features": features,
        "feature_query_error": features_result["error"],
        "kernel": _optional_shell(client, "uname", "-a"),
        "proc_version": _optional_shell(client, "cat", "/proc/version"),
        "observations": build_observations(properties, features),
        "safety": {
            "device_writes_performed": False,
            "note": (
                "Only getprop, pm list features, uname, and /proc/version were "
                "read. No reboot, wipe, unlock, or flash operation was attempted."
            ),
        },
    }


def _value(properties: dict[str, str | None], key: str) -> str:
    return properties.get(key) or "unknown"


def render_text_report(report: dict[str, Any]) -> str:
    props = report["properties"]
    observations = report["observations"]
    lines = [
        "KSTB7259 Android TV read-only inspection",
        "=========================================",
        f"Created (UTC): {report['created_utc']}",
        "",
        f"Manufacturer:       {_value(props, 'ro.product.manufacturer')}",
        f"Model:              {_value(props, 'ro.product.model')}",
        f"Product/device:     {_value(props, 'ro.product.name')} / "
        f"{_value(props, 'ro.product.device')}",
        f"SoC/board:          {_value(props, 'ro.soc.model')} / "
        f"{_value(props, 'ro.product.board')}",
        f"Android release:    {_value(props, 'ro.build.version.release')} "
        f"(SDK {_value(props, 'ro.build.version.sdk')})",
        f"Security patch:     {_value(props, 'ro.build.version.security_patch')}",
        f"CPU ABI list:       {_value(props, 'ro.product.cpu.abilist')}",
        f"Build fingerprint:  {_value(props, 'ro.build.fingerprint')}",
        "",
        "Observed indicators (not approval to flash):",
        f"  Exact target model:       {observations['target_model_detected']}",
        f"  Android TV indicator:     {observations['android_tv_indicator']}",
        f"  Treble property:          {observations['treble_property']}",
        f"  A/B update property:      {observations['ab_update_property']}",
        f"  Dynamic partitions:       {observations['dynamic_partitions_property']}",
        f"  Bootloader lock property: {observations['bootloader_lock_indicator']}",
        "",
        "CUSTOM OS STATUS: NOT ESTABLISHED",
        observations["note"],
        "",
        "No device data or firmware was changed by this inspection.",
        "Review the JSON report for private build/kernel details before sharing it.",
        "",
    ]
    return "\n".join(lines)


def write_report(report: dict[str, Any], output_directory: Path) -> tuple[Path, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"kstb7259-report-{timestamp}"
    json_path = output_directory / f"{stem}.json"
    text_path = output_directory / f"{stem}.txt"
    # Do not silently replace an earlier report if two runs share a timestamp.
    suffix = 1
    while json_path.exists() or text_path.exists():
        json_path = output_directory / f"{stem}-{suffix}.json"
        text_path = output_directory / f"{stem}-{suffix}.txt"
        suffix += 1
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    text_path.write_text(render_text_report(report), encoding="utf-8")
    return json_path, text_path


def check_adb_executable(executable: str) -> None:
    if shutil.which(executable) is None and not Path(executable).is_file():
        raise AdbError(
            "ADB was not found. Install Google's Android SDK Platform-Tools "
            "and add adb to PATH, or pass --adb /path/to/adb."
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Collect a read-only KSTB7259/Android TV report over ADB. "
            "This program cannot and will not flash firmware."
        )
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser(
        "inspect", help="inspect the connected Android device without modifying it"
    )
    inspect_parser.add_argument(
        "--adb", default="adb", help="ADB executable or path (default: adb)"
    )
    inspect_parser.add_argument(
        "--serial", help="ADB serial from `adb devices` when several devices exist"
    )
    inspect_parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports"),
        help="host directory for reports (default: ./reports)",
    )
    inspect_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="timeout in seconds for each ADB command (default: 30)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.timeout <= 0:
            raise AdbError("--timeout must be greater than zero")
        check_adb_executable(args.adb)
        client = AdbClient(args.adb, args.serial, args.timeout)
        report = collect_report(client)
        json_path, text_path = write_report(report, args.output)
    except (AdbError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(render_text_report(report), end="")
    print(f"JSON report: {json_path}")
    print(f"Text report: {text_path}")
    if report["observations"]["target_model_detected"] != "yes":
        print(
            "WARNING: the connected device did not identify itself as KSTB7259. "
            "Do not use KSTB7259 firmware or instructions on it.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
