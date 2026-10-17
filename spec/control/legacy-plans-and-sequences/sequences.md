# Sequences

Part of [legacy-plans-and-sequences](../legacy-plans-and-sequences.md). Requirement numbers continue across the chapter; basis and conventions are in the index.

## The stand-alone sequence list

The sequence list is the single-target form of autosave: one ordered map of sequence objects
([Sequence object](plans.md#sequence-object)) plus one settings record. It predates plans. READ.

Methods: [`set_sequence`](../../../docs/control/methods/set_sequence.md),
[`get_sequence`](../../../docs/control/methods/get_sequence.md),
[`get_sequence_number`](../../../docs/control/methods/get_sequence_number.md),
[`delete_sequence`](../../../docs/control/methods/delete_sequence.md),
[`clear_sequence`](../../../docs/control/methods/clear_sequence.md),
[`reset_sequence_progress`](../../../docs/control/methods/reset_sequence_progress.md),
[`set_sequence_setting`](../../../docs/control/methods/set_sequence_setting.md),
[`get_sequence_setting`](../../../docs/control/methods/get_sequence_setting.md),
[`get_target_sequences`](../../../docs/control/methods/get_target_sequences.md).

R13. `set_sequence` takes an array of sequence objects. Each needs an integer `id` other than -1
(else 200); a non-object element gives 107. Elements are applied in order and the list is saved
after each. `lapsed` is not an input. READ. Free space below estimate + 150 MB gives 208. READ.

R14. `get_sequence` takes a zero-based integer **index** in map order, not an id. A bad type gives
104; an index past the end gives 209. `get_sequence_number` counts every entry, disabled ones
included. READ. A client MUST iterate `0 .. count-1` and read `id` from each reply.

R15. `delete_sequence` takes an integer **id**. An unknown id gives 207. READ.

R16. `clear_sequence` empties the in-memory list. `reset_sequence_progress` sets every `lapsed`
to 0 and returns 206 while capture runs in exposure mode 2. READ. Neither change is saved. Only
writing a sequence saves it, one record per id; `delete_sequence` removes that record. READ. At
start-up the imager loads every stored sequence record from its persistent settings store into the
list, so sequences emptied by `clear_sequence` come back after an imager restart. READ (64-bit;
32-bit not checked). The stored record includes `lapsed`, but the loader does not read it back:
every loaded entry starts with `lapsed` 0. So progress, reset or not, is always 0 after a restart.
READ (64-bit; 32-bit not checked). A client that needs a clear to last MUST also delete each
sequence.

### Edit lock

The device allows sequence edits only when no exposure run would be corrupted. READ.

```text
can_modify = (exposure_mode != 2)
          OR (capture thread stopped AND (sum(lapsed) == 0 OR sum(lapsed) == sum(repeat)))
```

The sums run over enabled entries only. READ. Exposure mode 2 is the autosave exposure mode: on the
plan page it runs the enabled legacy plan, on any other page the sequence list (R21a). READ.
`set_page` `plan` and `set_page` `autosave` set it; `set_page` `preview` sets mode 0 and
`set_page` `focus` sets mode 1. The other pages leave the mode unchanged. READ (64-bit; 32-bit not
checked).

R17. When `can_modify` is false, `set_sequence`, `delete_sequence` and `clear_sequence` return
224 `cannot edit sequence unless reset the progress`. READ. A client SHOULD call
`reset_sequence_progress` (or wait for completion) and retry.

### Sequence settings

| Member | Type | Notes |
|---|---|---|
| `delay_first`, `delay_between_frame` | integer | Seconds (the runner sleeps for the value in seconds). READ |
| `group_by_slot`, `merid_flip`, `park_mount`, `shutdown_pi`, `close_cooler` | boolean | READ |
| `group_name` | string | Regularized ([Name regularization](plans.md#name-regularization)). READ |
| `target_coord` | `[ra, dec]` or `{ra, dec}` | Partial replacement allowed; absent when -999. READ |
| `left_size_m` | number | Getter only. Estimated storage left to use, binary MB. READ |
| `left_time_sec` | integer | Getter only. Estimated time left, whole seconds. Undefined when `left_size_m` is 0 (R20). READ |

R18. `set_sequence_setting` takes an object (or `[object]`); other shapes give 107. All members
are optional. It returns 224 only when the delays or `group_by_slot` change while `can_modify` is
false. READ.

R19. `get_sequence_setting` is not a pure read. On the 64-bit build, on the plan page in exposure
mode 2, it can enable the first plan when none is enabled. READ. A client SHOULD NOT poll it on the
plan page.

R20. `get_target_sequences` returns the settings members plus `slots`, an array of sequence
objects, in one reply. It never errors. On the plan page it rewrites an internal cache. READ.
`left_time_sec` is undefined when the camera frame-size query fails, which is the case when
`left_size_m` is 0. READ. A client MUST ignore `left_time_sec` when `left_size_m` is 0. Otherwise
it is the estimated remaining capture time in whole seconds. READ.

### Capture-run frames

These rules hold for both builds: the 32-bit build was checked rule by rule, and each label below
applies to both.

R20a. A sequence-list run (exposure mode 2 off the plan page) takes the enabled entries one frame
at a time. For each frame it does the following, in this order. READ.

1. If an earlier save failed, the run stops with 504.
2. It moves the wheel to the entry's `filter` ([Sequence object](plans.md#sequence-object)) and waits for the move to finish. A
   failed position read gives 507 and a failed move 508.
3. It sets the exposure. Automatic exposure runs only for a `flat` entry with `autoexp` true, and
   only on its first frame or after the filter changed (failure 509). Otherwise the exposure is
   `exp` (failure 505).
4. It applies `gain` ([Sequence object](plans.md#sequence-object)), then `bin` when it is not 0 (failure 506).
5. It sets the device frame type to the entry's `type`. The setting stays after the run (R20c).
6. For a light frame it runs guiding and dithering (failure 240), then the meridian flip when it
   is enabled or otherwise recentring, then the autofocus triggers. An entry counts as a light
   frame only when its `type` is `light` and its `filter` slot is not a dark slot
   ([focus-and-filter R22c](../focus-and-filter.md#factory-names-the-dark-slot-and-automatic-moves)).
   Any other entry skips all of these, and also skips annotation of the frame.
7. It takes one exposure (failure 238).
8. It saves the frame as its own FITS file (R20b). On success `lapsed` grows by 1 and a
   `Sequence` event is sent. If frames remain, the between-frame delay follows.

When the run ends, it sends the `Sequence` complete event and performs the after-run actions
([Sequence settings](#sequence-settings)). READ. The run never starts the View worker, so the star-view wheel restore
([focus-and-filter R22g](../focus-and-filter.md#factory-names-the-dark-slot-and-automatic-moves))
does not happen. READ.

A plan run uses its own frame routine. That routine contains the same wheel move and the same
light-frame skips, and it also skips the below-horizon check for entries that are not light
frames. READ. That its other steps match R20a is INFERRED.

R20b. Each capture-run frame is saved as its own FITS file with the extension `.fit`, under the
`Autorun` folder of the image root ([files-and-album R18a](../../media/files-and-album.md)). READ.
The frame-type name is the device frame type with a capital first letter (`Light`, `Dark`, `Bias`
or `Flat`); below it is written `<Type>`. The path is built from these parts, in order. READ.

- `Autorun/`, then `<Type>/`.
- For a `Light` frame of a run whose `group_name` is not empty: `<group_name>/`.
- `<Type>`. For that grouped `Light` frame, `_` and the `group_name` follow.
- The exposure, which is present only when it is greater than 0: `_` then the time in seconds
  with one decimal and `s` when it is 1 s or more, otherwise in milliseconds with `ms` when it is
  1 ms or more, otherwise in microseconds with `us` (for example `_10.0s`, `_500.0ms`).
- `_Bin` and the bin, for example `_Bin1`.
- Optional parts, in this order:
  - When the device's camera-name file-name setting is on: `_` and the camera name.
  - When the frame has a filter name: `_` and the filter name. No setting controls this part.
  - When the gain file-name setting is on: `_gain` and the gain, or `_ISO` and the ISO string
    when the frame has no gain.
  - When the time file-name setting is on: the device local time as `_YYYYMMDD-HHMMSS`.
  - When the temperature file-name setting is on and the frame has a valid temperature: `_`, the
    temperature with one decimal, and `C` (or `F` when the device uses Fahrenheit).
- `_` and a four-digit index, which is `lapsed` plus 1.
- `.fit`.

For example, a light frame of a run with group `M31` could be saved as
`Autorun/Light/M31/Light_M31_10.0s_Bin1_gain80_20240101-221500_0003.fit`. READ (pattern);
the example values are illustrative. The FITS `IMAGETYP` keyword holds `<Type>`. `FILTER` follows
[focus-and-filter R22b](../focus-and-filter.md#factory-names-the-dark-slot-and-automatic-moves).
READ. The FITS header is written by the same routine that writes a saved live-stack frame, so the
keyword set is the same. Depending on the frame and the device, it can hold `CREATOR`, `PRODUCER`,
`PROGRAM`, `TELESCOP`, `OBJECT`, `OBJCTTYP`, `IMAGETYP`, `DATE-OBS`, `DATE-EXP`, `EXPOSURE`,
`EXPTIME`, `TOTALEXP`, `STACKCNT`, `GAIN`, `EGAIN`, `ISO`, `OFFSET`, `BIAS`, `CCD-TEMP`,
`SET-TEMP`, `FILTER`, `FOCUSPOS`, `FOCALLEN`, `APERTURE`, `XPIXSZ`, `YPIXSZ`, `XBINNING`,
`YBINNING`, `CCDXBIN`, `CCDYBIN`, `XORGSUBF`, `YORGSUBF`, `BAYERPAT`, `RA`, `DEC`, `SITELAT`,
`SITELONG`, `EQMODE`, `WIDECAM`, `GUIDECAM` and `SHARPEN`. READ. Which of these are present for a
given frame is not covered here.

Dark and flat calibration is applied to the frame before it is saved only while the
`frame_calib` setting is on. The frame type is not consulted, so with `frame_calib` on a `dark`
entry is saved already calibrated. With `frame_calib` off every frame is saved raw. READ.

R20c. `start_exposure` takes an optional `type` string and an optional `keep_autosave_dev`
boolean. `type` is read only in exposure mode 0; in modes 1 and 2 it is ignored and gives no
error. `keep_autosave_dev` is checked in every mode and used only in mode 2. The checks are as
follows. READ.

| Condition | Result |
|---|---|
| three-point polar alignment running | 210 |
| `type` is not a string | 105 |
| `type` is `unknown` or any unrecognised string | 209 |
| `keep_autosave_dev` present and not a boolean | 106 |

A valid `type` sets the device frame type. The setting persists until another `type` or a
capture-run entry (R20a) changes it. It sets `IMAGETYP` and the type part of later saved names.
READ.

Apart from that, `type` changes nothing. In particular, `start_exposure {type:"dark"}` does not
move the wheel, does not start the View worker (so there is no star-view restore), does not start
an autosave run, and does not change calibration, which still follows `frame_calib`. READ.

Mode 0 takes one frame and saves no file. Mode 1 (continuous exposure, set by `set_page` `focus`)
streams frames and saves no file either: its loop contains no file-name or save step. Neither the
mode 0 nor the mode 1 exposure path contains a wheel command. READ. To keep a single frame, a
client uses `save_image`. It saves the current frame through the same name builder and FITS
writer as R20b, as `Preview/` then the R20b parts with `Preview` in place of `Autorun/<Type>/` and
`<Type>`, and with no index. When `group_name` is not empty, the group subfolder and the
`_<group_name>` part are added as for a grouped light frame. `IMAGETYP` holds the device frame
type. READ.

R20d. Mount state and a sequence-list run. Neither `start_exposure` nor the run checks whether
the arm is closed or parked, whether the mount is in equatorial mode, whether it is tracking, or
whether the mount is connected, at start or between frames. READ. Unlike mode 1, mode 2 does not
watch the tracking state. READ. The run queries the mount position once, before the first-frame
delay, and keeps it as the meridian-flip target. If the query fails it is retried once; if that
also fails the run continues without the stored target and does not fail. READ. Every exposure
also queries the mount position for the FITS header. A failed query does not fail the frame and
the frame is still saved. READ. The header's coordinates are reset to the -999 sentinel for each
frame before the query, and the FITS writer omits `RA` and `DEC` while either holds the sentinel,
so a frame saved after a failed query has no `RA` or `DEC` keyword; coordinates from an earlier
frame are not carried over. READ (64-bit build; the 32-bit build has the same reset and the same
writer check). The
light-frame steps of R20a (guiding, meridian flip or recentring) are the only per-frame steps that
command the mount and can end the run. READ. INFERRED: on an unparked or untracked mount a run
therefore captures and saves frames without any warning from the device. R20d holds on both
builds. READ.

