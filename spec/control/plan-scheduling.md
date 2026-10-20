# Plan scheduling (ViewPlan)

Scope: `set_view_plan`, `clear_view_plan`, the [`ViewPlan`](../../docs/control/events/ViewPlan.md) event. Machine-readable detail:
`catalog/control/`; generated cards: `docs/control/`.

App names: a “Plan” (with “Plan Settings”) is a ViewPlan, not a legacy plan. Its target types “Wide
Photo”, “Wide Star Trails”, “Wide Time-lapse” and “Wide Photo Framing” set the second camera's
capture type, and “Dual-camera Capture for Telephoto Target” uses both cameras. “AF on Target
Switch” is `plan_target_af` and “Close Arm on Completion” is `view_plan_go_home`. The app's “Auto
Plan” builds a plan on the phone; no device method generates one. Names are the English strings of
iOS app 3.4.0; links are READ (app call sites) unless marked.

## Conventions

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119 and RFC 8174. They bind
clients, except where a sentence says what "the device" does; those sentences are descriptions.

Every claim carries a short label (see `CONVENTIONS.md`):

- **READ**: seen in firmware 9.31 by static analysis. It says what the code does, not that the
  camera or mount operation then succeeds.
- **OBSERVED**: seen on a real device in a session. No observed session is known to match
  firmware 9.31 exactly (build and architecture were not established), so treat these as hints.
- **INFERRED**: a consequence or interpretation, not seen directly.
- **unresolved**: not established either way.

Firmware 9.31 ships a 64-bit and a 32-bit imager build. READ claims are for the 64-bit build
unless stated; the 32-bit build is "probable". Addresses in the YAML are 64-bit virtual
addresses. No code was executed and no device contacted. Integers are signed 32-bit on the
device; reals have 32-bit float precision.

## Overview

A ViewPlan is an ordered list of targets, each with a start offset and a duration. The device
keeps exactly one plan in memory (the "held plan"). One worker thread walks the list serially,
waits for each start, captures until the end, and moves on.

Typical flow: `set_view_plan` (reply code 0 means the worker was launched), then a
`ViewPlan/working` event, [`Target`](../../docs/control/events/Target.md) events per target, and a terminal `ViewPlan` event
(`complete`, `fail` or `cancel`). `clear_view_plan` stops the worker; on firmware 9.31 it keeps the plan, and on firmware 9.75 it also deletes the stored plan (R32).

R1. The ViewPlan API is distinct from the legacy plan API (`set_plan`, `import_plan`,
`list_plan`). They use different stores and different schemas. READ. An empty `list_plan`
therefore says nothing about the held ViewPlan (READ, INFERRED consequence).

## Starting a plan

`set_view_plan` has two forms, chosen by the presence of `params.plan_name`. READ.

1. **Full plan.** `plan_name` present: `list` is then required. The device replaces its held
   plan, starts the worker, and replies.
2. **Restart.** `plan_name` absent (params omitted, or params without it): the device reruns
   the held plan. A `list` supplied without `plan_name` is ignored. Non-object params behave
   as omitted. OBSERVED: the app sends a bare `{id, method}` for this form, and inline plans
   otherwise.

R2. A client SHOULD omit `params` for a restart, and MUST include `plan_name` whenever it
sends a `list` it wants used.

R3. A restart keeps names, schedule fields and skip flags, but resets per-target outputs and
progress. It does not reload from storage, resume an unfinished run, or compare plan names or
edit dates. READ.

R4. The reply is sent once the worker thread is launched. Success means "started", never
"completed". READ. Reply envelope: success has `result` 0 and `code` 0; failure has a flat
`error` string and nonzero `code`, with no `result`. The `error` is a string, not an object.
Receivers MUST NOT require the `jsonrpc` or `Timestamp` members: the handler does not emit
them, though the socket layer was OBSERVED adding both. READ / OBSERVED.

### Validation

Required per target: `start_min`, `duration_min`, `target_id` (all integers; a JSON real such
as `1.0` does not qualify) and `camera_mode`. READ.

R5. `camera_mode` is a case-sensitive lowercase string: `tele`, `wide` or `dual`. For `wide`
and `dual` the target MUST also carry `second_camera.stack.capt_type`,
`second_camera.stack.wide_size_index` (0 to 3) and `mount.tracking`. `capt_type` is matched
ASCII case-insensitively against `stack`, `startrails`, `timelapse`. For `dual` the validated
values are then discarded and 0/0 is used. READ. The 32-bit build has no wide/dual parsing
and reads `camera_mode` differently (absent allowed; any non-`tele` string gives 209). READ.

R6. Optional members with defaults: `skip` false, `alias_name` empty, `target_name` empty,
`lp_filter` false, `star_type` -1, `target_ra_dec` the sentinel pair -999/-999, `mosaic` unset.
A wrongly typed optional target member is silently ignored. READ.

R6a. `lp_filter` takes effect after the target's goto succeeds: on a wheel model the wheel
moves to slot 2 (`LP`) when it is true and stays at slot 1 (`IRCUT`) when it is false, and it is
not moved back afterwards. A failed goto returns the wheel to the slot it had before. READ.
The full list of automatic wheel moves is in
[focus-and-filter.md](focus-and-filter.md#factory-names-the-dark-slot-and-automatic-moves).

R7. `target_ra_dec` is read from the first two numbers; malformed coordinates do not reject
the plan. Units are RA in hours and Dec in degrees (INFERRED; an app trace agrees, OBSERVED).
`mosaic` is inspected only if both coordinates parsed; if `scale` is present, `angle` is
required (102 otherwise). Grid-size and overlap members are not read. READ. What the members
do at capture, and why `star_map_angle` must be sent with them, is in
[mosaic.md](mosaic.md#parameters-and-acceptance).

R8. Fields apps send but the parser never reads include `camera`, `camera.exp_ms`,
`second_camera.exp_ms` and `second_camera.stack.scene_*`. Clients MUST NOT assume they were
applied. READ.

R9. `plan_target_af` and `viewplan_gohome` accept boolean or integer (nonzero is true); any
other type gives 106. When absent, the held values are kept. READ.

Firmware 9.31 and firmware 9.75, 64-bit (READ): in `set_view_plan` the `plan_target_af` member is stored in a local plan object. It does not write the persistent `plan_target_af` setting, which is what the runtime target autofocus step ([focus-and-filter R14d](focus-and-filter.md#autofocus)) and the `ViewPlan` event read; that setting is changed with `set_setting` and read with `get_setting`. A request with `plan_target_af` false therefore does not turn the step off. OBSERVED 2026-10-20 (S50 Pro, firmware 9.75): `set_setting {plan_target_af:true}` returned code 0 and `get_setting` read it back true.

### Failure leaves partial state

R10. Parsing has no rollback. READ. `plan_name` and `update_time_seestar` are written first;
a correctly typed `list` array clears the old list at once, then targets are appended one by
one. Hence after a rejected full plan the held state can be: old list with new name (bad list
type), empty list (empty array), or a valid prefix of the new list (bad later target). Busy
rejections (268, 536) and flag errors (106) happen before any of this and change nothing.

R11. A restart after a failed full plan reruns the partial list (207 if empty). INFERRED. A
client SHOULD re-send the whole plan after any parse failure. Firmware 9.75: after `clear_view_plan` the
held plan is gone (R32), so there is nothing to restart; a client MUST send a full plan again.

R12. If the worker cannot be started (212), the replaced plan and flags stay committed. READ.

R13. Accepting a full plan or a restart is not an inert save. Before replying the device, READ:

- copies the stack settings and, when a simulation flag is set, clears it through the stack
  setter;
- stops a running demonstration worker, whose code contains mount-stop calls (INFERRED: this
  can stop existing motion);
- resets continuous-capture and stack settings and the image-adjustment state, which sends
  change notifications;
- launches the named `ViewPlan` worker and, on the 64-bit build only and where the model and
  process allow, sets the plan indicator LED from the launch result.

None of these opens the camera, commands a slew or arm movement, or touches the cooler or fan.
READ. The 32-bit build has the same reset, demonstration stop and launch, without the LED call.
READ.

### Errors

Specific codes: 268 `operation is in progress` (View working), 536 `view plan is already running`,
106 `expected bool param`, 102 `invalid params` (mosaic), 212 `fail to create thread`; all other
parse failures surface as 207 `fail to operate`, as no specific code is set. READ. Dispatcher
codes 200 (no id) and 100 (no method) also apply. The firmware's debug text such as
"camera_mode error" is never sent. Full table: `docs/control/methods/set_view_plan.md`.

## The time model

Plans carry no date. `start_min` is minutes after local midnight on the device; the
device does not use `update_time_seestar`, any request timestamp or a calendar date. READ.

R14. The worker reads the device's local time **once**, when it starts, and reduces it to
seconds since local midnight `n`. It then reads a monotonic millisecond clock `M` and derives
all deadlines from `n` and `M`. It never rereads wall-clock time for scheduling. READ.
Consequences, INFERRED: a later DST change or clock/zone change does not move deadlines, a
restart can pick a different day, and the "next day" shift is a fixed 86400 s regardless of a
23- or 25-hour local day. The plan mechanism has no zone parameter.

R14a. The worker uses the device's system time zone, which the `time_zone` member of
`pi_set_time` sets. READ. The imager sets no zone of its own. READ. The zone is sampled when the
plan worker starts, not when the process started, so a client that changes the zone SHOULD do so
before starting a plan. INFERRED for the exact reload behaviour.

R15. Day normalization, in list order, skipped targets included (no sorting). READ:

```text
carry = 0; previous_end = none
for each target i in list order:
    s[i] = start_min[i] + carry
    if previous_end exists and s[i] < previous_end:
        if carry != 0: abort the worker (see R17)
        carry = 1440;  s[i] = start_min[i] + carry      # no second overlap check for i
    previous_end = s[i] + duration_min[i]

n = seconds since local midnight, read once
first_start = 60*s[first];  last_end = 60*(s[last] + duration_min[last])
if      n >= last_end:               shift = +1440     # whole plan is over: do it tomorrow
else if n >= first_start:            shift = 0
else if n + 86400 < last_end:        shift = -1440     # cross-midnight plan already underway
else:                                shift = 0
for each target: s[i] += shift
    start_deadline = M + 1000*max(60*s[i] - n, 0)
    end_deadline   = M + 1000*(60*(s[i]+duration_min[i]) - n)   if that end is after max(n, 0), else 0
```

R16. A target whose start is before the previous target's end is read as "after midnight" and
gets +1440 for itself and all later targets, once. A plan authored with overlaps can thus be
silently moved to the next day. `start_min` of 1440 or more is accepted and is not reduced
(OBSERVED: 1560 and 1710 in an app trace). READ.

R17. A second overlap after the carry is already 1440 aborts the worker before any target runs,
with the initial code 207 left in place; a `ViewPlan` event with state `fail`, code 207 follows
(INFERRED from the guard logic; static example: starts 1380, 0, 30 with durations of 60). The
set_view_plan reply may already have said success. READ / INFERRED.

R18. There is no range check. Negative values are accepted, and large values overflow the
32-bit millisecond products, giving deadlines already in the past. A client MUST keep
`start_min` and `duration_min` to sane values. READ (arithmetic), INFERRED (effect).
The 32-bit build has the same normalization, early abort and 60-second entry gate (R22), but
keeps 32-bit millisecond deadlines compared unsigned; a future deadline that wraps past 2^32 ms
can compare as already expired. READ (widths), INFERRED (effect).

## The worker

States are exactly `idle`, `working`, `complete`, `fail`, `cancel` (READ); `complete`, `fail`
and `cancel` are end states. `idle` is the initial or restored state and is not announced.

```
        start                     per-target loop (serial, list order)
   idle ------> working ---------------------------------------------+---> complete
          (event: ViewPlan/working)                                   |     (code 0, even if
                |                                                     |      targets failed)
                |  for each target:                                   +---> fail     (abort, R17)
                |    skip ........... Target working+fail 204        |
                |    end passed .... Target working+fail 513         +---> cancel   (run flag
                |    start future .. sleep(floor(seconds)) once              cleared by stop)
                |    otherwise ..... Target working -> capture -> Target end state
                |  cancelled: remaining targets marked fail 253 (537 on shutdown),
                |             no Target events for them
                v
          plan terminal event sent once (ViewPlan/complete|fail|cancel)
```

R19. For each target the worker rereads the monotonic clock. If `skip` is true the target gets
code 204 without running. Otherwise if its end deadline has passed it gets 513 `target time out`
and the loop continues. If the start is in the future the worker sleeps once for the whole
seconds remaining (no polling loop), then rechecks the stop flag. READ.

R20. **Pre-start window.** Before a target's sleep the worker may switch the active camera
process selection; in one process type and only when the selection changes, this sends the
guider a [`speed_move_ratio`](../../docs/guider/methods/speed_move_ratio.md) update (camera id,
pixel scale, wide-camera selection), a scaling update and not a move. A guider connection
callback, when it runs, queries the mount mode and rewrites the power LED. Then a future target
gets the single sleep of R19, after which the target starts its capture. READ. The window
contains no arm opening, goto, camera open, cooler or fan command and no temperature-settling
wait, and nothing wakes the worker early except a stop. READ. The camera is opened at device
start, not by the plan; park does not close it. READ.

INFERRED consequences: there is no scheduled preparation, yet the device is not idle. The first
goto of a target runs inside the target's own view setup (auto-goto with solving), with no
fast path for an arm already raised; how much time an earlier arm opening saves is unresolved.
A plan cannot promise a thermally settled sensor, and sensor or cooler power state during the
sleep is unresolved.

R21. During the sleep other requests are not blocked by the plan. READ:

- guider [`scope_move_to_horizon`](../../docs/guider/methods/scope_move_to_horizon.md) has no
  536 check and can be accepted; a later [`scope_goto`](../../docs/guider/methods/scope_goto.md)
  admits the horizon worker's movement type and stops that worker before slewing;
- [`scope_park`](../../docs/guider/methods/scope_park.md) refuses with 536 only when its
  `equ_mode` member parses; `scope_set_eq_mode` has no plan check;
- [`set_control_value`](../../docs/control/methods/set_control_value.md) has no plan guard,
  so cooler controls can be changed; open-time options such as automatic cooler or heater
  apply only when the camera is opened;
- [`get_control_value`](../../docs/control/methods/get_control_value.md) for `Temperature` on
  the 64-bit main process is tier C, not a passive read: its relay to the peer can run a
  connection callback that updates the local storage record.

A client that wants the arm raised before the first target SHOULD send
`scope_move_to_horizon` before starting the plan, or early enough that the worker finishes
before the target start, and MUST treat its acceptance as a launch, not arrival. A client
SHOULD NOT poll `Temperature` through `get_control_value` as a harmless monitor, and MUST NOT
assume the device cools or settles the sensor before a target. INFERRED.

R22. A target whose end is within 60 seconds of now fails at once with 513. READ.

R23. Tele targets arm a one-shot relative timer for the whole seconds from entry to the end
deadline, then start the view; the timer stops the view. Setup time is not credited, so
expiry is nominally `arm time + floor(remaining)`, which may be later than the planned end.
Wide and dual targets poll the stored end deadline directly. READ / INFERRED. The 32-bit build
arms the timer before its coordinate setup rather than after. READ.

R24. A tele target with a mosaic uses the same timer; there is no mosaic exemption, and
setup and the initial goto consume the same budget. A mosaic has no completion of its own, so
the timer ending the view is its normal end; the target does not wait for all centers, and
the stop is cooperative, so the actual end can lag the planned end. The duration estimate
is not a deadline. READ / INFERRED. Details: [mosaic timing](mosaic/timing-and-errors.md#timing-and-deadline-interaction).

R25. Targets run strictly one after another; nothing compares a running target with the next
start. An overrun makes the next target start late, or fail with 513. READ / INFERRED.

R26. `complete` means the loop ended, not that targets succeeded; clients MUST check
`plan.list[].state` and `code`. INFERRED. OBSERVED (2026-10-12, indirect): for a stored one-target plan,
the device's file listing showed the last sub-frame and the final stack files written at a time
consistent with the nominal end of its duration; no end event was captured. INFERRED: the plan
ran its full duration from its first nominal start.

## Events

The `ViewPlan` event (receive-only, discriminated by `Event`) has `Event`, `Timestamp`, `state`
and `lapse_ms`; `code` and `error` when `state` is `fail`; `stage` and `route` sometimes; and a
`plan` object when the held list is nonempty. `Timestamp` is a nine-fraction-digit string from a
monotonic clock, not a calendar time. READ.

R27. A ViewPlan event is sent at worker start (before day normalization) and once at the end.
The worker loop sends no periodic ViewPlan event. A listener that attaches mid-run sees neither
transition. READ / INFERRED. The only caller that starts the worker is `set_view_plan`; restoring
the stored plan at boot does not start it. READ. OBSERVED (2026-10-12): `cancel` after
`stop_func` (described, not captured), and no `ViewPlan` event in a 300 s and a ten-minute listen
while a stored plan was imaging.

R27a. The ViewPlan worker sets no suppression flags, and no start or end suppression flag is
enabled anywhere in 9.31. READ. A ViewPlan event can go undelivered only if device
initialisation failed before the event callback was installed. READ. Absence of `ViewPlan`
events on a running device is therefore not explained by delivery suppression. INFERRED.

R28. OBSERVED once (2026-10-12): after a `set_view_plan` accepted with code 0, a [`Setting`](../../docs/control/events/Setting.md)
event arrived about 63 ms before the `ViewPlan` working event, and the echoed plan matched what
was sent (target coordinates equal within 32-bit float rounding). Reply-versus-event ordering
is unresolved.

OBSERVED (2026-10-17), firmware 9.75: a second instance of the same ordering, this time with both
events ahead of the RPC reply: a `set_view_plan` with no params (resuming the held plan) was
followed about 90 ms later by a `Setting` event, then a `ViewPlan` event
`{state: "working", lapse_ms, plan, route}` with `route` an empty array, and only then the
`set_view_plan` reply itself, code 0. This confirms both the `Setting` event and the `ViewPlan`
working event precede the reply, not just each other. The `Setting` event's members (`wide_cam`
and `stack.{brightness, contrast, saturation, dbe_enable}`) matched the always-appended shape
already catalogued in [`Setting`](../../docs/control/events/Setting.md), live confirmation of
that static finding.

R29. `plan.plan_target_af` and `plan.viewplan_gohome` in events come from device settings, not
from the held parsed flags, and the final go-home decision reads the setting too. The flags in a
request therefore do not by themselves guarantee the park action. READ / INFERRED.

R30. `Target` events are separate, one per runnable target: working at entry and an end state at
exit; skipped and expired targets show working then fail; cancelled-out targets get none.
Progress updates inside a wide capture refresh the cached target state but send no fresh
`Target` event. READ. A different, legacy `Target` event with `state` `start`/`complete` exists
for the old plan API. READ.

## Stopping, clearing, persistence

R31. `stop_func` with name `ViewPlan` clears the worker's run flag and signals it; the worker
wakes, checks the flag and unwinds (stopping the view, or the slave for wide/dual). The reply
does not prove a worker existed. READ.

R32. `clear_view_plan` reads no params, stops the worker through the same stop primitive, turns
the plan LED off and marks the ViewPlan function entry ignored. It does NOT erase the held plan
or its stored file on firmware 9.31, so a bare `set_view_plan` can run it again; that path always
replies code 0. The stop may wait with no established deadline. READ (firmware 9.31).

R32a. Firmware 9.75 (both builds): `clear_view_plan` also deletes the stored
`view_plan.json` in the per-user ZWO configuration directory, frees the held plan list, and resets the plan name and state. If
the file removal fails with an error other than "no such file" the reply is 218; otherwise it is
code 0. The stop of a running worker works as in R32. The 64-bit build also clears the plan-working LED indicator on this path; the 32-bit build does not call that step, and its file removal is only INFERRED (unnamed library stubs). READ (64-bit); INFERRED (32-bit file removal). Hence a bare `set_view_plan` can no
longer rerun the cleared plan on 9.75; a client MUST NOT rely on the 9.31 behaviour. `clear_view_plan` itself
sends no event; when a worker is running, the worker's own end path sends the terminal state
before the stop returns, and the stop clears the run flag. READ. Hence clearing a running plan
sends `ViewPlan` `cancel` (and `cancel` for the active `Target`) before the reply, provided event
sending is configured; with no worker running nothing is sent. INFERRED. No capture of
`clear_view_plan` exists.

R33. The held plan is persisted when the first end state is reported, to a `view_plan.json`
file under the device's per-user ZWO configuration directory; submitting a plan writes nothing, so
a power loss before the first end state can leave an older file. At startup the device loads
that file and restores the plan and last end state without starting a worker; per-target runtime
buffers are not restored. READ / INFERRED. Firmware 9.75: after `clear_view_plan` the file is
gone, so no plan is restored at the next start (the restart-code handling was not decoded;
INFERRED).

## Not covered or unresolved

- Framing, and whether pretty-printed multi-line requests are accepted.
- Reply versus event ordering; events from lower imaging and mount workers.
- Which build a live device runs. A stored plan was seen imaging (OBSERVED) with no `ViewPlan`
  event in a ten-minute listen; static reads offer explanations (missed transitions, the
  legacy-store split) but do not identify the live worker.
- 32-bit parity beyond what is stated; JSON-parser edge cases (duplicate keys, huge tokens).
- Hardware latency and errors below the parser.
- Pre-start window: time saved by an early arm opening, horizon stopping distance, sensor and
  cooler power state during the sleep (R20, R21).
- Mosaic targets: stop latency after the timer fires and the final code chosen for a stopped
  mosaic (R24, [mosaic.md](mosaic.md#open-questions)).
