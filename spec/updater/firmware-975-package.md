# Firmware package contents: 9.31 to 9.75

Differences between the firmware 9.31 and 9.75 packages, for the 64-bit and the 32-bit build.
Basis: file-level comparison of the unpacked packages (READ). Model implications are INFERRED. The
installation scripts are described in [Package scripts](firmware-975-package.md#scripts-and-configuration-firmware-975).

## 64-bit package

- Image dates in the update script change (READ), at the same image offset for all three:

  | Model | Firmware 9.31 | Firmware 9.75 |
  |---|---|---|
  | S30 Pro | 20260902 | 20260917 |
  | S50 Pro | 20260811 | 20260923 |
  | S30 Plus | 20260702 | 20260923 |

- The update images of the S30 Plus, S30 Pro and S50 Pro change. The S80 branch still replaces the
  camera SDK library, and its two camera libraries change.
- New in the system files: an `ffmpeg` executable with its shared libraries (libavcodec 58.134,
  libavformat 58.76, built with the MP3, Vorbis, Theora and OMX encoders and without x264/x265), a
  new CFITSIO library version, and a `zoneinfo/posix/America` directory.
- The image-quality tuning JSON files for the S30 Pro, S30 Plus and S50 Pro change; the S30 Pro gains
  tuning files for an `ov08b10` sensor in the moon, normal, planet and sun folders, and its `imx585`
  file renames or adds ISP autofocus and denoise keys. A second-source sensor variant is INFERRED.
- Platform label: the version remark and the updater identity say `1126bp`, but the ffmpeg build
  tree is named for a different Rockchip platform. Unresolved which board name is correct.

## 32-bit package

- Removed (READ): all S30P, S50N and S50P content (kernel modules, camera drivers, vendor libraries
  and update images), the image-quality tuning folders for those models, and the `dnoise_model.onnx`
  model. One RKNN denoiser model file changes.
- Remaining: S30 and S50 content only. The S30P branches remain in the update script, but their
  data is no longer shipped.
- Added: an `ffmpeg` executable and libraries (libavcodec 58.35, libavformat 58.20; built without
  GPL, x264, x265, MP3 and Vorbis, for a Cortex-A7), and a tzdata entry for `America/Coyhaique`.
- The 32-bit update image dates are unchanged. The unpacked archive for the 32-bit system files is
  no longer shipped; the files are shipped unpacked.
- Model implication (INFERRED): the 32-bit RV1126 platform now covers only the S30 and S50; the
  S30 Pro, S30 Plus, S50 Pro and S80 content (and the imx585 variants) is in the 64-bit package only.

## Platform identity and models

| Build | Updater hardware platform | Architecture | Models seen in the package |
|---|---|---|---|
| 64-bit | `1126bp` | `aarch64` | S30 Pro, S30 Plus, S50 Pro, S80 (and S50/S30 firmware paths where present) |
| 32-bit | `1126` | `armv7l` | S30, S50 |

READ for the platform and architecture literals; the model column is INFERRED from package contents.
The model name mapping used by the updater is in [index.md R10b](index.md#ota-methods-firmware-975).

## Unchanged

- The BLE daemon is byte-identical in both builds (R16 of the changes part).
- The OTA package public key is the same as in 9.31. A fixed package password also exists (the same
  for every device; its value is not given in this specification).

### Scripts and configuration (firmware 9.75)

R14. Firmware 9.75 package scripts (READ):
- Both builds: after the system files are synchronised the package script removes the x264 and
  x265 libraries (and, in 32-bit, the postproc library) because the bundled ffmpeg is built without
  them. The 32-bit package script no longer extracts a build archive, because the 32-bit package is
  now shipped unpacked.
- The 32-bit file check no longer requires the beeper and power-LED helper files.
- Both configuration files move to version number 2975, version string 9.75 and remark
  `seestar1126bp-3.4` (64-bit) or `seestar-3.4` (32-bit). The 64-bit configuration adds a key
  `secure_communication` set to 1, the client secure-communication authentication switch (1 on,
  0 off); the 32-bit configuration has no such key. Its effect is specified in the control
  chapters, not here.

## Open questions

- **The fixed OTA package password (deliberately withheld).** The updater decrypts package modules
  with `openssl enc -d -aes-256-cbc -pbkdf2` and a fixed password that is the same for every device,
  in both the 64-bit and the 32-bit updater. READ. This specification does not give the value.
  The rest of the decrypt step (AES-256-CBC, PBKDF2 key derivation, the public signature key) is in
  [OTA package handling: OTA package handling](ota-package-handling.md#ota-package-handling).
