# Maintenance, activation and diagnostic methods

This chapter covers firmware and device identity reporting (the `Version` greeting, the
`device` section of `get_device_state`), activation, factory test and shipping operations,
downgrade markers, demonstration mode, and the diagnostic and dangerous methods (`popen`,
`trigger_test_crash` and similar). It sits on the JSON-RPC envelope and event framing
([session-handshake.md](session-handshake.md), [events-overview.md](events-overview.md)). Related
chapters: [device-state-and-settings.md](device-state-and-settings.md) (snapshot),
[power-and-storage.md](power-and-storage.md) (shutdown, format). The firmware updater service is
specified in [updater/index.md](../updater/index.md).

App names: “Demonstration Mode” is the demonstrate worker (the split between it and “Exhibition Demo
Mode”, which may set `mock_mode`, is INFERRED); “Simulated Stargazing” is `user_stack_sim`; “Factory
Mode” drives the factory test methods. Names are the English strings of iOS app 3.4.0; links are
READ (app call sites) unless marked.

## Conventions

RFC 2119 / RFC 8174 key words bind clients. Labels **READ**, **OBSERVED**, **INFERRED** and
**unresolved** are used as in [plan-scheduling.md: Conventions](plan-scheduling.md#conventions). READ claims are
for the 64-bit imager build of firmware 9.31; the 32-bit build is "probable" unless stated.

Basis: static analysis of firmware 9.31 and app 3.3.2; the greeting shape also
OBSERVED(2026-10-12).

## Risk classes

Every method in this chapter is assigned one risk class. The class is normative guidance for
clients; the facts behind it are labelled in the sections that follow.

| Class | Meaning | Methods |
|---|---|---|
| Safe | read-only or logging only | `need_reboot`, `is_downgraded`, `pi_is_verified`, `test_connection`, `get_pcdid` |
| Operational | changes state the user expects to change | `get_factory_test_state`, `start_demonstrate`, `stop_demonstrate`, `play_sound`, `clear_downgrade`, `update_comet_txt`, `pi_vl805_version`, `test` |
| Destructive | loses data, identity or availability | `factory_test_control`, `pi_encrypt`, `trigger_test_crash` |
| Arbitrary execution | runs caller-supplied commands on the host | `popen` |

R1. A general-purpose client MUST NOT send methods in the Destructive or Arbitrary execution
classes except on explicit, informed user request. Normative.

R2. A stand-in device MAY refuse Destructive and Arbitrary execution methods with code 210
(`not supported`). Normative (stand-in guidance; not device behaviour).

## Firmware version and identity

### Version greeting

R3. When a client connects, each service sends one [`Version`](../../docs/control/events/Version.md)
event without being asked. READ.

| Member | Type | Present |
|---|---|---|
| `name` | string | always; identifies the service (imager, guider or updater) |
| `firmware_ver_int` | integer | imager only |
| `firmware_ver_string` | string | imager only |
| `is_verified` | boolean | imager only |
| `downgrade_fw_ver_int` | integer | imager, Plus- and Mini-class hardware only, when a staged update package with a parsable version is present |
| `downgrade_fw_ver_string` | string | same condition |
| `main_version` | string | firmware 9.75, imager; from the update manifest; present only when the local manifest read succeeds, with no fallback (READ, both builds; see R5b) |
| `modules` | array of `{name, version}` | firmware 9.75, imager; same source and condition |

READ. OBSERVED(2026-10-12): on the updater port the greeting has exactly `Event`, `Timestamp`
and `name`.

R4. Clients MUST NOT require the version members on guider or updater greetings, and MUST NOT
infer handshake order or authentication state from the greeting alone. READ (device);
normative (client).

### Device section

R5. `get_device_state` with `keys:["device"]` returns `name`, `firmware_ver_int`,
`firmware_ver_string`, `is_verified`, the OS version string (`ios_ver`), the serial number
(`sn`), a CPU identifier (`cpuId`), model fields (`product_model`, `user_product_model`,
`custom_model`), optics (`focal_len`, `fnumber`), `firmware_platform` and capability booleans
(`can_star_mode_sel_cam`, `can_wide_cam_roi`, `can_wide_cam_af`, `can_roi_scale`,
`can_adjust_brightness`, `can_dark_correction`). READ (firmware 9.31).

R5a. Firmware 9.75 adds to `device` six capability flags, `can_motion_monitor`,
`can_dual_capture`, `can_4k_quality`, `can_wide_mosaic_8k`, `can_comet_post_stack` and
`can_roi_smart_follow` (each model has its own mask), plus `main_version` and `modules` as in R3. `can_dark_correction` is now always true. READ.
Clients MUST treat every capability flag as optional.

R5b. The six flags are bits 0 to 5 of one per-model capability mask, in the order listed in R5a (bit
0 `can_motion_monitor`, 1 `can_dual_capture`, 2 `can_4k_quality`, 3 `can_wide_mosaic_8k`, 4
`can_comet_post_stack`, 5 `can_roi_smart_follow`). The six flag names, their listed bit assignments and the listed 64-bit model-mask mapping are READ (firmware 9.75, 64-bit build). The six names and bit assignments are also READ on the firmware 9.75 32-bit build; its model set and masks are stated separately above. The 64-bit masks per model:

| Model identifier | Mask | Bits set |
|---|---|---|
| unknown | 0x00 | none |
| S30, S50 | 0x14 | 2, 4 |
| S30P, S50P, S80 | 0x3b | 0, 1, 3, 4, 5 |
| S30Plus | 0x21 | 0, 5 |
| S50N | 0x20 | 5 |

Firmware 9.75 on both builds emits these six booleans directly from bits 0–5 of a cached per-model capability mask, in the listed order. These field-producing paths add no running-state, camera-open, network or module-version condition. The 64-bit model masks are those in the table; the 32-bit masks are 0 for unknown models and 0x14 for S30 and S50. READ (firmware 9.75, both builds). These advertisements do not establish that an operation succeeds in a particular runtime state.

Firmware 9.75 on both builds includes `main_version` and `modules` only after the local manifest read succeeds. The reader checks an object root, integer `schema_version` against 1, a nonempty string `main_version`, and an array `modules`. Every module entry is checked for nonempty string `name` and `version`; a failed entry check fails the whole read. An empty modules array is accepted. On read or required-field failure, this formatter omits both fields and emits no fallback `main_version`. READ (firmware 9.75, both builds). These manifest-derived fields are absent from the supplied firmware 9.31 formatters on both builds. Integer-representation edge cases beyond the observed schema check remain unresolved.

R5c. `can_comet_post_stack` is the only comet-related member of `get_device_state`. It is a boolean
that is true exactly when bit 4 of the capability mask is set (READ, firmware 9.75 64-bit build): true
for S30, S50, S30P, S50P and S80, false for S30Plus, S50N and an unknown model (model mapping READ, firmware 9.75 64-bit build). It gates nothing on the wire that was found: comet stacking is batch-only (see
[stacking.md R20b](stacking.md#batch-stack)) and there is no comet start or stop method.

R6. `sn` and `cpuId` identify the unit. Clients MUST NOT log or transmit them except to the
vendor service that requires them. Normative.

R7. [`pi_is_verified`](../../docs/control/methods/pi_is_verified.md) returns a boolean. `false` is
a success reply, not an error. It refreshes caches and writes scratch files but activates
nothing. READ. Tier B is INFERRED (probable): it rests on the assumed behaviour of the
utilities the check runs. The app sends it over BLE. READ.

R8. [`get_pcdid`](../../docs/control/methods/get_pcdid.md) returns `{pcbid: integer}`, a board
identifier (0, 1 or 2) derived from an ADC reading. The method name is spelled `get_pcdid`; the
result member is spelled `pcbid`. READ. If the command cannot start, the handler appends
neither `result` nor `error` (READ); the reply then carries only the envelope members (INFERRED).
Clients MUST tolerate such a reply. Normative.

R9. [`pi_vl805_version`](../../docs/control/methods/pi_vl805_version.md) returns the USB-controller
firmware version string. It marks a vendor tool executable and runs it with elevated
privileges. Errors 223, 214. READ. Class Operational: it changes file permissions.

## Update-related markers

R10. [`need_reboot`](../../docs/control/methods/need_reboot.md) returns true when a marker file
left by a firmware update exists. A failed check is `false`, not an error. Tier A. READ.

R11. [`is_downgraded`](../../docs/control/methods/is_downgraded.md) returns true when the update
log shows an update and no acknowledgement marker. An unreadable log gives `false`. READ.

R12. [`clear_downgrade`](../../docs/control/methods/clear_downgrade.md) appends the
acknowledgement marker through a privileged shell command; afterwards `is_downgraded` is false.
Nothing is removed. Error 214. READ.

R13. [`update_comet_txt`](../../docs/control/methods/update_comet_txt.md) requires `{md5: string}`.
The device compares the MD5 of a previously staged comet-data file with the supplied text and,
on a match, installs it. Errors 105, 207 (command failed, digest mismatch or no staged file).
READ. How the file is staged is outside this chapter.

## Activation: pi_encrypt

BLE references in this section use the [BLE transport and activation boundary](../transport/ble.md).

R14. [`pi_encrypt`](../../docs/control/methods/pi_encrypt.md) activates the device. It writes
licence and activation files and, on success, sets the power LED to its "activated" state. It is
not a check; `pi_is_verified` is the read-only counterpart. READ. Class Destructive: a wrong call
can overwrite activation data.

R15. Two request forms exist. Params are an object or `[object]`. Members of the wrong type
are treated as absent. When both legacy members are non-empty the legacy form is used and the
others are ignored. READ.

| Form | Members | Notes |
|---|---|---|
| Legacy | `passwd`, `license` (both non-empty strings) | Not supported on eMMC models (210) |
| Plus | `digest`, a device identity (`sn` or `cpuId`), `auth_code`, `sign` | All must be non-empty (217) |

The Plus-form values are issued by the vendor's activation web service. The app requests them
with the device's serial (and CPU id, model and location when known) and forwards the returned
values over BLE (R15a). READ (app). On the device, `sn` or `cpuId` must match the hardware identity
(222 otherwise); `sign` is Base64 and its RSA public-key recovery must equal `auth_code`;
`digest` is Base64 of an HMAC-SHA256 that the device recomputes and compares. Shell failures give
214, mismatches 222. READ. Which string the digest covers was not traced. unresolved. The app
never sends the legacy form; that pair is checked against a value derived from the CPU id and is
INFERRED to come from a vendor or factory tool. Its format is unresolved. All of these are per-
device secrets; this specification gives no values, and clients MUST NOT log them.

R15a. App side of the Plus form. The app takes `sn`, `cpuid`, `model` and `submodel` from the
result of the BLE `ble_connect` reply. It asks `pi_is_verified` over BLE, and when that returns
false and the user agrees, it POSTs a JSON body to the vendor's `/v1/activation` endpoint. The
body has `sn`, `cpuId` (only when the device reported a CPU id), `model` and `subModel` (only
when non-empty), and `latitude` and `longitude` from the phone's location service (only when a
fix is known). The app sends `sn` and `cpuId` encrypted, not in clear: each is RSA-encrypted
with PKCS#1 v1.5 padding under an RSA-1024 public key compiled into the app
([embedded-constants.md: Activation request public key (app)](../auth/cloud-auth/embedded-constants.md#activation-request-public-key-app)), then Base64-encoded. The reply carries `sn`, `cpuId`, `authCode`,
`digest` and `sign`. The app copies the reply's `sn`, its `cpuId` (only when the device reported
one), `authCode` as `auth_code`, `digest` and `sign` into `pi_encrypt` params `[{...}]`, with
`id` 14, inside a BLE `send_to_air_reply` frame. It treats activation as successful only when
the reply has `result` 0 and `code` 0 or absent. A web-service error 900006 is reported to the
user separately. READ (app 3.3.2). The service computes the digest and the app only relays it,
so the decompile cannot show which string the digest covers.

R16. Errors: 107 (not an object), 102 (neither form present), 217, 210, 222 (old-licence
verification mismatch). The app sends `pi_encrypt` over BLE. READ.

## Factory test and shipping

R17. [`get_factory_test_state`](../../docs/control/methods/get_factory_test_state.md) reads no
params and returns `items` with four operations: `scopePark`, `delUserImages`, `delLicense`,
`setLangEn`. Each has `state`, `idle` or `complete` and no other value (READ; `delUserImages`
reads `idle` while a deletion runs and while any user image remains), and an optional
`record` array of `{userId, platform, appVersion, osVersion, timestamp}` (each member only when
non-empty, `timestamp` only when positive). `scopePark` reads `complete` when the mount altitude
is at or below -85 degrees; `delLicense` when no licence files remain; `setLangEn` when the
language is English. READ. Its altitude query can
trigger a guider reconnect, so it is tier C. READ.

R18. [`factory_test_control`](../../docs/control/methods/factory_test_control.md) requires an
object with string `operation` and optional metadata `userId`, `platform`, `appVersion`,
`osVersion` (strings) and `timestamp` (integer). Parse errors: 107, 105, 104. READ.

| Operation | Effect | Risk |
|---|---|---|
| `scopePark` | homes the mount; completion may be deferred | Operational |
| `delUserImages` | deletes all user images, asynchronously | Destructive |
| `delLicense` | remounts read-write and deletes licence files | Destructive |
| `setLangEn` | sets language to English | Operational |
| `enterShippingMode` | privileged hardware register write, clears shipping records, then shuts down | Destructive |

READ (effects); risk column normative.

R19. Every parsed request replies `result:0`, even when the operation fails or the name is
unknown. The outcome arrives in a [`FactoryTestControl`](../../docs/control/events/FactoryTestControl.md)
event with `operation`, `state` (`complete` or `fail`) and, on failure, `code` and `error`. An
unknown or empty operation fails in the event with 102; other failures carry the helper's code,
or 207 when none is set. READ.

R20. The event is normally sent before the reply. When the operation is deferred (the event
text contains `"pending":true`), the final event comes later. Clients MUST correlate by
`operation`, not by arrival order. READ (device); normative (client).

```
client                                   device
  | factory_test_control {operation:"setLangEn"}
  |--------------------------------------->|  run operation
  | {Event:"FactoryTestControl",           |
  |  operation:"setLangEn",state:"complete"}
  |<---------------------------------------|
  | {result:0,code:0}                      |
  |<---------------------------------------|
```

The `FactoryTestControl` event's optional `record` can be an array or a single object. READ.
Parse errors for `factory_test_control`: 107, 105, 104. READ. `timestamp` is stored as 32 bits,
while the app sends epoch milliseconds. READ / INFERRED truncation.

## Demonstration mode and sound

R21. [`start_demonstrate`](../../docs/control/methods/start_demonstrate.md) reads no params, stops
the current view and starts a demonstration worker that slews the mount between random positions
([demonstration worker](#additional-demonstration-rules)).
536 if a view plan runs; 212, 207 otherwise. Success means the worker started. READ.

R22. [`stop_demonstrate`](../../docs/control/methods/stop_demonstrate.md) stops and joins the
worker and always replies success. It can block with no timeout. READ.

R23. [`Demonstrate`](../../docs/control/events/Demonstrate.md) is a function-state event (`idle`,
`working`, `complete`, `fail`, `cancel`) with no established extra members. When
`stop_demonstrate` stops a running demonstration the device sends a final `Demonstrate` with
`state:"cancel"`, which can arrive before the `stop_demonstrate` reply; a demonstration that ends
by itself ends with `complete` or `fail`. READ.

R24. [`play_sound`](../../docs/control/methods/play_sound.md) plays a numbered sound in the
current language, replacing any sound already playing. The number is the optional integer
member `num`; a missing, non-integer or non-object value plays sound 1, and no range is checked.
255 if the sound file does not exist.
The reply means submitted. READ.

### Additional demonstration rules

Basis: static analysis of firmware 9.31 (64-bit build; 32-bit build probable) and app 3.3.2, unless a line says otherwise.


[`start_demonstrate`](../../docs/control/methods/start_demonstrate.md) takes no params. It
returns 536 if a ViewPlan runs. Otherwise it stops the current view and starts the `Demonstrate`
worker. READ. The worker only moves the mount: it repeatedly slews to a random position
(altitude 5–79°, any azimuth) computed from the stored user location, waits up to 120 s for the
goto to finish, and pauses 5 s. It starts or changes no view. It ends with 207 when no location
is stored, and stops the mount and ends with 501 when a goto fails or times out. READ. It
reports through function-family `Demonstrate` events. READ.

[`stop_demonstrate`](../../docs/control/methods/stop_demonstrate.md) always returns 0. It
sets the stop flag, wakes all threads waiting on guider-request replies, and stops the worker
(waiting for it or signalling it, then joining). It can block with no known timeout. READ.
Stopping a running demonstration produces a final `Demonstrate` event with state `cancel` and no
`code`; it can arrive before the `stop_demonstrate` reply. A demonstration that ends by itself
ends with `complete` or `fail`. READ.

## Diagnostic and dangerous methods

R25. [`test_connection`](../../docs/control/methods/test_connection.md) returns the string
`"server connected!"`. The app uses it as a keep-alive. Tier A. READ.

R26. [`test`](../../docs/control/methods/test.md) differs by build: the 64-bit build loads a fixed
image and returns a boolean; the 32-bit build loads a reference file and returns 0. Clients
SHOULD NOT use it. READ (device); normative (client).

R27. [`trigger_test_crash`](../../docs/control/methods/trigger_test_crash.md) makes the control
process raise a segmentation fault. No reply is established; the connection drops and any
running session is interrupted. No guard. READ. On the fault the process logs the signal,
finalises any video recording, writes a crash dump through an external crash reporter, and
terminates with the default action. READ (handler); INFERRED (order). It does not restart itself.
The firmware package's supervisor script, started at boot next to the updater, checks every
2 seconds whether the control process (and the guider) is running and starts it again if not; the
boot unit has no restart policy of its own. A client SHOULD therefore expect the control port to
return within a few seconds. READ (package scripts, 64-bit and 32-bit); INFERRED (timing). Class
Destructive.

R28. [`popen`](../../docs/control/methods/popen.md) runs the caller-supplied `cmd` string on the
device host and returns its standard output as a string. `cmd` may be given as `{cmd}` or
`[cmd]`; an empty string is accepted. There is no timeout, no output cap and
no allow-list; exit status and standard error are not reported. Errors: 105 (no `cmd`), and 1 with
the message `runPopen error` when the runner fails. READ. Class Arbitrary execution.

R29. `popen` gives anyone who can reach the control port the ability to run commands on the
device. A client MUST NOT expose it to untrusted users. A stand-in device SHOULD NOT implement
it. Normative.

### Identity, update markers and diagnostic details

Basis: static analysis of firmware 9.31 (64-bit build; 32-bit build probable) and app 3.3.2, unless a line says otherwise.

[`is_downgraded`](../../docs/control/methods/is_downgraded.md) returns a boolean: true when
the update log shows an update and no acknowledgement marker.
[`clear_downgrade`](../../docs/control/methods/clear_downgrade.md) appends the marker. Neither
compares version numbers. READ.

[`play_sound`](../../docs/control/methods/play_sound.md) takes `{num}` (integer, default 1)
and plays a numbered sound in the device language. 255 when that sound file is missing. READ.

[`get_pcdid`](../../docs/control/methods/get_pcdid.md) (spelled so on the wire) returns
`{pcbid}`, a board identifier 0, 1 or 2 from an ADC reading. On command failure the reply has
neither `result` nor `error`. READ.

These diagnostic and factory methods are not used by the app in normal operation. READ
(bounded search), except `factory_test_control`, which the app's factory screen uses. READ.
A client MUST NOT send `popen` in normal operation; a stand-in device SHOULD reject it.
A client MUST NOT send `trigger_test_crash` or send `factory_test_control` outside factory use.

## Open questions

- Issuer and format of the legacy activation pair, and the input to the Plus-form digest.
  unresolved.

## Appendix: Validating on a live device (non-normative)

- Only the Safe class is suitable for routine testing.
- Read the `Version` greeting on connect and compare with `keys:["device"]`.
- Do not send Destructive or Arbitrary execution methods to a device in use.
