# Events: helper families and delta rules

Part of the [events chapter](../events-overview.md). Most events are built by a small set of
firmware helpers ("families"). This file defines each family's members, presence rules and state
values, the function-event (F) lifecycle, and the [`PiStatus`](../../../docs/control/events/PiStatus.md) delta mechanism as the worked example
of a delta event. The envelope and delivery rules are in [envelope.md](envelope.md); per-event
members are on the event cards (`docs/<service>/events/<Name>.md`).

Basis: static analysis of firmware 9.31 (D64, D32 counterparts) and app 3.3.2. Labels as in
[CONVENTIONS.md](../../../CONVENTIONS.md).

## The families

Every emitted event uses the envelope E (`Event`, `Timestamp`) plus one or more families below.
A family describes a helper's output, not every event that carries the same name: custom
producers (for example the stack-state notifier and the guider's own state helper) have their own
rules, given on their cards. READ.

| Family | Helper | Members added to E | State and error rule |
|---|---|---|---|
| N | notify-event | none | Only `Event` and `Timestamp`. |
| S | notify-state | `state` string; `error` string and `code` integer only when the supplied code is **> 0** | `state` is any caller literal (for example `start`, `frame_complete`); it need not be an F value. |
| SR | notify-state-with-route | S members plus `route` array of strings | Same code > 0 rule. |
| V | notify-value-state | non-empty `state` string; one named value member, typed integer, number, or string/raw JSON | No automatic `code`/`error`. Raw-JSON values (for example `result`, `curve`) are embedded objects or arrays, not JSON text in a string. |
| P | notify-progress | `state` string, `lapse` integer, `total` integer | Units are caller-specific; never automatically milliseconds. |
| F | function event (send → format detail → per-function formatter) | `state` always; `stage` if non-empty; `lapse_ms` (see 3); optional `route`; formatter-specific members | Five states ([F states](#f-states)). `error` and `code` at `fail` only. |
| custom | event-specific | see card | see card |

All family rows are READ.

R30. A receiver MUST NOT assume an S-family `fail` carries `code`/`error`: they appear only for a
positive supplied code. An F-family `fail` always carries both, even when the stored code is 0.
READ.

R31. `route` is an array of function names giving the ordered active function ancestry (for
example `["View","AutoGoto"]`; outermost first is INFERRED). It is built at send time. It is not
an address. Its absence is a legitimate branch. READ. (The app's internal DTO calls a similar property `router`; that is not a wire name.)

R32. Guider events in the PHD-style group ([`StarPos`](../../../docs/guider/events/StarPos.md), [`GuideStep`](../../../docs/guider/events/GuideStep.md), [`SettleDone`](../../../docs/guider/events/SettleDone.md), ...) use
capitalized members (`Frame`, `State`, `Mount`, `Status`, `Error`) and no lowercase `state`. A
client MUST NOT look for `state`/`code` on them. READ.

## F states

R33. The F formatter writes `state` from an internal enum:

| Internal | `state` | Kind |
|---|---|---|
| 0 | `idle` | initial / restored |
| 1 | `working` | running |
| 2 | `complete` | end |
| 3 | `fail` | end, with `code` and `error` |
| 4 | `cancel` | end, no `code`/`error` |
| other | `idle` | fallback for an unknown internal code |

READ. These are the values the formatter supports; whether a given operation visits each one is
operation-specific and is given, or listed as open, in the chapter for that operation.

R34. Lifecycle of a worker started through the generic guard. READ:

| From | Trigger | To | Event sent |
|---|---|---|---|
| (none) | worker started | `working`, stored code preset to 207 | `working`, unless the "skip start" flag is set |
| `working` | progress callback (some workers) | `working` | `working` with formatter members |
| `working` | finish, continuation flag present and false (stopped) | `cancel` (internal code 253) | `cancel`, no `code`/`error` |
| `working` | finish, stored code 0 | `complete` | `complete` |
| `working` | finish, stored code ≠ 0 | `fail` | `fail` with `code` and `error` |

Direct producers that call the sender themselves can use other sequences. READ.

R35. On `fail`, `error` is the text looked up for `code` in the shared error table; when the lookup
fails, `error` is `fail to operate`. READ. A worker that never sets a code ends `fail` with code
207 (the preset). INFERRED from R34.

R36. `stage` is written only when non-empty; its values are operation-specific. READ.

## F elapsed time

R37. `lapse_ms` is an integer number of milliseconds measured on a monotonic clock. READ:

- `working`, or any state where the start time is set and the end time is not (this includes a
  `complete` sent before the end time is stored): now minus start.
- `complete`, `fail`, `cancel` with both times set: end minus start.
- otherwise (`idle` with no timer started): `lapse_ms` is omitted.

R38. `lapse_ms` is independent of `Timestamp`. A client MUST NOT derive one from the other. READ.

## F suppression and lifecycle flags

R39. The F sender returns without sending when no function detail is available or the function
name is empty. READ. (This is why a blank-named worker produces no event at all.)

R40. Each function detail carries three flags, READ:

| Flag | Effect |
|---|---|
| skip end | Suppresses non-working notifications (end states). The cached tree still updates. |
| skip start | Suppresses the guard's initial `working` notification. |
| ignore | Marks the matching tree node ignored on non-working processing, also when the notification is suppressed. |

R41. The sender does no previous-state comparison and no terminal deduplication, and does not
require a preceding `working`. READ. A client can therefore see an end state with no `working`,
or (in principle) a repeated end state.

R42. Sending invokes the installed notification callback; delivery is not guaranteed. READ.

R42a. In 9.31 the skip-start and skip-end flags are never enabled. Only the ignore flag is used,
on a few internal helper workers: stack auto-exposure, image save, dark-frame creation and
probably one sun-finding exposure. Those workers send no function-state events at all. READ
(store scan; writes through computed pointers are not excluded). The callback is installed once
during device initialisation, after the camera SDK starts; if that start fails, no
function-state event is sent. READ.

R43. A "work error" variant of the sender adds `code`/`error` to a `working` event without a
terminal state. READ (definition). No code path calls it in 9.31, in either build. READ. A client
will therefore not see a `working` event carrying `code`/`error` from this path.

## Other family notes

R44. P-family `lapse`/`total` and legacy plan `progress` counters are counts or caller units, not
F `lapse_ms`. READ.

R45. Some events mix families by producer: for example [`Exposure`](../../../docs/control/events/Exposure.md) has a legacy direct variant
(`page`, `state`, `exp_us`, `gain`, S-style error) and an F variant (`state`, `lapse_ms`,
`exp_ms`, `port`, `route`). See the family column of the [event index](../events-overview.md#event-index).
READ.

R46. The polar-alignment custom formatter (`3PPA`) uses its own 18-value stage table, not the
F enum ([nested-schemas.md: Polar-align stages (3PPA custom formatter)](nested-schemas.md#polar-align-stages-3ppa-custom-formatter)). READ.

## Worked example: PiStatus deltas

`PiStatus` reports device thermal, battery and charger state. It is the reference delta event.

R47. The status checker keeps an internal list of changed fields. When the list is non-empty it
builds a `PiStatus` event with only the changed members and broadcasts it on I. It sends no
`state`, `code`, `error`, nested `result` or list of changed keys. READ.

| Member | Type | Meaning |
|---|---|---|
| `is_overtemp` | boolean | SoC over-temperature threshold crossed. READ |
| `temp` | number | SoC temperature, degrees Celsius (thermal zone reading / 1000). READ |
| `charger_status` | string | Literals include `unknown`, `discharging`, `full`, `charging`, `cool`, `warm`. The builds read different charger chips, so the mapping may differ by build, not by model. READ |
| `battery_capacity` | integer | Battery capacity; percent INFERRED. |
| `charge_online` | boolean | Charger present. READ |
| `is_typec_connected` | boolean | Type-C connected. READ |
| `battery_overtemp` | boolean | Battery over-temperature. READ |
| `battery_temp` | integer | Battery (charger) temperature as reported by the charger driver, unscaled integer. Source READ; whole degrees Celsius INFERRED from the device's own thresholds. |
| `battery_temp_type` | string | `normal`, `high` or `low`; omitted for an unknown internal value. READ |

R48. Formatting, READ:

- Delta mode (events): each member is written at most once even if its field was marked changed
  several times; then the whole change list is cleared. Unrecognized entries are cleared without
  output. Marking appends without deduplication; the formatter coalesces.
- Full mode (getters `pi_get_info` and the `pi_status` part of `get_device_state`): all
  supported members in fixed order; the change list is left intact, so a getter does not consume
  a pending delta.

R49. Rate, READ:

- The formatter has no timer, token bucket or throttle.
- A temperature poll loop sleeps 1 s per iteration. It marks `temp` changed only when the
  absolute difference from a retained baseline exceeds 1.0 °C, or `is_overtemp` changes. The
  baseline is not advanced by smaller changes, so drift accumulates until it exceeds 1.0 °C.
  Battery/charger reads are reached from the same loop.
- A Type-C change notifies immediately.

Consequences, INFERRED: there is no "one PiStatus per second" guarantee and no global 1 Hz cap,
and intervals are not exactly 1000 ms. OBSERVED (2026-10-12, firmware not matched): 29
`PiStatus` events in 300 s, each with `temp` only, at intervals of 1.0 to 44.6 s.

R50. `is_undervolt` and `is_over_current` appear in the app's PiStatus DTOs, and the checker has
voltage/current tracking helpers, but neither D64 nor D32 serializes them. They are not wire
members. A client MUST NOT expect them. READ.

R51. A client MUST merge each `PiStatus` into retained state and SHOULD seed that state from a
full-mode getter after connecting. INFERRED (the app's consumers merge partial events, READ).

Synthetic delta sequence (values invented):

```text
{"Event":"PiStatus","Timestamp":"5821.004417230","temp":47.5}
{"Event":"PiStatus","Timestamp":"5822.006120544","battery_temp":31}
{"Event":"PiStatus","Timestamp":"5830.512006001","is_typec_connected":true,"charge_online":true}
```

OBSERVED (2026-10-12): complete parsed shapes with exactly `Event`, `Timestamp` and `temp`
(real), and exactly `Event`, `Timestamp` and `battery_temp` (integer). These agree with delta
mode and differ from the getter snapshot.
