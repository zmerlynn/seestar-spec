# Power and storage

This chapter covers the device's power, thermal and storage layer as seen through the control
service: battery and temperature status (`PiStatus`), the power LED and auxiliary outputs,
shutdown, reboot and sleep, and image storage (volumes, mass storage, eject, format, save path).
It sits on the JSON-RPC envelope and event framing ([session-handshake.md](session-handshake.md),
[events-overview.md](events-overview.md)). The settings that influence power and storage are in
[device-state-and-settings.md](device-state-and-settings.md); firmware-level maintenance is in
[maintenance.md](maintenance.md).

## Conventions

RFC 2119 / RFC 8174 key words bind clients. Labels **READ**, **OBSERVED**, **INFERRED** and
**unresolved** are used as in [plan-scheduling.md: Conventions](plan-scheduling.md#conventions). READ claims are
for the 64-bit imager build of firmware 9.31; the 32-bit build is "probable" unless stated.

Basis: static analysis of firmware 9.31 and app 3.3.2; event shapes also OBSERVED(2026-10-12).

## Power and thermal status

### The status object

The same status object is returned by [`pi_get_info`](../../docs/control/methods/pi_get_info.md)
(merged into its result) and by the `pi_status` section of
[`get_device_state`](../../docs/control/methods/get_device_state.md), and is sent in part by the
[`PiStatus`](../../docs/control/events/PiStatus.md) event. READ.

| Member | Type | Meaning | Label |
|---|---|---|---|
| `is_overtemp` | boolean | SoC temperature over its threshold | READ |
| `temp` | number | SoC temperature, degrees Celsius | READ (event producer); see R3 |
| `charger_status` | string | `Charging`, `Discharging`, `Full`, `Cool`, `Warm`, `Cold`, `Hot` or `Unknown` (R3a) | READ |
| `battery_capacity` | integer | battery charge, percent | INFERRED unit |
| `charge_online` | boolean | external power present | READ |
| `is_typec_connected` | boolean | Type-C data connection present | READ |
| `battery_overtemp` | boolean | battery over temperature | READ |
| `battery_temp` | integer | battery temperature, degrees Celsius, passed through from the charger unscaled | READ (no scaling); INFERRED (unit) |
| `battery_temp_type` | string | `normal`, `high` or `low`; omitted for any other internal state | READ |

R1. Getters always return the full object. A getter does not consume pending event deltas. READ.

R2. `pi_get_info` also returns `is_pi4` and `model` when the model query succeeds, and `guid` (a
hardware identifier) when the serial query succeeds. It has no error branch. Clients MUST treat
`guid` as a device identifier and MUST NOT publish it. READ (device); normative (client).

R3. The event producer reads the SoC thermal sensor in millidegrees and divides by 1000, so
`temp` is in degrees Celsius. One formatter serves `pi_get_info`, `get_device_state` and
`PiStatus`, so the unit is the same everywhere. READ.

R3a. The device derives `charger_status` from the charger's own status, `battery_temp` and
`battery_capacity`. READ (the vendor library part was read from an archived copy that is
byte-identical to the library shipped in the 9.31 64-bit package; the 32-bit package does not
ship this library):

- `Discharging` and `Unknown` pass through.
- `Full` is kept only at 100 % capacity; otherwise it becomes `Charging`.
- Any other status is decided by `battery_temp` T: T <= 0 `Cold`; T <= 10 `Cool`; 45 <= T <= 49
  `Warm`; T > 49 `Hot`; otherwise `Charging` (or `Full` at 100 %).

The charger's "not charging" status is therefore never reported. READ. Clients SHOULD compare
the values case-insensitively.

R3b. Firmware 9.75: the status is derived inside the vendor SDK library, which reports an enum:
0 Unknown, 1 Charging, 2 Discharging, 3 Not Charging, 4 Full, 5 Warm, 6 Cool, 7 Cold, 8 Hot. The
strings sent on the wire and the thresholds of R3a are unchanged. The battery temperature has a
1 s cache and a filter (INFERRED). READ for the enum and strings.

R4. The app models `is_undervolt` and `is_over_current`, but no firmware build serializes them.
Clients MUST NOT expect them. READ.

### PiStatus event

R5. `PiStatus` is a delta. It carries `Event`, `Timestamp` and only the members that changed
since the last event, each at most once. There is no `state`, `code` or changed-key list. READ.
OBSERVED(2026-10-12): events with a single member (`temp` alone, `battery_temp` alone).

R6. Clients MUST merge `PiStatus` members into retained state and MUST NOT treat a missing
member as false or zero. READ (delta rule); normative (client).

R7. Temperature is polled about once a second. `temp` is reported only when it differs from the
last reported value by more than 1.0 degree, or when `is_overtemp` changes. Type-C changes are
sent at once. There is no rate limit and no fixed period. READ.

### High-temperature shutdown

R8. When the battery high-temperature branch fires, the device sends
[`BattHiTempShutdown`](../../docs/control/events/BattHiTempShutdown.md) (envelope only, no extra
members), stops its event server and shuts down. Clients SHOULD present this to the user and
expect the connection to close. READ (device); normative (client).

### Power supply query

R9. [`get_power_supply`](../../docs/control/methods/get_power_supply.md) always fails with 210
`not supported`. READ. OBSERVED(2026-10-12): a device returned code 210 with an error string and no
result for a bare request.

## Power LED and auxiliary outputs

R10. [`set_power_led_mode`](../../docs/control/methods/set_power_led_mode.md) takes a bare JSON
integer as `params`. Any other form gives 107, whose message reads "expected object param"
although an integer is required. The method checks no range: the mode is passed to the LED
driver, which on devices with the ring-pattern driver accepts 0 to 20 and rejects larger values
and on other drivers writes the value as given. READ. The visual meaning of each mode is
unresolved. A helper failure (including an
uninitialised power-LED handle) gives 207. The
method is registered on the 64-bit build only. READ. On the 32-bit build a request is
treated as an unknown method (INFERRED).

R11. The LED brightness is the `light_brightness` setting (0, 50 or 100) in `set_setting`. READ.

R12. [`pi_output_set`](../../docs/control/methods/pi_output_set.md),
[`pi_output_set2`](../../docs/control/methods/pi_output_set2.md),
[`pi_output_get`](../../docs/control/methods/pi_output_get.md) and
[`pi_output_get2`](../../docs/control/methods/pi_output_get2.md) drive and read GPIO/PWM outputs:
ports, `dslr`, `esp`, `beep`, `gpio<N>`, `heater` and `wide_heater`. Names are matched by
case-sensitive substring. The `gpio<N>` fallback exists only in `pi_output_set`. READ. The
app uses `pi_output_set2` with a `heater` member (state, value, freq) for the dew heater
(INFERRED from the app's data-transfer object). OBSERVED (2026-10-17), firmware 9.75: the
official app sent `pi_output_set2 {"heater":{"state":false,"value":<int>}}` and then, 2.6 s
later, the same with `"state":true`, each with no `freq` member; both got code 0 with an integer
`result` and neither produced any event. Both requests were accepted while a `ViewPlan` was in
its `working` state, so `pi_output_set2` is not gated by an active view plan, at least for this
output.

R13. Output writes are applied in order without rollback. A loop-breaking error can be followed
by an appended success, giving a reply with both `error` and `result` and duplicate `code`.
Clients MUST treat the first `code` as authoritative. READ (anomaly); normative (client).

R14. `beep:false` still drives the beeper output at 100% PWM. READ. Errors include 107, 109,
209, 204, 207, 273 (GPIO failure) and 102; the per-method sets are on the cards. READ.

R15. Clients SHOULD NOT write `gpio<N>` outputs: the raw pin number is passed to the driver
without bounds (a `port<N>` index is bounds-checked and fails with 204). READ (bounds);
normative (client).

## Shutdown, reboot and sleep

R16. [`pi_shutdown`](../../docs/control/methods/pi_shutdown.md) and
[`pi_reboot`](../../docs/control/methods/pi_reboot.md) read no params, start a shutdown worker
and reply `result:0` when the worker is launched. The reply means accepted, not completed. A
second call while the worker runs gives 268; a thread failure gives 212. READ.

R17. After a successful reply the connection will close. Clients MUST NOT send further requests
and SHOULD wait for the device to reappear before reconnecting after `pi_reboot`. INFERRED.

```
client                         device
  | pi_reboot                    |
  |----------------------------->| start shutdown worker
  | {result:0,code:0}            |
  |<-----------------------------|
  |        connection closes     |  host restarts
```

R18. The `auto_power_off` setting (boolean) enables automatic power-off. When it is true the
device shuts itself down after 15 minutes without activity; the delay is fixed. Activity is any
of: an exposure in progress, an open control connection, a client associated with the device's
access point, stacking, live streaming, a running view plan or a demonstration. The check runs
about once a minute, so shutdown comes 15 to 16 minutes after the last activity. READ.

R19. [`start_view_star_sleep`](../../docs/control/methods/start_view_star_sleep.md) reads no
params. It requires an open camera (318 otherwise), stops the current view and starts the sleep
stage of the view worker, then replies. If the sleep stage already runs it replies success at
once. Errors 212, 207. READ.

R20. [`Sleep`](../../docs/control/events/Sleep.md) is a function-state event (`idle`, `working`,
`complete`, `fail`, `cancel`) from the sleep stage. No members beyond the common function-state
fields are established. `start_view_star_sleep` reports through `Sleep`: `working` when the
stage starts, then `cancel` when a new view or stop request ends it, otherwise
`complete` or `fail`. The stage only waits while it runs. READ (emission); INFERRED (state
names).

R21. [`charge_only`](../../docs/control/methods/charge_only.md) reads no params and requests a
manual Type-C removal, blocking until the storage scan finishes. It is not a toggle. Error 207
(others possible). The effect of leaving only charging connected is INFERRED.

### Sleep stage details

Basis: static analysis of firmware 9.31 (64-bit build; 32-bit build probable) and app 3.3.2, unless a line says otherwise.

[`start_view_star_sleep`](../../docs/control/methods/start_view_star_sleep.md) stops the
current view, sets view mode 0 and the [`Sleep`](../../docs/control/events/Sleep.md) stage, clears the subframe, selects page 0 and
starts the view worker. If the stage is already `Sleep` it does nothing. 318 when the camera is
closed. READ. The stage reports as the `Sleep` function-state event: `working` on entry, then
`cancel` (no `code` on the wire) when stopped by request, otherwise `complete` or `fail`. READ (emission);
INFERRED (state names). The stage only waits while it runs. READ.

## Storage

### Storage names

Storages are addressed by name. READ.

| Model | Accepted names | Notes |
|---|---|---|
| With internal eMMC | `emmc`, `sd`, `udisk` | `emmc` is internal |
| Without eMMC | `sd`, `udisk` | `sd` is the internal slot |

R22. Names are matched case-insensitively. The same name can address different internal slots
on different models. Clients MUST use names, not slot numbers. READ (device); normative (client).

### Querying

R23. [`get_image_save_path`](../../docs/control/methods/get_image_save_path.md) reads no params and
returns `is_typec_connected`, `connected_storage` (array of names), `storage_volume` (array of
objects with `name`, `state` and, when the space query succeeds, size members) and
`cur_storage`. A failed space query omits the size members only. Tier B. READ.

R24. [`get_disk_volume`](../../docs/control/methods/get_disk_volume.md) takes a storage name or
path as a string, or `[usb_disk]` where false selects storage 0 and true selects storage 2, or nothing for the current storage. Object params are ignored (current storage). A string that
is not a storage name is used directly as a filesystem path. It returns `{totalMB, freeMB}`. The values are mebibytes
despite the name. Errors 318 (not mounted), 204, 255, 300. READ.

R25. [`list_mass_storage`](../../docs/control/methods/list_mass_storage.md) returns `{usb2, usb3}`
counts of attached USB mass-storage devices, from the USB device listing: a device at up to
480 Mbit/s counts as `usb2`, faster as `usb3`. An internal correction subtracts one from `usb2`
without a lower clamp, so `usb2` can be negative; clients SHOULD clamp it at zero. A failing
command gives zero counts; it has no errors. READ (device); normative (client).

### Selecting the save location

R26. [`set_image_save_path`](../../docs/control/methods/set_image_save_path.md) takes a storage
name (string), not a filesystem path. An empty or unknown name gives 109; a non-string gives 105.
Selecting the current storage succeeds at once. Otherwise the storage must be mounted (318). The
selection is persisted. READ.

R27. [`set_local_storage_info`](../../docs/control/methods/set_local_storage_info.md) is accepted
only by the secondary process type; elsewhere it gives 210. It takes `path` (string) and
`disk_gb` (number); a missing member gives 209. `disk_gb` is the peer storage's capacity in
binary gigabytes (GiB): the device multiplies it by 1024 and compares it with free space in MiB
when computing usage. The value takes effect only in the device role that accepts a peer's
storage. READ. Devices send it to each other; clients SHOULD NOT call it. INFERRED (advice).

R28. [`set_img_name_field`](../../docs/control/methods/set_img_name_field.md) sets which of
`temp`, `gain` and `camera_name` appear in image file names; params must be an object (107).
[`get_img_name_field`](../../docs/control/methods/get_img_name_field.md) returns those plus
`bin` (always true) and `date_time`. READ.

### Eject and format

R29. [`eject_disk`](../../docs/control/methods/eject_disk.md) takes an optional storage name
string. Absent: the device picks mounted storage 1, else 2; if neither is mounted, 207. A
non-string gives 105; an unknown name gives 207. The device marks the storage as ejecting and
starts the unmount. The reply means accepted; unmount failures are not reported. READ.

R30. Ejecting can change the current save location. Clients SHOULD re-read
`get_image_save_path` after an eject. READ (device); normative (client).

R31. [`format_emmc`](../../docs/control/methods/format_emmc.md) erases the internal memory with
no confirmation parameter and no state guard. It disables file sharing ([smb.md](../media/smb.md)), unmounts, formats as
exFAT, remounts, recreates the default folders and clears the favourites database. Partial
destructive work can precede an error. On success it returns the storage snapshot described in
R23. Errors 210 (no eMMC), 207, 214, 531. READ.

R32. A client MUST obtain explicit user confirmation before sending `format_emmc`, and MUST NOT
send it while imaging. Normative.

### Storage events

R33. [`DiskSpace`](../../docs/control/events/DiskSpace.md) carries `used_percent` (integer) only.
It is sent when a refresh (at most every 5000 ms, or forced by save and record paths) finds a
different integer percentage with a positive total. READ. OBSERVED(2026-10-12): exactly
`Event`, `Timestamp`, `used_percent`.

R34. [`DeviceChange`](../../docs/control/events/DeviceChange.md) reports hot-plug of storage,
serial devices or cameras: `arrival` (boolean), `device` (string) and, from the imager,
`auto_open` (boolean). Guider producers may omit `auto_open`. READ.

R35. [`DiskEject`](../../docs/control/events/DiskEject.md) carries `state` (eject stage string)
and `device` (storage name). Events are queued and flushed later, so delivery lags the
eject step it reports. `state` is `complete` when the requested unmount succeeded (or the
storage was already unmounted) and `fail` when it did not, in which case the storage stays
mounted. An eject request for storage that is not mounted produces no `DiskEject`, and physical
removal produces `DeviceChange` with `arrival` false instead. READ.

### Internal storage operations

Basis: static analysis of firmware 9.31 (64-bit build; 32-bit build probable) and app 3.3.2, unless a line says otherwise.

[`format_emmc`](../../docs/control/methods/format_emmc.md) erases and re-creates the
internal image store, then returns a storage snapshot
`{is_typec_connected, connected_storage, storage_volume, cur_storage}`. It has no confirmation
parameter and no capture guard. Errors 210 (no internal store), 207, 214, 531. READ. A client
MUST ask its user to confirm before sending it.

[`charge_only`](../../docs/control/methods/charge_only.md) simulates removal of the USB-C
storage link so the port only charges (INFERRED). It blocks until the storage scan finishes. Any
failure is 207 or a scanner code. READ.

## Open questions

- Event name of the sleep stage.
- Exact storage events after `format_emmc` and `charge_only`.

- The visual meaning of each power-LED mode: see [R10](#power-led-and-auxiliary-outputs).

## Appendix: Validating on a live device (non-normative)

- `get_device_state` with `keys:["pi_status","storage"]` is a low-impact read.
- Watch `PiStatus` while warming the device; expect `temp` only after a change of more than
  1 degree.
- Never send `format_emmc`, `pi_shutdown` or `pi_reboot` on a device that holds unsaved data.
