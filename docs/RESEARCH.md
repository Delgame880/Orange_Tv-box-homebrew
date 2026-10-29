# KSTB7259 investigation notes

Research date: **2026-10-29**. This page separates published facts from things
that remain unknown. It is not evidence that a custom ROM is safe or available.

## 1. Published hardware and software

| Item | Finding | Source |
|---|---|---|
| Manufacturer / model | Kaon Media **KSTB7259** | Orange device guide and Kaon EU declaration |
| Operator codename | **Suricata 2** | Android TV Guide device entry |
| Original OS | **Android TV 12** | Android TV Guide; Orange describes the device as Android TV and the first-setup guide describes a software-integrity check and system updates |
| SoC | Broadcom **BCM72127** | Orange device guide |
| CPU / GPU | Quad-core 2.0 GHz / VideoCore 6 | Android TV Guide |
| RAM / internal storage | 3 GB / 16 GB | Orange device guide |
| Network | Gigabit Ethernet, Wi-Fi 6, Bluetooth 5.0 | Orange device guide |
| Broadcast / media | DVB-T2 tuner; AV1, VP9, H.264 and H.265 listed by Android TV Guide | Orange device guide and Android TV Guide |
| External connections | HDMI 2.1, USB-A 2.0 (0.5 A), antenna, Ethernet, 12 V DC | Orange device guide |
| DRM | Widevine L1 listed | Android TV Guide |

The exact Android build, patch level, partition layout, CPU ABI, Treble state and
bootloader-lock properties can vary by production firmware. Use the read-only
inspector on the actual unit; do not infer those values from the model name.

## 2. What Orange officially supports

Orange documents two KSTB7259 factory-reset routes:

1. **Settings → Device Preferences → About → Factory reset** (the Spanish menu
   labels are **Ajustes → Preferencias del dispositivo → Información →
   Restablecer estado de fábrica**).
2. With the decoder powered on, hold the rear **RESET** button for about
   **10 seconds**.

Orange's first-setup documentation says the box then checks Internet
connectivity, software integrity (that it has not been modified), and available
system updates, installing an update when offered. This is the only published
clean-restore/update path identified for this exact model.

A factory reset is **not a full firmware flash**. It erases user data and returns
the installed system to its factory configuration. It is not guaranteed to
repair damaged boot/system/vendor partitions.

## 3. Custom Android TV OS: current finding

**No reproducible custom-OS installation method is published here, because the
required device-specific pieces were not found.**

Public web and GitHub searches performed for the exact model and codename did
not locate a usable public source for these prerequisites:

- a KSTB7259 factory/recovery image or complete official OTA download;
- a KSTB7259 custom Android TV ROM;
- an exact-model device tree and matching kernel source;
- a compatible custom recovery;
- a verified bootloader-unlock procedure;
- a documented, tested recovery route after a failed flash.

This is a statement about the public material found on the research date, not a
claim that porting is physically impossible. It does mean that publishing a
one-click flasher today would be fabricated and could permanently damage the
box.

### Why a generic Android image is not a safe substitute

An AOSP Generic System Image (GSI) replaces only the Android system image. It
does not supply the KSTB7259 bootloader, kernel, board device tree, vendor
implementation, DVB-T2 integration, remote-control support, or operator/DRM
components. Android's own GSI documentation requires a Treble-compatible device
**and a working unlock/fastboot method** before flashing. A Treble property alone
is not proof of a bootable or recoverable installation.

Images for the KSTB6130, Sagemcom DIW377, other BCM72127 products, Amlogic TV
boxes, phones, or generic ARM64 boards are **not interchangeable** with this
unit. Even devices using the same SoC can have different memory, storage,
bootloaders, verified-boot keys, peripherals and partition layouts.

AOSP/phone GSIs also should not be described as a ready-made Android TV ROM.
Android TV's launcher, TV input framework, DVB tuner service, remote pairing,
certifications and DRM require additional device/product integration.

## 4. Orange-independent Android use without replacing the ROM

Community reports for the **older KSTB6130**, not the KSTB7259, describe reaching
ordinary Android by installing a third-party launcher and disabling Orange's
first-time/authentication/home packages for user 0. Reported examples include
`net.quber.orangeftu`, `net.quber.orangesetupcustomizer`,
`com.kaon.orangecheckservice`, and `com.orange.es.stb`. This is useful evidence for
a reversible ADB approach, but it is not proof that the KSTB7259 has the same
packages or that its firmware permits disabling them.

No public report confirming that procedure on the exact KSTB7259 was found. The
homebrew tool therefore starts with an actual-device scan, installs and tests a
launcher before changing HOME, preserves setup/HOME/package state, refuses missing
or protected packages, and never uninstalls APKs. It targets local onboarding only;
it does not grant Orange IPTV/subscription content. ADB access remains a hard
prerequisite, and physical-model validation is still required.

The full procedure is in [NO_ORANGE.md](NO_ORANGE.md).

## 5. What a real port would need

A future contributor should establish these items **before** writing flashing
instructions:

1. **Ownership/authorization:** a privately owned test unit, not a decoder that
   must be returned to Orange.
2. **Exact identity:** model, hardware revision, build fingerprint, ABI, Android
   SDK/first API level and security patch from the inspector.
3. **Recovery first:** a complete known-good stock image and a demonstrated way
   to restore it after a failed boot. A package list or user-app APK backup is
   not a firmware backup.
4. **Authentic firmware:** an official full OTA/factory package from Orange or
   Kaon, with its origin and cryptographic verification documented. A SHA-256
   hash detects transfer changes but does not make an untrusted image genuine.
5. **Boot path:** a vendor-supported or otherwise verified bootloader unlock and
   flashing interface for this exact model. Never experiment with erase/flash
   commands merely to see whether fastboot exists.
6. **Platform support:** matching kernel source/configuration, device tree,
   vendor blobs/HALs, partition layout, AVB/rollback behavior and SELinux policy.
7. **TV hardware:** working HDMI, hardware video decode, Wi-Fi/Bluetooth, USB,
   Ethernet, IR/Bluetooth remote and DVB-T2. Widevine/Play certification and
   Orange IPTV may remain unavailable after modification.
8. **Repeatable test evidence:** exact host tool versions, image hashes,
   commands, results and tested rollback steps from more than one stage of the
   install.

Until items 3–6 are satisfied, the safe action is to stop at inspection. Do not
unlock or wipe a daily-use decoder on the assumption that a suitable ROM can be
found later.

## 6. Sources

1. Orange, [Nuevo descodificador de Orange Android TV (KSTB7259)](https://ayuda.orange.es/dispositivos-y-routers/descodificadores/7054-nuevo-descodificador-de-orange-android-tv-kstb7259) — official specifications, connectors and manuals.
2. Orange, [Cómo restaurar tu descodificador Orange TV](https://ayuda.orange.es/particulares/orange-tv/configurar-orange-tv/318-resuelve-incidencias-con-tu-descodificador-de-orange-tv-restauracion) — official KSTB7259 reset procedure and data-loss list.
3. Orange, [Guía de la primera configuración de un descodificador Android TV](https://s.orsac.net/p/ayuda/resources/orange/0/5/2005_guia-primera-configuracion-descodificador-android-tv.pdf) — setup, software-integrity check and system updates.
4. Android TV Guide, [MásOrange KSTB7259 / Suricata 2](https://www.androidtv-guide.com/pay-tv-provider/orange-tv-kstb7259/) — Android TV 12, codename, CPU/GPU and codec/DRM listing.
5. Kaon Media, [EU Declaration of Conformity](https://www.kaonmedia.co.kr/eng/ec/) and [KSTB7259 declaration](https://www.kaonmedia.co.kr/eng/ec/file/KSTB7259.PDF) — manufacturer/model confirmation.
6. Android Open Source Project, [Generic system images](https://source.android.com/docs/core/tests/vts/gsi) — GSI scope and unlock/Treble/flashing requirements.
7. Android Developers, [Android Debug Bridge](https://developer.android.com/tools/adb) and [developer options](https://developer.android.com/studio/debug/dev-options) — ADB authorization and debugging background.
8. BandaAncha community, [KSTB6130 package/launcher investigation](https://bandaancha.eu/foros/hola-gente-posible-nuevo-post-deco-2020-1742120) — older-model user reports only; explicitly not validated for KSTB7259.
9. FLauncher, [osrosal/flauncher source and releases](https://github.com/osrosal/flauncher) — GPL Android TV replacement launcher; release `v2025.07.001` is pinned by URL and SHA-256 in the tool.
