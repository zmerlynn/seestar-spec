# Updater: OTA package handling

Basis: static analysis of firmware 9.75, 64-bit and 32-bit builds; the 32-bit updater was compared by strings and symbols only. Nothing here was validated on a device.

## OTA package handling

R12. A module is delivered as `<name>.tar.bz2` over the existing binary channel on TCP 4361 and is
checked by byte count and SHA-256 against the target manifest before it is renamed from a partial
file. A mismatch is error 525 and a failed rename 515. READ (firmware 9.75, 64-bit).

R12a. The upgrade of each received module runs the 9.31 pattern. READ (firmware 9.75, 64-bit):
1. A package of 128 bytes or less is rejected. Otherwise the last 128 bytes are split off as an
   RSA signature over the SHA-1 of the rest; the signature is verified with the same built-in
   public key as in 9.31
   ([embedded-constants.md: Update-package signing public key (device)](../auth/cloud-auth/embedded-constants.md#update-package-signing-public-key-device)).
   The 128-byte signature size is INFERRED from a size comparison.
2. The remainder is decrypted with AES-256-CBC (password-based key derivation) using a fixed
   package password that is the same for every device. The value is deliberately not given here.
   The decrypted data is a bzip2 tar archive that is extracted into a per-module work directory.
3. `module.manifest` is validated (R12b), then `upgrade.sh` in the work directory is made
   executable and run; its exit status and an optional `need_reboot=true|false` line (default false)
   are read from its output.

R12b. `module.manifest` must have `schema_version` 1, a `module_name` and `module_version` that
match the target manifest, and lists `products`, `hardware_platforms`, `device_models` and
`system_architectures` that contain the device's own `seestar`, platform, model and architecture
values ([index.md R10b](index.md#ota-methods-firmware-975)). A mismatch is error 102. READ.

R12c. When every module succeeded the device writes the local manifest (a temporary file renamed
over the manifest file in the device user ASIAIR directory), emits `OtaUpdate` with state `complete`, plays a sound and,
when `need_reboot` is true, schedules a delayed reboot. READ. The delay is 2 s: the device starts a
detached shell that sleeps 2 s and then runs the device's shutdown helper script with the argument
`reboot`, with all output discarded; a failure to schedule it is reported as "schedule ota reboot
failed". READ (64-bit build; in the 32-bit build the command prefix exists but the delay value was
not verified). Which directory the helper script is taken from is unresolved.

Error codes in OTA replies and `OtaUpdate` events (firmware 9.75, 64-bit, READ unless noted):

| Code | Meaning |
|---|---|
| 101 | `module.manifest` invalid |
| 102 | Validation failure (parameters, manifest, module not listed) |
| 105 | `ota_prepare_module` needs a string `name` |
| 107 | Missing params |
| 207 | `upgrade.sh` could not be run (INFERRED mapping) |
| 214 | `upgrade.sh` reported failure (INFERRED mapping) |
| 218 | Writing the public key or splitting the package failed (INFERRED mapping) |
| 255 | Retry: module package missing or not received |
| 257 | Temporary directory cannot be created |
| 515 | Package could not be saved or the local manifest could not be replaced (partly INFERRED) |
| 546 | Pending receive timed out: the binary connection did not arrive within 15 s of `ota_prepare_module` (text "ota module binary connection timeout"). New in firmware 9.75, 64-bit, READ |
| 524 | Stage conflict or busy |
| 525 | Package size or SHA-256 mismatch |
| 529 | Package extraction failed |

R12d. The on-device manifest is a JSON object with `schema_version` 1, `main_version` and
`modules` [{`name`, `version`}]. If it is missing or invalid, `ota_get_current_manifest` returns
only the device identity and the client treats the device as needing a full OTA. READ.

R12e. Receiving. Firmware 9.75 adds a pending-receive record to the binary server: the
`ota_prepare_module` reply arms a receive keyed by the caller's address, which times out after 15 s
if the stream does not start. READ (15 s from a 15000 ms comparison). The check runs once per
loop of the updater's network thread, whose select timeout is 5 s, so the timeout fires within about
5 s after the 15 s mark. It clears the pending record and fails the receive with code 546 and the
text "ota module binary connection timeout" (READ, both the 64-bit and 32-bit builds; the 32-bit
checking function uses the identical 15000 ms and 546 constants, confirmed by disassembly). A
separate session-level timer reports
"ota_prepare_module was not called within pending timeout" (its 15 s value is INFERRED). The network
thread's idle timeout per connection is 10 s normally and 15 s when the connection's receive flag is
set; firmware 9.31 used a fixed 15 s, so the flag-dependent choice is new in 9.75 (READ). The control
server stays on 4350, and the updater records 4361 as the binary port reported by
`ota_prepare_module` at a second site next to the one that starts the binary server (READ). This means the legacy rule
that the caller's 4361 connection must already exist ([index.md R5b](index.md#legacy-upload-flow-begin_recv))
is not carried over to the OTA path automatically; the exact ordering is INFERRED. The legacy
`begin_recv` ordering is unchanged for the client: it validates, then calls the shared
receive-preparation routine, which now also takes the legacy lock (READ,
[index.md R5b1](index.md#legacy-upload-flow-begin_recv)). Whether the OTA pending mode requires the
connection to exist before `ota_prepare_module` remains INFERRED.

R12f. Version-info function. In firmware 9.75 the updater and the imager each contain a function
that returns OTA version information (a main version and a list of module versions). READ
(64-bit; the 32-bit updater has a counterpart). The updater's version reads the local manifest file
in the device user ASIAIR directory and parses it as JSON (the file of R12d); it contains no socket
or HTTP code. There is no outbound OTA-version query on TCP port 80: an earlier reading that took
80-byte list-node deallocations for a port immediate is withdrawn, and the listener and client sets
are unchanged ([ports.md](../transport/ports.md)). The imager's counterpart is the source of the
`main_version` and `modules` members of the `Version` event (see
[Version](../../docs/control/events/Version.md)), and the imager's cloud enrollment (`remote_join`)
calls it before it reports the OTA version, where firmware 9.31 reported the legacy firmware version
directly. READ. The cloud wire effect of that report is the OTA version and status reports named in
[cloud-auth.md](../auth/cloud-auth.md). The guider's counterpart was not examined in this review;
no HTTP use was found for it.

