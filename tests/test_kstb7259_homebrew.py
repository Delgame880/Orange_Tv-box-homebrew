import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.kstb7259_homebrew import (
    FLAUNCHER_COMPONENT,
    FLAUNCHER_PACKAGE,
    HomebrewError,
    canonical_component,
    command_disable,
    command_install_launcher,
    command_rollback,
    command_scan,
    command_set_launcher,
    command_skip_setup,
    download_launcher,
    is_operator_package,
    parse_components,
    parse_focused_activity,
    parse_packages,
    protected_reason,
    sha256_file,
    validate_disable_package,
)

ORANGE_HOME = "com.orange.es.stb/com.orange.es.stb.MainActivity"
FLAUNCHER_HOME = "me.efesser.flauncher/me.efesser.flauncher.MainActivity"


class ParserAndPolicyTests(unittest.TestCase):
    def test_parse_packages(self):
        output = "package:com.orange.es.stb\npackage:me.efesser.flauncher\ninvalid\n"
        self.assertEqual(
            parse_packages(output), ["com.orange.es.stb", "me.efesser.flauncher"]
        )

    def test_component_normalization(self):
        self.assertEqual(canonical_component(FLAUNCHER_COMPONENT), FLAUNCHER_HOME)
        self.assertEqual(canonical_component(FLAUNCHER_HOME), FLAUNCHER_HOME)
        self.assertIsNone(canonical_component("not-a-component"))
        self.assertIsNone(canonical_component("com.example;rm/.Main"))

    def test_parse_home_query(self):
        output = """priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=true
com.orange.es.stb/.MainActivity
me.efesser.flauncher/.MainActivity
"""
        self.assertEqual(
            parse_components(output), [ORANGE_HOME, FLAUNCHER_HOME]
        )

    def test_parse_focused_activity_with_window_braces(self):
        output = (
            "mCurrentFocus=Window{abc123 u0 "
            "net.quber.orangeftu/.LoginActivity}\n"
        )
        self.assertEqual(
            parse_focused_activity(output),
            "net.quber.orangeftu/net.quber.orangeftu.LoginActivity",
        )

    def test_operator_and_protected_classification(self):
        self.assertTrue(is_operator_package("net.quber.orangeftu"))
        self.assertFalse(is_operator_package("com.android.settings"))
        self.assertIsNotNone(protected_reason("net.quber.tvinput"))
        self.assertIsNotNone(protected_reason("com.kaon.tv.bluetoothrcupairing"))
        self.assertIsNone(protected_reason("net.quber.orangeftu"))

    def test_disable_policy_accepts_only_unprotected_operator_packages(self):
        validate_disable_package("net.quber.orangeftu", FLAUNCHER_HOME)
        validate_disable_package("com.kaon.orangecheckservice", FLAUNCHER_HOME)
        for package in (
            "com.android.settings",
            "net.quber.tvinput",
            "com.kaon.tv.bluetoothrcupairing",
            FLAUNCHER_PACKAGE,
            "invalid;package",
        ):
            with self.subTest(package=package), self.assertRaises(HomebrewError):
                validate_disable_package(package, FLAUNCHER_HOME)

    def test_sha256_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.bin"
            path.write_bytes(b"abc")
            self.assertEqual(
                sha256_file(path),
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            )

    def test_existing_launcher_hash_is_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "launcher.apk"
            path.write_bytes(b"trusted-test-content")
            digest = sha256_file(path)
            with mock.patch(
                "tools.kstb7259_homebrew.FLAUNCHER_SHA256", digest
            ):
                self.assertEqual(download_launcher(path), path)
            with mock.patch("tools.kstb7259_homebrew.FLAUNCHER_SHA256", "0" * 64):
                with self.assertRaisesRegex(HomebrewError, "wrong SHA-256"):
                    download_launcher(path)


class FakeHomebrewAdb:
    """Stateful Android 12 user-0 package/settings/HOME simulation."""

    def __init__(self):
        self.fingerprint = "Kaon/KSTB7259/suricata2:12/TEST/1:user/release-keys"
        self.packages = {
            "com.orange.es.stb",
            "com.kaon.orangecheckservice",
            "com.kaon.orangetvservice",
            "com.kaon.tv.bluetoothrcupairing",
            "net.quber.orangeftu",
            "net.quber.orangesetupcustomizer",
            "net.quber.tvinput",
            "me.efesser.flauncher",
        }
        self.disabled = set()
        self.home_packages = {"com.orange.es.stb", FLAUNCHER_PACKAGE}
        self.current_home = ORANGE_HOME
        self.settings = {
            "global/device_provisioned": "0",
            "secure/user_setup_complete": "0",
            "secure/tv_user_setup_complete": "null",
            "global/setup_wizard_has_run": "null",
        }
        self.calls = []
        self.device_writes = []
        self.started = []
        self.serial = None

    def select_device(self):
        self.serial = "fake-device"
        return self.serial

    def install_apk(self, apk):
        self.device_writes.append(("install", str(apk)))
        return "Success\n"

    @staticmethod
    def _package_output(packages):
        return "".join(f"package:{package}\n" for package in sorted(packages))

    def _home_candidates(self):
        candidates = []
        if "com.orange.es.stb" not in self.disabled:
            candidates.append(ORANGE_HOME)
        if FLAUNCHER_PACKAGE not in self.disabled:
            candidates.append(FLAUNCHER_HOME)
        return candidates

    def shell(self, *arguments):
        self.calls.append(arguments)
        if arguments == ("getprop",):
            return (
                "[ro.product.model]: [KSTB7259]\n"
                "[ro.product.device]: [suricata2]\n"
                f"[ro.build.fingerprint]: [{self.fingerprint}]\n"
                "[ro.build.version.release]: [12]\n"
                "[ro.build.version.sdk]: [31]\n"
                "[ro.product.cpu.abilist]: [arm64-v8a,armeabi-v7a]\n"
            )
        if arguments == ("pm", "list", "packages"):
            return self._package_output(self.packages)
        if arguments == ("pm", "list", "packages", "-d"):
            return self._package_output(self.disabled)
        if arguments[:4] == (
            "cmd",
            "package",
            "query-activities",
            "--brief",
        ):
            return "\n".join(self._home_candidates()) + "\n"
        if arguments[:4] == (
            "cmd",
            "package",
            "resolve-activity",
            "--brief",
        ):
            if self.current_home in self._home_candidates():
                return self.current_home + "\n"
            candidates = self._home_candidates()
            return (candidates[0] if candidates else "No activity found") + "\n"
        if arguments[:4] == ("cmd", "package", "set-home-activity", "--user"):
            component = canonical_component(arguments[-1])
            self.current_home = component
            self.device_writes.append(("set-home", component))
            return "Success\n"
        if arguments[:3] == ("settings", "get", "global") or arguments[:3] == (
            "settings",
            "get",
            "secure",
        ):
            return self.settings[f"{arguments[2]}/{arguments[3]}"] + "\n"
        if arguments[:3] == ("settings", "put", "global") or arguments[:3] == (
            "settings",
            "put",
            "secure",
        ):
            key = f"{arguments[2]}/{arguments[3]}"
            self.settings[key] = arguments[4]
            self.device_writes.append(("setting", key, arguments[4]))
            return ""
        if arguments[:3] == ("settings", "delete", "global") or arguments[:3] == (
            "settings",
            "delete",
            "secure",
        ):
            key = f"{arguments[2]}/{arguments[3]}"
            self.settings[key] = "null"
            self.device_writes.append(("setting-delete", key))
            return ""
        if arguments[:3] == ("pm", "disable-user", "--user"):
            package = arguments[-1]
            self.disabled.add(package)
            self.device_writes.append(("disable", package))
            if self.current_home and self.current_home.startswith(package + "/"):
                self.current_home = FLAUNCHER_HOME
            return f"Package {package} new state: disabled-user\n"
        if arguments[:3] == ("pm", "enable", "--user"):
            package = arguments[-1]
            self.disabled.discard(package)
            self.device_writes.append(("enable", package))
            return f"Package {package} new state: enabled\n"
        if arguments[:3] == ("am", "start", "-n"):
            self.started.append(arguments[-1])
            return "Status: ok\n"
        if arguments == ("dumpsys", "window", "windows"):
            return "mCurrentFocus=Window{abc u0 net.quber.orangeftu/.LoginActivity}\n"
        raise AssertionError(f"Unexpected ADB shell command: {arguments}")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state_path = self.root / "state.json"
        self.client = FakeHomebrewAdb()

    def tearDown(self):
        self.temporary.cleanup()

    def prepare_launcher(self):
        command_set_launcher(self.client, self.state_path, apply=True)
        self.client.device_writes.clear()

    def test_install_launcher_dry_run_has_no_side_effects(self):
        command_install_launcher(self.client, self.root / "launcher.apk", apply=False)
        self.assertEqual(self.client.calls, [])
        self.assertEqual(self.client.device_writes, [])

    def test_install_launcher_apply_installs_and_opens(self):
        apk = self.root / "verified-launcher.apk"
        with mock.patch(
            "tools.kstb7259_homebrew.download_launcher", return_value=apk
        ):
            command_install_launcher(self.client, apk, apply=True)
        self.assertIn(("install", str(apk)), self.client.device_writes)
        self.assertIn(FLAUNCHER_COMPONENT, self.client.started)

    def test_scan_is_read_only_and_identifies_wall(self):
        command_scan(self.client, self.root / "reports")
        self.assertEqual(self.client.device_writes, [])
        reports = list((self.root / "reports").glob("*.json"))
        self.assertEqual(len(reports), 1)
        report = json.loads(reports[0].read_text(encoding="utf-8"))
        self.assertEqual(
            report["foreground_activity"],
            "net.quber.orangeftu/net.quber.orangeftu.LoginActivity",
        )
        self.assertIn("net.quber.orangeftu", report["operator_review_packages"])
        self.assertFalse(report["device_changes_performed"])

    def test_set_launcher_records_original_home(self):
        self.prepare_launcher()
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["original_home"], ORANGE_HOME)
        self.assertEqual(state["preferred_home"], FLAUNCHER_HOME)
        self.assertEqual(self.client.current_home, FLAUNCHER_HOME)

    def test_skip_setup_and_full_rollback(self):
        self.prepare_launcher()
        command_skip_setup(self.client, self.state_path, apply=True)
        self.assertTrue(all(value == "1" for value in self.client.settings.values()))
        command_disable(
            self.client,
            self.state_path,
            ["net.quber.orangeftu", "com.kaon.orangecheckservice"],
            apply=True,
        )
        self.assertIn("net.quber.orangeftu", self.client.disabled)
        self.assertIn("com.kaon.orangecheckservice", self.client.disabled)

        command_rollback(self.client, self.state_path, apply=True)
        self.assertEqual(self.client.disabled, set())
        self.assertEqual(self.client.current_home, ORANGE_HOME)
        self.assertEqual(
            self.client.settings,
            {
                "global/device_provisioned": "0",
                "secure/user_setup_complete": "0",
                "secure/tv_user_setup_complete": "null",
                "global/setup_wizard_has_run": "null",
            },
        )

    def test_disable_dry_run_does_not_change_device(self):
        self.prepare_launcher()
        command_disable(
            self.client, self.state_path, ["net.quber.orangeftu"], apply=False
        )
        self.assertEqual(self.client.disabled, set())
        self.assertEqual(self.client.device_writes, [])

    def test_protected_and_missing_packages_are_refused(self):
        self.prepare_launcher()
        for package in ("net.quber.tvinput", "net.quber.doesnotexist"):
            with self.subTest(package=package), self.assertRaises(HomebrewError):
                command_disable(self.client, self.state_path, [package], apply=True)
        self.assertEqual(self.client.disabled, set())

    def test_disable_requires_launcher_workflow_first(self):
        with self.assertRaisesRegex(HomebrewError, "Rollback state"):
            command_skip_setup(self.client, self.state_path, apply=True)
        self.assertEqual(self.client.device_writes, [])

    def test_rollback_dry_run_does_not_connect(self):
        self.prepare_launcher()
        command_disable(
            self.client, self.state_path, ["net.quber.orangeftu"], apply=True
        )
        self.client.device_writes.clear()
        command_rollback(self.client, self.state_path, apply=False)
        self.assertIn("net.quber.orangeftu", self.client.disabled)
        self.assertEqual(self.client.device_writes, [])


if __name__ == "__main__":
    unittest.main()
