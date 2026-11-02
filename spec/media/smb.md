# SMB file sharing

Part of the [media chapter](index.md). The device runs a Samba SMB server that exposes its
image store on the local network. The app does not use it, so it is not part of the
app-compatible protocol, but a client or stand-in that shows the device's storage meets it.
Ports and the remote tunnel map are in [ports.md](../transport/ports.md).

Basis: static reading of the firmware 9.31 update packages (32-bit and 64-bit), the imager in
both builds and app 3.3.2, plus device observations through a P2P tunnel mapping (OBSERVED
2026-10-16, read-only). The update packages ship **no** Samba server binary, Samba
configuration, Samba accounts or Samba state directory; these come from the device's base
system image, which is not part of the analysed artefacts. Every server setting below is
therefore OBSERVED or unresolved, never READ. Firmware 9.75: the boot-script lines that configure
and start the Samba service are textually identical to firmware 9.31 in both builds (READ), and the
9.75 packages again ship no Samba configuration, so the server identity, share and protocol
statements below remain OBSERVED on the device (2026-10-16) and cannot be checked against the
firmware files. The observation was not tagged with a firmware version.

## Start and stop

R1. The device's boot script, run as the unprivileged system user at start-up, prepares a
Samba state tree in a temporary filesystem: it copies a persistent Samba state directory there,
creates cache and log directories, points the system Samba log directory at the temporary one,
then starts the NetBIOS name service and then the SMB service through the service manager. READ.
On the 32-bit build the service units are named `nmbd` and `smbd`; on the 64-bit build `nmb`
and `smb`. READ. The server is the Samba `smbd`/`nmbd` pair. INFERRED from the unit names,
consistent with the server string in R5.

R2. The imager can stop and start both services. It stops them before
[`format_emmc`](../../docs/control/methods/format_emmc.md) unmounts and reformats the internal
store and starts them again on every path after the format command has run, success or error.
If stopping fails, `format_emmc` returns error 207 and leaves the services as they were. No other
RPC method starts, stops or configures the SMB server. READ (both imager builds).

R3. A client SHOULD expect SMB connections to drop during `format_emmc` and MAY reconnect after
its reply. INFERRED.

## Server identity

R4. The 64-bit update package installs the host name `SeeStar` (in `/etc/hostname`, and as the
loopback alias in `/etc/hosts`). No script or binary in either package derives a host name
from the serial number, SSID or model. READ. The 32-bit package installs no host name; there it
comes from the base image. unresolved. The NetBIOS name is unresolved (no configuration ships;
Samba's default would derive it from the host name, INFERRED).

R5. The server string seen in the share list is `Samba 4.19.5`. OBSERVED 2026-10-16. The
device accepted a tree connect regardless of the server name the client presented (`seestar`, an
arbitrary name, `<loopback>` and `localhost` all worked). OBSERVED 2026-10-16. A client MAY
address the server by any name or address that reaches it. INFERRED.

## Protocol and access

R6. SMB1 is disabled. OBSERVED 2026-10-16. The upper protocol limit, signing and encryption
settings are unresolved from the packages (no Samba configuration ships).

R6a. OBSERVED 2026-10-23 (firmware 9.75, S50 Pro, negotiate and session setup only, no tree
connect, no file access): the server negotiated dialect 3.1.1 with SecurityMode 1 (signing
enabled, not required), capabilities DFS, LARGE_MTU and LEASING, and negotiate contexts for the
AES-128-GCM cipher, SHA-512 pre-authentication hash and AES-GMAC signing algorithm. A guest NTLM
session with an empty password succeeded but gave no session key, so that session had no signing
and no encryption; a client that required signing refused it. INFERRED: a guest session cannot
obtain an SMB integrity check, and whether any account exists for a signed session is unresolved.

R7. Anonymous share enumeration succeeds, and a guest tree connect to the image share succeeds.
OBSERVED 2026-10-16. Any client on a network that reaches the server can therefore at least
list and open the image share without credentials. INFERRED. Whether guests can write, and
which Samba accounts exist, are unresolved.

## Shares

Shares listed anonymously (OBSERVED 2026-10-16):

| Share | Type | Comment |
|---|---|---|
| `EMMC Images` | disk | `Images` |
| `print$` | disk | |
| `IPC$` | IPC | `Samba 4.19.5` |

R8. The `EMMC Images` share serves the internal image store mounted at `/boot/Image`. INFERRED:
the share name and comment match, and `format_emmc` stops the server around exactly that mount
(R2). The store is an exFAT filesystem labelled `Seestar`, mounted read-write and owned by the
device's unprivileged user. READ. The same tree is served over HTTP 80
([files-and-album.md: HTTP 80](files-and-album.md#http-80)).

R9. After `format_emmc` the imager re-creates the top-level `MyWorks` folder on the internal
store (Seestar models only). Other top-level entries (for example the dark-frame library and
working folders) are created by the features that use them. READ (folder creation), INFERRED
(the full set present on a given device). Firmware 9.75 stores its temperature-keyed dark library
at `/boot/Image/darklibrary/` ([calibration frames R6h1](../control/calibration-frames/dark-library.md#temperature-dark-library-firmware-975)),
directly under the image store root that this share serves (R8), so such a folder would be visible
through the share if present.

A read-only, anonymous guest listing of a firmware 9.75 device's `EMMC Images` share over SMB3,
through the tunnel proxy (OBSERVED 2026-10-17 ~02:45Z, device-reported build 2975): the share root
held, with device-local mtimes, `MyWorks/` (2026-10-16 20:02), `Autorun/` (2026-10-16 21:21), `log/`
(2026-10-17 01:10) and two hidden macOS Finder droppings, `.DS_Store` (6148 B, 2026-10-14) and
`._.DS_Store` (4096 B, 2026-10-13); `Autorun/` held only a `Dark/` subfolder (written by the
observing session itself, unrelated to R6b's legacy dark library); `log/` held only small
`Autorun_Log_<date>_<time>.txt` files. **No `darklibrary` folder was present at the root.**
`MyWorks/` was not walked. Since the temperature dark library's directory tree is created per
exposure length on first use (R6h1: "one directory per exposure named `<N>s`"), the simplest reading
is that this particular device had not yet run a temperature-keyed dark capture, not that the share
hides the path. INFERRED. The folder's presence after capture is documented by the observation
below.

A repeat listing of the same firmware 9.75 share, after a shoot using 60 s exposures (OBSERVED
2026-10-17 ~07:25Z): a `darklibrary/` folder is present at the root, with one subfolder per exposure
length seen so far (`60s`). Inside, two master darks are present, each stored as a set of three
files sharing the naming scheme of [calibration frames
R6h1](../control/calibration-frames/dark-library.md#temperature-dark-library-firmware-975)
(master-dark prefix, a small integer field, the exposure, the sensor temperature and a local-time
timestamp): the `.fit` master itself (about 16.6 MB), a full-size JPEG preview (about 4 MB) sharing
the same base name, and a thumbnail JPEG (about 22 KB) with a `_thn` suffix on the base name. The
two masters differ in temperature by about 5 degrees C and were written about 1h15m apart during the
shoot. The rest of the root is unchanged from the 02:45Z listing (`MyWorks/`, `Autorun/` holding
only `Dark/`, `log/` holding only `Autorun_Log` files, and the two `.DS_Store` droppings). OBSERVED.

On firmware 9.75, by later that same shoot a third master had appeared in the same `60s` folder,
again as a `.fit`/JPEG/`_thn` triple, taking the total to three. OBSERVED 2026-10-17. Detail on all
three runs, including the observed 2.5 °C selection threshold and a separate periodic dark capture
under `Autorun/Dark/`, is in [calibration frames
R6n](../control/calibration-frames/dark-library.md#building-the-dark-library).

## Image store layout (firmware 9.75)

Firmware 9.75, 64-bit and 32-bit imagers, compared with firmware 9.31 (READ, static reading; no folder below was listed on a device unless marked OBSERVED). A recovered writer shows a possible output, not that the folder exists on a given device. The set is an inventory of recovered path families, not a proof that nothing else is ever written. In this section R is the selected image root.

R13. Folders under R, with their writers (READ):

| Folder | Content and trigger |
|---|---|
| `MyWorks/` | Recreated after `format_emmc` and at startup on Seestar models (R9). Holds the observing outputs below. |
| `MyWorks/<target>/` | Stacked results. A mosaic adds a `mosaic` name part. |
| `MyWorks/<target>_sub/` | Kept subframes; `_failed` variants for rejected ones. Saved only when the matching retention setting allows it. |
| `MyWorks/MilkyWay/`, `MilkyWay_sub/`, `MilkyWay_timelapse/`, `MilkyWay_timelapse_sub/` | Wide-camera stack and sub outputs. |
| `MyWorks/Startrails/`, `Startrails_sub/`, `Startrails_video/` | Star-trail stacks, subs and videos. On the 64-bit build subs go into a per-session subfolder named from the start time; the 32-bit build uses a flat timestamp name. |
| `MyWorks/Meteor_sub/` | 64-bit only. A meteor save is three separate file copies, so an interruption can leave an incomplete set. |
| `MyWorks/PhotoMetry/` | Photometry result CSV files. |
| `MyWorks/<category>_photo/` and `_video/`, with category Scenery, Lunar, Solar or Planetary, | Snapshots and recordings by category. Older category folders are moved to the `_video` name at startup. |
| `MyWorks/Scenery_motion/` | 64-bit only: motion recordings (files-and-album R16a). |
| `Autorun/<type>/`, with type Light, Dark, Bias or Flat, | Legacy sequence frames ([sequences R20b](../control/legacy-plans-and-sequences/sequences.md)); light frames add a target folder. `Autorun/Dark` also receives the periodic dark captures (OBSERVED 2026-10-17). |
| `Plan/` | The multi-target plan worker saves with the Autorun builder under this name. Whether any current app flow reaches it is unresolved. |
| `Preview/` | The `save_image` single-frame save. |
| `Video/` | A fallback for recordings and snapshots that have no category. Whether a current app flow reaches it is unresolved. |
| `log/` | `Autorun_Log_*.txt`. |
| `dark_test/`, `batch_stack_tmp/`, `.StackReplayTemp/` | Diagnostic and working folders. The replay folder holds numbered JPEG frames that the replay encoder turns into `*_stack_replay.mp4` at 10 frames per second. |

R14. Folders under the fixed `/boot/Image/` path, whichever storage root is selected (READ): `darklibrary/<N>s/` (temperature master darks, R9), `AF_imagelog/` (autofocus `.fit` frames when a diagnostic flag is on), `tmp_stitch/` (mosaic stitch work files), and `solve_fail_img/<page>/` (a failed solver `.fit`, when a diagnostic flag is on). Autofocus diagnostic PNG files with timestamped names can be written directly in the root. `ai_process` is a path the file server maps to a temporary directory, not a folder of the image volume (INFERRED from the mount setup).

R15. `Live` and `Live/Light` are not present as paths in either architecture of 9.75 or 9.31, and nothing was found that writes them. READ. Whether a firmware before 9.31 used them is unresolved. Firmware 9.31 already uses `MyWorks`.

R16. File types (READ): `.fit`; a large `.jpg` and a `_thn.jpg` thumbnail beside a saved frame; `.avi` (raw video is `-RAW.avi`, 8 bits per pixel in the inspected branch) with a small text file of acquisition data; `.mp4`; `*_stack_replay.mp4`; `startrails_video_*.mp4`, with `STS_`-prefixed names for batch tasks; CSV; and `.png` diagnostics. No default MP4 bitrate was recovered. INFERRED arithmetic only: raw 8-bit video at 1920 by 1080 and 30 frames per second is about 3.7 GB per minute, and a compressed stream is about 7.5 MB per minute for each Mbit/s of bitrate. On a FAT-type filesystem the raw AVI writer stops near 4.28 GB; on other filesystems it sets no such limit. READ.

R17. Unfinished writes (READ): the common MP4 recorder writes `<name>.mp4.tmp` and renames it when finished, and a failure removes it, though a crash can leave the temporary file (INFERRED). FITS and AVI files are written under their final names, so a final name does not show that a file is complete, and stable size or modification time does not either (INFERRED). No closed-file marker was found in the inspected album and file-serving paths.

R18. Album reach (READ): an album request with no folder name lists only the `MyWorks` subtree, skips dot-named entries, and hides raw AVI files that have an MP4. `Autorun`, `Plan`, `Preview`, `Video`, `log` and every fixed-path folder above fall outside the default listing; an explicit folder name can still be requested. The app has no root-folder browser. The `.DS_Store` files seen in the OBSERVED listings have no imager writer (INFERRED: left by a macOS client).

## Reachability

R10. Network reach: TCP 445 is the SMB port (OBSERVED 2026-10-16). TCP 139 also accepts
connections; a connection that sent nothing was held open for about 5 s with no data from the
device. OBSERVED 2026-10-16. That 139 is Samba's NetBIOS session service is INFERRED; no session
request was sent. Which interfaces the server binds, and whether the NetBIOS name service answers on
UDP 137/138, are unresolved (the tunnel used for observation carries TCP only).

R11. The app's remote tunnel profile never maps 445 or 139
([p2p-tunnel/seestar-profile.md](../transport/p2p-tunnel/seestar-profile.md)). READ. The device's
tunnel server allows every requested remote port
([framing.md R20](../transport/p2p-tunnel/framing.md)), READ; a client that requested a 445
mapping had it accepted and forwarded. OBSERVED 2026-10-16. SMB is therefore reachable remotely
by any client holding a tunnel session, although the app never uses it. INFERRED.

R12. A client MUST NOT rely on SMB for app-compatible behaviour, and a stand-in device need not
offer it. INFERRED.

## Device as SMB client

The firmware also contains a crash-report uploader that acts as an SMB **client** (SMB3, falling
back to SMB2) towards a fixed vendor-internal host. READ. It is not part of the device's server
and is outside this specification; its host and account are not reproduced.

## Open questions

- Firmware 9.75: `darklibrary/` does appear at the share root after a temperature-keyed dark
  capture has actually run (R9, OBSERVED). Whether `MyWorks/` itself contains anything unexpected
  was not checked. unresolved.

- Samba configuration: upper protocol limit, signing, encryption, workgroup, security mode,
  guest write access, accounts. unresolved.
- The service behind TCP 139, UDP 137/138, bind interfaces. unresolved.
- NetBIOS name and the 32-bit host name. unresolved.
