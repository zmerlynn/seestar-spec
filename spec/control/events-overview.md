# Events overview

This chapter specifies the asynchronous JSON events a Seestar device sends to clients on its
JSON control servers: the envelope, framing, channels, recipients, ordering, the helper families
that shape payloads, and the full list of event names. It sits above the TCP control stream
([session handshake](session-handshake.md), [LAN discovery and ports](../transport/lan-discovery.md))
and beside the request/reply methods (`docs/<service>/methods/`). Per-event payloads are on the
generated event cards (`docs/<service>/events/<Name>.md`); one worked operation is in
[plan scheduling](plan-scheduling.md).

## Files

| File | Content |
|---|---|
| this file | Scope, conventions, client summary, full event index, open questions |
| [events/envelope.md](events/envelope.md) | Envelope, timestamp, framing (ABNF), channels I/I2/W/G/U, recipients, peer forwarding, observer idle timeout, ordering, client rules |
| [events/families.md](events/families.md) | Helper families N, S, SR, V, P, F; F state enum and lifecycle; `lapse_ms`; suppression flags; `PiStatus` delta and rate rules |
| [events/nested-schemas.md](events/nested-schemas.md) | Station object, 3PPA stage table, legacy plan progress, `ViewPlan.plan`, `Setting` producers and member inventory |
| [events/variants-and-consumers.md](events/variants-and-consumers.md) | D32 differences, app consumer behaviour and names without an emitter (non-normative), coverage, synthetic wire examples |

## Conventions

The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are used as in RFC 2119 and RFC 8174.
They bind clients (and stand-in devices where stated); sentences about what "the device" does are
descriptions.

Every claim carries a label (see [CONVENTIONS.md](../../CONVENTIONS.md)): **READ** (static
analysis of firmware 9.31 or app 3.3.2; says what the code does), **OBSERVED** (seen in sanitized
captures on 2026-10-12 from a device whose firmware build was not matched to 9.31; treat as
hints), **INFERRED**, **unresolved**. READ claims are for the 64-bit imager build ("D64") unless
stated; the 32-bit build ("D32") is covered in
[variants-and-consumers.md](events/variants-and-consumers.md). No code was executed.

Requirement numbers run continuously across the chapter: R1–R2 here, R3–R29 in
[envelope.md](events/envelope.md), R30–R51 in [families.md](events/families.md), R52–R66 in
[nested-schemas.md](events/nested-schemas.md) and R67–R73 in
[variants-and-consumers.md](events/variants-and-consumers.md).

## Client summary

The full rules are in [envelope.md: Client rules](events/envelope.md#client-rules). In short:

1. An event is a CRLF-terminated JSON object with top-level `Event` and `Timestamp` strings and
   no `jsonrpc`/`id`. It shares the socket with replies; dispatch each line by content. READ.
2. `Timestamp` is monotonic seconds with nine decimals, as a string. It is not wall-clock time.
   READ.
3. Connect to TCP 4700 for imager, auxiliary-imager and guider events (forwarded); 4350 for
   updater events. READ.
4. **Merge deltas.** Events carry changed or present members only; merge into retained state and
   never read absence as false, zero or removal. Seed state with getters. INFERRED.
5. **Parse tolerantly.** Ignore unknown names, members and states; accept any subset. INFERRED.
6. **No reply/event ordering.** Do not assume an event comes after (or before) the reply to the
   request that caused it, nor a fixed rate, nor exactly one `working` and one end state. READ.
7. Send something at least every 15 s or a listen-only connection may be closed. INFERRED from
   READ idle rule.
8. F-family `fail` always has `code` and `error`; S-family `fail` only for a positive code;
   `cancel` has neither. READ.

## Event index

Every event name with a proved firmware emitter (107 names in firmware 9.31; firmware 9.75 adds
`MotionMonitor`, `SmartFollow`, `MotionDetection` and `SkyReplay`, 111 in all). READ for emitter existence.
**Service** is the catalog service holding the card: `guider` for events whose primary channel is
G (TCP 4400), `updater` for U (TCP 4350), `control` otherwise. `ScopeGoto` is under `control`
because both the guider slew worker and the imager emit it. **Family** is from
[families.md](events/families.md) ("custom" = event-specific formatter; "legacy" = an older
direct producer with its own states). **Delivery** gives the port(s) the event is written to;
"4400 → 4700" means emitted by the guider and forwarded by the main imager; "4702 → 4700"
likewise for the auxiliary imager. All are ordinary broadcasts unless a special rule is named
([envelope.md](events/envelope.md) R14).

### Device, connection and settings

| Event | Service | Family | Delivery | Summary |
|---|---|---|---|---|
| [`PiStatus`](../../docs/control/events/PiStatus.md) | control | custom delta | 4700 | Changed SoC temperature, battery and charger fields. |
| [`Version`](../../docs/control/events/Version.md) | control | custom | arriving socket on 4700, 4400, 4350 | Connection greeting: server name; on the imager also firmware version and verification. |
| [`DiskSpace`](../../docs/control/events/DiskSpace.md) | control | custom | 4700 | Storage `used_percent` after a changed read. |
| [`Client`](../../docs/control/events/Client.md) | control | custom | 4700, 4400; guest-mode clients | Connected client names and master index; `is_master` per recipient. |
| [`CameraStateChange`](../../docs/control/events/CameraStateChange.md) | control | N | 4700 | A camera was opened or closed. |
| [`DeviceChange`](../../docs/control/events/DeviceChange.md) | control | custom | 4700, 4400 | Storage, serial or camera hotplug arrival or removal. |
| [`AutoOpenDevice`](../../docs/control/events/AutoOpenDevice.md) | control | custom | 4700 | A device was reopened automatically after reconnection. |
| [`AppStateChange`](../../docs/control/events/AppStateChange.md) | control | custom | 4700, 4400 | Reconnection changed the active page or resumed an activity. |
| [`SelectCamera`](../../docs/control/events/SelectCamera.md) | control | custom | 4700 | The selected imaging camera or process changed. |
| [`ViewTargetNameChanged`](../../docs/control/events/ViewTargetNameChanged.md) | control | custom | 4700 | The current view target's name was updated. |
| [`Setting`](../../docs/control/events/Setting.md) | control | custom delta | 4700, 4702 | Changed settings, with `stack`/`exp_ms` companions and camera origin. |
| [`Station`](../../docs/control/events/Station.md) | control | S + custom | 4700 | Result of a Wi-Fi station connection attempt, with the station object. |
| [`DiskEject`](../../docs/control/events/DiskEject.md) | control | custom (queued) | 4700 | Storage eject status. |
| [`Alert`](../../docs/control/events/Alert.md) | control | custom | 4700, 4400; one rejected socket | Operational fault, or connection-limit rejection before close. |
| [`BattHiTempShutdown`](../../docs/control/events/BattHiTempShutdown.md) | control | N | 4700 | Battery over-temperature shutdown is starting. |
| [`BalanceSensor`](../../docs/control/events/BalanceSensor.md) | control | custom | 4700 | Periodic balance (tilt) sensor data. |
| [`GSensorMove`](../../docs/control/events/GSensorMove.md) | control | N | 4700 | Device moved; polar-alignment calibration cleared. |
| [`CompassCalibration`](../../docs/control/events/CompassCalibration.md) | control | SR + custom | 4700 | Compass calibration progress and sector coverage; `fail` carries `code` and `error` in firmware 9.75. |
| [`CalibGSensor`](../../docs/control/events/CalibGSensor.md) | control | F | 4700 | G-sensor calibration worker lifecycle. |
| [`ScopeMoveRound`](../../docs/control/events/ScopeMoveRound.md) | control | custom | 4700 | End of a round (rotation) movement, with result. |
| [`FactoryTestControl`](../../docs/control/events/FactoryTestControl.md) | control | custom | 4700 | Completion of a factory-control operation. |

### Viewing, imaging and processing

| Event | Service | Family | Delivery | Summary |
|---|---|---|---|---|
| [`View`](../../docs/control/events/View.md) | control | F + view formatters | 4700 | Main view (imaging session) lifecycle, mode and target. |
| [`SecondView`](../../docs/control/events/SecondView.md) | control | F + view formatters | 4702 → 4700 | Wide-camera view lifecycle (auxiliary process). |
| [`Initialise`](../../docs/control/events/Initialise.md) | control | F | 4700 | View initialisation stage. |
| [`Sleep`](../../docs/control/events/Sleep.md) | control | F | 4700 | View sleep stage. |
| [`Demonstrate`](../../docs/control/events/Demonstrate.md) | control | F | 4700 | Demonstration mount/view loop. |
| [`Exposure`](../../docs/control/events/Exposure.md) | control | F + legacy | 4700, 4702 | Exposure and download transitions; legacy and F payload variants. |
| [`AutoExp`](../../docs/control/events/AutoExp.md) | control | F + V/S | 4700 | Auto-exposure loop and chosen exposure. |
| [`ContinuousExposure`](../../docs/control/events/ContinuousExposure.md) | control | F | 4700 | Continuous exposure loop with frame rate. |
| [`PlateSolve`](../../docs/control/events/PlateSolve.md) | control | F + legacy | 4700 | Plate-solve start, progress and result. |
| [`Annotate`](../../docs/control/events/Annotate.md) | control | F + legacy | 4700 | Annotation of a solved image. |
| [`AutoGoto`](../../docs/control/events/AutoGoto.md) | control | F + legacy | 4700 | Goto-and-centre workflow progress. |
| [`AutoGotoStep`](../../docs/control/events/AutoGotoStep.md) | control | custom | 4700 | Mount error during a goto step. |
| [`AutoFocus`](../../docs/control/events/AutoFocus.md) | control | F + legacy/V | 4700, 4702 | Autofocus run, V-curve samples and result. |
| [`FocuserMove`](../../docs/control/events/FocuserMove.md) | control | F + custom | 4700, 4702 | Focuser movement and position. |
| [`GoPixel`](../../docs/control/events/GoPixel.md) | control | F | 4700 | Centring on a selected pixel. |
| [`FindStar`](../../docs/control/events/FindStar.md) | control | S + V | 4700 | Star finding start and result. |
| [`DarkLibrary`](../../docs/control/events/DarkLibrary.md) | control | F; guider custom | 4700, 4400 | Dark-frame library capture progress. |
| [`CreateCalibFrame`](../../docs/control/events/CreateCalibFrame.md) | control | F | 4700 | Calibration-frame creation. |
| [`CreateHPC`](../../docs/control/events/CreateHPC.md) | control | F | 4700 | Hot-pixel-correction map creation. |
| [`3PPA`](../../docs/control/events/3PPA.md) | control | F + custom PA | 4700 | Three-point polar alignment progress and error. |
| [`EqModePA`](../../docs/control/events/EqModePA.md) | control | F + PA callback | 4700 | Equatorial-mode polar alignment. |
| [`Stack`](../../docs/control/events/Stack.md) | control | F + custom | 4700, 4702 | Live stacking frame accept/drop and progress. |
| [`PlanetStack`](../../docs/control/events/PlanetStack.md) | control | F + custom progress | 4700 | Planetary stacking progress and output. |
| [`BatchStack`](../../docs/control/events/BatchStack.md) | control | F | 4700 | Batch (offline) stacking progress and output. |
| [`ScanSun`](../../docs/control/events/ScanSun.md) | control | F | 4700 | Sun scan worker. |
| [`ObjectTrack`](../../docs/control/events/ObjectTrack.md) | control | F | 4700 | Object-tracker position and size. |
| [`MotionMonitor`](../../docs/control/events/MotionMonitor.md) | control | F + custom members | 4700 | Firmware 9.75: motion monitor stage, settings and remaining time ([function states](function-states.md#motion-monitor)). |
| [`SmartFollow`](../../docs/control/events/SmartFollow.md) | control | F + custom members | 4700 | Firmware 9.75: smart follow stage and tracking result, both strings ([function states](function-states.md#smart-follow)). |
| [`MotionDetection`](../../docs/control/events/MotionDetection.md) | control | F + custom members | 4700 | Firmware 9.75, 64-bit only: detector image size and points ([function states](function-states.md#smart-follow)). |
| [`SkyReplay`](../../docs/control/events/SkyReplay.md) | control | F + custom members | 4700 | Firmware 9.75: sky replay recorder counts; the feature is force-disabled ([function states](function-states.md#sky-replay)). |
| [`AIProcess`](../../docs/control/events/AIProcess.md) | control | F | 4700 | AI denoise processing. |
| [`CheckPhotoMetry`](../../docs/control/events/CheckPhotoMetry.md) | control | F | 4700 | Photometry check before capture. |
| [`RTSP`](../../docs/control/events/RTSP.md) | control | F + custom | 4700, 4702 | Preview stream state, ROI and port. |
| [`AviRecord`](../../docs/control/events/AviRecord.md) | control | F + V/S | 4700 | Video recording progress and saved file. |
| [`AviRtmp`](../../docs/control/events/AviRtmp.md) | control | F + S | 4700 | Video playback start and end. |
| [`SaveImage`](../../docs/control/events/SaveImage.md) | control | F + S/custom | 4700, 4702 | Image save result with file names. |
| [`ExportImage`](../../docs/control/events/ExportImage.md) | control | custom P | 4700 | Copy/export progress. |
| [`WheelMove`](../../docs/control/events/WheelMove.md) | control | S/V | 4700 | Filter-wheel move and position. |
| [`WheelSlotNum`](../../docs/control/events/WheelSlotNum.md) | control | custom | 4700 | Discovered filter-wheel slot map. |

### Plans and legacy automation

| Event | Service | Family | Delivery | Summary |
|---|---|---|---|---|
| [`ViewPlan`](../../docs/control/events/ViewPlan.md) | control | F | 4700 | ViewPlan worker lifecycle with the plan object. |
| [`Target`](../../docs/control/events/Target.md) | control | F + legacy S | 4700 | ViewPlan target transitions (and legacy plan targets). |
| [`Sequence`](../../docs/control/events/Sequence.md) | control | S + custom | 4700 | Legacy sequence and frame transitions. |
| [`TargetChange`](../../docs/control/events/TargetChange.md) | control | N | 4700 | Legacy plan moved to the next target. |
| [`FirstDelay`](../../docs/control/events/FirstDelay.md) | control | V/S | 4700 | Legacy initial delay start/end. |
| [`FrameDelay`](../../docs/control/events/FrameDelay.md) | control | V/S | 4700 | Legacy inter-frame delay start/end. |
| [`TargetDelay`](../../docs/control/events/TargetDelay.md) | control | V/S | 4700 | Legacy inter-target delay start/end. |
| [`MeridianFlip`](../../docs/control/events/MeridianFlip.md) | control | S/V | 4700 | Legacy meridian flip and retries. |
| [`MountSettle`](../../docs/control/events/MountSettle.md) | control | S | 4700 | Legacy wait for the mount to settle after a flip. |
| [`LoopingFrames`](../../docs/control/events/LoopingFrames.md) | control | S | 4700 | Exposure loop start/end. |
| [`RestartGuide`](../../docs/control/events/RestartGuide.md) | control | S | 4700 | Guiding restart after goto or retry. |
| [`Settle`](../../docs/control/events/Settle.md) | control | S | 4700 | Guide-settle wait stages. |
| [`Dither`](../../docs/control/events/Dither.md) | control | S | 4700 | Legacy dither movement. |

### Mount

| Event | Service | Family | Delivery | Summary |
|---|---|---|---|---|
| [`ScopeGoto`](../../docs/control/events/ScopeGoto.md) | control | F | 4400 → 4700; also 4700 | Mount slew to coordinates, with distance. |
| [`ScopeHome`](../../docs/guider/events/ScopeHome.md) | guider | F | 4400 → 4700 | Mount go-home. |
| [`ScopeMoveToHorizon`](../../docs/guider/events/ScopeMoveToHorizon.md) | guider | F | 4400 → 4700 | Mount move to the horizon position. |
| [`ScopeTrack`](../../docs/guider/events/ScopeTrack.md) | guider | custom | 4400 → 4700 | Tracking turned on or off. |
| [`MountMode`](../../docs/guider/events/MountMode.md) | guider | custom | 4400 → 4700 | Mount mode (equatorial or alt-az) changed. |
| [`MoveByAngle`](../../docs/guider/events/MoveByAngle.md) | guider | S-like (guider) | 4400 → 4700 | Move by an angle. |
| [`MountConnection`](../../docs/guider/events/MountConnection.md) | guider | custom | 4400 → 4700 | Mount serial link lost or restored. |
| [`AutoCloseMount`](../../docs/guider/events/AutoCloseMount.md) | guider | N | 4400 → 4700 | Mount closed automatically. |
| [`MountUpdate`](../../docs/control/events/MountUpdate.md) | control | F | 4700 | Mount firmware (boot) write worker. |

### Guider

| Event | Service | Family | Delivery | Summary |
|---|---|---|---|---|
| [`AutoOpenCamera`](../../docs/guider/events/AutoOpenCamera.md) | guider | custom | 4400 → 4700 | Guide camera reopened automatically. |
| [`Temperature`](../../docs/guider/events/Temperature.md) | guider | custom | 4400 → 4700 | Camera temperature update. |
| [`StartCalibration`](../../docs/guider/events/StartCalibration.md) | guider | custom | 4400 → 4700 | Guide calibration begins. |
| [`Calibrating`](../../docs/guider/events/Calibrating.md) | guider | custom | 4400 → 4700 | Guide calibration step. |
| [`CalibrationFailed`](../../docs/guider/events/CalibrationFailed.md) | guider | custom | 4400 → 4700 | Guide calibration failed, with reason. |
| [`CalibrationDataFlipped`](../../docs/guider/events/CalibrationDataFlipped.md) | guider | custom | 4400 → 4700 | Calibration flipped for a pier-side change. |
| [`CalibrationComplete`](../../docs/guider/events/CalibrationComplete.md) | guider | custom | 4400 → 4700 | Guide calibration complete. |
| [`StarPos`](../../docs/guider/events/StarPos.md) | guider | custom | 4400 → 4700 | New measured star position. |
| [`StarSelected`](../../docs/guider/events/StarSelected.md) | guider | custom | 4400 → 4700 | Guide star selected. |
| [`LockPositionSet`](../../docs/guider/events/LockPositionSet.md) | guider | custom | 4400 → 4700 | Lock position set. |
| [`LoopingExposures`](../../docs/guider/events/LoopingExposures.md) | guider | custom | 4400 → 4700 | Guider loop frame. |
| [`AppState`](../../docs/guider/events/AppState.md) | guider | custom | 4400 → 4700 | Guider application state. |
| [`INDIServer`](../../docs/guider/events/INDIServer.md) | guider | custom | 4400 → 4700 | INDI server notification. |
| [`GuidingDithered`](../../docs/guider/events/GuidingDithered.md) | guider | custom | 4400 → 4700 | Dither offset applied. |
| [`Settling`](../../docs/guider/events/Settling.md) | guider | custom | 4400 → 4700 | Settling progress. |
| [`SettleDone`](../../docs/guider/events/SettleDone.md) | guider | custom | 4400 → 4700 | Settling finished or failed. |
| [`StarLost`](../../docs/guider/events/StarLost.md) | guider | custom | 4400 → 4700 | Guide star lost on a frame. |
| [`LoopingExposuresStopped`](../../docs/guider/events/LoopingExposuresStopped.md) | guider | N | 4400 → 4700 | Guider loop stopped. |
| [`GuideStarLostTooMuch`](../../docs/guider/events/GuideStarLostTooMuch.md) | guider | N | 4400 → 4700 | Star-loss threshold crossed. |
| [`StartGuiding`](../../docs/guider/events/StartGuiding.md) | guider | N | 4400 → 4700 | Guiding started. |
| [`GuidingStopped`](../../docs/guider/events/GuidingStopped.md) | guider | N | 4400 → 4700 | Guiding stopped. |
| [`Paused`](../../docs/guider/events/Paused.md) | guider | N | 4400 → 4700 | Guider paused. |
| [`Resumed`](../../docs/guider/events/Resumed.md) | guider | N | 4400 → 4700 | Guider resumed. |
| [`LockPositionLost`](../../docs/guider/events/LockPositionLost.md) | guider | N | 4400 → 4700 | Lock position lost. |
| [`SettleBegin`](../../docs/guider/events/SettleBegin.md) | guider | N | 4400 → 4700 | Settling started. |
| [`GuideStep`](../../docs/guider/events/GuideStep.md) | guider | custom | 4400 → 4700 | Per-frame guide correction and measurements. |

### Updater

| Event | Service | Family | Delivery | Summary |
|---|---|---|---|---|
| [`Receive`](../../docs/updater/events/Receive.md) | updater | custom | 4350; IP-matched | Result of a binary upload on TCP 4361. |
| [`Update`](../../docs/updater/events/Update.md) | updater | custom | 4350; IP-matched | Update-script progress (`desc`) and failure. |

R1. `Version` is also sent by the guider and the updater on their own ports, with only `name`;
its card is under `control`. READ. `DarkLibrary`, `Client`, `DeviceChange`, `AppStateChange` and
`Alert` can also originate on 4400; their cards are under `control` because their primary channel
is I. READ.

R2. Names that the app knows but no firmware emits (`Align`, `StackExpLoop`, `ExposureTag`,
`OtaUpdate`, `Unknown`, and definition-only constants) are not events of this protocol; see
[variants-and-consumers.md: Names without a proved firmware emitter](events/variants-and-consumers.md#names-without-a-proved-firmware-emitter) (non-normative).

## Open questions

1. Runtime reachability, per model, of retained guider functionality, and all guest, auth and
   remote-tunnel admission states. unresolved.
2. Runtime activation and cadence of `MountUpdate` per model; any other firmware producer of
   `Align` or `StackExpLoop`. unresolved.
3. Event attribution in the stripped file server and opaque shared libraries. The 64-bit file
   server binary (the file server) contains no code that constructs an `"Event":"<name>"`
   JSON string anywhere; it only consumes the event stream (register/unregister callbacks, a
   JSON-RPC client) and separately serves a file-browsing HTTP API, consistent with it being an
   event consumer plus file server rather than an independent emitter. READ (absence of the
   construction pattern, presence of the consumer pattern); INFERRED (role). Address-level
   cross-reference of the consumer call sites, and a check of the other opaque shared libraries
   (the vendor camera/media SDKs) for event-construction code of their own, remain unresolved.
4. Closed schemas for open extension maps, cached plan-target JSON, annotation objects and every
   `output_file` variant. unresolved.
5. AutoFocus `result`/curve meaning; star-finder enum closure; polar-align transition conditions;
   mount distance/coordinate validity branches. unresolved.
6. Units marked INFERRED or unresolved: battery temperature and capacity, balance axes, guide
   displacement, time, star mass and corrections, solver field of view, algorithm status enums.
   Battery temperature and capacity are raw, unscaled integers (degrees Celsius and a raw
   0-to-100-style capacity reading) taken directly from the platform battery-charge/gauge calls,
   with no device-side scaling; the temperature is compared directly against whole-degree
   thresholds elsewhere in the same code, supporting plain Celsius. Balance-sensor x/y/z are raw
   Q30-normalised gravity-vector doubles, likewise unscaled at the point they are packed into
   `BalanceSensor`. READ.
6a. Resolved: two static readings of `GuideStep`'s displacement members disagreed on which
   members carry the arcsecond conversion. The address shift between the readings was just
   firmware 9.31 vs 9.75, not an error by itself, but the two readings' actual conclusions
   conflicted, so the catalog's prior claim (`dx`/`dy` = arcseconds, the four
   `...Distance...` members unconverted) was independently re-verified byte-for-byte against
   the 9.31 binary it cites as its own basis: the pixel pair multiplied once by the camera
   pixel scale is serialized under `RADistanceRaw`/`DECDistanceRaw` (confirmed from the literal
   key strings); `dx`/`dy` and `RADistanceGuide`/`DECDistanceGuide` are serialized with no
   scaling in this function. The prior catalog claim had the assignment backwards. `GuideStep.yaml`
   and [guider/index.md: Events](../guider/index.md#events) have been corrected: `dx`/`dy` are raw
   camera pixels; `RADistanceRaw`/`DECDistanceRaw` are arcseconds despite the "Raw" name;
   `RADistanceGuide`/`DECDistanceGuide` remain unconverted (probably pixels, INFERRED). READ.
7. Per-worker F state reachability and flag settings; progress between begin and end on every
   build; ordering across parent/child transitions and replies. unresolved.
8. Balance thresholds are settled on the 64-bit build. `angle` is the tilt from vertical in
   degrees. The first valid sample is sent. After that, a sample is sent only when it differs
   from the last sent angle by more than 0.26 degrees and the 2-degree level lies between the two
   values. A failed read is sent once, as code 1. READ (64-bit; 32-bit not checked). There is no
   periodic compass or heading event: the compass reading is packed only into the `compass_sensor`
   member of `get_device_state`, and the only compass event is `CompassCalibration`, sent during a
   calibration run once per newly covered 30-degree sector (at most 12 per run). READ (64-bit and
   32-bit, firmware 9.31 and 9.75). Throttles inside image-processing libraries: unresolved.
9. Full D32 parity beyond the listed differences. A bounded comparison of RPC handlers and
   event senders found no new differences in handlers: the 64-bit build has five extra handlers
   (`get_view_plan_stack_result`, `restore_view_plan_wide_setting`, `set_power_led_mode`,
   `set_view_plan_target_name`, `set_view_plan_wide_setting`), all already recorded, and the
   32-bit build has none of its own. The event senders match, except that only the 64-bit build
   has the RTSP zoom path that sends `RTSP` with `roi_scale` and `route`. READ. Payload-level
   parity of every event is still unresolved.
10. The full set of non-zero `code` values per event. unresolved. The observed `Exposure` code
    514 is settled: an exposure interrupted by an internal stop (view stop, camera close, stage
    or mode change). A client stop gives 253 and exhausted retries give 238. READ. All three flow
    through one shared mechanism (a generic `NotifyState` call, a thread-local error-code
    variable, and a general per-worker state-detail code field) that is reused by at least two
    dozen unrelated worker threads across the 64-bit imager, so a given numeric code is not
    special to `Exposure` and the same code can recur under other event names. READ. Two further
    codes resolved by the same route: `Stack`'s own `start` state is always sent with `code:0`
    (matching the existing example); `ViewPlan` can also send 536 when a start is requested while
    a ViewPlan/demonstrate sequence is already running — distinct from the existing 207 "second
    schedule overlap" case (see `ViewPlan`'s `code` member). READ. `DeviceState` is not an event
    name produced anywhere in the spec or found in the binary; a same-named internal routine
    elsewhere in the binary is unrelated vendor-cloud telemetry, not a local client-facing event. Mount/goto
    codes 270 and 527 were seen via a shared error-code helper in mount-command handlers but not
    attributed to a specific event name. unresolved (full enumeration and the mount-code
    attribution).
10a. Firmware 9.75: `MotionDetection` and `SkyReplay` both send function-state events (READ: the
    send call is present in each worker), and the cards give the members of their state printers
    (`width`, `height`, `points`; `camera_id`, `recorded_frame_count`, `video_frame_count`). The
    shape of `points` and the states visited are unresolved, and because sky replay is
    force-disabled whether `SkyReplay` appears on a live device is unresolved. `MotionMonitor`,
    `SmartFollow`, `MotionDetection` and `SkyReplay` use the shared function-state envelope (READ).
11. Firmware build and architecture of the observed sessions; complete RTSP and ViewPlan packets;
    reply-relative ordering on the wire. unresolved.
