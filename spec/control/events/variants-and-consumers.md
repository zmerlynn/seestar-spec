# Events: build variants, app consumers and examples

Part of the [events chapter](../events-overview.md). This file records how the 32-bit firmware
build differs, what the reference app consumes (non-normative), which names have no proved
emitter, how complete the event inventory is, and synthetic wire examples. Normative rules are in
[envelope.md](envelope.md) and [families.md](families.md).

Basis: static analysis of firmware 9.31 (D64 AArch64 and D32 ARM imager, guider, updater) and
Android app 3.3.2; [Firmware 9.75 deltas](#firmware-975-deltas) records firmware 9.75 / app 3.4.0 deltas. Labels as in [CONVENTIONS.md](../../../CONVENTIONS.md).

## D32 differences

R67. D32 has equivalent envelope, framing, F-state and route helpers, with 32-bit sizes. READ.
A D32 counterpart emitter does not by itself prove payload, cadence or state parity, and absence
from this table does not declare two builds identical.

| Event | D64 | D32 (READ unless marked) |
|---|---|---|
| [`PiStatus`](../../../docs/control/events/PiStatus.md) | nine members, full/delta modes | Same nine members and enum, integer `battery_temp`, same delta scheme. Neither build sends `is_undervolt`/`is_over_current`. The member set does not depend on the model; the model only changes the device's low-battery shutdown voltage on D32. The builds read different charger chips, so the `charger_status` mapping may differ by build, not by model. |
| [`RTSP`](../../../docs/control/events/RTSP.md) | `roi_index` (conditional), `roi_scale` number, `port` integer | `roi_index` and `port`; no `roi_scale` in this callback. |
| [`Exposure`](../../../docs/control/events/Exposure.md) (F) | `exp_ms`, `port` | Same. The legacy `Exposure` extension map has one member in both builds: `ac_count` (integer, the auto-goto attempt counter), on exposures taken by auto-goto and its solve retry. Other legacy `Exposure` events carry no extension members. |
| [`AutoGoto`](../../../docs/control/events/AutoGoto.md) | `count` integer, `hint` boolean | Same names. |
| [`CreateCalibFrame`](../../../docs/control/events/CreateCalibFrame.md) | `exp_us`, `adu`, `type` | Same names. The `type` enum is identical: `bias`, `flat_IR`, `flat_LP` for custom types 1–3; other values give `unknown`. |
| [`View`](../../../docs/control/events/View.md) | `mode`, `target_type`, `cam_id` plus other callbacks | Same three names; full equality not established. |
| [`Stack`](../../../docs/control/events/Stack.md) (F) | wide-mosaic progress/stitch/part-complete/`ra_dec`; `scene_shooting`; `auto_exp_us`; video `file_saved`; shared count/JPG/photometry members | Lacks the wide-mosaic, `scene_shooting`, `auto_exp_us` and video `file_saved` branches. Shares `cont_capt_frame`, `frame_errcode`, `stacked_frame`, `dropped_frame`, `can_annotate`, `jpg_name`, `output_file`, `angle`, `csv_saved`. |
| [`BatchStack`](../../../docs/control/events/BatchStack.md) | task types `deepsky`, `startrail_image`, `startrail_video`, `comet`; `keep` | No `startrail_video` or `keep`. Shared `remaining_sec`, `percent`, counts, `input_thn`, `output_file`. |
| [`PlanetStack`](../../../docs/control/events/PlanetStack.md) | `percent`, `output_file`, `input_thn`, procedure callback | Same three callback members. `procedure_code` 0–4 maps to `procedure` `read frame calculate score`, `calculate average frame`, `create ap griad` (firmware spelling), `calculate frame qualities`, `stack frames` in both builds; the out-of-range default was not checked. |
| [`Target`](../../../docs/control/events/Target.md) | main and wide outputs/counters, `wide_state`/`wide_code`/`wide_error` | `target_id`, `camera_mode`, `output_file`, `stack_total_sec` only; no wide branches. |
| [`ViewTargetNameChanged`](../../../docs/control/events/ViewTargetNameChanged.md) | `original_name`, `updated_name` | Same, although some related D64 methods are absent in D32. |
| [`Setting`](../../../docs/control/events/Setting.md) | filtered getter and direct producers | Same six producers and the same filtered-notify keys (`ap_changed`, `mosaic`, `drizzle2x`, `wide_denoise`, `wide_cross_offset_show`). `wide_cross_offset_show` is sent from the camera page setter on D32 and from the camera streaming function on D64. Other differences are serializer members only. |
| guider / updater events | as cards | Counterparts exist; [`GuideStep`](../../../docs/guider/events/GuideStep.md) details and updater failure codes not fully compared. No `OtaUpdate` emitter in either build. |

### Firmware 9.75 deltas

R67b. Firmware 9.75, app 3.4.0 adds four function events, `MotionMonitor`, `SmartFollow`, `MotionDetection` and `SkyReplay`
([function states](../function-states.md)). READ (64-bit). The 32-bit 9.75 imager has no motion
monitor or motion detector (no handlers for their methods) and so neither `MotionMonitor` nor `MotionDetection`; the sky replay getter and setter are identical in both builds. It has the
`start_smart_follow` handler; whether its worker sends `SmartFollow` was not verified, and its
worker differs (no detection step). `CompassCalibration` `fail` now carries `code` and `error`
([polar alignment R18c](../polar-alignment.md#automatic-compass-calibration-firmware-975)); the
D32 behaviour of those codes is partly verified (code 560 only; the strings of 560 to 565 are present in both builds). The inventory count of R69 is
107 for firmware 9.31 and 111 with these four. The app's treatment of the new names in app 3.4.0 was
not examined; [App consumer behaviour (non-normative)](#app-consumer-behaviour-non-normative) describes app 3.3.2 only.

## App consumer behaviour (non-normative)

This section describes what app 3.3.2 does with events. It is evidence of client expectations,
not of firmware requiredness, units or presence. A compatible device does not need to satisfy
app DTO fields that firmware never sends.

- The app reads CRLF-delimited lines and routes every non-`jsonrpc` line to its event dispatcher.
  Its main socket is 4700. A second "event socket" class in the app is empty. READ.
- A new-style service sees each event before the legacy UI switch, so an event can be handled even
  if the old UI ignores it. READ.
- Unknown names map to an internal Unknown-name sentinel sentinel and are dropped. READ.
- The app normalizes only `idle`, `working`, `cancel`, `complete`, `fail`; any other state (`start`,
  `moving`, `downloading`, `frame_complete`, `save fail`, `on`, `off`, ...) becomes `idle` inside
  the app. That is app behaviour, not firmware normalization. READ.
- For "app state" events the new service drops an event with no `route`, except for
  [`SelectCamera`](../../../docs/control/events/SelectCamera.md),
  [`ViewPlan`](../../../docs/control/events/ViewPlan.md), `Target`,
  [`Demonstrate`](../../../docs/control/events/Demonstrate.md) and `ViewTargetNameChanged`.
  [`Station`](../../../docs/control/events/Station.md) and
  [`CompassCalibration`](../../../docs/control/events/CompassCalibration.md) are also exempt. READ.
  A stand-in device SHOULD therefore include `route` on other app-state F events. INFERRED.
- The app merges partial `PiStatus` events into retained state. READ.
- The app expects `output_file` as `{path: string, files: array}`. READ. This matches the firmware
  shape (R67a).

R67a. One firmware builder makes every `output_file` and `wide_output_file` member (`Stack`,
`PlanetStack`, `BatchStack`, `Target`, `ViewPlan`). The object has `path` (string, the output
directory relative to the storage root, no trailing slash) and `files`, an array of exactly one
object with `name` (string), `date` (string), `thn` (string, thumbnail name) and `type` (integer
file type). Every member is always written. READ (builder); that every formatter's stored object
comes only from this builder is INFERRED.

### Names the app consumes

Non-normative. "svc" = new-style typed service, "legacy" = legacy UI dispatcher, "conn" =
connection service, "upd" = updater screens. All names have a firmware emitter (see the
[event index](../events-overview.md#event-index)) unless listed in 2.2.

| Consumers | Names |
|---|---|
| svc + legacy | `3PPA`, [`AIProcess`](../../../docs/control/events/AIProcess.md), [`Alert`](../../../docs/control/events/Alert.md), [`AutoFocus`](../../../docs/control/events/AutoFocus.md), [`AviRecord`](../../../docs/control/events/AviRecord.md), [`CalibGSensor`](../../../docs/control/events/CalibGSensor.md), [`Client`](../../../docs/control/events/Client.md), [`ContinuousExposure`](../../../docs/control/events/ContinuousExposure.md), [`DarkLibrary`](../../../docs/control/events/DarkLibrary.md), [`FocuserMove`](../../../docs/control/events/FocuserMove.md), [`GoPixel`](../../../docs/control/events/GoPixel.md), [`Initialise`](../../../docs/control/events/Initialise.md), [`SaveImage`](../../../docs/control/events/SaveImage.md), [`ScopeHome`](../../../docs/guider/events/ScopeHome.md), [`ScopeMoveToHorizon`](../../../docs/guider/events/ScopeMoveToHorizon.md), [`SecondView`](../../../docs/control/events/SecondView.md), `SelectCamera`, `Setting`, [`Sleep`](../../../docs/control/events/Sleep.md), `View`, `ViewPlan`, [`WheelMove`](../../../docs/control/events/WheelMove.md) |
| svc + legacy + conn | `AutoGoto`, [`DiskSpace`](../../../docs/control/events/DiskSpace.md), `Exposure`, `PiStatus`, [`PlateSolve`](../../../docs/control/events/PlateSolve.md), [`ScopeGoto`](../../../docs/control/events/ScopeGoto.md), `Stack` |
| svc only | [`AutoExp`](../../../docs/control/events/AutoExp.md), [`CheckPhotoMetry`](../../../docs/control/events/CheckPhotoMetry.md), `CompassCalibration`, [`CreateHPC`](../../../docs/control/events/CreateHPC.md), `Demonstrate`, [`FactoryTestControl`](../../../docs/control/events/FactoryTestControl.md), [`MountMode`](../../../docs/guider/events/MountMode.md), [`ObjectTrack`](../../../docs/control/events/ObjectTrack.md), `RTSP`, [`ScanSun`](../../../docs/control/events/ScanSun.md), [`ScopeTrack`](../../../docs/guider/events/ScopeTrack.md), `Station`, `Target`, `ViewTargetNameChanged` |
| legacy only | [`Annotate`](../../../docs/control/events/Annotate.md), [`AviRtmp`](../../../docs/control/events/AviRtmp.md), [`BalanceSensor`](../../../docs/control/events/BalanceSensor.md), `BatchStack`, [`BattHiTempShutdown`](../../../docs/control/events/BattHiTempShutdown.md), `CreateCalibFrame`, [`DeviceChange`](../../../docs/control/events/DeviceChange.md), [`EqModePA`](../../../docs/control/events/EqModePA.md), `PlanetStack` |
| legacy + upd | [`Version`](../../../docs/control/events/Version.md) |
| upd only | [`Receive`](../../../docs/updater/events/Receive.md), [`Update`](../../../docs/updater/events/Update.md) |

READ. Firmware events not in this table (for example most guider events) are emitted but not
consumed by this app version.

### Names without a proved firmware emitter

Non-normative. A device is not expected to send these; a client MUST NOT rely on them.

| Name | App use | Status |
|---|---|---|
| `Align` | legacy dispatcher compares it and ignores it | no emitter in any 9.31 binary or vendor library; app-only legacy name (READ) |
| `StackExpLoop` | legacy dispatcher compares it | no emitter in any 9.31 binary or vendor library; app-only name. The related worker has a blank function name, so the F sender suppresses it (READ) |
| Local exposure-tag notification | app-internal event derived from `Exposure` | local to the app; no wire emitter (READ) |
| `OtaUpdate` | new OTA channel on 4350 expects `state`, `stage`, `code`, `error`, `main_version`, `need_reboot` (no `Timestamp` required) | no emitter in either packaged firmware 9.31 updater (READ); other firmware versions are out of scope |
| Unknown-name sentinel | fallback sentinel | not a wire event |

R68. The legacy firmware-update screen uses `Version`, `Receive` and `Update` on 4350; the newer
`OtaUpdate` workflow is a different protocol, not an alias. A client MUST NOT substitute one name
for the other. READ.

### Defined but never dispatched

Non-normative. The app defines these event-name constants but has no dispatch for them, and no
firmware emitter is proved: `AutoGoto_3ppa`, `CoolerPower`, `CoolTooSlow`, `cooling`, `Nginx`,
`RTMP`, `scenery`, `SendStopped`, `stacking`, `Warning`, `jpg_format`, `WheelCalibrate`,
`wide_cross_offset`. READ (definitions). Several are payload keys or mode values elsewhere.
Other defined constants ([`AutoGotoStep`](../../../docs/control/events/AutoGotoStep.md), [`CameraStateChange`](../../../docs/control/events/CameraStateChange.md), [`DiskEject`](../../../docs/control/events/DiskEject.md), [`Dither`](../../../docs/control/events/Dither.md),
[`ExportImage`](../../../docs/control/events/ExportImage.md), [`FindStar`](../../../docs/control/events/FindStar.md), [`FirstDelay`](../../../docs/control/events/FirstDelay.md), [`FrameDelay`](../../../docs/control/events/FrameDelay.md), [`GuidingDithered`](../../../docs/guider/events/GuidingDithered.md), [`LoopingFrames`](../../../docs/control/events/LoopingFrames.md),
[`MeridianFlip`](../../../docs/control/events/MeridianFlip.md), [`RestartGuide`](../../../docs/control/events/RestartGuide.md), [`Sequence`](../../../docs/control/events/Sequence.md), [`Settle`](../../../docs/control/events/Settle.md), [`TargetDelay`](../../../docs/control/events/TargetDelay.md), [`Temperature`](../../../docs/guider/events/Temperature.md)) do have
firmware emitters but no app dispatch. READ.

## Coverage

R69. The inventory has at least 107 emitted or named-worker events: `PiStatus` plus 106 per-event
records. READ. The search covered all disassembled imager functions, every envelope construction,
every family helper and caller, the broadcast senders, the function-event path and initialized
function-name strings; the packaged guider and updater were inspected separately. Update scripts
were read, never run. READ.

R70. The file server (9.31, 64-bit) has no JSON event emitter. Its function-state sender has no
installed callback, and it only parses events it receives as a client of the main imager. READ.
Unsolicited events on the control port therefore come from the imager processes. INFERRED. The
32-bit file server matches: same function-state sender, and its callback is never installed (READ). The vendor shared libraries in
the package cannot add events: none builds the event envelope, and the only networking in them is
a logging appender. The SDK's own callback-registration entry points are not imported by any
packaged process, and the callbacks the processes do register (messaging client, USB hot-plug,
library error handlers) land in process code that the search above covered. READ (64-bit
package; the 32-bit package was checked for callback imports only). Image,
thumbnail and video bytes, RPC replies, UDP discovery replies, internal condition-variable
notifications and INDI messages without an envelope are not events. READ.

R71. [`MountUpdate`](../../../docs/control/events/MountUpdate.md) is a proved named-worker event. Lower-case mount descriptions (`move`, `none`,
`clear_backlash`, `move_home_horizon`) are not proved event names. READ.

R72. Updater `Update.desc` values include `copy file`, `write disk`, `update mount FW`,
`restart server` and progress descriptions parsed from script output; D32 and D64 scripts differ.
READ. Percent values are not fixed.

R73. App inventory: 60 compared, recognized or derived names (including Unknown-name sentinel and
Local exposure-tag notification), 44 typed enum values, 77 defined constants; 4 consumed names lack
an emitter (2.2). READ.

## Wire-shape examples

All values are synthetic. Literal strings that are firmware constants are noted as such. Members
not shown can also occur; see the cards.

```text
{"Event":"BattHiTempShutdown","Timestamp":"7310.000412877"}
```

N family: envelope only.

```text
{"Event":"Exposure","Timestamp":"7311.204551030","page":"preview","state":"start","exp_us":10000000,"gain":80}
{"Event":"Exposure","Timestamp":"7321.880102114","page":"preview","state":"fail","error":"<text>","code":514}
{"Event":"Exposure","Timestamp":"7321.880230991","state":"working","lapse_ms":10512,"exp_ms":10000.0,"port":4700,"route":["View","Stack"]}
```

Legacy and F variants of one name (shapes READ and OBSERVED 2026-10-12; values synthetic; the
code 514 was the observed value).

R70a. A legacy `Exposure` `fail` with code 514 means the exposure was interrupted by an internal
stop, not by a client stop command. After a client stop (`stop_exposure`, `iscope_stop_view`,
`stop_stack` and similar) the code is 253. When retries run out while the exposure is still
running, the code is 238. READ. Which internal stops occur live is INFERRED (for example a mode
or page change).

```text
{"Event":"Stack","Timestamp":"7322.001000004","state":"frame_complete","frame_type":"light","stacked_frame":12,"dropped_frame":1,"total_frame":13,"error":"","lapse_ms":0,"code":0}
{"Event":"Stack","Timestamp":"7322.001100410","state":"working","lapse_ms":152003,"frame_errcode":0,"stacked_frame":12,"dropped_frame":1,"can_annotate":true,"scene_shooting":false,"route":["View"]}
```

Custom stack-state and F variants (shapes READ and OBSERVED 2026-10-12; values synthetic).

```text
{"Event":"ViewPlan","Timestamp":"7400.250000123","state":"fail","lapse_ms":30,"code":207,"error":"fail to operate"}
{"Event":"View","Timestamp":"7401.000000777","state":"cancel","lapse_ms":64210}
```

F family: `fail` carries `code` and `error`; `cancel` carries neither (READ).

```text
{"Event":"Client","Timestamp":"7402.120004455","connected":["phone-a","tablet-b"],"master_index":0,"is_master":false}
{"Event":"Alert","Timestamp":"7402.500011000","Msg":"Exceed the maximum number of connections","Type":"error","code":429}
{"Event":"Update","Timestamp":"7500.330000901","state":"working","desc":"write disk","route":[]}
{"Event":"GuideStep","Timestamp":"7600.010203040","Frame":42,"Time":84.2,"Mount":"<string>","dx":0.31,"dy":-0.12}
```

The connection-limit `Alert` text, `Type` and code 429 are firmware literals (READ). The
updater sends `route` as an empty array (READ). `GuideStep` has further members (card).
