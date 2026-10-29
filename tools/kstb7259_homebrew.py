#!/usr/bin/env python3
"""Reversible, ADB-based operator-onboarding bypass for the KSTB7259.

The goal is to use independently installed Android TV apps without completing
Orange's service onboarding.  This does not authenticate Orange TV, unlock paid
channels, root the box, unlock the bootloader, or modify firmware partitions.

Device changes require --apply.  Only per-user package disabling is supported;
package uninstallation is deliberately not implemented.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

if __package__:
    from .kstb7259 import (
        AdbClient,
        AdbError,
        check_adb_executable,
        parse_getprop,
        target_model_detected,
    )
else:  # Direct execution: python3 tools/kstb7259_homebrew.py
    from kstb7259 import (  # type: ignore
        AdbClient,
        AdbError,
        check_adb_executable,
        parse_getprop,
        target_model_detected,
    )

__version__ = "0.1.0"
TARGET_MODEL = "KSTB7259"
DEFAULT_STATE = Path("backups/kstb7259-homebrew-state.json")

FLAUNCHER_PACKAGE = "me.efesser.flauncher"
FLAUNCHER_COMPONENT = f"{FLAUNCHER_PACKAGE}/.MainActivity"
FLAUNCHER_VERSION = "2025.07.001"
FLAUNCHER_URL = (
    "https://github.com/osrosal/flauncher/releases/download/"
    "v2025.07.001/flauncher-universal-release.apk"
)
FLAUNCHER_SHA256 = "8410b07003c3cd25a864f06a0bd5c3b34a0be71af57db5748ba6657d05be66be"
DEFAULT_APK = Path("downloads/flauncher-v2025.07.001-universal.apk")

SETUP_SETTINGS = (
    ("global", "device_provisioned"),
    ("secure", "user_setup_complete"),
    ("secure", "tv_user_setup_complete"),
    ("global", "setup_wizard_has_run"),
)

# These tokens only identify packages for human review.  They do not mean that a
# package is safe to disable.
OPERATOR_TOKENS = ("orange", "quber", "kaon", "suricata")

# Preserve connectivity, remote control, updates, DVB/TV input, DRM and service
# frameworks.  The bypass targets onboarding/home, not the rest of the box.
PROTECTED_PACKAGES = {
    "com.orange.es.conf",
    "com.kaon.orangetvservice",
    "com.kaonmedia.rmsproxy",
    "com.kaonmeida.rmsproxy",  # Spelling present in the older KSTB6130 list.
    "com.kaonmedia.kaonrcuupdater",
    "com.kaon.tv.bluetoothrcupairing",
    "net.quber.tvinput",
    "net.quber.rmsservice",
    "net.quber.updateservice",
    "net.quber.settingservice",
    "net.quber.orangemaintenance",
    "net.quber.quantum",
}
PROTECTED_TOKENS = (
    "bluetooth",
    "rcu",
    "remote",
    "tvinput",
    "tvservice",
    "tuner",
    "dvb",
    "drm",
    "widevine",
    "rms",
    "tr069",
    "update",
    "settingservice",
    "maintenance",
)

PACKAGE_RE = re.compile(r"^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+$")
COMPONENT_RE = re.compile(
    r"^([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)/([A-Za-z0-9_.$-]+)$"
)


class HomebrewError(RuntimeError):
    """A validation, download, state, or device-operation error."""


class HomebrewAdb(AdbClient):
    """Add host-side APK installation to the shared ADB transport."""

    def install_apk(self, apk: Path) -> str:
        return self._run(["install", "-r", str(apk)])


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_packages(output: str) -> list[str]:
    packages = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            package = line.removeprefix("package:").strip()
            if PACKAGE_RE.fullmatch(package):
                packages.append(package)
    return sorted(set(packages))


def canonical_component(value: str) -> str | None:
    match = COMPONENT_RE.fullmatch(value.strip())
    if not match:
        return None
    package, activity = match.groups()
    if activity.startswith("."):
        activity = package + activity
    return f"{package}/{activity}"


def component_package(component: str) -> str:
    return component.split("/", 1)[0]


def parse_components(output: str) -> list[str]:
    components = []
    for token in re.split(r"\s+", output.strip()):
        cleaned = token.strip("{}()[]<>,;\"") if token else ""
        component = canonical_component(cleaned)
        if component and component not in components:
            components.append(component)
    return components


def parse_focused_activity(output: str) -> str | None:
    markers = ("mCurrentFocus", "mFocusedApp", "mResumedActivity", "topResumedActivity")
    for line in output.splitlines():
        if any(marker in line for marker in markers):
            components = parse_components(line)
            if components:
                return components[-1]
    return None


def is_operator_package(package: str) -> bool:
    lowered = package.lower()
    return any(token in lowered for token in OPERATOR_TOKENS)


def protected_reason(package: str) -> str | None:
    lowered = package.lower()
    if lowered in PROTECTED_PACKAGES:
        return "protected TV/remote/update/service component"
    for token in PROTECTED_TOKENS:
        if token in lowered:
            return f"protected token: {token}"
    if package == FLAUNCHER_PACKAGE:
        return "replacement launcher"
    return None


def validate_disable_package(package: str, preferred_home: str) -> None:
    if not PACKAGE_RE.fullmatch(package):
        raise HomebrewError(f"Invalid Android package name: {package}")
    if not is_operator_package(package):
        raise HomebrewError(
            f"Refusing non-operator package {package}; this tool only accepts "
            "Orange/Quber/Kaon/Suricata package names."
        )
    reason = protected_reason(package)
    if reason:
        raise HomebrewError(f"Refusing to disable {package}: {reason}.")
    if package == component_package(preferred_home):
        raise HomebrewError("Refusing to disable the replacement home launcher.")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_launcher(destination: Path = DEFAULT_APK) -> Path:
    """Download the pinned GPL launcher release and verify its pinned digest."""
    if destination.exists():
        actual = sha256_file(destination)
        if actual == FLAUNCHER_SHA256:
            print(f"Verified existing launcher: {destination}")
            return destination
        raise HomebrewError(
            f"Existing APK has the wrong SHA-256: {destination}. Move it away "
            "or choose another --output; it will not be installed."
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    request = urllib.request.Request(
        FLAUNCHER_URL,
        headers={"User-Agent": f"KSTB7259-Homebrew/{__version__}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            with temporary.open("wb") as target:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    target.write(chunk)
        actual = sha256_file(temporary)
        if actual != FLAUNCHER_SHA256:
            temporary.unlink(missing_ok=True)
            raise HomebrewError(
                "Downloaded launcher failed SHA-256 verification. Nothing was installed."
            )
        os.replace(temporary, destination)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        temporary.unlink(missing_ok=True)
        raise HomebrewError(f"Could not download the pinned launcher: {exc}") from exc
    print(f"Downloaded and SHA-256-verified FLauncher {FLAUNCHER_VERSION}: {destination}")
    return destination


def connect_target(client: HomebrewAdb) -> dict[str, str]:
    client.select_device()
    properties = parse_getprop(client.shell("getprop"))
    if not target_model_detected(properties):
        raise HomebrewError(
            "The connected device did not identify itself as KSTB7259. "
            "No operator/home/setup changes are allowed on an unidentified model."
        )
    return properties


def query_home_activities(client: HomebrewAdb) -> list[str]:
    output = client.shell(
        "cmd",
        "package",
        "query-activities",
        "--brief",
        "-a",
        "android.intent.action.MAIN",
        "-c",
        "android.intent.category.HOME",
    )
    return parse_components(output)


def resolve_home_activity(client: HomebrewAdb) -> str | None:
    output = client.shell(
        "cmd",
        "package",
        "resolve-activity",
        "--brief",
        "-a",
        "android.intent.action.MAIN",
        "-c",
        "android.intent.category.HOME",
    )
    components = parse_components(output)
    return components[-1] if components else None


def read_setup_settings(client: HomebrewAdb) -> dict[str, str]:
    values = {}
    for namespace, key in SETUP_SETTINGS:
        values[f"{namespace}/{key}"] = client.shell(
            "settings", "get", namespace, key
        ).strip()
    return values


def read_focused_activity(client: HomebrewAdb) -> str | None:
    try:
        output = client.shell("dumpsys", "window", "windows")
    except AdbError:
        return None
    return parse_focused_activity(output)


def write_scan(report: dict[str, Any], output_directory: Path) -> tuple[Path, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"kstb7259-homebrew-scan-{timestamp}"
    json_path = output_directory / f"{stem}.json"
    text_path = output_directory / f"{stem}.txt"
    suffix = 1
    while json_path.exists() or text_path.exists():
        json_path = output_directory / f"{stem}-{suffix}.json"
        text_path = output_directory / f"{stem}-{suffix}.txt"
        suffix += 1

    lines = [
        "KSTB7259 Orange-onboarding scan (read-only)",
        "=============================================",
        f"Created (UTC): {report['created_utc']}",
        f"Model/device: {report['identity'].get('model')} / "
        f"{report['identity'].get('device')}",
        f"Build: {report['identity'].get('fingerprint')}",
        f"Current HOME: {report.get('current_home')}",
        f"Foreground activity: {report.get('foreground_activity')}",
        "",
        "Setup flags:",
    ]
    for key, value in report["setup_settings"].items():
        lines.append(f"  {key} = {value}")
    lines.extend(["", "HOME activities:"])
    lines.extend(f"  {item}" for item in report["home_activities"])
    lines.extend(
        [
            "",
            "Operator packages for HUMAN REVIEW ONLY (not a disable list):",
        ]
    )
    for package in report["operator_review_packages"]:
        reason = protected_reason(package)
        suffix_text = f"  [PROTECTED: {reason}]" if reason else ""
        disabled = "  [already disabled]" if package in report["disabled_packages"] else ""
        lines.append(f"  {package}{disabled}{suffix_text}")
    lines.extend(
        [
            "",
            "No settings, packages, launcher preferences, or firmware were changed.",
            "The JSON contains your installed-package list; review it before sharing.",
            "",
        ]
    )
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    text_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, text_path


def command_scan(client: HomebrewAdb, output: Path) -> None:
    properties = connect_target(client)
    packages = parse_packages(client.shell("pm", "list", "packages"))
    disabled = parse_packages(client.shell("pm", "list", "packages", "-d"))
    report = {
        "schema_version": 1,
        "created_utc": utc_now(),
        "identity": {
            "model": properties.get("ro.product.model"),
            "device": properties.get("ro.product.device"),
            "fingerprint": properties.get("ro.build.fingerprint"),
            "android_release": properties.get("ro.build.version.release"),
            "sdk": properties.get("ro.build.version.sdk"),
            "abi_list": properties.get("ro.product.cpu.abilist"),
        },
        "current_home": resolve_home_activity(client),
        "foreground_activity": read_focused_activity(client),
        "home_activities": query_home_activities(client),
        "setup_settings": read_setup_settings(client),
        "packages": packages,
        "disabled_packages": disabled,
        "operator_review_packages": [
            package for package in packages if is_operator_package(package)
        ],
        "device_changes_performed": False,
    }
    json_path, text_path = write_scan(report, output)
    print(text_path.read_text(encoding="utf-8"), end="")
    print(f"JSON report: {json_path}")
    print(f"Text report: {text_path}")


def new_state(properties: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "target_model": TARGET_MODEL,
        "device_fingerprint": properties.get("ro.build.fingerprint"),
        "created_utc": utc_now(),
        "packages": {},
        "setup_original": {},
        "history": [],
    }


def load_state(path: Path) -> dict[str, Any]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HomebrewError(f"Rollback state does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise HomebrewError(f"Could not read rollback state {path}: {exc}") from exc
    if state.get("schema_version") != 1 or state.get("target_model") != TARGET_MODEL:
        raise HomebrewError(f"Unrecognized or wrong-model rollback state: {path}")
    if not isinstance(state.get("packages"), dict) or not isinstance(
        state.get("setup_original"), dict
    ):
        raise HomebrewError(f"Corrupt rollback state: {path}")
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def check_state_device(state: dict[str, Any], properties: dict[str, str]) -> None:
    expected = state.get("device_fingerprint")
    actual = properties.get("ro.build.fingerprint")
    if expected and actual and expected != actual:
        print(
            "WARNING: the current build fingerprint differs from the rollback "
            "state. Verify this is the same decoder (an OTA can also change it).",
            file=sys.stderr,
        )


def record_history(state: dict[str, Any], action: str, detail: str = "") -> None:
    state.setdefault("history", []).append(
        {"time_utc": utc_now(), "action": action, "detail": detail}
    )


def require_launcher_state(state: dict[str, Any]) -> str:
    preferred = state.get("preferred_home")
    if not preferred or "original_home" not in state:
        raise HomebrewError(
            "No tested replacement-home step is recorded. Run install-launcher "
            "and then set-launcher before skip-setup or disable."
        )
    return preferred


def ensure_preferred_home_available(client: HomebrewAdb, preferred: str) -> None:
    if preferred not in query_home_activities(client):
        raise HomebrewError(
            f"The replacement HOME activity is not installed/enabled: {preferred}. "
            "Reinstall it before changing Orange components."
        )


def start_component(client: HomebrewAdb, component: str) -> None:
    client.shell("am", "start", "-n", component)


def command_install_launcher(client: HomebrewAdb, apk: Path, apply: bool) -> None:
    if not apply:
        print(
            "DRY RUN: would verify the pinned FLauncher APK, install it with "
            "`adb install -r`, and open it for testing. No default home or "
            "Orange package would be changed. Re-run with --apply."
        )
        return
    connect_target(client)  # Require the exact model before installing anything.
    verified_apk = download_launcher(apk)
    result = client.install_apk(verified_apk)
    if "Success" not in result:
        raise HomebrewError(f"APK installation did not report Success: {result.strip()}")
    preferred = canonical_component(FLAUNCHER_COMPONENT)
    assert preferred is not None
    ensure_preferred_home_available(client, preferred)
    start_component(client, FLAUNCHER_COMPONENT)
    print(
        "FLauncher was installed and opened. Test D-pad navigation, Back, Apps, "
        "and Android Settings now. Do not continue unless it works. Next run "
        "the set-launcher command; Orange setup/packages are still unchanged."
    )


def command_set_launcher(
    client: HomebrewAdb, state_path: Path, apply: bool
) -> None:
    properties = connect_target(client)
    preferred = canonical_component(FLAUNCHER_COMPONENT)
    assert preferred is not None
    ensure_preferred_home_available(client, preferred)
    current = resolve_home_activity(client)
    print(f"Current HOME: {current}")
    print(f"Requested replacement HOME: {preferred}")
    if not apply:
        print("DRY RUN: no preference or rollback state was changed. Use --apply.")
        return

    if state_path.exists():
        state = load_state(state_path)
        check_state_device(state, properties)
    else:
        state = new_state(properties)
    state.setdefault("original_home", current)
    state["preferred_home"] = preferred
    record_history(state, "set-home-request", f"{current} -> {preferred}")
    save_state(state_path, state)  # Save rollback data before changing Android.

    result = client.shell(
        "cmd",
        "package",
        "set-home-activity",
        "--user",
        "0",
        FLAUNCHER_COMPONENT,
    )
    if re.search(r"(?i)(unknown command|exception|permission denial|securityexception)", result):
        raise HomebrewError(f"Could not set replacement HOME: {result.strip()}")
    resolved = resolve_home_activity(client)
    record_history(state, "set-home-result", f"resolver={resolved}; output={result.strip()}")
    save_state(state_path, state)
    start_component(client, FLAUNCHER_COMPONENT)
    print(f"Rollback state: {state_path}")
    if resolved == preferred:
        print("Android now resolves HOME to FLauncher.")
    else:
        print(
            f"WARNING: Android still reports HOME as {resolved}. FLauncher was "
            "opened directly and remains available as a fallback. Continue only "
            "if you can see and operate it; a later Orange-home disable step may "
            "be needed. Do not disable any Google/Android settings package."
        )


def command_skip_setup(client: HomebrewAdb, state_path: Path, apply: bool) -> None:
    properties = connect_target(client)
    state = load_state(state_path)
    check_state_device(state, properties)
    preferred = require_launcher_state(state)
    ensure_preferred_home_available(client, preferred)
    current = read_setup_settings(client)
    print("Current setup flags:")
    for key, value in current.items():
        print(f"  {key} = {value}")
    if not apply:
        print("DRY RUN: would set these four flags to 1 and preserve old values.")
        return

    for key, value in current.items():
        state["setup_original"].setdefault(key, value)
    record_history(state, "skip-setup-request")
    save_state(state_path, state)
    for namespace, key in SETUP_SETTINGS:
        client.shell("settings", "put", namespace, key, "1")
    observed = read_setup_settings(client)
    wrong_values = {
        key: value for key, value in observed.items() if value != "1"
    }
    record_history(state, "skip-setup-result", f"observed={observed}")
    save_state(state_path, state)
    if wrong_values:
        raise HomebrewError(
            f"Setup flags did not remain at 1: {wrong_values}. Use rollback "
            f"with state {state_path}; do not disable setup packages at random."
        )
    start_component(client, FLAUNCHER_COMPONENT)
    print(
        "Android setup-completion flags were set to 1 and FLauncher was opened. "
        "Test Home, Back, Settings and a manual reboot. If Orange's login wall "
        "returns, run scan while the wall is visible and identify its foreground "
        "package; do not disable packages randomly."
    )


def command_disable(
    client: HomebrewAdb, state_path: Path, packages: Sequence[str], apply: bool
) -> None:
    properties = connect_target(client)
    state = load_state(state_path)
    check_state_device(state, properties)
    preferred = require_launcher_state(state)
    ensure_preferred_home_available(client, preferred)
    installed = parse_packages(client.shell("pm", "list", "packages"))
    already_disabled = set(parse_packages(client.shell("pm", "list", "packages", "-d")))

    unique_packages = list(dict.fromkeys(packages))
    for package in unique_packages:
        validate_disable_package(package, preferred)
        if package not in installed:
            raise HomebrewError(
                f"Package is not present on this KSTB7259: {package}. Do not copy "
                "package names from another model; run scan and use its report."
            )

    pending = [package for package in unique_packages if package not in already_disabled]
    print(f"Replacement HOME fallback: {preferred}")
    print("Packages requested for per-user disabling:")
    for package in unique_packages:
        status = "already disabled; skip" if package in already_disabled else "pending"
        print(f"  {package}: {status}")
    if not apply:
        print(
            "DRY RUN: nothing was disabled. Only `pm disable-user --user 0` "
            "would be used with --apply; uninstall is not supported."
        )
        return

    for package in pending:
        state["packages"].setdefault(package, {"was_disabled": False})
        record_history(state, "disable-request", package)
        save_state(state_path, state)  # Log before each individual change.
        try:
            client.shell("pm", "disable-user", "--user", "0", package)
        except AdbError as exc:
            raise HomebrewError(
                f"Could not disable {package}: {exc}. No uninstall fallback was "
                f"attempted. Use rollback with state {state_path}."
            ) from exc
        disabled_now = set(parse_packages(client.shell("pm", "list", "packages", "-d")))
        if package not in disabled_now:
            raise HomebrewError(
                f"{package} did not remain disabled. It may be protected or "
                "automatically re-enabled. No uninstall fallback was attempted. "
                f"Use rollback with state {state_path}."
            )
        record_history(state, "disable-result", package)
        save_state(state_path, state)

    start_component(client, FLAUNCHER_COMPONENT)
    print(
        "Requested packages were disabled only for Android user 0 and FLauncher "
        "was opened. Test navigation, Wi-Fi/Ethernet, Bluetooth remote, TDT if "
        "needed, and a manual reboot. Orange IPTV/authentication is not bypassed "
        "for content access. Keep the rollback state safe."
    )


def command_rollback(client: HomebrewAdb, state_path: Path, apply: bool) -> None:
    state = load_state(state_path)
    print("Rollback plan:")
    print(f"  Re-enable {len(state['packages'])} package(s) changed by this tool")
    print(f"  Restore HOME to: {state.get('original_home')}")
    print(f"  Restore {len(state['setup_original'])} setup flag(s)")
    print("  FLauncher remains installed; it is not uninstalled by rollback")
    if not apply:
        print("DRY RUN: no device changes were made. Use --apply to roll back.")
        return

    properties = connect_target(client)
    check_state_device(state, properties)
    errors = []
    for package, details in reversed(list(state["packages"].items())):
        if details.get("was_disabled"):
            continue
        try:
            client.shell("pm", "enable", "--user", "0", package)
            disabled_now = parse_packages(client.shell("pm", "list", "packages", "-d"))
            if package in disabled_now:
                raise HomebrewError(f"{package} is still disabled")
            record_history(state, "rollback-enable", package)
            save_state(state_path, state)
        except (AdbError, HomebrewError) as exc:
            errors.append(f"enable {package}: {exc}")

    original_home = state.get("original_home")
    if original_home:
        try:
            if original_home not in query_home_activities(client):
                raise HomebrewError(
                    f"Original HOME is not available after re-enabling: {original_home}"
                )
            client.shell(
                "cmd",
                "package",
                "set-home-activity",
                "--user",
                "0",
                original_home,
            )
            resolved = resolve_home_activity(client)
            if resolved != original_home:
                raise HomebrewError(
                    f"HOME resolver is {resolved}, not requested {original_home}"
                )
            record_history(state, "rollback-home", original_home)
            save_state(state_path, state)
        except (AdbError, HomebrewError) as exc:
            errors.append(f"restore HOME: {exc}")

    for key, value in state["setup_original"].items():
        namespace, setting = key.split("/", 1)
        try:
            if value == "null":
                client.shell("settings", "delete", namespace, setting)
            else:
                client.shell("settings", "put", namespace, setting, value)
            observed = client.shell("settings", "get", namespace, setting).strip()
            if (value == "null" and observed not in {"null", ""}) or (
                value != "null" and observed != value
            ):
                raise HomebrewError(
                    f"{key} is {observed}, expected original value {value}"
                )
            record_history(state, "rollback-setting", f"{key}={value}")
            save_state(state_path, state)
        except (AdbError, HomebrewError) as exc:
            errors.append(f"restore {key}: {exc}")

    record_history(state, "rollback-complete", "; ".join(errors))
    save_state(state_path, state)
    if errors:
        raise HomebrewError(
            "Rollback finished with errors; all steps were attempted:\n- "
            + "\n- ".join(errors)
        )
    print(
        "Rollback completed. Press Home and test the Orange system. FLauncher "
        "is still installed but no packages or setup values changed by this "
        "tool should remain modified."
    )


def add_adb_arguments(
    parser: argparse.ArgumentParser, include_state: bool = True
) -> None:
    parser.add_argument("--adb", default="adb", help="ADB executable or path")
    parser.add_argument("--serial", help="ADB serial when several devices exist")
    parser.add_argument(
        "--timeout", type=int, default=120, help="per-command timeout (default: 120s)"
    )
    if include_state:
        parser.add_argument(
            "--state", type=Path, default=DEFAULT_STATE, help="rollback-state JSON path"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Use a KSTB7259 without Orange onboarding via a replacement launcher, "
            "reversible setup flags, and per-user package disabling. No paid-content "
            "access, root, firmware flashing, or bootloader unlock."
        )
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="read-only package/HOME/setup report")
    scan.add_argument("--adb", default="adb")
    scan.add_argument("--serial")
    scan.add_argument("--timeout", type=int, default=60)
    scan.add_argument("--output", type=Path, default=Path("reports"))

    download = subparsers.add_parser(
        "download-launcher", help="download and verify pinned FLauncher on the host"
    )
    download.add_argument("--output", type=Path, default=DEFAULT_APK)

    install = subparsers.add_parser(
        "install-launcher", help="install/open FLauncher; requires --apply"
    )
    add_adb_arguments(install, include_state=False)
    install.add_argument("--apk", type=Path, default=DEFAULT_APK)
    install.add_argument("--apply", action="store_true")

    set_launcher = subparsers.add_parser(
        "set-launcher", help="record old HOME and prefer FLauncher; requires --apply"
    )
    add_adb_arguments(set_launcher)
    set_launcher.add_argument("--apply", action="store_true")

    skip = subparsers.add_parser(
        "skip-setup", help="set Android setup flags with rollback; requires --apply"
    )
    add_adb_arguments(skip)
    skip.add_argument("--apply", action="store_true")

    disable = subparsers.add_parser(
        "disable", help="disable named operator packages for user 0 only"
    )
    add_adb_arguments(disable)
    disable.add_argument("packages", nargs="+", metavar="PACKAGE")
    disable.add_argument("--apply", action="store_true")

    rollback = subparsers.add_parser(
        "rollback", help="undo package/setup/HOME changes recorded in state"
    )
    add_adb_arguments(rollback)
    rollback.add_argument("--apply", action="store_true")
    return parser


def make_client(args: argparse.Namespace) -> HomebrewAdb:
    if args.timeout <= 0:
        raise HomebrewError("--timeout must be greater than zero")
    check_adb_executable(args.adb)
    return HomebrewAdb(args.adb, args.serial, args.timeout)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "download-launcher":
            download_launcher(args.output)
            return 0
        client = make_client(args)
        if args.command == "scan":
            command_scan(client, args.output)
        elif args.command == "install-launcher":
            command_install_launcher(client, args.apk, args.apply)
        elif args.command == "set-launcher":
            command_set_launcher(client, args.state, args.apply)
        elif args.command == "skip-setup":
            command_skip_setup(client, args.state, args.apply)
        elif args.command == "disable":
            command_disable(client, args.state, args.packages, args.apply)
        elif args.command == "rollback":
            command_rollback(client, args.state, args.apply)
        else:  # pragma: no cover - argparse prevents this.
            raise HomebrewError(f"Unknown command: {args.command}")
    except (AdbError, HomebrewError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
