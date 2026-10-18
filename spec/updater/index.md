# Updater process

This chapter covers the updater process: its JSON control and event server on TCP 4350, its
binary upload socket on TCP 4361, the legacy firmware-upload flow the app uses, and the newer
app OTA methods. The release app 3.3.2 does not reach the OTA methods; firmware 9.75 implements them ([OTA methods (firmware 9.75)](#ota-methods-firmware-975)). It sits beside the imager control
stream (TCP 4700, [../control/session-handshake.md](../control/session-handshake.md)) and the
guider ([../guider/index.md](../guider/index.md)); below it are the device's update script and
storage. See [../00-overview.md](../00-overview.md) for the process map.

App names: “Update Firmware” uses the upload and OTA flows here. Names are the English strings of
iOS app 3.4.0; links are READ (app call sites) unless marked.

> **High-risk operation.** A firmware upload replaces device software and can update the
> mount firmware. An interrupted or malformed update can leave the device unusable. This
> chapter describes the protocol so that clients and stand-in devices interoperate. It is not
> a procedure. Implementers MUST NOT exercise the upload path on a real device to "test" it,
> and nothing here was validated by doing so.

## Conventions

Labels, RFC 2119 keywords and the request/reply envelope follow
[../guider/index.md: Conventions](../guider/index.md#conventions). Basis: static analysis of
firmware 9.31 (updater ELF, both builds) and app 3.3.2. One item is OBSERVED and dated. Statements are
firmware 9.31 unless tagged otherwise; firmware 9.75 (app 3.4.0) changes are tagged and collected in
[firmware-975-changes.md](firmware-975-changes.md). The package contents of both firmware versions
are in [firmware-975-package.md](firmware-975-package.md).

## Contents

This page is the updater chapter itself. Its companion pages:

- [Legacy update flow in firmware 9.75](legacy-update-flow.md)
- [Firmware 9.75 version-delta index](firmware-975-changes.md)
- [Firmware package contents: 9.31 to 9.75](firmware-975-package.md)

## Endpoints

| Port | Content |
|---|---|
| TCP 4350 | JSON control requests, replies and updater events. READ. |
| TCP 4361 | Raw binary upload stream; no JSON and no events on this socket. READ. |

R1. Framing on 4350 is the shared JSON socket server's: one JSON text per line, CRLF after
each device line. READ (shared server class) / INFERRED (identity with the imager framing).
Clients MUST terminate each request with LF or CRLF.

R2. On connect the updater sends a [`Version`](../../docs/control/events/Version.md) greeting with exactly `Event`, `Timestamp` and
`name` (the literal `ASI AIR updater`). READ; OBSERVED 2026-10-12 on a passive connection.

```text
{"Event":"Version","Timestamp":"1234.123456789","name":"ASI AIR updater"}
```

R2a. Admission on 4350 and 4361 is open. READ (64-bit; 32-bit has the same log texts, limits
not checked). Each port accepts any TCP peer: the peer address is used only for logging, and
there is no client-auth, verification or address check. Each port keeps at most 2 connections;
a further connection is accepted and closed at once. A connection with no received data for
15 s is closed. A client SHOULD keep 4350 alive with the `test_connection` heartbeat ([Legacy upload flow (begin_recv)](#legacy-upload-flow-begin_recv)) and
SHOULD NOT hold more than one connection per port. INFERRED (client advice).

## Registered methods

In firmware 9.31 the updater registers four methods, identically in both builds. READ. Firmware
9.75 registers ten (both builds): the four below plus the six OTA methods of [OTA methods (firmware 9.75)](#ota-methods-firmware-975). READ.

| Method | Card | Status |
|---|---|---|
| `test_connection` | [control/test_connection](../../docs/control/methods/test_connection.md) | shared liveness method (catalogued under control) |
| `trigger_test_crash` | [control/trigger_test_crash](../../docs/control/methods/trigger_test_crash.md) | diagnostic; clients MUST NOT send it |
| `begin_recv` | [begin_recv](../../docs/updater/methods/begin_recv.md) | READ ([Legacy upload flow (begin_recv)](#legacy-upload-flow-begin_recv)) |
| `stop_recv` | [stop_recv](../../docs/updater/methods/stop_recv.md) | READ ([stop_recv](#stop_recv)) |
| `ota_get_current_manifest`, `ota_get_session`, `ota_begin`, `ota_prepare_module`, `ota_retry_upgrade`, `ota_abort` | [OTA methods (firmware 9.75)](#ota-methods-firmware-975) | firmware 9.75 only; READ |

Replies use the common envelope: `result` and `code` 0 on success; `error` and a nonzero
`code` on failure. READ (shared server). Any other method name gets error 103 (method not
found) with the request's `id`. A request without a usable `method` gets 100. READ.

## stop_recv

R3. `stop_recv` reads no params. The updater compares the requesting connection's source
string byte-for-byte with that of the connection currently receiving, and on a match clears
the active-receive flag. READ.

R4. The reply is always result 0, whether or not the comparison matched. A client MUST NOT
treat result 0 as proof that a transfer was stopped. READ.

## Legacy upload flow (begin_recv)

The app's legacy device-firmware screen performs this flow. The request shape and the app's
expectations are READ from app 3.3.2. The updater side (R5a to R5c, R7a, R7b) is READ from
firmware 9.31.

```text
app                                updater :4350            updater :4361
 |-- connect (10 s timeout) ------------>|                        |
 |-- connect (10 s timeout) --------------------------------------->|
 |<-- Version {name:"ASI AIR updater"} --|                        |
 |-- begin_recv (id 100) --------------->|                        |
 |<-- reply code 0 ----------------------|                        |
 |== raw file bytes ------------------------------------------------>|
 |<-- Receive {state:"complete"} --------|                        |
 |<-- Update {state:"working", desc} ... |                        |
 |<-- Update ... (or state "fail")       |                        |
```

R5. Request sent by the app, as one LF-terminated line. READ (app):

```text
{"id":100,"method":"begin_recv","params":[{"file_name":"air","run_update":true,"file_len":<int>,"md5":"<32 lowercase hex digits>"}]}
```

`file_len` is the byte length of the image and `md5` its MD5 digest, both of the file the app
bundles. READ (app). The updater's handling is in R5a to R5c.

R5a. Firmware 9.31. `begin_recv` takes params as an object or a one-element array. In firmware 9.31, both builds, `begin_recv` reads `file_name` and `md5` from string members, `file_len` from an integer member, and `run_update` from a boolean member. Missing params give 107. A zero file length or empty filename gives error 1; an absent or differently typed `run_update` does not independently cause that error. READ. Duplicate-member interoperability policy remains unspecified. Firmware 9.31, both 64-bit and 32-bit builds, also recognizes `run_update` as a JSON boolean: `true` sets the receive flag and `false` clears it. The flag starts false; numeric and string values are ignored. This same type handling is present in both firmware 9.75 builds. READ. Handling a differently typed occurrence does not reset an earlier boolean assignment. A `file_name` that begins with a dot, contains `..`,
exceeds 255 bytes or has characters other than letters, digits, `-` and `_` gives 102. The file is created in the updater's private directory under
the device user's home; failure to create it gives 258. READ.

R5a1. Firmware 9.75 (64-bit build, READ; the 32-bit build has the same method and the `run_update`
string but no legacy-lock code, INFERRED from absence). The handler requires an object after the
shared array-to-object step (otherwise 107; the one-element array form of R5 is unverified in
firmware 9.75). The members are typed strictly by the JSON parser:
- `file_len` is accepted only as a JSON integer. A float or a string such as `"123.0"` is not
  accepted and `file_len` stays 0.
- `file_name` and `md5` MUST be strings.
- `run_update` is accepted only as a JSON literal: `true` sets it and `false` clears it. A numeric
  `1` is not accepted and the flag stays false. Firmware 9.75 accepts the app's `true` literal.
  Firmware 9.31 handles `run_update` the same way (R5a).
- A `file_len` of 0 (a signed-integer test only) or an empty `file_name` gives error 1 with the text
  "expected param". The `file_name` rules (102) are unchanged from 9.31.
- With `run_update` true the destination path is the legacy update package directory plus
  `file_name` and the handler does not create the file itself; with `run_update` false the path is
  in the temporary directory and the handler creates the file, failure giving 258 "fail to create
  file". The legacy package directory is `/etc/zwo/update` on the S30 Plus model class and
  `/tmp/zwo/update` otherwise. READ. Success is result 0.

R5b. Firmware 9.31. The handler arms the caller's own 4361 connection. If there is none, or a receive or
update is already running, the reply is 524 and a failed update result is recorded. A client
MUST open 4361 before sending `begin_recv`. READ. On success the reply is result 0. READ.

R5b1. Firmware 9.75 (64-bit, READ). `begin_recv` validates the params and builds the path first, then
calls the shared receive-preparation routine. On failure it records a failed update result with the
error code and text and returns that error. The preparation errors are: 524 "is already updating"
(a script thread is running); 524 "<ip> is already receiving", "<ip> is already running script" or
"receive is already running"; 524 "failed to acquire legacy update lock"; and 257 "failed to prepare
legacy update directories". The "binary port is not connected" branch does not set an error code,
so the code returned for it can be stale or 0 (INFERRED; the text is the same in 9.31). The legacy
ordering is therefore unchanged for the client: open 4361, then send `begin_recv`. When the shared
routine is entered in pending mode (the OTA path, [changes R12e](ota-package-handling.md#ota-package-handling))
it stores the pending record and its start time instead.

R5b2. Legacy update lock (firmware 9.75, 64-bit build only, READ; the 32-bit updater has none of the
lock or marker strings, INFERRED from absence). When `run_update` is true and the receive is not
pending, the preparation routine takes a non-blocking exclusive lock on a lock file under the
device's temporary zwo directory, clears the legacy update directory (a failure is logged and the
receive continues), reserves the receive file, and releases the lock before it returns. The lock
therefore covers only the directory clear and the reservation, not the transfer or the
installation. A second caller that cannot take the lock gets 524 "failed to acquire legacy update
lock". The failure paths of the update status poll (R8a) clear the legacy directory under the same
lock and skip the clean-up, with a log line, when it is held. A marker file named for the legacy
update monitor is written with the text "done" on every terminal path of the status poll; a failed
write ends the poll with code 207. The marker is the one the update script waits for
([changes R13a](legacy-update-flow.md#legacy-update-flow-in-64-bit-firmware-975)). In firmware 9.75, 64-bit build, the legacy update launcher removes a stale monitor marker before updating. Its background subshell runs the delivered update script, then waits for the marker only if that script advertises the cleanup protocol. It uses a regular-file test and performs at most 150 sleeps of 0.1 seconds before logging a timeout and attempting cleanup. It removes the marker afterward and exits that background subshell with the delivered script's saved status. It does not read the marker contents. READ. No additional exact-basename consumer was found in the supplied package files; other images, constructed paths and subsequently delivered payloads remain unresolved. INFERRED. The exact basename was not found in either firmware 9.31 package or the firmware 9.75 32-bit package; equivalent behavior under another name is unresolved.

R5c. After the transfer the updater checks the MD5 against `md5`, then verifies a detached
`update-package.sign` signature over a SHA-1 digest of the package, using the system `openssl`
tool and a built-in public key written out to a temporary file
([embedded-constants.md: Update-package signing public key (device)](../auth/cloud-auth/embedded-constants.md#update-package-signing-public-key-device));
either failure gives a failing `Receive` state (R7a). READ. `file_len` is the expected length and
`run_update` gates installation. INFERRED. In firmware 9.75 `run_update` true selects the legacy
package directory (R5a1) and the lock (R5b2).

R6. The app starts streaming only after a reply with code 0, and streams the file as raw
bytes on 4361 with no header, length prefix or trailer. READ (app). A nonzero code is an
upgrade error to the app; the app special-cases 207 and 524. READ (app). The updater's
`begin_recv` emits 524 (R5b); 207 was not seen in that handler. READ.

R7. The end of the transfer is signalled by the updater's `Receive` event on 4350: `state`
`complete` on success, otherwise a failure string. A client MUST treat any value other than
`complete` as failure. READ. If the 4361 socket closes before the app has sent the whole
file, the app waits 10 s for a 4350 result before reporting failure. READ (app).

R7a. The failing `Receive` values are `recv interrupted`, `timeout`, `recv timeout`,
`md5 verify_fail`, `verify_fail` and `verify_fail: sign`. READ. The updater also records a
result code: 201 for a receive failure, 204 for a timeout, and 525 for an interruption, an MD5
failure or a signature failure. READ. That these codes reach the `Update` event's `code` is
INFERRED.

R7b. The updater ends a 4361 receive that stays idle for about 10 s, and closes any 4350 or 4361
connection that has had no activity for 15 s (R2a; its log calls this a "no connection"
timeout). READ.

The legacy screen also sends the `test_connection` heartbeat on 4350 every 3000 ms while the
update socket is open. READ (app).

## Events

Updater events go only to 4350 connections whose IP string equals the target client's (an
IP-matched send); several connections from one host all receive them, other hosts receive
nothing. The sender adds an empty `route` array. READ.

| Event | Members | Meaning |
|---|---|---|
| `Version` | `name` | greeting (R2) |
| [`Receive`](../../docs/updater/events/Receive.md) | `state`, `route` | upload result (R7) |
| [`Update`](../../docs/updater/events/Update.md) | `state`, `desc`, `error`, `code`, `route` | installation progress |
| [`OtaUpdate`](../../docs/updater/events/OtaUpdate.md) | `state`, `stage`, `module`, `code`, `error`, `main_version`, `need_reboot`, `route` | OTA session progress (firmware 9.75 only, [OTA methods (firmware 9.75)](#ota-methods-firmware-975)) |

R8. `Update` reports installation progress after a successful receive. `state` is `working`
or `fail`. `desc` carries a stage marker, not a percentage. READ. Markers in the firmware:

| `desc` | Stage |
|---|---|
| `copy file` | copying the received image |
| `write disk` | writing to storage |
| `update mount FW` | updating the mount firmware |
| `restart server` | restarting services |

The app also handles `retry mount FW update`. READ (app). No 9.31 firmware binary emits it.
READ (exhaustive search for absence).
R8a. Failing `Update` codes (firmware 9.75, 64-bit build, READ for the codes; the same constants
exist in 9.31). The status poll ends a failed update with a failure notification whose numeric code
is 204 for a 900 s timeout, 529 for an "update error" status, and 207 when the update output file is
not found, the poll is aborted before it appears, or the done marker cannot be written (R5b2). The
notification carries the strings "fail" and "error" and the code; that these are the `state` and
`desc` or `error` members of the wire event is INFERRED, because the member names were not traced.
In 9.75 the failure path also clears the legacy update directory and writes the done marker.

The updater produces these events by polling the update script's status with short sleeps
(50 to 200 ms); there is no fixed cadence. READ.

R9. After `restart server` the device restarts services and connections drop. A client MUST
expect the 4350 socket to close without a final success event. INFERRED.

## OTA methods (firmware 9.75)

Firmware 9.75 (app 3.4.0) implements, in both builds, the OTA methods that app 3.3.2 already sends (R10, R11). Firmware 9.31 had none. App 3.3.2 has a newer OTA channel that sends these methods on 4350 (CRLF-terminated JSON,
`id` 100, `params` added only when non-null, so omitted for the null-param methods;
READ (app 3.3.2)) and a `test_connection` heartbeat (`id` 1) every 4000 ms. Module files are streamed
raw on 4361 with no header. READ (app).

R9a. App request order. The app sends one OTA request at a time. It treats a 4350 line as the
reply when its `id` is 100 or its `method` equals the pending method, and it routes lines with
`Event` `OtaUpdate` to its event handler. Before it downloads a package, the app reads
`ota_get_current_manifest` to compare versions. An upgrade then runs in this order:
1. `ota_get_session`. The app continues only when `stage` is blank, `idle`, `fail` or
   `complete`.
2. `ota_begin`. `target_manifest` is the downloaded manifest, and `send_modules` lists the names
   of the package files to be sent.
3. For each module in manifest order, `ota_prepare_module` `{name}`. When the reply's
   `already_received` is true, the app skips that module. Otherwise it streams the file on 4361,
   then waits for an `OtaUpdate` event with `state` `working` and the expected stage.
4. After the last module, it waits for `OtaUpdate` `working` with `stage` `upgrading`.

At any of these waits, a `fail` or `complete` event ends the run. The app ignores the reply's
`binary_port` and always streams to 4361. The app never sends `ota_retry_upgrade`: its retry
action restarts the whole sequence from `ota_get_session`. Before each step it checks that the
connected device serial is still the target serial. READ (app 3.3.2). The stage the app expects
after each module is INFERRED to be `receiving`.

R9b. Package source and reachability. The OTA screen is the only caller of these methods. Its
entry sits in the device beta settings and is shown only when a developer switch is on, and in
the release build of app 3.3.2 that switch is a constant false. READ (app 3.3.2). The release app
therefore never runs this channel and updates only through the legacy flow ([Legacy upload flow (begin_recv)](#legacy-upload-flow-begin_recv)) with the image it
bundles. INFERRED. When it does run, the screen asks the vendor API for the target with
`POST v1/upgrade` (query `appPlatform`, `appVersion`; body `product`, `deviceModel`,
`hardwarePlatform`, `systemArchitecture`, `mainVersion` and `modules` [{`name`, `version`}]
from `ota_get_current_manifest`). The reply carries `schemaVersion`, `mainVersion`,
`releaseTime`, `forceUpdate` and `modules` [{`name`, `version`, `size`, `sha256`, `url`}]. The app
downloads each module from its `url` into its cache and rejects a file whose size or SHA-256
does not match. READ (app 3.3.2). The server's replies are unresolved (server-side).

R9c. Legacy flow trigger. The app picks the bundled 64-bit image when the device reports
`firmware_platform` 1 ([device-state R2a](../control/device-state-and-settings.md)) and the 32-bit
image otherwise. It sends that image's length and MD5, which are build constants. It offers an
upgrade to the connected master device when the device's firmware version number is below the
bundled one (2931, "9.31", for both images in app 3.3.2), and it treats a version below 2626 as a
forced upgrade. READ (app 3.3.2).

| Method | Params (app DTO) | Card |
|---|---|---|
| `ota_get_current_manifest` | none | [card](../../docs/updater/methods/ota_get_current_manifest.md) |
| `ota_get_session` | none | [card](../../docs/updater/methods/ota_get_session.md) |
| `ota_begin` | `{send_modules: [string], target_manifest: {main_version, modules: [{name, sha256, size, version}]}}` | [card](../../docs/updater/methods/ota_begin.md) |
| `ota_prepare_module` | `{name}` | [card](../../docs/updater/methods/ota_prepare_module.md) |
| `ota_retry_upgrade` | none | [card](../../docs/updater/methods/ota_retry_upgrade.md) |

The table lists the app 3.3.2 request shapes; the firmware 9.75 reply and error shapes are on the cards.
`ota_abort` is firmware 9.75 only: the app 3.3.2 DTOs have no abort call.

| Method | Params (firmware 9.75) | Card |
|---|---|---|
| `ota_get_current_manifest` | none | [card](../../docs/updater/methods/ota_get_current_manifest.md) |
| `ota_get_session` | none | [card](../../docs/updater/methods/ota_get_session.md) |
| `ota_begin` | `{send_modules: [string], target_manifest: {main_version, modules: [{name, sha256, size, version}]}}` | [card](../../docs/updater/methods/ota_begin.md) |
| `ota_prepare_module` | `{name}` | [card](../../docs/updater/methods/ota_prepare_module.md) |
| `ota_retry_upgrade` | none | [card](../../docs/updater/methods/ota_retry_upgrade.md) |
| `ota_abort` | none | [card](../../docs/updater/methods/ota_abort.md) |

R10. Firmware 9.31 registers none of these names and no alias to `begin_recv` exists; a client
MUST NOT assume a firmware 9.31 device answers them. Firmware 9.75 registers all six in both
builds (READ); the app request shapes match the firmware parser (READ). Each handler resets the
thread error code and calls one OTA manager object; it does not use the secure-session layer of
the imager and guider (READ), and whether 4350 JSON is wrapped is not established.

R10a. The OTA session has the stages idle, pending, receiving, upgrading, complete and fail
(firmware 9.75). READ. A call that is not allowed in the current stage is refused with 524 and a
text naming the stage. The device keeps received module packages across sessions and reuses those
whose size and SHA-256 still match. READ.

R10b. The device identity in `ota_get_current_manifest` is build-specific (firmware 9.75): hardware
platform `1126bp` and architecture `aarch64` on the 64-bit build, `1126` and `armv7l` on the 32-bit
build. READ. The model name maps the internal S30P, S50P and S30Plus to S30 Pro, S50 Pro and S30
Plus. READ. Modules are delivered as packages over TCP 4361 and installed by the device; the
package format, checks and error codes are in
[OTA package handling](ota-package-handling.md#ota-package-handling).

R11. The `OtaUpdate` event ([card](../../docs/updater/events/OtaUpdate.md)) is emitted by firmware
9.75 with the members the app consumes plus `module` and a `cancel` state. READ. Unlike `Update`
and `Receive`, which go to one client's address, `OtaUpdate` is a broadcast: both the progress and
the completion notification are sent through the event server without a requester address or
socket (firmware 9.75, 64-bit build, READ). Whether every retained event socket receives it, and
the 32-bit recipient rule, were not separately audited. No emitter existed in firmware 9.31.

R11a. `ota_abort` (firmware 9.75, 64-bit build, READ; the 32-bit build has the same integer
result). Success is `result` 0, including when the session is idle, and also stops the binary
receive for the caller's address. While the stage is upgrading the call is refused with 524.

R11b. `ota_get_session` result members by stage below describe firmware 9.75, 64-bit build. The 32-bit difference is stated after the table. READ.

| Stage | Members present |
|---|---|
| idle | `stage`, `received_modules` |
| pending, receiving | `stage`, `target_main_version`, `received_modules`, `receiving_module`, `missing_modules` |
| upgrading | `stage`, `target_main_version`, `received_modules` |
| complete | `stage`, `target_main_version` |
| fail | `stage`, `target_main_version`, then `failure` when the failure flag is set, then `received_modules`, `receiving_module`, `missing_modules` |

`received_modules` entries are `{name, version, sha256}`. `receiving_module` is an array holding one
`{name, version, sha256}` object when a receiving module is set and found, otherwise empty (at
most one element is INFERRED). `failure` has `stage`, an optional `module`, an integer `code` and
`error`. A client MUST NOT expect every member in every stage. In firmware 9.75, 64-bit build, `failure` is included only in stage `fail` when a stored failure is present. It contains `stage`, integer `code` and string `error`; `module` is included only when the stored module-name string is nonempty. The 32-bit build omits `failure`, including in stage `fail`. In both builds, `missing_modules` is an array of objects with string members `name`, `version` and `sha256`, or `[]` when no entries qualify. READ. Complete session-result parity between the builds is not implied by these details.

## Open questions

| Question | State | Where |
|---|---|---|
| Wire member names of the failing legacy `Update` event (R8a) | INFERRED; the codes are read, the member names are not traced | [Events](#events) |
| Delayed-reboot helper prefix; other legacy marker consumers | Firmware 9.75 helper prefix and 2-second delay read on both builds. The 64-bit local wrapper consumer is read; consumers outside the searched package files remain unresolved. | [changes R12c](ota-package-handling.md#ota-package-handling), R5b2 |
| `begin_recv` "binary port is not connected" error code (stale or 0) | INFERRED | R5b1 |
| `ota_get_session` failure-module condition and missing-module entry shape | Resolved for firmware 9.75: conditional stored module name on 64-bit; no `failure` on 32-bit; three-string missing-module objects on both builds. READ. | R11b |
| Firmware 9.75, 32-bit legacy `Update` codes | unresolved here; the OTA reboot delay is read as 2 seconds | R8a, [changes R12c](ota-package-handling.md#ota-package-handling) |

## Appendix: Validating on a live device (non-normative)

The only safe live check is passive: connect to 4350, read the `Version` greeting (R2), and
disconnect without sending anything. That check was made on 2026-10-12. Do not send
`begin_recv`, `ota_*` methods or bytes on 4361 to a real device.
