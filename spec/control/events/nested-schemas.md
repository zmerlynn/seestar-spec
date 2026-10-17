# Events: nested schemas and delta companions

Part of the [events chapter](../events-overview.md). This file defines nested objects shared by
several events or by events and getters: the Wi-Fi station object, the polar-alignment stage
table, legacy plan progress, the ViewPlan plan object, and the [`Setting`](../../../docs/control/events/Setting.md) event's member inventory.
Families and presence rules are in [families.md](families.md); plan semantics are in
[plan scheduling](../plan-scheduling.md).

Basis: static analysis of firmware 9.31 (D64; D32 differences in
[variants-and-consumers.md](variants-and-consumers.md)). Labels as in
[CONVENTIONS.md](../../../CONVENTIONS.md).

## Station object

Used by the [`Station`](../../../docs/control/events/Station.md) event (under `station`, on success) and by the station-state and
device-state getters, which share the formatter. READ.

| Member | Type | Presence / meaning |
|---|---|---|
| `server` | boolean | always |
| `freq` | integer | only when `server` is true; MHz INFERRED |
| `ip` | string | only when `server` is true |
| `ssid` | string | only when `server` is true |
| `gateway` | string | only when `server` is true |
| `netmask` | string | only when `server` is true |
| `sig_lev` | integer | only when `server` is true; received signal level as reported by the wireless driver, unscaled (READ); normally negative dBm (INFERRED) |
| `key_mgmt` | string | only when `server` is true |

R52. The formatter writes no password member. READ.

## Polar-align stages (3PPA custom formatter)

The `3PPA` custom status packet uses this table instead of the F enum. D64 and D32 tables are
identical. READ.

| `state_code` | `state` | `state_code` | `state` | `state_code` | `state` |
|---|---|---|---|---|---|
| 0 | `idle` | 6 | `delay1` | 12 | `exp3` |
| 1 | `start` | 7 | `exp2` | 13 | `solve3` |
| 2 | `exp1` | 8 | `solve2` | 14 | `calc3` |
| 3 | `solve1` | 9 | `calc2` | 15 | `exp4` |
| 4 | `calc1` | 10 | `move2` | 16 | `solve4` |
| 5 | `move1` | 11 | `delay2` | 17 | `calc4` |

R53. Members, READ:

- Always: `state`, `state_code`, `auto_move`, `auto_update`, `paused` (true when the
  polar-alignment worker is not running).
- Only while the status is active: `detail` object, `lapse_ms`, `retry_cnt`; and `pa_error`
  when both offset components are valid (each differs from the sentinel -999 by more than 0.1).
- `detail` by stage: solve stages (3, 8, 13, 16) carry `lapse_ms` and a non-negative
  `star_number`; exposure stages (2, 7, 12, 15) carry elapsed and total milliseconds; wait
  stages (6, 11) use a total of 4000 ms. Other stages can give an empty `detail`.
- No `detail.operation` or `detail.stage` member is written.

R54. An unrecognized code uses the shared unknown-name fallback. READ. The F-family `3PPA` and
[`EqModePA`](../../../docs/control/events/EqModePA.md) events are different packets with their own members (see their cards). READ.

## Legacy plan progress

No firmware event is named `Plan`. READ. The plan-progress helper attaches `progress` to legacy
[`Target`](../../../docs/control/events/Target.md) events (`state` `start` or `complete`) and
legacy [`Sequence`](../../../docs/control/events/Sequence.md) events (`state` `frame_start` or
`frame_complete`). Those events carry `state` and `progress` only. READ. `get_app_state` returns
the same object. READ unless marked.

| Path | Type | Meaning |
|---|---|---|
| `progress.targets.total` / `.lapse` | integer | planned targets / completed targets |
| `progress.cur_plan.total` / `.lapse` | integer | current plan total / completed |
| `progress.cur_target.total` / `.lapse` | integer | target total / completed |
| `progress.cur_target.target_name` | string | current target |
| `progress.cur_target.id` | integer | target id |
| `progress.cur_seq.total` / `.lapse` | integer | sequence total / completed frames |
| `progress.cur_seq.frame_type` | string | frame type name |
| `progress.cur_seq.id` | integer | sequence id |
| `progress.plan_end` | boolean | end flag |

R55. "Completed" meanings follow the counter names (INFERRED). These are counts, not durations.
Every member is always written. READ. When no current target or sequence exists, the object is
still complete, with these defaults (READ):

| Member | Default |
|---|---|
| `cur_target.id`, `cur_seq.id` | -2147483648 (INT32 minimum) |
| every `total` and `lapse` | 0 |
| `cur_target.target_name` | `""` |
| `cur_seq.frame_type` | `unknown` |
| `plan_end` | false |

Clients SHOULD treat -2147483648 as "none". `frame_type` is `light`, `dark`, `bias` or `flat`
for codes 0 to 3, and `unknown` otherwise. READ.

## ViewPlan.plan and cached target objects

R56. The [`ViewPlan`](../../../docs/control/events/ViewPlan.md) event's `plan` object has `plan_name` (string), `plan_target_af` (boolean),
`viewplan_gohome` (boolean), `list` (array of objects), and `update_time_seestar` (string) when
non-empty. READ. Producing a terminal-state event also persists the plan (see
[plan scheduling](../plan-scheduling.md) R33); the shape matches the getter, the side effects do
not. READ.

R57. Each `plan.list[]` item is the target's cached state JSON followed by `start_min` (integer,
minutes), `duration_min` (integer, minutes), `skip` (boolean); `alias_name` (string) if
non-empty; `camera_mode` (string) if set. For wide/dual targets also
`second_camera.stack.capt_type` (string), `second_camera.stack.wide_size_index` (integer) and
`mount.tracking` (boolean). `mosaic` only for a valid scale, with `scale` (number), `angle` and
`star_map_angle` (numbers; degrees, READ in the app, see
[grid-and-movement.md R20a](../mosaic/grid-and-movement.md)). READ.

R58. Cached target state can include `state`, `stage`, `lapse_ms`, `code`, `error`, `target_id`,
`wide_state`, `wide_code`, `wide_error` and output objects. READ. The list is not exhaustive; a
client MUST treat these objects as open.

R59. The standalone [`Target`](../../../docs/control/events/Target.md) event does not repeat the scheduling fields of `plan.list[]`. With no
current target it adds no target members. Main (tele/dual) and wide (wide/dual) outputs are
independent, conditionally present objects with separate counters. READ.

## Setting: producers

The `Setting` event reports changed settings. It is built two ways. Neither transmits a list of
changed keys (`keys`, `changed`, `fields` do not exist). READ.

R60. **Filtered getter.** A generic change notifier calls the settings getter with a filter of the
changed key, appends the camera origin `wide_cam` (boolean) and broadcasts. There is no debounce
interval. READ. The filtered getter always appends several `stack` members ([Setting: getter inventory](#setting-getter-inventory)), so even a
single-key change produces a `Setting` with a `stack` object. READ.

R61. **Direct producers** write changed members themselves, not through the getter. They can
therefore emit members that the getter writes only in full mode. READ:

| Producer | Members |
|---|---|
| stack-setting setter | `stack.save_discrete_frame`, `stack.light_duration_min` (minutes), `user_stack_sim`, `stack_after_goto`, `auto_3ppa_calib`, `auto_master_dark`, `stack.wide_size_index`, `stack.scene_separate`, `stack.scene_shooting_duration_min` (minutes), `stack.auto_lenhance`, `stack.airplane_line_removal`, `stack.goto`, `stack.move_sleep_sec` (seconds), `stack.save_video`, `stack.save_meteor_frame`, `stack.save_discrete_ok_frame`, `stack.capt_num`, `stack.capt_type` (string), `exp_ms.stack_l` (ms), `exp_ms.stack_l_auto`, `expert_mode`, `wide_cam` |
| image-adjust setter | `stack.brightness`, `stack.contrast`, `stack.saturation` (numbers), `stack.dbe_enable`, `wide_cam` |
| stack-time check | `exp_ms.stack_l` (integer), `wide_cam` |
| remote-change notifier | `remote_joined` (boolean) |
| camera selection in `set_setting` | `selected_cam` (string) |

Unlisted members are booleans or integers as in [Setting: getter inventory](#setting-getter-inventory). D32 lacks
`stack.scene_shooting_duration_min` in this setter (READ).

R62. Direct setters compare values or normalize before notifying, so an unchanged write may send
nothing. Conditions vary by setter. READ.

R63. A client MUST merge `Setting` members into its retained settings, recursively for nested
objects (`stack`, `exp_ms`, `preview`, ...), and MUST NOT treat absent members as reset.
INFERRED.

## Setting: getter inventory

Presence conditions for the getter used by `get_setting` (full) and by `Setting` (filtered).
"Full" means the unfiltered getter; "P2" means running in the auxiliary imager process; "W" means
the current camera is the wide camera. These are device-internal conditions. Full-only members
appear in an event only through a direct producer (R61). READ unless marked. Booleans are JSON
booleans; pairs are two-element integer arrays.

### Full output, main process only

| Member | Type | Presence / meaning |
|---|---|---|
| `calib_location` | integer | always. Location-calibration source: 1 = ordinary location-offset calibration, 2 = offset derived from three-point polar alignment (READ); other values mean no calibration offset is applied (INFERRED). It is a persisted test setting (config key `setting2/imager/test/calibrate_location`, written by the test-setting serializer) that the location-offset routines only read as a mode gate; `set_setting` and `set_test_setting` do not assign it and no runtime routine that sets the in-memory field to 1 or 2 was located, so how it comes to be set remains unresolved (READ) |
| `effect_offset_deg` | number[2] | when the ordinary pair is available; **written a second time** with the 3PPA pair when that is available; the two can differ |
| `offset_deg` | number[2] | both components valid (not the -999 sentinel) |
| `offset_deg_3ppa` | number[2] | both components valid, independent of current calibration mode |
| `center_xy` | integer[2] | when the autofocus centre is available; display pixels INFERRED |
| `temp_unit` | string | `C` or `F` |
| `beep_volume` | string | written twice in full output |
| `lang` | string | language name |
| `stack_lenhance` | boolean | filter wheel at position 2 |
| `heater_enable` | boolean | only if the heater GPIO read succeeds |
| `expt_heater_enable`, `auto_power_off`, `auto_af`, `frame_calib`, `wide_4k`, `main_8k`, `guest_mode`, `user_stack_sim`, `auto_master_dark`, `usb_en_eth`, `dark_mode`, `plan_target_af`, `viewplan_gohome`, `stack_after_goto` | boolean | always |
| `wide_cam` | boolean | only if camera info is available |
| `light_brightness` | integer | always (also filtered, 6.2) |
| `remote_joined`, `auto_3ppa_calib`, `expert_mode` | boolean | full only (`expert_mode` still emitted in firmware 9.75) |
| `wifi_country` | string | full only, if the country read succeeds |

R64. The four calibration members (`calib_location`, `effect_offset_deg`, `offset_deg`,
`offset_deg_3ppa`) never appear in a filtered `Setting`. Degree units are INFERRED. The -999 test
is a validity sentinel, not a geographic bound. A client MUST tolerate the duplicate
`effect_offset_deg` member and MUST NOT assume the two pairs are equal. READ.

### Main process, full or filtered on that exact key

| Member | Type | Additional condition |
|---|---|---|
| `rec_res_index` | integer | gated by a can-set-recording-resolution helper that is a stub returning false on both the 64-bit and 32-bit builds, so the member never appears in firmware 9.31; the value, when emitted, is a raw index from the stored RTMP setting with no firmware-side enum (READ) |
| `ap_changed` | boolean | model has NFC |
| `light_brightness` | integer | filtered: exact key selected |
| `typec_mode` | string | read succeeds; the setter accepts `file` and `net` |
| `alpaca_enable` | boolean | Alpaca status query returns running (true) or stopped (false); other results omit it |
| `password` | string | always when selected; not redacted |
| `connect_lock` | boolean | always when selected |

R65. The settings getter and filtered `Setting` events can carry the device's `password` setting
in clear text. READ. A client SHOULD NOT log `Setting` payloads verbatim. Firmware 9.75: the
getter omits `password` when `get_setting` is sent with `include_sensitive:false`; the value is still
not `enc1:` encoded.

R65a. Firmware 9.75 changes the getter inventory. `expert_mode` is still emitted (boolean, full
path only); only `set_setting` dropped the key. The full output gains these members (64-bit build;
types and conditions READ):

| Member | Type and nesting | Condition |
|---|---|---|
| `annotation` | object: `stargazing_deepsky`, `stargazing_supernovae`, `milkyway_lines`, `milkyway_background` (booleans) | main process; full path or exact key |
| `sky_replay` | boolean, always false | main process |
| `can_encrypt` | boolean, constant true | main process; full path or exact key |
| `comet_max_frame_num` | integer, constant 200 | main process; full path only |
| `enable_dark_library` | boolean | main process; full path only |
| `motion_monitor` | object: `mode`, `return_to_origin`, `sensitivity`, `waiting_time` (seconds), `duration_min` (minutes, -1 unlimited) | either process; full path or exact key |
| `preview.raw_bin2` | boolean, after `image_transfer_mode` | whenever `preview` is emitted |
| `exp_ms.more_exposure` | boolean, between `stack_l` and `continuous` | full path only |
| `stack.startrails_duration_min`, `stack.startrail_mode` | integers (minutes, -1 or 0 no limit; mode 0 to 2) | full path only; wide camera only; see [stacking.md R8b to R8f](../stacking.md#sky-replay-and-star-trail-decay-firmware-975) |

The earlier flat top-level names for `milkyway_*`, `stargazing_*`, `more_exposure`, `raw_bin2`,
`startrail_mode` and `startrails_duration_min` were wrong. See
[device state and settings](../device-state-and-settings.md) R8b. The password rule of R64 is
unchanged.

### Either process

| Member / path | Type | Presence / units |
|---|---|---|
| `preview` | object | full, or `preview` selected |
| `preview.rtsp_quality` | string | `Smooth`, `HighQuality`, `unknown` |
| `preview.image_transfer_mode` | string | `Jpg`, `Raw`, `unknown` |
| `preview.rtsp_width`, `preview.rtsp_height` | integer | if size computed; smaller dimension in width; pixels INFERRED |
| `timelapse` | object | full, or `timelapse` selected |
| `timelapse.solar_sys`, `timelapse.scenery` | object | each `{delay_sec: number (interval between frames in seconds, fractions allowed, must be > 0; READ; default 1.0), src_dura_min: integer (minutes, unscaled; READ; default -1)}` |
| `timelapse.starry_sky` | object | W only; `{src_dura_min: integer (minutes, unscaled; READ)}` |
| `wide_cross_offset`, `wide_cross_offset_show` | integer[2] | W only; full or exact key; pixels INFERRED |
| `mosaic` | object | full or selected: `scale`, `angle`, `estimated_hours`, `star_map_angle`, `star_map_ratio` (numbers). `scale`: unitless multiplier of the camera frame size (canvas = frame × scale), default 1, no range check; READ. `angle`: planner rotation, stored truncated to an integer and reported as that integer, default 0, no range check; READ; degrees INFERRED (passed unconverted to the imported rotation routine). `star_map_angle`: degrees, 361 = no value (the initial value); READ. `star_map_ratio`: unitless copy of `scale` taken when the live canvas was last initialized, default 1; READ. `estimated_hours`: hours, computed as list length × `exp_ms.stack_l` / 1000 / 3600 × 1.5; formula and source setting READ, millisecond source unit (hence hours) INFERRED from the `exp_ms` name. See [mosaic](../mosaic.md). The 32-bit build emits this same object in the same field order with no scaling difference (READ) |
| `stack` | object | always present (unconditional members below) |
| `stack.dbe`, `stack.star_correction`, `stack.airplane_line_removal`, `stack.drizzle2x`, `stack.wide_denoise` | boolean | full, or that exact key selected (`dbe` key, not `stack`) |
| `stack.cont_capt` | boolean | full only, capture type 1 |
| `stack.capt_type` | string | full only |
| `stack.goto`, `stack.save_discrete_frame`, `stack.save_discrete_ok_frame`, `stack.save_meteor_frame`, `stack.auto_lenhance` | boolean | full only |
| `stack.move_sleep_sec`, `stack.capt_num` | integer | full only |
| `stack.save_video`, `stack.scene_separate` | boolean | full only and W |
| `stack.wide_size_index`, `stack.scene_shooting_duration_min` | integer | full only and W |
| `stack.light_duration_min` | integer | **unconditional**, also filtered; minutes INFERRED |
| `stack.brightness`, `stack.contrast`, `stack.saturation` | number | unconditional |
| `stack.dbe_enable` | boolean | unconditional |
| `rtsp_roi_index` | integer | **filtered only**, selected and compatible scale (about 1/2/4 maps to 0/1/2) |
| `rtsp_roi_scale` | number | full or exact key |
| `hdr` | boolean | full or exact key |
| `ae_bri_percent` | number | full or exact key; 0..100; written twice in full output |
| `manual_exp` | boolean | full only |
| `isp_range_gain`, `isp_range_exp_us` | integer[2] | full only, if the range query succeeds; `[min,max]` |
| `isp_range_exp_us_scenery` | integer[2] | full only, always written; upper bound forced to 1000000; lower bound may be stale if the range query failed |
| `focal_pos`, `factory_focal_pos` | integer | full only |
| `stack_dither` | object | full only: `pix` integer, `interval` integer, `enable` boolean |
| `exp_ms` | object | full only: `stack_l`, `continuous` integers (ms INFERRED) |
| `exp_ms.stack_l_auto` | boolean | full only and W |
| `second_camera` | object | full only, main process, when the peer read succeeds; same full shape for the peer |

R66. Internal read failures omit the member; they do not produce error envelopes. READ.
