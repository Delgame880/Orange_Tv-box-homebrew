import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.kstb7259 import (
    AdbClient,
    AdbError,
    build_observations,
    collect_report,
    parse_adb_devices,
    parse_features,
    parse_getprop,
    render_text_report,
    target_model_detected,
    write_report,
)


class ParserTests(unittest.TestCase):
    def test_parse_adb_devices_and_states(self):
        output = """List of devices attached
* daemon started successfully
abc123 device
def456 unauthorized
192.0.2.10:5555 offline
???????????? no permissions (user in plugdev group)

"""
        self.assertEqual(
            parse_adb_devices(output),
            [
                {"serial": "abc123", "state": "device"},
                {"serial": "def456", "state": "unauthorized"},
                {"serial": "192.0.2.10:5555", "state": "offline"},
                {"serial": "????????????", "state": "no permissions"},
            ],
        )

    def test_parse_getprop(self):
        output = """[ro.product.model]: [KSTB7259]
[ro.treble.enabled]: [true]
[ro.empty]: []
not a property
"""
        self.assertEqual(
            parse_getprop(output),
            {
                "ro.product.model": "KSTB7259",
                "ro.treble.enabled": "true",
                "ro.empty": "",
            },
        )

    def test_parse_features(self):
        output = (
            "feature:android.software.leanback\n"
            "feature:android.hardware.wifi\n"
            "feature:android.software.leanback\n"
        )
        self.assertEqual(
            parse_features(output),
            ["android.hardware.wifi", "android.software.leanback"],
        )

    def test_target_model_normalization(self):
        self.assertTrue(target_model_detected({"ro.product.model": "KAON KSTB-7259"}))
        self.assertFalse(target_model_detected({"ro.product.model": "KSTB6130"}))
        self.assertFalse(target_model_detected({"ro.product.model": "KSTB72590"}))


class ObservationTests(unittest.TestCase):
    def test_locked_tv_treble_observations(self):
        properties = {
            "ro.product.model": "KSTB7259",
            "ro.treble.enabled": "true",
            "ro.build.ab_update": "true",
            "ro.boot.dynamic_partitions": "true",
            "ro.boot.flash.locked": "1",
        }
        observations = build_observations(
            properties, ["android.software.leanback", "android.hardware.wifi"]
        )
        self.assertEqual(observations["target_model_detected"], "yes")
        self.assertEqual(observations["android_tv_indicator"], "yes")
        self.assertEqual(observations["treble_property"], "true")
        self.assertEqual(observations["bootloader_lock_indicator"], "locked")
        self.assertEqual(observations["custom_os_clearance"], "not established")

    def test_unlocked_indicator_does_not_clear_flashing(self):
        observations = build_observations(
            {"ro.product.model": "Other", "ro.boot.flash.locked": "0"}, []
        )
        self.assertEqual(observations["bootloader_lock_indicator"], "unlocked")
        self.assertEqual(observations["custom_os_clearance"], "not established")


class DeviceSelectionTests(unittest.TestCase):
    def test_selects_only_ready_device(self):
        client = AdbClient()
        with mock.patch.object(
            client,
            "_run",
            return_value="List of devices attached\nabc123\tdevice\n",
        ):
            self.assertEqual(client.select_device(), "abc123")
            self.assertEqual(client.serial, "abc123")

    def test_multiple_devices_require_serial(self):
        client = AdbClient()
        with mock.patch.object(
            client,
            "_run",
            return_value=(
                "List of devices attached\nabc\tdevice\ndef\tdevice\n"
            ),
        ):
            with self.assertRaisesRegex(AdbError, "--serial"):
                client.select_device()

    def test_unauthorized_device_has_actionable_error(self):
        client = AdbClient()
        with mock.patch.object(
            client,
            "_run",
            return_value="List of devices attached\nabc\tunauthorized\n",
        ):
            with self.assertRaisesRegex(AdbError, "authorization"):
                client.select_device()


class FakeAdbClient:
    """Returns known data and records every attempted device shell command."""

    def __init__(self, fail_optional=False):
        self.calls = []
        self.serial = None
        self.fail_optional = fail_optional

    def select_device(self):
        self.serial = "test-device"
        return self.serial

    def shell(self, *arguments):
        self.calls.append(arguments)
        if arguments == ("getprop",):
            return """[ro.product.manufacturer]: [KAON]
[ro.product.model]: [KSTB7259]
[ro.product.device]: [suricata2]
[ro.build.version.release]: [12]
[ro.build.version.sdk]: [31]
[ro.treble.enabled]: [true]
[ro.boot.flash.locked]: [1]
"""
        if arguments == ("pm", "list", "features"):
            if self.fail_optional:
                raise AdbError("pm unavailable")
            return "feature:android.software.leanback\nfeature:android.hardware.wifi\n"
        if arguments == ("uname", "-a"):
            return "Linux localhost 5.4.0 #1 SMP aarch64 Android"
        if arguments == ("cat", "/proc/version"):
            return "Linux version 5.4.0 (builder@example) #1 SMP"
        raise AssertionError(f"Unexpected command: {arguments}")


class ReportTests(unittest.TestCase):
    def test_collect_report_is_read_only_and_complete(self):
        client = FakeAdbClient()
        report = collect_report(client)
        self.assertEqual(report["properties"]["ro.product.model"], "KSTB7259")
        self.assertNotIn("ro.serialno", report["properties"])
        self.assertEqual(report["observations"]["target_model_detected"], "yes")
        self.assertEqual(report["observations"]["bootloader_lock_indicator"], "locked")
        self.assertFalse(report["safety"]["device_writes_performed"])
        self.assertEqual(
            client.calls,
            [
                ("getprop",),
                ("pm", "list", "features"),
                ("uname", "-a"),
                ("cat", "/proc/version"),
            ],
        )
        text = render_text_report(report)
        self.assertIn("CUSTOM OS STATUS: NOT ESTABLISHED", text)
        self.assertIn("KSTB7259", text)

    def test_optional_feature_failure_does_not_abort(self):
        report = collect_report(FakeAdbClient(fail_optional=True))
        self.assertEqual(report["features"], [])
        self.assertEqual(report["feature_query_error"], "pm unavailable")
        self.assertEqual(report["observations"]["android_tv_indicator"], "unknown")

    def test_write_report_round_trip(self):
        report = collect_report(FakeAdbClient())
        with tempfile.TemporaryDirectory() as temporary_directory:
            json_path, text_path = write_report(report, Path(temporary_directory))
            loaded = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["target_model"], "KSTB7259")
            self.assertTrue(text_path.is_file())
            # A second report in the same second must not overwrite the first.
            second_json, second_text = write_report(report, Path(temporary_directory))
            self.assertNotEqual(json_path, second_json)
            self.assertNotEqual(text_path, second_text)


if __name__ == "__main__":
    unittest.main()
