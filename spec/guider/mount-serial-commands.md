# Mount serial command set

This chapter describes the ASCII command set the guider speaks to the mount controller over the
serial link: framing, reply shapes, the commands by group, how the `scope_*` methods map onto
them, the goto sequence, status flags and limit alerts, speed clamps, version gates and the
startup motor-current check. It is the layer below the `scope_*` methods of
[index.md](index.md) and [guiding.md](guiding.md); the raw bridge that lets a client share the
same line is in [serial-bridge.md](serial-bridge.md).

App names: “RA Backlash Compensation (arcsec)” and “DEC Backlash Compensation (arcsec)” are read and
written through `scope_send_cmd`. Names are the English strings of iOS app 3.4.0; links are READ
(app call sites) unless marked.

## Conventions

Labels, RFC 2119 keywords and the reply envelope are as in [index.md: Conventions](index.md#conventions).
Basis: static analysis of the 64-bit guider build of firmware 9.31, compared with firmware 9.75
(app 3.4.0) for the deltas in [Firmware 9.75 deltas (app 3.4.0, 64-bit)](#firmware-975-deltas-app-340-64-bit). The 32-bit builds were compared at string level only
([32-bit build parity](#32-bit-build-parity)). Nothing here was sent to a device or a mount. Clients normally do not issue these
commands: they use the `scope_*` methods, or the raw bridge. Command text below is what the
guider writes; the meaning of a letter or reply is READ only where the text says so.

## Transport and framing

R1. Every command starts with `:` and ends with `#`. There is no checksum, length field or
escaping. READ. Non-printable bytes are hex-escaped in the guider's log only. READ.

R2. The guider opens the mount line at 115200 baud, 8 data bits, no parity, 1 stop bit, then
runs the version handshake ([Connect sequence and version gates](#connect-sequence-and-version-gates)). READ. This is separate from the 9600 baud default of
the serial bridge ([serial-bridge.md R3](serial-bridge.md#raw-byte-socket)), which applies to
bytes a bridge client sends on its own.

R3. One whole command/reply exchange is serialized by a process-wide lock, so two mount
commands never interleave on the guider's side. READ. A failed write returns code 207 and
triggers the automatic reopen of the serial link. READ.

R4. Four reply shapes exist (three kinds of read, and no read). READ:

| Shape | Read rule | Used for |
|---|---|---|
| Single status byte | 1 byte, 1 s; the byte `1` means accepted | most set commands (the "ack" below) |
| Terminated string | bytes until `#`, buffer of 32 bytes, 2 s | queries |
| Fixed count | N bytes, 2 s | a few queries |
| None | the guider does not read | motion rates, aborts, timed moves |

The command-send primitive takes a type and an argument: type 0 with a positive argument reads
that many bytes; type 0 with zero or less reads one byte and, if that byte is `e`, reads on to
`#` and returns the error text; type 3 reads up to the terminator character; types 1, 2 and -1
write only. Success is 0, failure 1. With no mount connected it sets code 318. READ.

R5. The mount reports errors as `e<N>#` (for example `e13#`). READ. The guider maps only a few
values to its own codes ([The scope_* method to command mapping](#the-scope_-method-to-command-mapping), [Status flags, tracking reason and limit alerts](#status-flags-tracking-reason-and-limit-alerts), [Goto sequence and watcher](#goto-sequence-and-watcher)); any other `e...` is a plain failure. The meaning
of the mount's own numbers is not stated anywhere in the code ([Startup motor-current check (S50 Pro, 64-bit only)](#startup-motor-current-check-s50-pro-64-bit-only)).

R6. Read failures carry these codes. READ.

| Code | Cause |
|---|---|
| 516 | port error |
| 519 | end of file or zero bytes |
| 248 | buffer full without a terminator |
| 300 | time reversal |
| 201 | reconnect failed |

R7. There is no generic retry or backoff. READ. The exceptions are the version loop at connect
([Connect sequence and version gates](#connect-sequence-and-version-gates)) and one coordinate read that is retried once after 2 s.

## Command table (firmware 9.31, READ unless noted)

### Queries

| Command | Reply and use |
|---|---|
| `:GV#` | version string; see [Connect sequence and version gates](#connect-sequence-and-version-gates) |
| `:GVT#` | version/time string; the field meaning is INFERRED from a log message |
| `:GR#` | right ascension, hours:minutes:seconds; the failure sentinel is -1000 (code 101) |
| `:GD#:GFR2#:GFD2#` | three commands in one write; declination in degrees, minutes, seconds; the extra `#` replies are drained by counting |
| `:GA#`, `:GZ#` | altitude, azimuth |
| `:Gt#`, `:Gg#` | site latitude, longitude |
| `:Gm#` | pier side: `E#` is 0, `W#` is 1, anything else -1 |
| `:GDd#`, `:GDr#` | axis coordinates as decimal numbers (at least 2 bytes) |
| `:GL#`, `:GC#`, `:GG#` | local time (`h:m:s`), date (`m/d/y`), UTC offset; the field order of `:GL#` and `:GC#` is INFERRED from the set commands |
| `:GT#` | tracking mode as an integer, matched against the mode table ([Goto, home, tracking, mode](#goto-home-tracking-mode)) |
| `:GBu#` | beep volume; compared with the strings `0#`, `1#`, `2#` |
| `:GBZR#` | test-date string, returned as a one-element list by `scope_get_test_date` |
| `:GU#` | status string; [Status flags, tracking reason and limit alerts](#status-flags-tracking-reason-and-limit-alerts) |
| `:GAT#` | tracking-reason code; [Status flags, tracking reason and limit alerts](#status-flags-tracking-reason-and-limit-alerts); only when the version gate allows |
| `:GFI#` and sixteen `:GI...#` parameter queries | startup motor-current check; [Startup motor-current check (S50 Pro, 64-bit only)](#startup-motor-current-check-s50-pro-64-bit-only) |

### Set time and site

| Command | Notes |
|---|---|
| `:SG<sign>HH:MM#` | UTC offset; the sign is `-` when the guider's offset is zero or positive and `+` otherwise (west-positive), the offset being whole hours |
| `:SCMM/DD/YY#` | date; a two-digit year of 21 or less is refused with code 209 (message "can't set year") |
| `:SLHH:MM:SS#` | local time; the three are sent in the order SG, SC, SL, each acknowledged |
| `:St<sign>DD*MM'SS#` | site latitude, `+` for zero or positive, degrees truncated |
| `:Sg<sign>DDD*MM'SS#` | site longitude, east-positive and signed (not negated); latitude is sent first |
| `:SH0#` | sent at connect to close daylight-saving handling (INFERRED from the log text and the zero argument) |
| `:SBu0#`, `:SBu1#`, `:SBu2#` | beep volume close, low, high; an index above 2 gives code 204 |
| `:Sr` and `:Sd` | goto target, [Goto sequence and watcher](#goto-sequence-and-watcher) |

### Sync

| Command | Notes |
|---|---|
| `:CM#` | sync the mount to the target; the reply is read to `#`. `e5#` gives 270, `e11#` gives 209, other `e...` is a failure. |

### Motion

| Command | Notes |
|---|---|
| `:R2#` to `:R8#` | move-rate selection: `:R2#` "2x", `:R3#` "4x", `:R4#` "8x", `:R5#` "20x", `:R6#` "60x", `:R7#` "MAX/2", `:R8#` "MAX"; an eighth table row sends `:R9#` and has no name |
| `:RG#` | guide rate, no reply |
| `:Mn#`, `:Ms#`, `:Me#`, `:Mw#` | start motion; the rate command is sent first |
| `:Q#`, `:Qe#`, `:Qn#` | abort all, abort east/west, abort north/south; none is read back. `:Q#` is the only stop that does not depend on a direction. |
| `:Mg<dir>%d#` | guide pulse of that many milliseconds; the guider then sleeps for the same time |
| `:MTn%02d#`, `:MTs%02d#`, `:MTe%02d#`, `:MTw%02d#` | timed move, 0 to 99, seconds INFERRED; needs the version gate in R12, else code 210 |
| `:MTD<nsew>%02d#` | the same duration field with a direction letter; used by the speed-move worker; send-only |
| `:Rv<d or r>%.2f#` | axis rate; `d` is the Dec axis and `r` the RA axis; send-only. The unit of the value is unresolved |

### Goto, home, tracking, mode

| Command | Notes |
|---|---|
| `:MS#` | slew to the target; [Goto sequence and watcher](#goto-sequence-and-watcher) |
| `:SZ%03d#` | azimuth in whole degrees from the compass; sent before a goto in alt-az mode |
| `:CE#` / `:CD#` | sent before every goto; `:CE#` when the local device state says the charger is online, else `:CD#`. The letters' meaning on the mount is INFERRED from a log message |
| `:Te#` / `:Td#` | tracking on / off, acknowledged; with the version gate set, `:GAT#` follows |
| `:TQ#`, `:TS#`, `:TL#` | tracking mode sidereal, solar, lunar (names matched case-insensitively) |
| `:hC#` | go home (park) |
| `:AA#` / `:AP#` | alt-az mode (equatorial flag false) / equatorial mode (flag true) |
| `:TO0#` | sent before the line is closed |
| `:CR#` | sent after a recovery when `:GU#` returned an unexpected value ([Status flags, tracking reason and limit alerts](#status-flags-tracking-reason-and-limit-alerts)); meaning INFERRED to be a reset of the mount's state |

## Motor-current commands

The writes `:SIZRTI5#`, `:SIZRGI10#`, `:SIZDTI5#` and `:SIZDGI10#` belong to the startup check in
[Startup motor-current check (S50 Pro, 64-bit only)](#startup-motor-current-check-s50-pro-64-bit-only).

## The scope_* method to command mapping

R8. Every mount-facing handler first tests that a mount is connected (otherwise 315). READ.
Mapping (64-bit, 9.31). READ:

| Method | Serial traffic |
|---|---|
| [`scope_speed_move`](../../docs/guider/methods/scope_speed_move.md) | `:Rv...#`, a 10 ms pause, then a timed move or `:MTD...#`; an absolute speed below 0.01 becomes an abort |
| [`scope_move`](../../docs/guider/methods/scope_move.md) | rate command plus `:MT<dir>%02d#`; the duration MUST be an integer 1 to 9, else 204 |
| [`scope_goto`](../../docs/guider/methods/scope_goto.md) | [Goto sequence and watcher](#goto-sequence-and-watcher) |
| [`scope_abort_slew`](../../docs/guider/methods/scope_abort_slew.md) | `:Q#`, `:Qe#`, `:Qn#` |
| [`scope_park`](../../docs/guider/methods/scope_park.md) | `:hC#` plus the watcher in [Goto sequence and watcher](#goto-sequence-and-watcher) |
| [`scope_sync`](../../docs/guider/methods/scope_sync.md) | `:CM#` |
| [`scope_set_time`](../../docs/guider/methods/scope_set_time.md), [`scope_get_time`](../../docs/guider/methods/scope_get_time.md) | `:SG`, `:SC`, `:SL` / `:GL#`, `:GC#`, `:GG#` |
| [`scope_set_location`](../../docs/guider/methods/scope_set_location.md), [`scope_get_location`](../../docs/guider/methods/scope_get_location.md) | `:St`, `:Sg` / `:Gt#`, `:Gg#` |
| [`scope_get_ra_dec`](../../docs/guider/methods/scope_get_ra_dec.md), [`scope_get_equ_coord`](../../docs/guider/methods/scope_get_equ_coord.md) | `:GR#`, `:GD#...` |
| [`scope_get_horiz_coord`](../../docs/guider/methods/scope_get_horiz_coord.md), [`scope_get_state`](../../docs/guider/methods/scope_get_state.md) | `:GA#`, `:GZ#` |
| [`scope_get_axle_coord`](../../docs/guider/methods/scope_get_axle_coord.md) | `:GDd#`, `:GDr#` |
| [`scope_get_pierside`](../../docs/guider/methods/scope_get_pierside.md) | `:Gm#` |
| [`scope_get_mode`](../../docs/guider/methods/scope_get_mode.md) | `:GU#`: letter `G` present gives 1, `Z` gives 2, else 0 |
| [`scope_set_eq_mode`](../../docs/guider/methods/scope_set_eq_mode.md) | needs the home flag `H` in `:GU#` (else 254, `mount operation failed`; the guider logs "not home pos"), then `:AA#` or `:AP#`, then a `MountMode` event |
| [`scope_get_track_state`](../../docs/guider/methods/scope_get_track_state.md), [`scope_set_track_state`](../../docs/guider/methods/scope_set_track_state.md) | `:GU#` (no `n` means tracking) / `:Te#`, `:Td#` |
| [`scope_get_track_mode`](../../docs/guider/methods/scope_get_track_mode.md), [`scope_set_track_mode`](../../docs/guider/methods/scope_set_track_mode.md) | `:GT#` / `:TQ#`, `:TS#`, `:TL#` |
| [`scope_get_beep_volume`](../../docs/guider/methods/scope_get_beep_volume.md), [`scope_set_beep_volume`](../../docs/guider/methods/scope_set_beep_volume.md) | `:GBu#` / `:SBu0#` to `:SBu2#` |
| [`scope_is_moving`](../../docs/guider/methods/scope_is_moving.md) | `:GU#`, last digit |
| [`scope_send_cmd`](../../docs/guider/methods/scope_send_cmd.md) | raw pass-through of a caller-supplied command |
| [`scope_get_test_date`](../../docs/guider/methods/scope_get_test_date.md) | `:GBZR#` |
| [`scope_set_slew_rate`](../../docs/guider/methods/scope_set_slew_rate.md), [`scope_get_slew_rate`](../../docs/guider/methods/scope_get_slew_rate.md), [`scope_set_guide_rate`](../../docs/guider/methods/scope_set_guide_rate.md), [`scope_get_guide_rate`](../../docs/guider/methods/scope_get_guide_rate.md) | none. The slew rate (0 to 7) is stored in the driver and goes out as a rate command at the next move |
| [`scope_fine_move`](../../docs/guider/methods/scope_fine_move.md), [`scope_move_left_by_angle`](../../docs/guider/methods/scope_move_left_by_angle.md), [`scope_move_to_horizon`](../../docs/guider/methods/scope_move_to_horizon.md) | worker threads; their serial output was not traced beyond the axis-coordinate read of `scope_fine_move`. unresolved |
| `scope_set_connection_mode`, `scope_set_connection_para`, `scope_get_connection_mode`, `scope_get_connection_para` | driver and port configuration (INFERRED), not mount commands |

## Connect sequence and version gates

R9. After the line opens, the guider sends `:GV#` up to 5 times within about 8 s with a 1 s
pause. If the very first write fails it asks the local control layer to power-cycle the mount
(a local `mount_repower` request). READ.

R10. If `:GV#` never answers, the guider reads the version of the mount firmware image stored on
the device and writes it to a setting; the result is then used for the gates below. READ.

R11. After the version check the guider reads the coordinates, sends `:GVT#`, sends `:SH0#`,
sets slew-rate index 7, reads the tracking state and sets time and site. READ.

R12. The version string selects features. READ:

| Version at least | Feature |
|---|---|
| 1.1.0 | `:GAT#` tracking-reason query |
| 1.1.9 | timed moves (`:MT...#`); without it the timed-movement helper fails with 210 |
| 1.2.2 | sync data |
| 1.6.6 | the model-setting area (`:SH...`) |

## Status flags, tracking reason and limit alerts

R13. `:GU#` returns a status string (read to `#`, 32 bytes, 2 s). READ: letters are flags,
among them `n`, `G`, `Z`, `H`, `N`, `R`, `r`, `l`, `L`; the first two non-letter characters are
compared and `00`, `01` and `03` are accepted. Anything else triggers a recovery (time and
site are set again and a sync is done) and `:CR#`. The meaning of the letters is INFERRED and
no legend exists in the binary. Where the code uses a letter, this chapter says so: `n` absent
means tracking; `H` means at home; `G` and `Z` select the mode value of `scope_get_mode`; `R`,
`r`, `l`, `L` drive the limit alerts below.

R14. The last digit of `:GU#` is mapped to a movement type. READ: 0 and 1 none, 2 goto, 3 and 5
move, 4 home, 6 clear-backlash. The movement type names the guider uses internally are 0 none,
1 goto, 2 and 4 move, 3 home, 5 move-to-horizon, 6 move-home-horizon, 7 clear-backlash.

R15. `:GAT#` answers `1#` for OK. READ. Error replies map as follows.

| Reply | Code |
|---|---|
| `e5#` | 270 (`below horizon`) |
| `e7#` | 502 (`mount sync failed`) |
| `e8#` | 272 (`meridian flip failed`) |
| `e13#` | 527 (`alt exceed limit`) |
| other `e..#` | 207 (`fail to operate`) |

R16. A limit check reads `:GU#` every few seconds with the current angle and raises an alert.
READ. The alert numbers were already specified; the source (the mount's flags), the sound
number and the angle windows are the new detail.

| Flag | Angle window | Alert | Sound |
|---|---|---|---|
| `R` | angle at most 179 | 532 | 24 |
| `r` | angle above 180 | 533 | 25 |
| `l` | 91 to 269 | 540 | 42 |
| `L` | outside 90 to 270 | 541 | 41 |

R17. Speed clamps for `scope_speed_move` (the speed-move worker). READ: a speed above 1440 is
clamped to 1440; below 0.01 in absolute value it becomes an abort. With the anti-resonance
option set, 900 up to 950 becomes 900 and 950 up to 1000 becomes 1000; above 1000 is unchanged.
The driver has no stall-detection command. The unit of the `:Rv` value is unresolved.

## Goto sequence and watcher

R18. `scope_goto` runs these steps. READ:

1. Fail with 203 if a goto thread is already running.
2. Ask the local control layer for the device state (pod status and compass), 10 s timeout.
   Failure is logged and the goto is abandoned.
3. In alt-az mode, when the azimuth flags are clear, read the calibration flag and direction
   from that state and send `:SZ%03d#` with the rounded direction. When the compass is not
   calibrated the guider logs that the check failed and skips the azimuth.
4. Send `:CE#` or `:CD#`. A failure only logs.
5. Send the target (`:Sr`, `:Sd`), then `:MS#`, and read one byte.
6. Reply `0` is success and the watcher starts, with the target RA converted from hours to
   degrees. Reply `e` is followed by a read to `#`:

| Reply | Code |
|---|---|
| `e13#` | 527 (`alt exceed limit`) |
| `e3#` | 203 (`equipment is moving`) |
| `e5#` | 270 (`below horizon`) |
| `e6#` | 270 |

Any other `e...` fails without a code.

R19. The watcher (shared by goto and home) polls `:GU#` every 500 ms. READ. On exit it sends
`:Q#`. After a goto it turns tracking back on if needed. After a home it sees the home flag,
clears the azimuth state and re-applies the equatorial mode. It also tests the arrival against
a 0.1 degree tolerance and logs "far from target" otherwise. Its time-out and exit-code
mapping are unresolved.

## Firmware 9.75 deltas (app 3.4.0, 64-bit)

R20. Compared by instruction sequence for about sixty mount-driver and `scope_*` functions and
by string references, with two differences. READ:

1. Firmware 9.75 sends `:GP#` at connect, before the `:GV#` loop (type 3, terminator `#`). The
   result is discarded and the version gate flag is cleared. The reply meaning is unresolved.
2. Firmware 9.75 no longer has the charge-temperature precondition of the startup motor-current
   check ([Startup motor-current check (S50 Pro, 64-bit only)](#startup-motor-current-check-s50-pro-64-bit-only)). The S50 Pro model test is still there. INFERRED: the check now always
   runs on that model when the temperature read succeeds.

R21. Everything else listed in [The scope_* method to command mapping](#the-scope_-method-to-command-mapping), including time, tracking-mode and test-date handling,
is identical in firmware 9.75 apart from address shifts and register allocation. Operand-level
constants were not compared. READ (one function) / unresolved (constants).

## 32-bit build parity

R22. At string level the 32-bit builds contain the same commands as the 64-bit builds, plus the
same `:GP#` in firmware 9.75, but not the motor-current block: its strings and code are absent.
No 32-bit code was traced for this chapter, so instruction-level parity is unresolved. The
seven state-changing paths checked independently are in [index.md: Build differences](index.md#build-differences).

## Startup motor-current check (S50 Pro, 64-bit only)

R23. The check runs only on an S50 Pro; on other models the guider logs that it was skipped.
READ. In firmware 9.31 it reads the charger chip's temperature (an integer, degrees C by the log
text) and proceeds only when it is above 10. Firmware 9.75 removes that condition (R20).

R24. It queries 17 parameters ("before"): `:GFI#` and sixteen `:GI<a><b><c><d>#` queries, with
`a` in Z or G, `b` in R or D, `c` in T or G and `d` in H or I. Each is sent as type 3 with `#`
as terminator. It then writes four settings, each acknowledged: `:SIZRTI5#`, `:SIZRGI10#`,
`:SIZDTI5#`, `:SIZDGI10#`, and queries again ("after"). READ. The letter decode (R or D for
the RA or Dec axis, T or G for track or goto, H or I for hold or run current) is INFERRED from
the names only; the unit of the values is unresolved.

## Open questions

- The `:GP#` reply in firmware 9.75, and the `:GVT#` field layout.
- The mount-side meaning of `:CR#`, `:CE#`, `:CD#` and of the `e<N>#` numbers other than those
  mapped in R15 and R18.
- The `:GU#` letter legend (R13).
- The unit of the `:Rv` value, and why both `:MTD...#` and `:MT<dir>...#` exist.
- Serial output of `scope_fine_move`, `scope_move_left_by_angle` and `scope_move_to_horizon`.
- The watcher time-out and exit-code mapping (R19), and the reply handling of the track-mode
  command (an acknowledgement is assumed, not traced).
- Fragments with no code reference (`:TB`, `:GBZD#`, `:GFGD#`, `:GFGR#`): possibly dead strings.
- 32-bit instruction-level parity (R22).
