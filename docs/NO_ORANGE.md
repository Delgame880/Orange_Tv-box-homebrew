# Use the KSTB7259 without Orange account onboarding

This procedure is for using the decoder as an **independent Android TV app box**
when you do not want to sign into Orange. It installs an independent home screen,
can mark Android's setup as complete, and—only if necessary—can disable selected
Orange onboarding/login packages for Android user 0.

> **Scope:** this does **not** provide Orange TV channels, decrypt IPTV, authenticate
> a subscription, remove DRM, or make paid Orange content free. Orange TV service
> will normally stop working. Use apps and content you are independently entitled
> to access. Only modify a decoder you own or are authorized to modify.

## Status and limitations

- **No root, ROM flash, bootloader unlock, or package uninstall is used.** The tool
  changes Android user-0 settings/package states and keeps a rollback JSON.
- The package-disable operation is `pm disable-user --user 0`. It leaves the APK on
  the system partition and can normally be undone with `pm enable`.
- **Hardware status: experimental and not yet tested on a physical KSTB7259.**
  Orange can protect or automatically re-enable components. A factory reset will
  restore Orange's onboarding and erase your data.
- The package names found on the older KSTB6130 are clues only. The tool verifies
  the connected model and refuses packages absent from the actual unit.
- **ADB is the hard prerequisite.** If the Orange wall blocks Settings and ADB was
  never enabled/authorized, this method cannot bootstrap itself. There is currently
  no verified KSTB7259 recovery/bootloader route for that situation.

## If the Orange login wall blocks Settings

Do this **before** the normal procedure. Do not press RESET or factory-reset the
box.

### A. Test whether ADB is already listening

ADB normally has to be enabled first, but some operator builds already listen on
the network. You can test this without opening any menu:

1. Find the decoder's IP in your router's **connected devices / DHCP client list**
   (look for Orange, Kaon, KSTB7259, or an unknown wired device).
2. On a computer connected to the same router, install Android Platform-Tools and
   run, replacing the example IP:

   ```sh
   adb connect 192.168.1.123:5555
   adb devices
   ```

3. If the result is `device`, proceed directly to `scan`; no Settings visit is
   needed. If it is `unauthorized`, an authorization dialog still has to be
   accepted on the TV. If it is `connection refused`, ADB is not listening on that
   endpoint. For a timeout, first verify that you selected the correct wired device
   and that the router is not isolating clients.

### B. Try Android Settings from the network-error screen (unverified on this model)

Some older Orange Android TV boxes allowed Google Assistant to open Android
Settings from the initial network-error screen. This does not bypass Orange
content; it is only a possible way to reach ADB settings.

1. Power the decoder off normally, disconnect Ethernet, and power it back on. Do
   **not** hold RESET.
2. Wait for a **no Internet connection** screen. Do not acknowledge/retry it.
3. Reconnect Ethernet while leaving that screen open.
4. Press the remote's **Google Assistant/microphone** button and say **“Abrir
   ajustes”**, **“Abrir configuración”**, or **“Open Android settings.”** Also try
   the remote's gear/Settings button if it has one.
5. Voice requires the remote's Bluetooth pairing and may require a Google account;
   it can legitimately fail on this model. If Android Settings opens, enable ADB
   and continue with the normal procedure.

If neither route works, there is currently no verified Ethernet-only way to enable
ADB or install a launcher from the Orange wall. Stock recovery normally accepts
only properly signed updates; an unsigned launcher/ZIP is not a valid recovery
image. Do not experiment with random reset-button combinations or generic firmware.

## 1. Before changing anything

**No USB connection is needed.** HDMI is only the display, DC powers the decoder,
and ADB travels over the network. Connect the decoder to your router by Ethernet;
your computer can use Ethernet or Wi-Fi as long as both are on the same LAN.

1. **Do not factory-reset now.** That can remove ADB authorization and put you back
   at the same Orange onboarding screen.
2. Install **Python 3.10+** and Google's official
   [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools)
   on your computer.
3. Connect the computer and decoder to the same trusted LAN. Ethernet is preferred.
4. If you can reach Android Settings, enable Developer options and **ADB/USB/network
   debugging**, then note the decoder's IPv4 address. Do not use a USB-A-to-USB-A
   cable: Orange documents the KSTB7259 USB-A port for accessories, not PC ADB.
5. Connect and authorize ADB:

   ```sh
   adb connect DECODER_IP:5555
   adb devices
   ```

   The state must be `device`, not `unauthorized` or `offline`. Port 5555 is common
   on operator Android TV firmware but is not guaranteed for this model. If ADB was
   never enabled and the wall prevents you from enabling it, stop here rather than
   running an unknown ADB-enabler or recovery script.

Commands below use Linux/macOS notation. On Windows, replace:

```text
python3 tools/kstb7259_homebrew.py
```

with:

```text
py tools\kstb7259_homebrew.py
```

Run every command from the repository root. Device-changing commands are **dry runs
unless you add `--apply`**.

## 2. Scan the actual decoder (read-only)

Leave the Orange login/subscription screen visible and run:

```sh
python3 tools/kstb7259_homebrew.py scan
```

Review the terminal output and the files created in `reports/`:

- **Foreground activity:** the best clue for the package currently displaying the
  Orange wall. It can sometimes show a system fallback instead.
- **Current HOME:** Orange's current home activity, if Android reports it.
- **HOME activities:** available home screens. FLauncher will appear here after the
  installation stage.
- **Operator packages:** a human-review list, **not** an automatic disable list.
  Entries marked `PROTECTED` cannot be disabled by this tool.
- **Setup flags:** values that the later skip-setup stage will preserve for rollback.

The JSON includes your installed-app list; review it before sharing. The scan does
not change the decoder.

## 3. Install and test an independent launcher

First, optionally download the pinned launcher without connecting to the decoder:

```sh
python3 tools/kstb7259_homebrew.py download-launcher
```

Then preview and perform the installation:

```sh
python3 tools/kstb7259_homebrew.py install-launcher
python3 tools/kstb7259_homebrew.py install-launcher --apply
```

The tool downloads **FLauncher 2025.07.001** from the
[`osrosal/flauncher` GitHub release](https://github.com/osrosal/flauncher/releases/tag/v2025.07.001),
using the universal APK and this pinned SHA-256:

```text
8410b07003c3cd25a864f06a0bd5c3b34a0be71af57db5748ba6657d05be66be
```

It installs with `adb install -r`, verifies that FLauncher registered a HOME
activity, and opens it. **Do not continue until you have verified with the remote
that FLauncher itself works**: D-pad, Back, app list, and access to Android Settings.

The APK is saved under `downloads/` and is not committed to Git. A file with an
unexpected hash is rejected. To use an existing copy of that exact APK:

```sh
python3 tools/kstb7259_homebrew.py install-launcher \
  --apk /full/path/to/flauncher-universal-release.apk --apply
```

Restricted networks must permit both `github.com` and GitHub's release-asset host,
`release-assets.githubusercontent.com`. You can also download the exact release in
a browser on another network and transfer it to the computer; the SHA-256 check is
still enforced before installation.

## 4. Prefer FLauncher and create rollback state

Preview and apply:

```sh
python3 tools/kstb7259_homebrew.py set-launcher
python3 tools/kstb7259_homebrew.py set-launcher --apply
```

This records the original HOME before asking Android to prefer:

```text
me.efesser.flauncher/.MainActivity
```

The rollback file is created at:

```text
backups/kstb7259-homebrew-state.json
```

Keep it until you have finished testing. If Android still resolves HOME to Orange
but FLauncher opens and works, that is a known possibility with operator launchers;
the later targeted Orange-home stage may be needed. Do not disable Android Settings
or a Google setup fallback to force the choice.

Test the Home button and several apps before proceeding.

## 5. Mark Android setup complete, with rollback

This is the least invasive attempt to bypass first-run onboarding. Preview and apply:

```sh
python3 tools/kstb7259_homebrew.py skip-setup
python3 tools/kstb7259_homebrew.py skip-setup --apply
```

The tool saves the old values, then sets these user-0 values to `1`:

```text
global/device_provisioned
secure/user_setup_complete
secure/tv_user_setup_complete
global/setup_wizard_has_run
```

It reads them back and opens FLauncher. Test **Home, Back, Settings, networking, and
a manual reboot**.

- If Android now starts in FLauncher without Orange authentication, you are done.
  Install apps normally and test TDT if you need it.
- If the Orange wall returns, continue to the next stage. Do not immediately disable
  every Orange-named package.

## 6. If necessary, disable only the Orange wall package(s)

### Identify the active wall first

With the unwanted Orange screen visible, run `scan` again. Compare its foreground
activity and package list with the table below.

The older KSTB6130 community procedure reported these packages. **They are not
confirmed KSTB7259 package names and must not be copied unless your scan shows
them:**

| Older-model package | Reported role on KSTB6130 | How to use that clue here |
|---|---|---|
| `net.quber.orangeftu` | First-time/setup/authentication flow | Candidate only if present and consistent with the current wall |
| `net.quber.orangesetupcustomizer` | Orange setup customization | Try only with the actual setup flow, not as a generic debloat step |
| `com.kaon.orangecheckservice` | Orange service checking | Consider only if setup is complete but this checker restores the wall |
| `com.orange.es.stb` | Orange home/launcher | Last resort for HOME override, after FLauncher has been tested |

The tool rejects missing, non-operator, and protected packages. It never falls back
to `pm uninstall`.

### Stage A — actual first-time/login package

For example, **only if both names are present and identified by your scan**, preview:

```sh
python3 tools/kstb7259_homebrew.py disable \
  net.quber.orangeftu net.quber.orangesetupcustomizer
```

Review the dry run. Then apply the same command with `--apply`:

```sh
python3 tools/kstb7259_homebrew.py disable \
  net.quber.orangeftu net.quber.orangesetupcustomizer --apply
```

On Windows, enter the command on one line or use PowerShell's backtick for line
continuation. The packages are disabled one at a time, with state saved before each
change. Test FLauncher and reboot manually before disabling anything else.

### Stage B — service checker only if it recreates the wall

If your new scan identifies `com.kaon.orangecheckservice` as the active cause:

```sh
python3 tools/kstb7259_homebrew.py disable com.kaon.orangecheckservice
python3 tools/kstb7259_homebrew.py disable com.kaon.orangecheckservice --apply
```

This is intended to stop local operator onboarding, **not** to make Orange IPTV
work without an account. Expect Orange service features to be unavailable.

### Stage C — Orange HOME only if it overrides the replacement

If `com.orange.es.stb` is present, is the unwanted HOME, and FLauncher has already
been tested:

```sh
python3 tools/kstb7259_homebrew.py disable com.orange.es.stb
python3 tools/kstb7259_homebrew.py disable com.orange.es.stb --apply
```

### Components deliberately protected

Do not attempt to bypass the tool's refusal for these or equivalent components:

- `net.quber.tvinput`, DVB/TDT/tuner and HDMI/input services;
- Bluetooth/IR remote and RCU pairing/updaters;
- `net.quber.rmsservice`, update/settings/maintenance services;
- `com.kaon.orangetvservice`, DRM/Widevine and media frameworks;
- Android Settings, SystemUI, Google Play services, setup fallback, ADB, or the new
  launcher.

Disabling those can remove the remote, TDT, networking, updates, or the only usable
home screen. The goal is the minimum onboarding change, not general debloating.

## 7. Roll back the changes

If anything behaves incorrectly and ADB still connects, preview and apply:

```sh
python3 tools/kstb7259_homebrew.py rollback
python3 tools/kstb7259_homebrew.py rollback --apply
```

Rollback attempts every applicable step even if one fails:

1. Re-enables only packages that this tool disabled (not packages already disabled
   by Orange/you).
2. Restores the recorded original HOME if it is available.
3. Restores or deletes setup values to match their original state.
4. Verifies the resulting package/HOME/settings states and reports errors.

FLauncher remains installed so you still have a usable home screen while recovering.
Rollback does not provide an Orange subscription or repair a damaged OS.

If ADB no longer works and the box is unusable, the last-resort recovery is Orange's
documented factory reset: with the decoder powered on, hold rear **RESET** for about
**10 seconds**. **This erases user data and restores the Orange wall.**

## 8. Troubleshooting

| Symptom | Action |
|---|---|
| `no ADB device found` | Check LAN/IP, ADB authorization and `adb devices`. If ADB was never enabled and the wall blocks Settings, this method cannot currently start. |
| `unauthorized` | Accept the RSA/ADB prompt on the TV, then reconnect. |
| Model does not identify as KSTB7259 | Stop. Do not override the check or use another model's package list. |
| Launcher download/hash failure | Do not install the file. Re-download the exact pinned GitHub release or use `download-launcher` again. |
| `set-home-activity` succeeds but HOME stays Orange | Continue only if FLauncher opens and works; use scan and, if present/appropriate, Stage C. Never disable Android/Google setup fallback. |
| `pm disable-user` is refused or immediately reversed | Stop. The tool intentionally has no uninstall/root fallback. Roll back earlier changes. |
| Black screen, missing Home, remote failure, or TDT failure | Run `rollback --apply` over ADB. If ADB is unavailable and the box is unusable, use the factory-reset last resort. |
| Orange wall returns after an OTA/reboot | Scan again; Orange may have re-enabled components or changed packages. Do not repeat an old package list blindly. |
| Need Orange service again | Run rollback and complete Orange onboarding with a valid account/subscription. A factory reset may be required for a clean service setup. |

After you finish testing, disable ADB debugging in Android Settings to reduce LAN
attack surface. Keep the rollback JSON and remember that disabling ADB means you
must re-enable it through Settings before using the tool again.

## Technical references

- [KSTB6130 community package investigation](https://bandaancha.eu/foros/hola-gente-posible-nuevo-post-deco-2020-1742120):
  evidence for the older-model approach and package names; not proof for KSTB7259.
- [FLauncher source and release documentation](https://github.com/osrosal/flauncher):
  open-source GPL launcher used by the pinned installer.
- [AOSP trade-in-mode reference](https://source.android.com/docs/core/perf/trade-in-mode):
  documents `USER_SETUP_COMPLETE` and `DEVICE_PROVISIONED` as provisioning state;
  this project does **not** invoke trade-in mode.
- [AOSP PackageManager shell implementation](https://android.googlesource.com/platform/frameworks/base/+/master/services/core/java/com/android/server/pm/PackageManagerShellCommand.java):
  implementation reference for `set-home-activity`.
