# Function states: settings reset, motion monitor, smart follow, sky replay

This chapter covers control-channel features added in firmware 9.75 (app 3.4.0) that run as
functions or change many settings at once: the settings-reset transaction, the motion monitor
and motion detection, smart follow, and sky replay. The function-event envelope is in
[events-overview.md](events-overview.md) and [events/families.md](events/families.md); object
tracking, which smart follow builds on, is in [special-modes.md](special-modes.md#object-tracking).
Settings themselves are in [device-state-and-settings.md](device-state-and-settings.md).

App names (iOS app 3.4.0, English; all INFERRED: the strings match but no app call site was read):
“Reset to Default” is the settings reset, “Stacking Playback” is sky replay, “Motion Monitoring”
with “Auto Capture” or “Auto Tracking” is the motion monitor, and the smart-tracking screens (“Auto
Select”, “Manual Select”, “Stop Smart Tracking?”) are smart follow.

Basis for the whole chapter: static analysis of firmware 9.75 (64-bit build; 32-bit build where a
line says so) and app 3.4.0. Nothing here exists in firmware 9.31 unless a line says so.

## Settings reset

R1. Firmware 9.75, app 3.4.0: [`reset_setting`](../../docs/control/methods/reset_setting.md) takes
`{items: [string, ...]}` and sets each named setting back to its default. An item is either an exact
setting name or a group prefix such as `stack`, which selects every `stack.*` key. Item characters
are limited to letters, digits, underscore and dot; empty items, a leading dot, two dots and
duplicates are rejected. An item with the prefix `second_camera.` is relayed to the second camera.
Any member of `params` other than `items` gives 109. READ.

R2. The reply is `result` 0 and, when some items cannot be reset on this build, an
`unsupported_keys` array of strings. An unsupported key is not an error. A `Setting` event
follows a successful reset. A thread-local suppression check exists in the `Setting` notification
path; its trigger and lifetime are unresolved. `Setting.wide_cam` is true when the reporting
camera is the wide camera. READ.

R3. The reset is applied through the same path as [`set_setting`](../../docs/control/methods/set_setting.md)
and is all or nothing: the first failure rolls the whole call back (207 for a failed apply, 300 when
the rollback itself fails). A second reset while one is pending gives 524. Items starting with
`exp_ms.` are refused while Stack is active (259) or a view plan runs (536); that association of
the two codes is INFERRED. Whether items outside `exp_ms.` check busy state is unresolved. READ.

R4. Firmware 9.75: the resettable items differ by build. READ.

| Group | Items (64-bit build, 18) |
|---|---|
| Top level | `auto_af`, `stack_after_goto`, `auto_3ppa_calib`, `auto_master_dark`, `hdr` |
| Preview | `preview.rtsp_quality`, `preview.image_transfer_mode`, `preview.raw_bin2` |
| Stack | `stack.drizzle2x`, `stack.save_discrete_ok_frame`, `stack.save_meteor_frame`, `stack.save_video`, `stack.startrail_mode`, `stack.auto_lenhance`, `stack.scene_separate`, `stack.scene_shooting_duration_min` |
| Exposure | `exp_ms.stack_l`, `exp_ms.stack_l_auto` |

The handler's table has 18 descriptors.

The 32-bit build resets 10 of these. It reports `hdr`, `preview.rtsp_quality`,
`stack.save_meteor_frame`, `stack.save_video`, `stack.startrail_mode`, `stack.scene_separate`,
`stack.scene_shooting_duration_min` and `exp_ms.stack_l_auto` as unsupported. The 32-bit build has no
busy gating in `reset_setting`, so the 259 and 536 replies exist only in the 64-bit build; the
prepare, commit and rollback transaction is present in both. The default value of each item is
unresolved. READ (firmware 9.75).

R4a. Two-phase form. The primary process drives the second-camera process through
[`reset_setting_prepare`](../../docs/control/methods/reset_setting_prepare.md) (`{transaction_id, keys}`),
then [`reset_setting_commit`](../../docs/control/methods/reset_setting_commit.md) or
[`reset_setting_rollback`](../../docs/control/methods/reset_setting_rollback.md)
(`{transaction_id}`). These three accept requests only in the second-camera process and reply 210
elsewhere. The pending transaction has no expiry. A client SHOULD use `reset_setting` and MUST NOT
rely on the three phase methods. `reset_setting_commit` replies `result:0`. READ (firmware 9.75).

## Motion monitor

R5. Firmware 9.75, app 3.4.0, 64-bit build only (the 32-bit build has neither the monitor nor the
detector): [`start_motion_monitor`](../../docs/control/methods/start_motion_monitor.md) watches the
scene for movers and then tracks them or captures, with optional return of the mount to its start
position. It requires scenery view mode (otherwise 210) and a running preview stream (otherwise
300). READ.

R6. All parameters are optional and omitted ones keep their saved values: `mode`
(`auto_track` or `auto_capture`), `sensitivity` (`low`, `middle` or `high`), `return_to_origin`
(bool), `waiting_time` (int, seconds) and `duration_min` (-1 for unlimited, otherwise 1 to
35791394). The settings are saved on every start. `waiting_time` is the time to wait for a lost target and is used only when `return_to_origin` is
true; when `return_to_origin` is false the wait is 10 s, 0 skips the wait and a negative value gives
209. `duration_min` is in minutes: the monitor stops after that time, and -1 means unlimited. The
detector area threshold follows from the sensitivity (5, 10 or 20 for the three levels; a pixel
area in the detection image, unit INFERRED) and cannot be set by a client. The worker polls every
200 ms; automatic tracking retries after 2 s and gives up after 3 attempts. Errors: 209 for an out-of-range value, 105/106/104 for a wrong type,
268 when already running, 524 on conflict with smart follow, the mount, AVI recording, motion
detection or object tracking, 254 when the track stop or reading the origin fails. READ.

R7. [`stop_motion_monitor`](../../docs/control/methods/stop_motion_monitor.md) has no error path
and is idempotent. [`set_motion_detection`](../../docs/control/methods/set_motion_detection.md)
`{enable, wide_cam?}` runs the detector alone and is refused with 524 while smart follow runs.
For `wide_cam` the call is routed by process type (210 when the process cannot serve it). READ.

R8. State is reported by the [`MotionMonitor`](../../docs/control/events/MotionMonitor.md) event with
the members `mode`, `stage`, `return_to_origin`, `sensitivity`, `waiting_time`, `duration_min` and
`remaining_sec`. `stage` is `idle`, `detecting`, `starting_track`, `tracking` or `returning`. They ride in the shared
function-state envelope (the common formatter with an attached state printer). The detector's own
state (`width`, `height`, `points`) is carried by the `MotionDetection` event (R11a). READ.

## Smart follow

R9. Firmware 9.75, app 3.4.0: [`start_smart_follow`](../../docs/control/methods/start_smart_follow.md)
takes no parameters. In the 64-bit build the worker loops motion detection and object tracking and
returns to detection when a track fails. In the 32-bit build the worker only waits for a target and
starts the tracker, with no detection step. Errors
(64-bit): 210 when the view mode cannot track, 268 when already running, 300 without a running
stream, 524 when the mount is occupied or motion detection runs, 254 when the track stop fails.
The 32-bit handler has 268, 300, 210 and 524, and no 254, and lacks the motion-detection checks. READ
for the immediates and strings; the semantics of 268, 300, 210 and 524 were not rechecked in the
32-bit build (INFERRED). The 32-bit stage strings are an older set that includes `waiting_target`
and `starting_track` and not `detecting`, `returning` or `tracking`, and its log says "wait for next
target" where the 64-bit build says "resume motion detection"; it also lacks the 64-bit message for
a view mode that cannot smart-follow. READ (string inventory).

R10. [`stop_smart_follow`](../../docs/control/methods/stop_smart_follow.md) and
[`stop_track_object`](../../docs/control/methods/stop_track_object.md) take an optional
`{wide_cam}`. `stop_smart_follow` signals the worker and is idempotent. `stop_track_object`
stops the object tracker and gives 524 while smart follow runs. While smart follow runs,
[`start_track_object`](../../docs/control/methods/start_track_object.md) hands its rectangle to the
smart-follow worker instead of starting a separate tracker; that the purpose is to choose the
target is INFERRED. READ.

R11. State is reported by the [`SmartFollow`](../../docs/control/events/SmartFollow.md) event with
`stage` and `track_result`, both strings in firmware 9.75 (64-bit build). READ. The envelope is the
shared function-state envelope (the common formatter with the state printer attached), as for
`MotionMonitor`. `stage` is derived from an internal integer: 1 `detecting`, 2 `starting_track`,
3 `tracking`, anything else `idle`. `track_result` likewise: 1 `running`, 2 `stopped`, 3 `lost`,
4 `init_failed`, 5 `image_failed`, 6 `mount_failed`; 0 or any other value is `idle`.

R11b. Transitions in the worker. It sets stage `detecting` after it starts motion detection. When
a target appears it sets `starting_track` and starts the object tracker, then sets `track_result`
`running` and stage `tracking`. When the tracker ends, its result is copied into `track_result`
and the worker returns to detection. The tracker's results are: 4 when the image-centre query fails,
5 when an image cannot be fetched, 6 when a mount command fails, 3 when the target is lost (also on
a tracking timeout) and 2 on a stop request or when the target stays static for over 5 minutes.
If the tracker cannot be started at all, 4 is stored in `track_result` before detection resumes.
Start errors of the smart-follow start path are 268, 300, 524, 209 and 254. When `start_track_object`'s
call into the smart-follow worker (a resume call if already running, else a start call)
fails, the RPC reply's error code is not a literal chosen by `start_track_object` itself: the handler
reads the shared thread-local error-code variable ([events overview: Open questions](events-overview.md#open-questions))
and relays whatever is already in it. READ (64-bit imager). This is the same generic mechanism
documented there for `Exposure`, `Stack` and `ViewPlan` codes, reused across unrelated worker
threads; which value the worker's start or resume call leaves there on its own
internal failure paths was not independently traced. unresolved. A receiver MUST NOT depend on
seeing every transition.

R11a. `MotionDetection` is a registered function-state name in firmware 9.75 and its worker
sends function-state events while the detector runs, alone or under the monitor or smart follow
(64-bit build only). READ. The [`MotionDetection`](../../docs/control/events/MotionDetection.md)
state printer reports `width`, `height` and `points`. The element shape of `points` is
unresolved. The detector start requires its first argument (the area threshold) to be at most
1,000,000 (209 otherwise); other start errors are 268, 524 and 300.

## Sky replay

R12. Firmware 9.75, app 3.4.0: `sky_replay` in
[`set_setting`](../../docs/control/methods/set_setting.md) and
[`get_setting`](../../docs/control/methods/get_setting.md) was meant to switch on a time-lapse style
video of the stacking session, but the feature is force-disabled in this firmware. READ (also in
the 32-bit build, whose getter and setter are identical). `get_setting` always reports false and
clears the stored flag; `set_setting` accepts a boolean or integer (106 otherwise) and ignores the
value; it also clears the flag and ends any current replay session. A `Setting` event follows only
if the stored flag had been true. A client SHOULD NOT offer the feature on firmware 9.75.

R13. The worker (registered function name `SkyReplay`, states `idle` and `recording`) records
frames while stacking and encodes a `*_stack_replay.mp4` in the target's works folder, with a JPEG
thumbnail. It sends function-state events (READ) through the
[`SkyReplay`](../../docs/control/events/SkyReplay.md) event, whose state printer reports
`camera_id`, `recorded_frame_count` and `video_frame_count`. A session records at most 600
frames. At least 20 recorded frames are needed, and a free-space floor of 200 MB applies:
alert 551 (disk full) is raised when the session starts below that floor, and 552 (video too short
to save) when too few frames were recorded. See [errors.md](errors.md). Because the feature is
force-disabled, whether any of this runs on a real device is unresolved. READ for the limits.

## Open questions

- The trigger and lifetime of the thread-local suppression of the `Setting` event after a reset.
- Default values of the resettable items.
- The specific value the smart-follow worker's start or resume call leaves in the shared
  thread-local error-code variable on its own internal failure paths, which is what a failed
  smart-follow hand-over in `start_track_object` reports ([R11b](#smart-follow)).
- The element shape of `MotionDetection` `points` and the exact set of states visited by the
  function-state events of the monitor, detector and smart follow.
- The 32-bit smart-follow worker uses an older design (see the
  [parity matrix](secure-communication.md#firmware-975-parity-matrix-32-bit-imager-and-guider)); its stage strings and the `starting_track`
  and result semantics were not traced.
