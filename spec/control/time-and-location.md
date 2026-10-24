# Time and location

This chapter covers how a client reads and sets the device's host clock and time zone
(`pi_get_time`, `pi_set_time`), how those values reach the mount and the plan scheduler, and how
the user's site location is stored and reported. It sits on the JSON-RPC envelope
([session-handshake.md](session-handshake.md)) and on the imager-to-guider relay described there.
Consumers of the clock are [plan-scheduling.md](plan-scheduling.md) and
[mount-and-motion.md](mount-and-motion.md). The NTP side effect of `check_internet` is in
[network.md](network.md).

## Conventions

RFC 2119 / RFC 8174 key words bind clients. Labels **READ**, **OBSERVED**, **INFERRED** and
**unresolved** are used as in [plan-scheduling.md: Conventions](plan-scheduling.md#conventions). READ claims are
for the 64-bit build of firmware 9.31 ("D64"); the 32-bit build ("D32") is noted where it differs.

Basis: static analysis of firmware 9.31 (imager and guider processes, packaged scripts) and app
3.3.2. All dates, zones and coordinates below are synthetic.

## Overview

The device has three clocks that a client may care about. READ / INFERRED.

| Clock | Read with | Set with | Notes |
|---|---|---|---|
| Host wall clock and system time zone | `pi_get_time` | `pi_set_time`; NTP inside `check_internet` | libc local time on the device |
| Monotonic clock | event `Timestamp` | none | not wall time (INFERRED from clock source) |
| Mount controller clock | `scope_get_time` (guider) | `scope_set_time` (guider); `pi_set_time` also updates it | offset and UTC strings |

The Android app sets the time once per connection, after verification and before the
language. READ. The iOS app was seen sending the language first, then `pi_set_time`, then
`set_user_location`, on each connect. OBSERVED 2026-10-12. See
[liveness-and-ordering.md](session-handshake/liveness-and-ordering.md).

## Reading the time: pi_get_time

R1. [`pi_get_time`](../../docs/control/methods/pi_get_time.md) reads no params and returns integer
`year`, `mon` (1..12), `day`, `hour`, `min`, `sec` and string `time_zone`. The calendar fields
are libc local time on the host. READ (fields); INFERRED (standard calendar meaning).

R2. `time_zone` is read separately from the calendar. D64 takes it from the system time-zone
tool's output; D32 reads the system time-zone file. The two reads are not atomic and can
disagree. READ.

R3. The reply has no epoch, no numeric UTC offset and no DST flag. A client that needs an
absolute instant MUST resolve `time_zone` with its own time-zone database. READ (absence);
normative (client).

R4. The device does not trim `time_zone`; D32 may include the file's trailing byte. Clients
SHOULD trim whitespace. D64 can return an empty `time_zone` with success. Error: 207. READ.

Example (synthetic):

```
{"id":3,"method":"pi_get_time","result":{"year":2026,"mon":1,"day":1,"hour":12,
 "min":0,"sec":0,"time_zone":"Etc/UTC"},"code":0}
```

## Setting the time: pi_set_time

### Routing

R5. `pi_set_time` is implemented in the guider process, not in the imager. A request sent to the
main control port is not found locally (103) and is relayed to the guider with a 10000 ms wait;
the guider's reply is returned. READ. Guest-table clients cannot use this relay (READ, per the
guider cards), so they cannot set the time.

### Request

R6. `params` is an object, or an array whose first element is that object. Null or a non-object
gives 107. READ.

| Member | Type | Default | Meaning |
|---|---|---|---|
| `year` | integer | -1 | four-digit year |
| `mon` | integer | -1 | month 1..12 |
| `day` | integer | -1 | day of month |
| `hour` | integer | -1 | hour 0..23 |
| `min` | integer | -1 | minute |
| `sec` | integer | -1 | second |
| `time_zone` | string | empty | IANA zone name, e.g. `Etc/UTC` |

READ (names, types, defaults); INFERRED (ranges; the device does not check them).

R7. Members of the wrong type and unknown members are ignored, not rejected. READ.

R8. A client SHOULD send all six calendar fields and `time_zone` together, with the calendar
expressed in that zone. This is what the app does: it sends the phone's current time in the
app-selected zone and the zone's IANA ID. READ (app); normative (client).

R9. A client MUST send a plain IANA zone name: letters, digits, `/`, `_`, `+`, `-` only. The zone
is passed to a shell script without quoting and into a 255-byte command buffer. READ (device);
normative (client).

### Processing order

The device performs these steps in order and does not roll back. READ.

1. If `time_zone` is non-empty, run the device's set-timezone script with it.
2. If all six calendar fields are present (none is -1), set the host calendar with the system
   date utility. The utility interprets the values in the host's current zone (INFERRED).
3. If the mount is not connected, reply 315. If it has no time capability, reply 210.
4. If a view is running, skip the mount update and reply success.
5. Otherwise update the mount time and reply with its result.

R10. Steps 1 and 2 happen before the mount checks. A reply of 315 or 210 does not mean the host
clock or zone was left unchanged. READ.

R11. Only the output of the time-zone script is checked: if it contains the lowercase text
`error`, the device replies 216 and skips the calendar and mount steps. The calendar step's
output is not parsed, and child exit statuses are ignored. If the device cannot obtain the
output stream of either command, it replies 214. READ.

R12. On D64 the time-zone script reports an unknown zone with a message that starts with
uppercase `Error:`. The check in R11 is case-sensitive, so an unknown zone usually does not
produce 216 and processing continues. READ. D32 uses a different script that does not test the
zone file first. READ.

R12a. Zone-name acceptance differs by build. The 64-bit script rejects an empty name and any
name without a matching zoneinfo file, and exits early if the zone is unchanged. The 32-bit
script has neither check and leaves acceptance to the system time service. READ. Both report a
rejection as output containing "error", which gives 216. READ. Valid IANA names are accepted by
both. INFERRED for the 32-bit build.

R13. A success reply (`result:0`) is not an acknowledgement that the zone or calendar changed.
Clients that need certainty MUST read back with `pi_get_time` and compare. READ (device);
normative (client). An empty object runs neither host step and only attempts the mount update.
READ.

On 2026-10-12 the iOS app sent a one-element array holding an object with integer calendar
members and a zone string; the reply was code 0 with an integer result, and a `pi_get_time`
readback confirmed the change. OBSERVED.

### Effect on other components

R14. `pi_set_time` does not touch the held ViewPlan. A running plan keeps its monotonic
deadlines; a new or restarted plan samples local time again. READ (no plan call); INFERRED
(deadlines unaffected). See [plan-scheduling.md](plan-scheduling.md).

R15. Event `Timestamp` values are monotonic and are not affected. INFERRED.

R16. Changing the time or zone with `pi_set_time` produces no event. READ. A client that needs
to confirm the change SHOULD call `pi_get_time` afterwards.

R16a. After a zone change `pi_get_time` reports the new `time_zone` at once, because the name is
read from the system time service on every call. READ. The calendar fields come from the running
process's local-time conversion, and no process refreshes its zone after the change, so they may
stay in the previous zone until the services restart. READ (no refresh) / INFERRED (effect). A
client SHOULD treat a zone change as fully applied only after a restart.

Flow (main control port):

```
client               imager (control port)          guider
  | pi_set_time {...}   |                             |
  |-------------------->| 103 locally -> relay        |
  |                     |---------------------------->| zone script, date, mount checks
  |                     |<----------------------------| {result:0,code:0} or error
  |<--------------------| (waits up to 10000 ms)      |
  | pi_get_time         |                             |
  |-------------------->| read calendar + zone        |
  |<--------------------|                             |
```

## Mount time

R17. The guider methods `scope_set_time` (params `offset` and `utc`, both strings) and
`scope_get_time` act on the mount controller only. They do not change the host clock or zone.
READ. `utc` must contain a `YYYY-MM-DDTHH:MM:SS` date-time; it is found by search, so trailing
text such as `Z` or a fraction is tolerated. `offset` is the zone offset in hours, fractions
allowed, positive east of UTC (`"8"` for UTC+8). Both are required (105); 315 when no mount is
connected; 210 when the mount has no time capability; 207 on failure, including a year whose last two digits are 21 or less. The device
converts the pair to local date and time and sends the offset, date and time to the mount.
READ (syntax and checks); INFERRED (east-positive sign, from the mount command's convention).
Cards:
[`scope_set_time`](../../docs/guider/methods/scope_set_time.md),
[`scope_get_time`](../../docs/guider/methods/scope_get_time.md). The guider also registers
[`scope_get_test_date`](../../docs/guider/methods/scope_get_test_date.md), which sends a vendor
date query to the mount and returns the reply in `list`, split by a loop into several strings.
READ (loop), INFERRED (that each `#`-terminated segment becomes one string). On an S50 Pro with
firmware 9.31 the reply was `["0#", "0#", "#", "#"]` while the device clock read the correct local
date and time; it is not a calendar value. OBSERVED 2026-10-16. Its meaning is unresolved.

## NTP

R18. `check_internet` first tries an NTP sync that can set the host clock (4-second command
timeout), then checks connectivity. A client that has just set the time manually SHOULD expect
it to be overwritten when `check_internet` runs with internet access. READ (device); INFERRED
(interaction).

## User location

R19. The device keeps a persisted user location (degrees INFERRED). `get_device_state` reports it as
`location_lon_lat: [lon, lat]` (longitude first). The section is present only when
-360.1 < lon < 360.1 and -90.1 < lat < 90.1; the sentinel -999 means "unset" and suppresses it.
READ.

R20. The guider method `scope_set_location` passes a site to the mount, with `latitude` and
`longitude` (numbers, latitude first, or positional `[latitude, longitude]`). The handler
applies no range check. READ. Longitudes, stored and supplied, are decimal degrees positive
east; latitude is positive north. INFERRED (strong: the device negates the longitude for the
mount's west-positive site command and passes the stored value unchanged to an east-positive
astronomy routine). Card: [`scope_set_location`](../../docs/guider/methods/scope_set_location.md).

R21. The app stores the user location with the guider method
[`set_user_location`](../../docs/guider/methods/set_user_location.md) (object `lon`, `lat`,
`force`, or positional `[lon, lat, force]`), sent on every connect after `pi_set_time` and when
the user picks a site. Like `pi_set_time` it reaches the guider from the main control port through
the imager relay (R5). The handler parses `lon` and `lat` (104 if missing or not numeric), persists
them, and then, unless the View function is running, updates the mount's site; `force` is not
read and does not touch the clock or zone. READ (D64; the D32 handler was not analysed). A
`set_user_location` reply with code 0 and a changed `location_lon_lat` on readback was OBSERVED
(2026-10-12). [`get_user_location`](../../docs/guider/methods/get_user_location.md) returns the
stored pair as `[lon, lat]`. READ.

R22. Clients MUST NOT assume the order of the arrays is the same: `location_lon_lat`,
`set_user_location` and `get_user_location` use `[lon, lat]`, while `scope_set_location`'s
positional form is `[latitude, longitude]`. READ.

R23. Firmware 9.31, 64-bit imager: [`cali_user_location`](../../docs/control/methods/cali_user_location.md) takes an optional `ra`/`dec` pair (object or `[ra, dec]`). When the calibration-location test setting (`calib_location`) is 1, a parsed pair enters the offset-computation path; after successfully loading the user location, that path computes and stores calibration offsets from the supplied coordinates. Location-load failure exits without that store. READ. The runtime writer enabling this test setting remains unresolved; the reader gate does not establish that this call enables it. It always returns
`calib_location` and, when available, `effect_offset_deg` (possibly twice), `offset_deg` and
`offset_deg_3ppa`, each a two-number array in degrees. A missing or bad pair is not an error.
READ. `calib_location` is an integer mode: 1 enables goto location calibration (goto and
solve-and-calibrate apply the offset and fail with 210 when it is unavailable); 2 enables
instead the offset used by three-point polar alignment (`offset_deg_3ppa`, also writable through
`set_setting`); any other value disables both. READ.

R24. Clients MUST tolerate the duplicate `effect_offset_deg` key. READ.

## iOS app connect-time writes and Remote Network mode (apps 3.4.0 and 3.4.1)

iOS app 3.4.0 build 4 and iOS app 3.4.1 build 2 (READ): After the connection-initialization device-state callback runs, the app checks that connection status is 1. With a stable cached `Client` event, either an absent event or nonzero `is_master` permits submission of language through `set_setting`, followed by `pi_set_time` and `set_user_location` with `force:false`. A present nonmaster event suppresses these submissions. Local and Remote Network connections use this same gate. The event is fetched separately during the check, so this describes a stable cache rather than an atomic snapshot. The calls establish submission order; request success and successful device application remain unresolved.

iOS app 3.4.0 build 4 and iOS app 3.4.1 build 2 (READ): The connect-time `pi_set_time` constructor puts one object in the parameter array, containing integer `year`, `mon`, `day`, `hour`, `min`, `sec` and string `time_zone`. It samples the phone's current date and extracts Gregorian calendar components. The time-zone lookup uses a remote override when one is set and the phone's local time zone otherwise. Remote entry installs the override by converting the time-zone name stored in the remote-device record, and remote exit clears it. The time-zone name and the calendar configuration use separate lookups, so an atomic snapshot across an override change is unresolved. The constructor has no branch that omits `time_zone`. Successful device clock or zone changes, and the freshness of stored remote metadata, are unresolved.

iOS app 3.4.0 build 4 and iOS app 3.4.1 build 2 (READ): Connect-time `set_user_location` takes longitude and latitude from the app's working-coordinate cache and sends `force:false`. Remote entry fills that cache from the remote-device record before service startup, so over the Remote Network the app resubmits the stored site's coordinates and zone, not a phone fix. The constructor does not obtain a new phone fix and does not test permission, coordinate freshness, equality with the device's reading or whether the coordinate changed.

iOS app 3.4.1 build 2 (READ): Locally, the working coordinate can come from a saved site or a phone-location callback. A phone-location update changes the phone cache, but changes the working coordinate only when no selected saved site matches and the app is not in Remote Network mode. When connected, that permitted callback also submits `set_user_location` with `force:false` without repeating the cached `Client` master check. Startup and foreground code start this workflow. A saved-site refresh can replace the working coordinate without testing remote mode, but does not itself submit a request. Initialization has no once-only or changed-coordinate test and can resubmit the cache after a reconnection reaches the gate. Whether a submission overwrites the device's location is unresolved.

iOS app 3.4.1 build 2 (READ): The ordinary home-site selector shows a notice and does not open during Remote Network sessions. Its local selection workflow can submit explicit coordinates with `force:true` after plan and observing-stack checks. A connected numeric-coordinate picker can also submit `force:true`; its save option controls whether the working cache is replaced before submission, not whether submission happens. A separate remote-device location screen hides the phone-location option and submits the selected coordinate and address metadata to the network service; that metadata contains neither `time_zone` nor `force`. The effect of metadata changes on an active session or on the physical device is unresolved.

iOS app 3.4.1 build 2 (READ): Device-state decoding stores the device-reported location separately from the working-coordinate cache. The connect-time constructors compare neither that location nor a reported time or zone before submitting, and the connect path has no confirmation before overwriting. Location-error alerts for codes 315 and 259 appear after a request. No `pi_get_time` literal was found in either main executable. Indirect requests, other readback consumers, firmware acceptance and the firmware meaning of `force:false` are unresolved.

## Open questions

- Whether running processes actually keep the old zone after a change (R16a). unresolved.
- Behaviour of the date utility for ambiguous or non-existent local times around DST. unresolved.
- Meaning of the mount's reply to `scope_get_test_date`. Unresolved; see [R17](#mount-time).

## Appendix: Validating on a live device (non-normative)

- Read `pi_get_time` before and after `pi_set_time`; compare both calendar and zone.
- Send `pi_set_time` with only `time_zone` set to a valid zone; the calendar step is skipped.
- Expect 315 when no mount is connected, after the host steps have run.
