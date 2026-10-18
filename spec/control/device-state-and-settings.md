# Device state and settings

This chapter covers the configuration and status layer of the control service: the device
snapshot (`get_device_state`), the settings object (`get_setting`, `set_setting`), application
state polling, and the `Setting`, `Client`, `AppStateChange`, `Initialise` and `Alert` events. It
sits on top of the JSON-RPC envelope and event framing ([session-handshake.md](session-handshake.md),
[events-overview.md](events-overview.md)). Topic chapters that share these structures are
[network.md](network.md), [time-and-location.md](time-and-location.md),
[power-and-storage.md](power-and-storage.md) and [maintenance.md](maintenance.md).

App names for settings in this chapter: “Guest Mode” (`guest_mode`), “Device Lock” (`connect_lock`
and its password), “Interface mode” with “Ethernet” or “Transfer” (`typec_mode`), “Seestar Alpaca”
(`alpaca_enable`; only the switch is specified, not the Alpaca protocol), “Telephoto Live HDR”
(`hdr`) and “Expert mode” (`expert_mode`). “Wide-angle center calibration” sets `wide_cross_offset`
(INFERRED). Names are the English strings of iOS app 3.4.0; links are READ (app call sites) unless
marked.

## Conventions

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119 and RFC 8174. They bind
clients. Sentences that say what "the device" does are descriptions.

Every claim carries a label (see `CONVENTIONS.md`): **READ** (seen in firmware 9.31 by static
analysis), **OBSERVED** (seen on a device; no session is known to match 9.31 exactly),
**INFERRED** (a consequence or interpretation), **unresolved** (not established). READ claims
are for the 64-bit imager build unless stated; the 32-bit build is "probable" unless stated.

Basis for this chapter: static analysis of firmware 9.31 and app 3.3.2, plus firmware 9.75 (app 3.4.0) where a statement is tagged so; untagged statements are firmware 9.31.

Common envelope rules used below (READ): a success reply carries `result` and `code:0`; an error
reply carries a top-level `error` string and a nonzero `code` and no `result`. The socket layer
may add `jsonrpc` and `Timestamp`. Event `Timestamp` is a monotonic-clock string with nine
fractional digits, not wall-clock time (INFERRED from the clock source).

## Overview

The device keeps three separate settings stores. READ.

| Store | Getter | Setter | Purpose |
|---|---|---|---|
| Device settings | [`get_setting`](../../docs/control/methods/get_setting.md) | [`set_setting`](../../docs/control/methods/set_setting.md) | Typed, validated device options. Changes produce `Setting` events. |
| App settings | [`get_app_setting`](../../docs/control/methods/get_app_setting.md) | [`set_app_setting`](../../docs/control/methods/set_app_setting.md) | Free-form key/value store kept on the device for the app. |
| Test settings | [`get_test_setting`](../../docs/control/methods/get_test_setting.md) | [`set_test_setting`](../../docs/control/methods/set_test_setting.md) | Engineering flags. |

Read-only views over many subsystems are [`get_device_state`](../../docs/control/methods/get_device_state.md)
(hardware and configuration snapshot) and the application-state pollers
[`get_app_state`](../../docs/control/methods/get_app_state.md),
[`iscope_get_app_state`](../../docs/control/methods/iscope_get_app_state.md) and
[`get_view_state`](../../docs/control/methods/get_view_state.md). READ.

A client that wants a coherent picture SHOULD fetch `get_device_state` once after connecting,
then apply `Setting`, [`PiStatus`](../../docs/control/events/PiStatus.md), `Client` and other deltas to its copy. INFERRED (events are
deltas; see [Device settings](#device-settings) and [Guest mode, Client and Alert events](#guest-mode-client-and-alert-events)).

## Device snapshot: get_device_state

R1. `params.keys` is an optional array of section names. Only string elements are kept;
other elements are skipped. If the kept list is empty, every section is returned: this covers
missing or non-object `params`, missing or non-array `keys`, `[]`, and arrays with no strings,
so `{"keys":[null]}` and `{"keys":42}` select everything. None of these forms is rejected.
Matching is exact and case-sensitive. Unknown names select nothing; `keys:[""]` and
`keys:["second_camera"]` therefore yield `result:{}`. READ.

R2. The section names, in emission order, are: `device`, `setting`, `location_lon_lat`,
`camera`, `focuser`, `ap`, `station`, `storage`, `balance_sensor`, `compass_sensor`, `mount`,
`pi_status`, `client`. READ. The order is fixed in code and does not follow the order of
`keys`. It is the same in the 64-bit and 32-bit builds. READ. Members inside `device` differ: the
32-bit build lacks `can_roi_scale`, `firmware_platform` and `can_adjust_brightness`. READ. Clients
SHOULD still look sections up by name.

R2a. Telling the builds apart. Only the 64-bit build emits `device.firmware_platform`, and it
always emits the literal 1. READ. A client can therefore treat a `get_device_state` reply that
includes `firmware_platform` as coming from the 64-bit imager, and one without it, at firmware
9.31, as coming from the 32-bit imager. INFERRED. OBSERVED 2026-10-16 (S50 Pro, firmware 9.31):
the device reported `firmware_platform` 1 and an `ios_ver` string naming the RV1126B platform,
which matches the 64-bit build's SDK build tag
([cloud-auth.md: Bundled firmware version comparison](../auth/cloud-auth.md#bundled-firmware-version-comparison)).
OBSERVED 2026-10-16, on the same device after a firmware update from the iOS app:
`firmware_ver_string` "9.75", `firmware_ver_int` 2975, `firmware_platform` 1, and `ios_ver`
unchanged. `ios_ver` therefore does not track the firmware version. INFERRED. Firmware 9.75 was later
statically analysed; statements tagged 9.75 below are READ from that analysis and untagged READ
statements are against 9.31. OBSERVED
2026-10-16 on 9.75: replies to `get_device_state` (`client`, `camera`, `second_camera`),
`list_plan`, `get_view_plan_stack_result` and `pi_get_time` had the same member names and types
as on 9.31, and reply correlation by `id` was unchanged.

R3. There is no error envelope for a failing section. A section whose query fails is omitted.
Clients MUST treat every section as optional. READ.

| Section | Contents (summary) | Specified in |
|---|---|---|
| `device` | product identity, firmware version (integer and string), verification flag, OS version, model flags and capability booleans | [maintenance.md: Firmware version and identity](maintenance.md#firmware-version-and-identity) |
| `setting` | same serializer as `get_setting` ([Device settings](#device-settings)) | this chapter |
| `location_lon_lat` | `[lon, lat]`, present only when valid | [time-and-location.md](time-and-location.md) |
| `camera` | `chip_size`, `pixel_size_um`, `focal_len`, `fnumber`, `debayer_pattern` (colour only), `hpc_num`, `gain`; present only if the camera info query succeeds | catalog schema |
| `focuser` | `state` (`close`, `idle`, `moving`); `max_step` and `step` only when the focuser is open | catalog schema |
| `ap`, `station` | access-point and Wi-Fi client state | [network.md](network.md) |
| `storage` | Type-C flag, connected storages, volumes, current storage | [power-and-storage.md](power-and-storage.md) |
| `pi_status` | full power and thermal snapshot | [power-and-storage.md](power-and-storage.md) |
| `balance_sensor`, `compass_sensor` | embedded `code` (0 valid) and `data`; `data` is present even when `code` marks it invalid | catalog schema |
| `mount` | `move_type`, `close`, `tracking`, `equ_mode` | mount chapters |
| `client` | guest-mode client list, present only in guest mode | [Guest mode, Client and Alert events](#guest-mode-client-and-alert-events) |

R4. The `ap` section returns the access-point password in clear. Clients MUST NOT log or display
it without user intent. READ (device behaviour); the client obligation is normative.

R4a. Firmware 9.75 (64-bit build): the `ap` section's `passwd` is no longer plaintext when the
connection has a crypto session. It is encoded as an `enc1:` string
([secure communication](secure-communication.md#encrypted-wi-fi-strings)); the result stays
flat, with no `wifi` object (the word is only a cipher context). The encoding applies when the
`ap` section is selected. A connection without a session gets the `ap` section without `passwd`,
and that is not an error; only a real encoding failure returns an error reply (571 to 573).
Firmware 9.31 returns the password in clear as stated above. READ.

R5. `mount.close` is true when the reported altitude is at or below -85 degrees. READ.

R6. The full call can open and close the focuser to read it, so it is not observation-safe
(tier C); the reported focuser state is the state during the query. Effects differ by section
(READ, 64-bit build): `client` alone is a pure getter; `camera` and `location_lon_lat` refresh
shared caches (software metadata, no hardware motion); `device` runs shell and identity
queries; `setting` has all `get_setting` effects; `ap` refreshes the shared access-point
cache; `focuser` opens and closes hardware. `station` runs a shell query of the Wi-Fi station
state and `storage` reads the cached storage state and file-system usage; neither changes state.
`mount` sends three read-only queries to the mount controller, each with its own 10 s wait, so
this section can delay the reply by up to about 30 s when the mount does not answer. No section
moves hardware except the focuser open and close. A client that needs an observation-safe call MUST send a nonempty `keys` list of
string names, because a malformed selector selects every section (R1). READ (device);
normative (client).

On 2026-10-12, `keys:["client"]` over the tunnel path returned code 0 with an empty `result`
object (no connection list, no `is_master`). OBSERVED. This matches R1 and the guest-mode-only
`client` section (INFERRED); clients MUST NOT rely on this section to list connections.
On 2026-10-15, keyed `get_device_state` replies on four tunnel sockets (45 replies) again
carried no `client` member. OBSERVED.

R7. In the main-imager process the `camera` section may add a `second_camera` object holding
the peer process's camera state, fetched with a 10000 ms wait; `second_camera` is not a key of
its own. The `focuser` section may likewise add `second_focuser` on models with a wide-camera
focuser. A failed peer query omits only these objects. Clients MUST tolerate their absence.
READ.

The app requests narrowed sets such as `["ap"]`, `["storage"]`, `["device"]`,
`["client","camera","second_camera"]`. READ.

## Device settings

### Reading: get_setting

R8. `get_setting` returns the full settings object. There is no error
branch; sub-queries that fail omit their members. READ. A stored value starting with the byte
`{` (0x7b) is JSON, not an error code; no 123 error exists: the byte is the opening brace of a JSON document, and `get_setting` has no demonstrated error reply at all. READ (firmware 9.75).

R8a. Firmware 9.75: `get_setting` reads one optional parameter, `include_sensitive` (boolean or
integer, default true). When it is false the `password` member is left out. A non-bool value
type is treated as the default. The flag is passed on to the second-camera process, so
`second_camera` follows it. READ. A client that does not need the password SHOULD send
`include_sensitive:false`. Normative (client).

R8b. Firmware 9.75 (64-bit build) adds these members to the full object. READ for names, types
and conditions; the meanings are INFERRED from the names except where other chapters define them.
"Main process" means the process that is not the second-camera process; "W" means the reply is for
the wide camera.

| Member | Type | Condition |
|---|---|---|
| `annotation` | object of four booleans: `stargazing_deepsky`, `stargazing_supernovae`, `milkyway_lines`, `milkyway_background` | main process; full path |
| `sky_replay` | boolean, always false | main process; full path (see R8c) |
| `can_encrypt` | boolean, constant true | main process; full path |
| `comet_max_frame_num` | integer, constant 200 | main process; full path; output only; the batch comet frame limit, see [stacking.md R20c](stacking.md#batch-stack) |
| `enable_dark_library` | boolean | main process; full path |
| `motion_monitor` | object: `mode` (`auto_track`, `auto_capture` or `unknown`), `return_to_origin` (boolean), `sensitivity` (`low`, `middle`, `high` or `unknown`), `waiting_time` (integer, seconds), `duration_min` (integer, minutes, -1 unlimited); all five always present | either process; 64-bit build only |
| `preview.raw_bin2` | boolean | whenever `preview` is emitted, either process; after `image_transfer_mode` |
| `exp_ms.more_exposure` | boolean | full path; between `stack_l` and `continuous`; not wide-camera gated on output (the setter is tele-camera only, R16a) |
| `stack.startrails_duration_min`, `stack.startrail_mode` | integers; minutes (-1 or 0 no limit) and mode 0 to 2 | full path; W only; meanings in [stacking.md R8b to R8f](stacking.md#sky-replay-and-star-trail-decay-firmware-975) |

The names `milkyway_background`, `milkyway_lines`, `more_exposure`, `raw_bin2`,
`stargazing_deepsky`, `stargazing_supernovae`, `startrail_mode` and `startrails_duration_min` are
nested as shown, rather than top-level members. `expert_mode` is still emitted by `get_setting` in
firmware 9.75 (boolean, full path only) although `set_setting` no longer accepts it (R16a).
`can_encrypt` is effectively read only (`set_setting` accepts only `true`, as a no-op, R16a); that
it relates to the secure-communication switch ([secure-communication.md](secure-communication.md))
is INFERRED. The 32-bit build has no motion monitor; the other additions were not compared member by
member on the 32-bit build, which has the `sky_replay` getter and setter unchanged. The `Setting`
event serializer uses the same getter, with an exact-key filter.

R8c. Firmware 9.75: `sky_replay` is force-disabled. `get_setting` reports `sky_replay` false
whatever was stored, and reading it clears the persisted flag and ends any replay session. READ
(also in the 32-bit build, whose getter and setter pair is identical). See
[function-states.md: Sky replay](function-states.md#sky-replay).

R9. The full object can contain duplicate member names, notably `beep_volume`,
`ae_bri_percent` and `effect_offset_deg`. Clients MUST tolerate duplicate keys and MUST NOT rely
on which duplicate a JSON parser keeps. READ.

R10. `rtsp_roi_index` can be set but is not emitted by the full getter. READ.

R11. In the main-imager process the reply can include `second_camera` with the peer's settings
(10000 ms wait). READ.

Selected members and their meaning are listed on the card. Members that matter for other
chapters: `temp_unit` (`C`/`F`), `lang`, `beep_volume`, `auto_power_off`, `guest_mode`,
`usb_en_eth`, `typec_mode` (`file`/`net`), `wifi_country`, `ap_changed`, `remote_joined`,
`password`, `connect_lock`, `alpaca_enable`, `dark_mode`, `light_brightness`. READ.

R12. `password` is returned without redaction, also on firmware 9.75: it is not `enc1:` encoded
(only the Wi-Fi key fields are), and it is present unless `include_sensitive` is false (R8a).
Clients MUST treat it as a secret. READ (device); normative (client).

### Writing: set_setting

R13. `params` MUST be an object; anything else gives 107. `{}` succeeds and changes nothing.
READ.

R14. Members are applied in document order. The first failing member stops processing. Members
applied before it stay applied; there is no rollback. Clients that need atomicity SHOULD send
one member per request. READ (device); normative advice INFERRED.

R15. An unknown key gives 109. In guest mode a non-master client may set only `master_cli`,
`cli_name`, `cli_uuid`, `support_socks5` and `socks5`. READ.

R16. Success normally returns integer `0`. Two members return an object instead:
`manual_exp:true` returns `{isp_exp_ms, isp_gain}`, and a mosaic change that is calculated returns
`{estimated_hours}`. Both return early: later members in the same request are not processed.
Clients MUST accept either an integer or an object. READ.

Validation of selected members (READ; "B" means boolean or integer, nonzero is true):

| Key | Accepted | Failure |
|---|---|---|
| `temp_unit` | `"C"` or `"F"` | other string 102; other type 109 |
| `beep_volume` | `close`, `backyard`, `field`; other strings map to the default | none |
| `lang` | `zh`, `en`, `fr`, `ja`, `ko` (case-insensitive) | unknown 210; non-string 109 |
| `ae_bri_percent` | number 0..100 | out of range 204; non-number 102 |
| `light_brightness` | integer 0, 50 or 100 only | other integer 207; wrong type 104 |
| `rtsp_roi_index` | integer 0, 1, 2 (1x, 2x, 4x) | other integer 204; wrong type 104 |
| `rtsp_roi_scale` | number 1..4, continuous | out of range 204; wrong type 108 |
| `stack_dither.pix` | integer 0..200; wrong type ignored | out of range 204 |
| `stack_dither.interval` | integer 1..100; wrong type ignored | out of range 204 |
| `typec_mode` | `file` or `net`; runs the network script | other string 102; non-string 105; script reports error 207 |
| `auto_power_off` | B; persisted. Enables shutdown after 15 minutes of inactivity: no exposure, no client connection, no access-point station, and no running stack, stream or plan. READ | wrong type ignored without error. READ |
| `guest_mode` | B; persisted. Enabling makes the requester the master; disabling is allowed only for the master and closes the other connections. READ | wrong type 106; setting the current value again fails with a nonspecific (stale) error code. READ |
| `usb_en_eth` | B; persisted. Turns Ethernet-over-USB-C on or off; when on, USB-C storage is detached, and when off the device rescans for it. READ | wrong type 106; an unchanged value is accepted silently. READ |
| `dark_mode` | B; persisted. Switches the battery and power LEDs to their dark style. READ; the visual effect is INFERRED | wrong type 106; an unchanged value is accepted silently. READ |
| `password` | string, no length or character check; stored persistently | 105 |
| `connect_lock` | B; stored persistently | 106 |
| `alpaca_enable` | B; the control thread waits up to 30000 ms | 106; 210 in the secondary process |
| `ap_changed` | B; NFC models only | 106; 210 without NFC |

R16a. Firmware 9.75 (64-bit build) key rules. READ unless marked.

- `expert_mode` is no longer in the key table, so `set_setting` gives 109 for it, although
  `get_setting` still emits it. Firmware 9.31 accepted it.
- `annotation` MUST be an object (107). Its members `stargazing_deepsky`, `stargazing_supernovae`,
  `milkyway_lines` and `milkyway_background` are each boolean or integer (106 otherwise); an unknown
  or null member name gives 109; a persistence failure returns the thread's error code. A change
  adds `annotation` to the `Setting` event in the main process.
- `sky_replay` is boolean or integer (106 otherwise) and its value is ignored (R8c). A `Setting`
  event is raised only if the stored flag was true.
- `annotation` or `sky_replay` sent in the same request as `wide_cam` gives 102.
- `preview.raw_bin2` is boolean or integer (106 otherwise). Writing the stored value is a no-op;
  otherwise it is saved and a persistence failure returns the thread's error code. In the same
  `preview` branch `rtsp_quality` and `image_transfer_mode` are strings (105 otherwise), an
  `image_transfer_mode` value above 1 gives 102, and changing `rtsp_quality` while a video recording
  runs gives 524.
- `comet_max_frame_num` is not settable (output only): sending it gives 109.
- Members are applied in document order; an unknown key reaches the guest-settings fallback and
  gives 109 unless it is one of the guest keys (R15).
- `can_encrypt` is parsed as boolean or integer (106 otherwise). `true` is accepted as a no-op
  (nothing stored, no event); `false` gives 210, matching the constant-true getter. READ.
- `enable_dark_library` is parsed as boolean or integer; a wrong type is silently ignored and the
  call succeeds. Otherwise the stack setting flag is stored and applied; the result of applying is
  ignored. There is no wide-camera gate and no running-stack check. READ.
- `exp_ms.more_exposure` is boolean or integer (106 otherwise), tele camera only (210 on the wide
  camera; the getter is not gated), and is applied to the stack setting. There is no running-stack
  check for it alone. Its siblings: `exp_ms.stack_l` (integer, 259 while stacking) and
  `exp_ms.stack_l_auto` (boolean, wide camera only else 210, 259 while stacking). READ.
- `stack.startrail_mode` and `stack.startrails_duration_min` are decoded in [stacking.md R8b and
  R8d](stacking.md#sky-replay-and-star-trail-decay-firmware-975): integers (104 otherwise), wide
  camera only (210); mode above 2 gives 209; the duration gives 259 while a stack runs and has no
  range check. READ.
- `motion_monitor` (firmware 9.75, 64-bit, either process) must be an object (107). Members are
  optional and unknown members are ignored. `mode` is a string, `auto_track` (0) or `auto_capture`
  (1), else 105 for a wrong type or 209 for another string; `sensitivity` is a string whose id above
  2 gives 209; `return_to_origin` is boolean (106); `waiting_time` and `duration_min` are integers
  (104). `waiting_time` is read only when `return_to_origin` is true after the update (otherwise
  ignored even if mistyped). The final check gives 209 for: mode or sensitivity out of range, a
  sensitivity whose stored threshold does not match its table value, a negative `waiting_time`, or
  `duration_min` that is neither -1 nor 1 to 35791394 (the duration branch giving 209 is INFERRED).
  If nothing changed the call succeeds without applying or emitting. If something changed and the
  motion-monitor function is running, the reply is 524; otherwise the configuration is applied and
  `motion_monitor` is added to the changed keys of the `Setting` event. READ, except as marked.
- Unknown members inside the nested `exp_ms` and `stack` objects are ignored (members are looked up
  by name); inside `annotation` they give 109. Unknown members inside `preview` are ignored. Firmware 9.31 on the 64-bit build looks up `rtsp_quality` and `image_transfer_mode`; firmware 9.75 on that build also looks up `raw_bin2`. The 32-bit build looks up only `image_transfer_mode` in firmware 9.31, and `image_transfer_mode` plus `raw_bin2` in firmware 9.75. A name not looked up by that build is ignored even when its value has another type. Recognized members retain their validation and busy checks. READ (firmware 9.31 and 9.75, both builds).
- Of the `set_setting` keys, the 32-bit build was not traced; the `include_sensitive` string exists
  in both builds, so the parameter is probably present in both (INFERRED).

R17. `guest_mode:false` closes all non-master connections. A client that sends it MUST expect
other clients to be disconnected. READ.

R17a. Of `auto_power_off`, `guest_mode`, `usb_en_eth` and `dark_mode`, all reject a wrong type
with 106 except `auto_power_off`, which skips it silently. READ. Enabling `guest_mode` needs the
requester's connection UUID, and disabling it needs the requester to be master; when a secondary
process exists the change is relayed to it, and a relay failure is an error. READ. A client
SHOULD read `guest_mode` first and send it only when the value changes, because resending the
current value fails. INFERRED.

R18. A request that changes at least one key and succeeds causes a `Setting` event. A request
that fails sends no `Setting` event, even if earlier members were applied. Clients that receive
an error from `set_setting` SHOULD re-read `get_setting`. READ (device); advice INFERRED.

## The Setting event

[`Setting`](../../docs/control/events/Setting.md) is a delta of the settings object. READ.

R19. Payload: `Event:"Setting"`, `Timestamp`, usually `wide_cam` (boolean, origin camera), plus
the changed members in the same shapes as `get_setting`. There is no list of changed keys on
the wire. READ.

R20. Producers: `set_setting`, internal setting changes (stacking options, image adjustment,
stack-time checks), and remote-access join or disjoin (`remote_joined`). Direct producers build
sparse objects, so a `Setting` event can carry members that the filtered getter path never
emits. READ.

R21. The filtered serializer always adds the stack companions `light_duration_min`,
`brightness`, `contrast`, `saturation` and `dbe_enable` under `stack`. Clients MUST merge
members into their copy rather than replace it. READ (companions); normative (merge).

R22. There is no debounce timer. Direct setters may suppress an event when the value did not
change. Clients MUST NOT treat a missing event as proof that a value is unchanged. READ /
INFERRED. On a live device, five `set_setting` calls that wrote a cosmetic key back with its
current value each returned code 0, and no `Setting` event arrived within 5 s of any reply
(2026-10-16). OBSERVED.

Flow for a successful change:

```
client                                 device
  | {id:7,method:"set_setting",          |
  |  params:{"dark_mode":true}}          |
  |------------------------------------->|  apply members in order
  |  {Event:"Setting",dark_mode:true,..} |
  |<-------------------------------------|  (order vs reply: see below)
  |  {id:7,result:0,code:0}              |
  |<-------------------------------------|
```

The relative order of the reply and the event is unresolved; it was not observed, because
unchanged-value writes produced no event (R22).

## Guest mode, Client and Alert events

R23. In guest mode the device tracks connected clients and one master. Changes in membership,
master or names send [`Client`](../../docs/control/events/Client.md) to eligible clients:
`connected` (array of client names), `master_index` (index into `connected`, negative when no
match) and `is_master` (true only in the copy sent to the master). READ.

R24. In guest mode, `get_device_state` with `keys:["client"]` returns the same information on
demand; with guest mode off the section is absent (see R6). READ.

R25. The device limits distinct external source addresses: 2 with guest mode off, 8 with it on.
A connection beyond the limit receives one [`Alert`](../../docs/control/events/Alert.md) with
`code:429`, `Type:"error"` and `Msg:"Exceed the maximum number of connections"`, and is then
closed. This is an event followed by EOF, not an RPC error. Delivery is attempted, not
guaranteed. READ.

R26. Other `Alert` producers send `code` and `error` (from the RPC error-string table),
optionally `wide_cam` and `required_storage_mb`. Clients MUST accept both the `code`/`error`
form and the `Msg`/`Type` form. READ.

## Application state

R27. [`get_app_state`](../../docs/control/methods/get_app_state.md) with the scalar string
params `"is_autosave_running"` returns a boolean. Any other params return the full state: a
`page` member plus objects for annotate, solve, capture, pa, pa_3p, auto_goto, stack,
export_image, merid_flip, auto_focus, find_star, avi_record, rtmp, auto_exp and restart_guide,
each with `is_working`. READ.

R28. On page 6 in autosave mode the full form runs plan auto-selection and can change the
current target and sequence. Clients that only need the autosave flag SHOULD use the scalar
form. READ (device); advice INFERRED.

R29. [`iscope_get_app_state`](../../docs/control/methods/iscope_get_app_state.md) returns the
function tree keyed by function name, each node with a `state` from `idle`, `working`,
`complete`, `fail`, `cancel`. A failed function is a node inside a successful reply. Printing
can save a completed plan or close a cached stack file, so the method is tier C. READ.

R30. [`clear_app_state`](../../docs/control/methods/clear_app_state.md) takes a function name
(string, `[string]` or `{name}`), marks it ignored and replies 0. An unknown name is not an
error. READ.

R31. [`AppStateChange`](../../docs/control/events/AppStateChange.md) carries `page` (string)
when the imager restores a page or resumes exposure after a reconnect. A guider producer may
send the envelope only. READ.

R32. [`Initialise`](../../docs/control/events/Initialise.md) is a function-state event from view
set-up, with the common `state` member. It is not a full tree snapshot. READ.

## App and test settings

R33. `set_app_setting` takes an object (or a one-element array holding it) of arbitrary keys
and stores integer, string, boolean and number values by their JSON type; arrays, objects and
null are ignored. Anything else gives 107; `{}` succeeds without writes. Keys are placed in a
255-byte configuration path, so very long keys are truncated. Write failures are ignored, so a
success reply does not prove persistence. READ.

R34. `get_app_setting` takes an array of key names (INFERRED intended form; only string
elements are read), or nothing, `[]` or `{}` for all keys. There are no defaults: a read failure
for a selected key aborts the whole reply with the configuration layer's error code. A selected
key stored under another type returns the literal string `"unknow type"`; enumeration skips such
keys. Zero enumerated items gives 236. READ.

R35. `set_test_setting` requires an object. It assigns `auto_open_heater`, `auto_open_cooler`,
`station_5g`, `goto_simulate`, `new_solve_exec` and `autogoto_threshold`. `autogoto_threshold`
is persisted when it differs from the stored value. READ. Wrong member types are ignored
silently. READ.

R36. `get_test_setting` returns `autogoto_threshold`, `auto_open_heater`, `auto_open_cooler`,
`station_5g`, `plan_simulate`, `goto_simulate`, and `new_solve_exec` only when the solver
executables are present. READ.

R36a. `autogoto_threshold` is a unitless fraction of the smaller field-of-view dimension.
Auto-goto treats the target as centred when the solved offset divided by that dimension is at
most the threshold, and the threshold is scaled for the wide camera. READ; the FOV divisor is
INFERRED.

R36b. `plan_simulate` is a test-only auto-goto simulation level: 0 normal; any positive value
skips the initial angle step; 1 ends after the goto and 2 after the first solve, both reporting
success without real centring. READ. Clients MUST NOT set nonzero values in normal use.

## Automatic device reopen

R37. [`AutoOpenDevice`](../../docs/control/events/AutoOpenDevice.md) is broadcast on TCP 4700
to every retained connection after the imager's automatic-reconnect logic has successfully
reopened a device. It carries `device` (string, the reopened device) and `type` (string; the
vocabulary is not established) besides `Event` and `Timestamp`, and has no `state`, `error` or
`code`. READ. No app consumer was found (READ, app 3.3.2). A client that caches device state
SHOULD re-read the affected device after this event, for example with
[`get_connected_cameras`](../../docs/control/methods/get_connected_cameras.md),
[`get_connected_focuser`](../../docs/control/methods/get_connected_focuser.md) or
[`get_connected_wheels`](../../docs/control/methods/get_connected_wheels.md) (INFERRED; check
each card's side-effect tier first). Hot-plug arrival and removal are reported separately by
[`DeviceChange`](../../docs/control/events/DeviceChange.md) ([power-and-storage.md R34](power-and-storage.md#storage-events)).

## Open questions

- Ordering of the `set_setting` reply and its `Setting` event for a changed value: see
  [The Setting event](#the-setting-event).
- How `calib_location` is changed: it is a persisted test setting (config key
  `setting2/imager/test/calibrate_location`) that the location-offset routines read only as a mode
  gate; neither `set_setting` nor `set_test_setting` assigns it and no runtime routine that sets the
  in-memory field to 1 or 2 was located by static reading, so how it comes to be set remains
  unresolved. See
  [events/nested-schemas.md: Full output, main process only](events/nested-schemas.md#full-output-main-process-only).
  Whether values other than 1 and 2 occur is unresolved.
- Members added by each direct `Setting` producer on the 32-bit build: settled for a bounded
  comparison. The producer set is the same as on the 64-bit build. The image-adjustment,
  stack-time and remote-access producers name the same members. The stack-settings producer on
  the 32-bit build lacks `exp_auto`, `save_meteor_frame`, `save_video`, `scene_separate`,
  `scene_shooting_duration_min`, `stack_l_auto` and `wide_size_index`; the 32-bit build has no
  such setting names at all except `scene_separate`. READ (member names; nesting not compared).
- Firmware 9.75 `get_setting`/`set_setting` on the 32-bit build: the `sky_replay` getter and setter are traced and match the 64-bit build (force-disabled; READ). The other new keys were checked by name and partly by logic (see the [32-bit parity matrix](secure-communication.md#firmware-975-parity-matrix-32-bit-imager-and-guider)); complete parity is not established. The public `get_setting` requests the full serializer; its internal event filter matches stack-option leaf names and also retains stack duration and image-adjustment members. Full `exp_ms` contains integer `stack_l` and `continuous`; their setter ignores unknown nested names and noninteger values. An integer `stack_l` encounters error 259 while Stack is running; otherwise its caller requests the assignment with notification enabled but does not propagate the underlying setter's false return. The 64-bit exposure caller checks that return and propagates the stored error. An otherwise unhandled `annotation` key reaches error 109 on the 32-bit build; the 64-bit build implements annotation parsing. The 32-bit stack parser uses fixed recognized-member lookups and ignores unknown nested names. Its boolean conversions for `save_discrete_frame`, `save_discrete_ok_frame` and `goto` fail with 104; the reviewed DBE, correction, drizzle, wide-denoise, enhancement and airplane-removal conversions fail with 106. Capture count, movement sleep and light duration require integers (104); capture type requires a string (105) and retains camera and Stack/ViewPlan checks. When `capt_type` is absent, legacy `cont_capt` supplies a boolean/integer alternative, with conversion failure 106. Earlier assignments remain after a later error, which may bypass the queued event tail. READ. Complete parity for other legacy backends, direct-event nesting, exception/thread suppression and reply/event wire order remains unresolved. `reset_setting` is traced (10 keys); see [function-states.md R4](function-states.md#settings-reset) for its busy checks.
- Firmware 9.75 `reset_setting`: exception-path restoration of the thread-local `Setting` notification suppression, and notification behavior on other threads. unresolved. The normal-path lifetime and the descriptor defaults are READ ([function-states.md R2 and R4](function-states.md#settings-reset)).
- Firmware 9.75, both imager builds: the module-manifest schema predicate requires an integer-tagged value whose stored 32-bit word equals 1. The parser accumulates integer digits and applies the sign with 32-bit arithmetic without checking overflow. Decimal-point and exponent forms have a different numeric tag and fail this predicate even when mathematically equal to 1. READ. Consequently, successfully parsed integer tokens congruent to 1 modulo 2^32 pass this predicate when the remaining manifest checks succeed. INFERRED. The required-field, invalid-module-entry, empty-array and missing-manifest behavior remains as described in [maintenance.md R5b](maintenance.md); malformed-document acceptance and server validation are not established by this predicate.
- Unit of the timelapse `src_dura_min` is minutes: the saved integer is used unscaled (no
  multiply or divide) at the one internal debug-log site that names it, which labels the same
  raw value "minutes". READ. How a worker turns the minute count into a stop condition is a
  separate, untraced mechanism.

## Appendix: Validating on a live device (non-normative)

- Send `get_device_state` with `keys:["client"]` first; it is the lowest-impact form.
- Change one harmless key (`dark_mode`) and watch for a `Setting` event with that member.
- Send `set_setting` with an unknown key and confirm code 109 and no `Setting` event.
