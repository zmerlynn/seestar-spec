# Plans

Part of [legacy-plans-and-sequences](../legacy-plans-and-sequences.md). Requirement numbers continue across the chapter; basis and conventions are in the index.

## Two plan systems

The device has two unrelated plan mechanisms.

| Aspect | Legacy plan (this chapter) | ViewPlan ([plan-scheduling.md](../plan-scheduling.md)) |
|---|---|---|
| Write | [`set_plan`](../../../docs/control/methods/set_plan.md), [`import_plan`](../../../docs/control/methods/import_plan.md) | [`set_view_plan`](../../../docs/control/methods/set_view_plan.md) |
| List / read | [`list_plan`](../../../docs/control/methods/list_plan.md), [`get_plan`](../../../docs/control/methods/get_plan.md), [`get_enabled_plan`](../../../docs/control/methods/get_enabled_plan.md) | no getter RPC; events and app-state getters only |
| How many | a map of plans keyed by integer id | exactly one held plan |
| Shape | plan > targets > sequences (frame recipes) | ordered target list with start/duration minutes |
| Timing | start/end time types (`none`, `date`, `dawn`) | minute offsets from a day origin |
| Events | `Target` (start/complete) and `Sequence` with `progress`, `TargetChange`, delay events; no `Plan` event | [`ViewPlan`](../../../docs/control/events/ViewPlan.md), `Target` (function states) |
| Start | `set_page` `plan`, then `start_exposure` (R21a) | `set_view_plan` |
| Stop | `stop_exposure` (R1a) | `stop_func` name `ViewPlan`, `clear_view_plan` |

R1. The two stores are separate. A client MUST NOT use `list_plan` or `get_plan` to find out
whether a ViewPlan is held or running, and MUST NOT expect `set_plan` to affect the ViewPlan.
READ.

R1a. A running legacy plan is stopped with `stop_exposure`. The plan runs inside the exposure
worker, and `stop_exposure` stops that worker. READ. `stop_func` with `ViewPlan` and
`clear_view_plan` do not affect a legacy plan run. READ. Any action that stops exposure also ends
the plan run, for example closing the camera or starting a view. READ.

R2. There is no `get_view_plan` RPC. A function named like it exists inside the firmware but is
not registered in either dispatcher table. READ.

R3. The app 3.3.2 has no emitter for `set_plan` or `import_plan`. The legacy plan API is
therefore reachable only by third-party clients. READ (bounded negative search of the app).

R3a. The app 3.3.2 has no emitter for any other legacy plan or sequence method either:
`get_plan`, `list_plan`, `get_enabled_plan`, `reset_plan`, `clear_plan`, `delete_plan`, the
`set_sequence`/`get_sequence`/`delete_sequence`/`clear_sequence`/`reset_sequence_progress`
family, `set_sequence_setting`, `get_sequence_setting`, `get_target_sequences`,
`clear_autosave_err`, `set_page`, `start_exposure` or `stop_exposure`. Their names exist only as
unused constants. The app therefore has no legacy plan writer, sets no `target_coord` units, no
`start_time`/`end_time` hour or new-plan defaults, and never starts or stops a legacy plan run. The
open points of [Legacy plan data model](#legacy-plan-data-model) cannot be settled from the app. READ (app 3.3.2, bounded negative search).

## Legacy plan data model

Basis: plan parser and plan formatter of firmware 9.31.

### Plan object

| Member | Type | Default on create | Notes |
|---|---|---|---|
| `id` | integer | required | Missing gives 200. READ |
| `plan_name` | string | empty | READ |
| `start_guide`, `merid_flip`, `mount_go_home`, `close_cooler`, `wait_cooling` | bool or integer | true | Nonzero integer is true. READ |
| `shutdown_pi`, `focuser_go_home`, `enable` | bool or integer | false | READ |
| `start_time` | object `{type, hour}` | type `none` | `type` `"date"` selects a timed start; any other string selects none. READ |
| `end_time` | object `{type, hour}` | type `none` | `"date"` timed end, `"dawn"` end at dawn, other none. READ |
| `targets` | array of target objects | empty | READ |

### Target object

| Member | Type | Default | Notes |
|---|---|---|---|
| `id` | integer | required | Missing gives 200. READ |
| `target_name` | string | empty | Passed through the filename regularizer ([Name regularization](#name-regularization)). READ |
| `target_original_img`, `target_original_name`, `real_start_date`, `real_end_date`, `obj_type` | string | empty | Stored and echoed unchanged. READ. The device itself writes `real_start_date` and `real_end_date` as device local time `YYYY-MM-DD HH:MM:SS`. READ |
| `capture_index`, `delay_first`, `delay_between_frame`, `extra_sec_per_target`, `code` | integer | 0 | Delay units are seconds: the runner sleeps for the value in seconds. READ |
| `group_by_slot`, `enable` | bool or integer | true | READ |
| `target_coord` | `[ra, dec]` or `{ra, dec}` | sentinel -999 | Malformed gives 108. READ. RA in hours, Dec in degrees: the device multiplies RA by 15 before an equatorial-to-horizontal conversion in degrees (READ), so the units are INFERRED. The runner uses it to skip targets below the horizon. READ |
| `seqs` | array of sequence objects | empty | READ |

### Sequence object

The same 12 members are used for plan sequences and for the stand-alone sequence list
([The stand-alone sequence list](sequences.md#the-stand-alone-sequence-list)).

| Member | Type | Default | Notes |
|---|---|---|---|
| `id` | integer | required | READ |
| `type` | string | `light` | Frame type: `light`, `dark`, `bias`, `flat`; unknown strings map to `unknown`. READ |
| `filter` | integer | 0 | Filter-wheel slot index. Before every frame of the entry, when a wheel is fitted and the value is 0 or more and below the slot count, the run moves the wheel there if it is elsewhere, waits for the move to finish, and does not restore it; a value out of range leaves the wheel alone. A slot named `dark` makes the entry a non-light frame ([focus-and-filter R22c](../focus-and-filter.md#factory-names-the-dark-slot-and-automatic-moves), R20a). READ |
| `suffix` | string | empty | Stored and returned only. Neither capture run's frame routine reads it, and it is not part of the saved file name (R20b), whatever its name suggests. READ (both builds). A client should treat it as stored metadata only |
| `exp` | number | 0 | Exposure in seconds. READ |
| `gain` | integer | -1 | Set before every frame when 0 or more; a failure is only logged. A negative value keeps the camera's current gain. READ |
| `bin`, `repeat`, `capture_index` | integer | 0 | `repeat` is the planned frame count: a run shoots an enabled entry only while its `lapsed` is less than `repeat`, one frame per pass, and stops it once `repeat` passes are reached. READ (both builds) |
| `lapsed` | integer | 0 | Frames already taken: a run resumes the entry from `lapsed` and adds 1 after each successfully saved frame. READ (both builds). Not accepted by `set_sequence`. In the stand-alone list it is saved but not loaded back, so it is 0 after a restart (R16). READ |
| `enable` | JSON boolean only | true | An integer here is ignored. READ |
| `autoexp` | JSON boolean only | false | READ |

In the plan parser `type` and `suffix` are read without a tag check. READ. A client SHOULD send
them as strings.

### Name regularization

`target_name` and `group_name` pass through one regularizer. It removes `/` and the characters
`:*?"<>|`, and trims leading and trailing spaces. READ. A client SHOULD read the name back
rather than assume it was stored verbatim.

R4. Plan, target and sequence ids are the keys. A write with an existing id first copies the
stored record and then applies the given members, so omitted members keep their stored values.
READ. A client that wants defaults MUST send every member explicitly.

R5. `start_time.hour` and `end_time.hour` are real numbers of hours in the device's local time of
day; fractions are allowed. READ. For `date` the device reduces the value modulo 24 and stores the
reduced value, and a time already past today means tomorrow. READ. For `dawn` the hour is ignored
and local sunrise is used. READ. A new plan defaults to type `none`. READ. A client that sends
`date` MUST also send `hour`: a new plan's hour is never initialized, so an absent or non-numeric
hour stores an indeterminate value, which can be an earlier plan's hour from the same request.
READ.

## Writing and editing legacy plans

### `set_plan` and `import_plan`

Both take `params` as an array of plan objects ([Plan object](#plan-object)). The array root is not type-checked.
READ. `import_plan` is `set_plan` without the free-space check. READ.

R6. A client MUST send `params` as a JSON array. A missing `params` is read without a check.
The dispatcher passes a missing `params` to the handler as null (absent, not a JSON `null`
value). READ (64-bit build; 32-bit not checked). The imager process therefore crashes on a fatal
signal and sends no reply. INFERRED; the unchecked read and the crash handler are READ.

R7. Errors (READ; the order of checks is not specified):

| Code | Condition |
|---|---|
| 268 | The plan loader is still running (boot load). |
| 200 | A plan, target or sequence lacks `id`. |
| 108 | `target_coord` is malformed. |
| 224 | The edit would change a restricted field of an enabled plan that is being exposed on the plan page. |
| 208 | `set_plan` only: free space is below the estimated size of the first enabled plan plus 150 MiB. |

R8. The store is saved to disk after a successful write. The save result is not checked, so code
0 does not prove persistence. READ.

### Selectors

[`get_plan`](../../../docs/control/methods/get_plan.md), [`delete_plan`](../../../docs/control/methods/delete_plan.md)
and [`reset_plan`](../../../docs/control/methods/reset_plan.md) take one selector object
`{plan_id, target_id, seq_id}`; `[selector]` is also accepted. Each member is an optional integer.
[`clear_plan`](../../../docs/control/methods/clear_plan.md) takes an array of selectors only. READ.

```abnf
selector     = "{" [ plan-part ] "}"          ; JSON object, members in any order
plan-part    = %s"plan_id" ":" int [ "," target-part ]
target-part  = %s"target_id" ":" int [ "," %s"seq_id" ":" int ]
```

The grammar shows the nesting rule only: `target_id` needs `plan_id`, and `seq_id` needs
`target_id`. Breaking the rule gives 209. A non-object selector gives 107. READ.

R9. Selector semantics (READ):

| Method | No member | `plan_id` | `+ target_id` | `+ seq_id` | Not found |
|---|---|---|---|---|---|
| `get_plan` | all plans | that plan | that target | that sequence | 204 |
| `delete_plan` | deletes all plans | deletes the plan | deletes the target | deletes the sequence | 204 |
| `reset_plan` | resets all progress | that plan | that target | that sequence | 200 |
| `clear_plan` | 204 (not "clear all") | empties `targets` | empties `seqs` | checked, selects nothing | 204 |

R10. `delete_plan` returns 224 while the plan worker runs in exposure mode 2. `reset_plan` and
`clear_plan` also return 224 when the edit is not allowed. READ. A `clear_plan` parse failure is
reported as 207, not 107. READ.

R11. `clear_plan` processes its selectors one by one and is not transactional. A later failure
does not undo earlier clears. READ. A client SHOULD send one selector per request when it needs
a clear error mapping.

R12. [`clear_autosave_err`](../../../docs/control/methods/clear_autosave_err.md) with no params, or
with non-object params, clears the capture error. With `{plan_last: true}` it clears the current
target's last error instead. `plan_last` other than true gives 106. READ.

