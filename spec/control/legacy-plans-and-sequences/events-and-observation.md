# Events and observation

Part of [legacy-plans-and-sequences](../legacy-plans-and-sequences.md). Requirement numbers continue across the chapter; basis and conventions are in the index.

## Legacy plan reply format

`get_plan` and `get_enabled_plan` return an array of plan objects with every member of section
3.1, nested targets with every member of [Target object](plans.md#target-object), and nested sequences with [Sequence object](plans.md#sequence-object).
READ. Additions:

| Level | Member | Condition |
|---|---|---|
| plan | `left_size_m`, `left_time_sec`, `total_time_sec` | Enabled plan, estimate flag set. READ |
| plan | `cur_id` | A current target is set. READ |
| target | `left_time_sec`, `total_time_sec`, `left_size_m` | Always. READ |
| target | `error` string | Estimate flag set. READ |
| target | `cur_id` | A current sequence is set. READ |
| target | `target_coord` | Not the -999 sentinel. READ |

Time objects serialize as `{"type":"none"}`, `{"type":"date","hour":n}` or (end only)
`{"type":"dawn"}`. A stored type the formatter does not know serializes as `{}`. READ.

R21. `list_plan` returns `[{id, plan_name, enable, target_cnt}]` and is the only pure plan
getter. READ. `get_enabled_plan` filters disabled **plans**, not disabled targets. "Enabled" does
not mean "running". READ. All three getters return 268 while the plan loader runs. READ.

## Legacy plan events

All events carry `Event` and `Timestamp`
([events/envelope.md](../events/envelope.md)). Family letters are defined in
[events/families.md](../events/families.md).

| Event | Members | States | Trigger |
|---|---|---|---|
| [`Target`](../../../docs/control/events/Target.md) | `state`, `progress` (legacy branch) | `start`, `complete` | legacy plan target transition. READ |
| [`TargetChange`](../../../docs/control/events/TargetChange.md) | none | none | current target changed. READ |
| [`Sequence`](../../../docs/control/events/Sequence.md) | `state`, `id`, `frame`, `total_lapse_frame`, `total_frame` | `start`, `frame_complete`, `complete`, `fail` | sequence-list run; the counters only on `frame_complete` (R22a). READ |
| [`Sequence`](../../../docs/control/events/Sequence.md) (plan run) | `state`, `progress` | `frame_start`, `frame_complete` | frame transition inside a legacy plan run. READ |
| [`FirstDelay`](../../../docs/control/events/FirstDelay.md) | `state`, `seconds` on start | `start`, `complete` | delay before the first frame. READ |
| [`FrameDelay`](../../../docs/control/events/FrameDelay.md) | same | `start`, `complete` | delay between frames. READ |
| [`TargetDelay`](../../../docs/control/events/TargetDelay.md) | same | `start`, `complete` | delay between targets. READ |

No firmware event is named `Plan`. READ. The plan-progress helper sends the event name its
caller passes, and its only callers pass `Target` (`start`, `complete`) and `Sequence`
(`frame_start`, `frame_complete`). Those events carry `state` and `progress` only. READ for the
64-bit build; the 32-bit build has the same helper with four callers, so the same set is
INFERRED.

`progress` holds counters `targets`, `cur_plan`, `cur_target`, `cur_seq` (each
`{total, lapse}` with names and ids) and `plan_end`; see
[events/nested-schemas.md](../events/nested-schemas.md#legacy-plan-progress). The counters are
counts, not milliseconds. READ.

R22. `Sequence`, `FirstDelay`, `FrameDelay` and `TargetDelay` carry `code` and `error` only on
failure with a nonzero code. READ. No per-second countdown event exists; a client that shows a
countdown MUST compute it from `seconds`. READ / INFERRED.

R22a. Events of a sequence-list run (exposure mode 2 off the plan page), in order. READ (both
builds).

1. `Sequence` `start` with `state` only.
2. `FirstDelay` `start` with `seconds`, then `complete`, only when `delay_first` is above 0 and
   no entry has a completed frame yet (a resumed run skips it).
3. For each frame: the legacy `Exposure` events of the exposure (`page`, `start` with `exp_us`
   and `gain`, `downloading`, then `complete`, or `fail` with `error` and `code`; no `tag`); then
   `Sequence` `frame_complete` with `id`, `frame`, `total_lapse_frame` and `total_frame` after a
   successful save, where `frame` is the entry's `lapsed` count after the increment; then, if frames remain,
   `FrameDelay` `start` and `complete`.
4. `Sequence` `complete` with `state` only, or `fail` with `error` and `code`.

`id`, `frame`, `total_lapse_frame` and `total_frame` appear only on `frame_complete`. A
sequence-list run never sends `frame_start`; only a plan run does (with `progress`). READ.
`fail` with `code` 253 means a client stop; the after-run actions ([Sequence settings](sequences.md#sequence-settings)) then do not run.
Any other `fail` code still runs them. READ. Each frame's save also emits
[`SaveImage`](../../../docs/control/events/SaveImage.md) from the save worker: `start`, then
`complete` with `filename` and `fullname`, or the literal `save fail`. The save runs in a worker,
so these can interleave with the `Sequence` and `FrameDelay` events. READ (64-bit build); the
interleaving is INFERRED.

R23. `TargetChange` has no payload. A client SHOULD refresh `get_app_state` on receipt. INFERRED.

R24. The `Target` event name is shared with ViewPlan. A client MUST tell them apart by `state`
values: legacy uses `start`/`complete`; ViewPlan uses function states
(`working`, `complete`, `fail`, `cancel`) and may add `target_id` and `camera_mode`. READ.

R25. The app 3.3.2 has no handler for `TargetChange`, `Sequence` or the delay events.
READ (bounded search). Their live delivery is unresolved.

```text
client                       device
  |  set_plan [plan]           |
  |--------------------------->|
  |  code 0                    |
  |<---------------------------|
  |  set_page plan             |
  |--------------------------->|
  |  start_exposure            |
  |--------------------------->|
  |        Event Target start {progress}
  |<---------------------------|
  |        Event FirstDelay start {seconds}
  |<---------------------------|
  |        Event Sequence frame_start / frame_complete ...
  |<---------------------------|
  |        Event TargetChange  |
  |<---------------------------|
  |        Event Target complete {progress}
  |<---------------------------|
```

The diagram is an INFERRED ordering.

R21a. To run a legacy plan, a client MUST enable exactly the plan to run, send `set_page` with
`plan`, then send `start_exposure`. READ. `set_page` `plan` sets exposure mode 2 and returns 268
while the exposure worker already runs. READ. The runner picks the enabled plan. READ. Mode 2 on
any page other than the plan page runs the sequence list instead of a plan. READ. Stop the run
with `stop_exposure` (R1a).

## Observing plans

No pure getter returns the whole ViewPlan queue. READ. The getters below overlap; several have
side effects.

| Getter | Covers | Grade |
|---|---|---|
| [`list_plan`](../../../docs/control/methods/list_plan.md) | legacy plan summaries | pure. READ |
| [`get_plan`](../../../docs/control/methods/get_plan.md), [`get_enabled_plan`](../../../docs/control/methods/get_enabled_plan.md) | legacy plan detail | mutator (refreshes a camera cache, logs). READ |
| [`get_app_state`](../../../docs/control/methods/get_app_state.md) | legacy plan progress (`progress` as on legacy `Target`/`Sequence`) | mutator: can auto-select a plan in exposure mode 2 on the plan page. READ |
| [`iscope_get_app_state`](../../../docs/control/methods/iscope_get_app_state.md) | whole function tree, including `ViewPlan` and its `plan` object | mutator: can persist the held ViewPlan file. READ |
| [`get_view_state`](../../../docs/control/methods/get_view_state.md) | View subtree only | pure. READ |
| [`get_device_state`](../../../docs/control/methods/get_device_state.md) | device subsystems; optional `{keys:[...]}` | mutator (can open/close the focuser). READ |
| [`get_view_plan_stack_result`](../../../docs/control/methods/get_view_plan_stack_result.md) | wide ViewPlan output | pure. READ |

R26. The ViewPlan state seen through `iscope_get_app_state` has `state`, `lapse_ms` and
`plan {plan_name, update_time_seestar, list}`. The app models exactly this. READ. The `list`
entries follow [events/nested-schemas.md](../events/nested-schemas.md#viewplanplan-and-cached-target-objects).

R27. A client SHOULD prefer events for change detection and use `iscope_get_app_state` after
(re)connect, accepting its side effect. INFERRED.

## ViewPlan wide-camera helpers

These four methods exist only on the 64-bit build and only in the wide (slave) process
(process type 2). Elsewhere they return 210 `not supported`. READ. They tune the secondary camera
for a ViewPlan target; the plan itself is in [plan-scheduling.md](../plan-scheduling.md).

| Method | Purpose |
|---|---|
| [`set_view_plan_wide_setting`](../../../docs/control/methods/set_view_plan_wide_setting.md) | set wide capture type and size, optional scene group |
| [`restore_view_plan_wide_setting`](../../../docs/control/methods/restore_view_plan_wide_setting.md) | restore the snapshot taken on first set |
| [`set_view_plan_target_name`](../../../docs/control/methods/set_view_plan_target_name.md) | set or clear the wide target name |
| [`get_view_plan_stack_result`](../../../docs/control/methods/get_view_plan_stack_result.md) | read wide stack output |

R28. `set_view_plan_wide_setting` requires `capt_type` in {0 stack, 4 startrails, 5 timelapse}
and `wide_size_index` in 0..3. The group `scene_separate`, `scene_shooting_duration_min` (>= 1),
`exp_ms` (>= 1) and `auto_exp_enable` MUST be sent all together or not at all. A missing or
non-integer integer member gives 104, a wrongly typed boolean member gives 106, and a duration
or exposure below 1 gives 204. READ. Other errors: 107 (params not an object), 209 (bad
`capt_type`), 204 (`wide_size_index` out of range), 524 (exposure change while the stack
simulator is on). READ.

R29. On the wide-camera path a changed `exp_ms` is normalized to one of 10000, 20000, 30000,
60000; any other value becomes 10000 (other routes normalize differently). Code 0 does not prove
the value was kept. READ. A client SHOULD send one of the four values.

R30. The first successful set saves a snapshot. `restore_view_plan_wide_setting` applies it; with
no snapshot it succeeds and does nothing. The set also emits a [`Setting`](../../../docs/control/events/Setting.md) event with the changed
fields and clears saved output metadata. READ.

R31. `set_view_plan_target_name` takes `{target_name: string}`. An empty string clears the name.
Other names are regularized ([Name regularization](plans.md#name-regularization)) before use. Errors 107, 105. READ.

R32. `get_view_plan_stack_result` returns `{has_output, image_id, stack_total_sec, error_code}`
plus `saved_fullname` when `has_output` is true. `error_code` 267 means no image. `image_id` is an
unsigned 16-bit value. READ.

## Open questions

- Live delivery of the legacy events; no capture is known.
- Steps of a plan run's frame routine other than the wheel move and the light-frame skips (R20a).

## Appendix: How to validate on a live device (non-normative)

1. Call `list_plan`; note the result. Call `set_plan` with one disabled plan (unused id); confirm
   `list_plan` shows it and that no `ViewPlan` event arrives.
2. Call `get_plan {plan_id}` for that id, then `delete_plan {plan_id}`; confirm 204 on a second
   `get_plan`.
3. Call `get_sequence_number`, then `get_sequence 0..n-1`; confirm `id` differs from index once
   entries were deleted.
4. Listen for `Target`, `Sequence` and delay events during a short legacy run started as in R21a.
