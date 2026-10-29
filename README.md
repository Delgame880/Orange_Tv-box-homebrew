# Orange Kaon KSTB7259 — Android TV restore and homebrew research

A safety-first guide for the **Orange Spain / Kaon Media KSTB7259 (Suricata 2)**.
This is an unofficial research project, not support documentation endorsed by
Orange, Kaon, Broadcom, or Google.

> **Goal:** use the decoder as an independent Android TV app box **without Orange
> account onboarding**. The new [Orange-free ADB procedure](docs/NO_ORANGE.md)
> installs a verified independent launcher, can skip local setup, and can disable
> selected Orange wall packages reversibly for user 0. It does not provide paid
> Orange content, root, a different ROM, or a bootloader unlock.
>
> **Custom-OS limitation:** no verified public KSTB7259 custom ROM, factory-image
> download, bootloader-unlock method, or recovery path was found. Do not pretend a
> generic ROM is compatible with this hardware.

Research status: **2026-10-29** · [Detailed findings and sources](docs/RESEARCH.md)

Validation: official procedures source-checked; both tools tested offline with a
simulated Android device, **not on a physical KSTB7259**. The Orange-free method is
therefore experimental and requires working, authorized ADB access.

## Choose the correct procedure

| What you want | Status | What to do |
|---|---|---|
| Use independent Android TV apps without Orange account onboarding | **Experimental ADB method included** | Follow [Use without Orange](docs/NO_ORANGE.md); no paid Orange content is unlocked |
| Return the box to a clean, working Orange Android TV system | **Supported by Orange** | Follow [Clean restore](#1-clean-restore-of-the-existing-android-tv-os) |
| Install the latest official system update | **Supported during setup** | Complete the restore/setup while connected to the Internet; the setup checks integrity and updates |
| Install apps from Google Play | **Already supported by Android TV** | Sign in with a Google account and open Google Play |
| Replace Orange's OS with AOSP, LineageOS, or another Android TV ROM | **No verified method/image currently available** | Read [Custom OS reality](#3-custom-android-tv-os-current-limitation); do not flash a generic image |
| Research a future port without changing the box | **Tool included** | Run the [read-only ADB inspector](#4-read-only-adb-inspector) |

## 1. Clean restore of the existing Android TV OS

Use this when your goal is a fresh installation-like state of the Android TV
system already supplied for the decoder.

**What it does:** erases user data and returns the installed Android TV system to
its factory configuration. During first setup, the decoder checks software
integrity and can download/install an official update.

**What it does not do:** it does not install a different Android version, remove
Orange's service software, or guarantee recovery from damaged system partitions.
A factory reset is not the same as flashing a full factory image.

### Before you start

- Only modify a decoder you own or are authorized to service. If Orange supplied
  it on loan, check the contract; a rented/loaned unit should be returned in its
  original state.
- Use the original **12 V, 1 A** power supply. Do not disconnect power during the
  reset, first boot, or an update.
- Connect HDMI and, preferably, Ethernet. Keep the remote and fresh AAA batteries
  nearby.
- Make a list of your installed apps and settings. There is no complete user-data
  backup in this repository.
- Have your Orange TV and Google credentials available. You may need the account
  holder to complete service activation.

**Factory reset deletes user-installed apps, app/user data, the configured Google
account, Orange TV credentials, PINs, TDT channel configuration, and Bluetooth
remote pairing.** This is intentional and cannot be undone by the inspector.

### Method A — from the Android TV menu (preferred)

1. Turn on the TV and decoder.
2. Open **Settings** using the gear button/icon.
3. Open **Device Preferences**.
4. Select **About**.
5. Select **Factory reset** and confirm the erase prompts.

Orange's Spanish labels are:

**Ajustes → Preferencias del dispositivo → Información → Restablecer estado de fábrica**.

### Method B — rear RESET button

Use this if the menu is unavailable but the decoder is powered on.

1. Locate the rear hole labelled **RESET**.
2. With the decoder **powered on**, use a straightened paper clip as described by
   Orange to hold the internal button for approximately **10 seconds**. Do not
   force the clip or substitute a sharp object.
3. Release the button. The decoder starts the factory-restore process
   automatically.
4. Leave power connected and follow the on-screen setup.

Do not substitute a different power/reset button combination found in a generic
TV-box tutorial; it may invoke an undocumented mode rather than this procedure.

### Complete first setup

1. **Pair the remote.** Point it at the decoder and press **OK/Select** when asked.
   If manual pairing is requested, hold the two buttons highlighted on screen.
2. **Connect to the Internet.** Ethernet is recommended; otherwise select your
   Wi-Fi network and enter its password.
3. **Allow the software check and update.** Orange's setup documentation says the
   decoder checks connectivity, software integrity, and available system updates.
   Install an offered official update and let the box restart without interrupting
   power.
4. **Authenticate Orange TV.** Activation is normally automatic. If asked, use the
   displayed QR flow or the Orange TV credentials supplied with the service.
5. **Configure TV basics.** Select the time zone, connect the aerial and scan for
   DVB-T/T2 (TDT) channels, set the parental/adult PIN, and configure TV infrared
   control if offered.
6. **Configure Google.** Sign in to use Google Play, Google Assistant and Google
   services, or skip this if you do not want a Google account on the device.
7. **Verify the result.** Open Google Play, check that the remote and network work,
   and confirm that Orange TV and TDT behave as expected. The model's original OS
   remains Android TV; restoring does not upgrade it to an arbitrary newer release.

If setup reports modified/corrupt software, repeated update failure, or a boot
loop, stop retrying resets. A full exact-model recovery image and documented
recovery route are not publicly available here; contact Orange/Kaon support for
service or a signed recovery package.

## 2. Normal app installation (no firmware change)

Because the device already runs certified Android TV, the safest homebrew-friendly
setup is to keep the stock boot/vendor/system software and install applications:

1. Complete the setup above and sign in to Google Play.
2. Install apps published for Android TV/Google TV.
3. Keep system, Orange, DVB/TV-input, remote-pairing and DRM components enabled.
4. Do not disable the current launcher until another launcher has been installed
   and tested. Removing operator/TV framework packages can leave the box without
   a usable home screen or tuner.

Installing an APK is **not** installing an OS. Avoid random “KSTB7259 firmware”
sites and APKs promising root, free paid channels, or a bootloader unlock.

## 3. Custom Android TV OS: current limitation

No safe custom-ROM installer is included because the investigation did not find
these required items for the KSTB7259:

- a model-specific custom Android TV image;
- an official full recovery/factory image;
- a verified bootloader-unlock and flashing procedure;
- an exact-board kernel/device tree and compatible vendor support;
- a tested way back to stock after a failed flash.

A same-SoC image is not enough. **Never flash firmware for a KSTB6130, DIW377,
another BCM72127 device, a phone, or a generic Amlogic/ARM TV box.** Do not run
bootloader unlock, partition erase, `fastboot flash`, or `adb sideload` commands
from a generic tutorial against this decoder.

Even if an inspection reports Treble support or an unlocked indicator, that does
not prove a compatible image or recovery path exists. An AOSP GSI replaces only
part of the software stack and does not automatically provide Android TV, DVB-T2,
remote, DRM, or Orange service support.

See [RESEARCH.md](docs/RESEARCH.md) for the evidence and the requirements a real
port must satisfy.

## 4. Read-only ADB inspector

`tools/kstb7259.py` records the actual unit's model, build fingerprint, Android
version, ABI, TV features, Treble/A-B/partition properties, bootloader-lock
indicators, and kernel version. It writes reports on the computer and never
reboots, wipes, unlocks, roots, or flashes the decoder.

The report is for research only; **it is not clearance to flash**. Review the JSON
before sharing it because build/kernel details can still identify a particular
firmware or environment.

### Requirements

- A computer with **Python 3.10+**.
- Google's official [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools)
  (`adb` must be on `PATH`, or pass its path with `--adb`).
- A KSTB7259 that boots Android and on which you are authorized to enable ADB.
- ADB access exposed by the device's firmware. The stock manual documents the
  USB-A socket for accessories, **not as a PC debug interface**. Do not use a
  USB-A-to-USB-A cable or assume that socket supports ADB.

### Enable and connect ADB, if Orange's firmware permits it

Menu names can differ between operator builds.

1. Open **Settings → Device Preferences → About**.
2. Select **Build number** seven times to reveal Developer options. If the build
   entry is hidden or disabled, do not bypass the restriction with an exploit.
3. In **Developer options**, enable **ADB debugging** or **USB debugging**.
4. Note the decoder's IPv4 address from its network settings. Connect the computer
   and decoder to the same trusted LAN.
5. On the computer, check the connection:

   ```sh
   adb connect DECODER_IP:5555
   adb devices
   ```

   Replace `DECODER_IP` with the actual address. Accept the authorization prompt
   on the TV. A `device` state means it is ready; `unauthorized` means the prompt
   still needs approval.

   Port 5555 is a common operator-TV ADB configuration, not a guarantee for this
   model. If the connection is refused or no authorization prompt appears, stop:
   this stock Android TV 12 unit is not documented as supporting Google's newer
   Wireless debugging pairing workflow (Google lists that workflow for TV from
   Android 13). Do not run an unknown “ADB enabler” script.
6. When finished, disable ADB debugging and use `adb disconnect DECODER_IP:5555`.

### Run the inspection

From this repository's root on Linux/macOS:

```sh
python3 tools/kstb7259.py inspect
```

On Windows PowerShell or Command Prompt:

```powershell
py tools\kstb7259.py inspect
```

If more than one ADB device is attached:

```sh
adb devices
python3 tools/kstb7259.py inspect --serial DEVICE_SERIAL
```

If `adb` is not on `PATH`:

```sh
python3 tools/kstb7259.py inspect --adb /full/path/to/adb
```

Reports are written to `reports/` and ignored by Git. To choose another host
folder:

```sh
python3 tools/kstb7259.py inspect --output ./my-inspection
```

The inspector intentionally has no `flash`, `unlock`, `root`, `wipe`, or `reboot`
command. If a connected device does not identify itself as KSTB7259, it prints a
warning; do not apply this model's instructions to that device.

## 5. Repository layout and tests

```text
README.md                       Main procedure index and recovery instructions
docs/NO_ORANGE.md               Step-by-step Orange-onboarding bypass and rollback
docs/RESEARCH.md                Hardware/custom-ROM evidence and future-port checklist
tools/kstb7259_homebrew.py      Reversible launcher/setup/operator-package tool
tools/kstb7259.py               Read-only ADB hardware inspector
tests/                         Offline tests with a simulated Android device
```

Run the tests (no decoder required):

```sh
python3 -m unittest discover -s tests -v
```

## Sources

- [Orange: KSTB7259 specifications and manuals](https://ayuda.orange.es/dispositivos-y-routers/descodificadores/7054-nuevo-descodificador-de-orange-android-tv-kstb7259)
- [Orange: official KSTB7259 factory-reset procedure](https://ayuda.orange.es/particulares/orange-tv/configurar-orange-tv/318-resuelve-incidencias-con-tu-descodificador-de-orange-tv-restauracion)
- [Orange: Android TV first-setup guide (PDF)](https://s.orsac.net/p/ayuda/resources/orange/0/5/2005_guia-primera-configuracion-descodificador-android-tv.pdf)
- [Android TV Guide: KSTB7259 / Suricata 2](https://www.androidtv-guide.com/pay-tv-provider/orange-tv-kstb7259/)
- [AOSP: Generic System Image requirements](https://source.android.com/docs/core/tests/vts/gsi)
- [Android Developers: ADB](https://developer.android.com/tools/adb)
- [FLauncher open-source launcher and releases](https://github.com/osrosal/flauncher)
- [Older KSTB6130 operator-package investigation (not evidence for KSTB7259)](https://bandaancha.eu/foros/hola-gente-posible-nuevo-post-deco-2020-1742120)
