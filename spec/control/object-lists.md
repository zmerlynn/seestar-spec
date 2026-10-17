# Object lists, sky objects and target names

This chapter covers the control-channel methods that manage user object lists and that return
positions of sky objects: comets, the Sun and Moon, and constellation overlays. It also covers
target-name matching for the live view. Above it, plans use these names and coordinates
([plan-scheduling.md](plan-scheduling.md),
[legacy-plans-and-sequences.md](legacy-plans-and-sequences.md)). Sun and Moon pointing and
tracking are in [special-modes.md](special-modes.md). The request/reply envelope is in
[session-handshake.md](session-handshake.md).

Basis for the whole chapter: static analysis of firmware 9.31 (64-bit build; 32-bit build
probable) and app 3.3.2, unless a line says otherwise.

## Conventions

RFC 2119 / RFC 8174 key words bind clients. Labels **READ**, **OBSERVED(date)**, **INFERRED** and
**unresolved** are as in [CONVENTIONS.md](../../CONVENTIONS.md). Error codes and messages are
those of the common error table.

## User object lists

A user object list is a named list of objects. Each object has a name, an integer type and a
coordinate pair. Lists are stored as keys in a persistent XML configuration file on the device.
READ.

| Method | Params | Result | Errors (READ) |
|---|---|---|---|
| [`add_list`](../../docs/control/methods/add_list.md) | bare string name, or `[name]` | 0 | 105, 225 exists, 234, 226 |
| [`del_list`](../../docs/control/methods/del_list.md) | bare string name | 0 | 105, 236 not found, 234, 229, 230 |
| [`rename_list`](../../docs/control/methods/rename_list.md) | `{old, new}` or `[old, new]` | 0 | 105, 236, 225, 234, 229 |
| [`get_list`](../../docs/control/methods/get_list.md) | none | `[{name, obj_number}]` | none |
| [`add_obj`](../../docs/control/methods/add_obj.md) | `{list, object, type, coord}` or `[{...}]` | 0 | 107, 108, 236, 234, 226 |
| [`del_obj`](../../docs/control/methods/del_obj.md) | `{list, obj}` or `[list, obj]` | 0 | 105, 236, and the lower XML errors |
| [`get_obj`](../../docs/control/methods/get_obj.md) | bare string list name | `[{name, coord, type}]` | 105, 236, 229, 231 |

### Object record

| Member | Type | Default | Notes |
|---|---|---|---|
| `list` (input) | string | required | Must name an existing list, else 236. READ |
| `object` (input) / `name` (output) | string | required | The input key and the output key differ. READ |
| `type` | integer | 0 | Opaque: stored and returned unchanged, never acted on by the device. READ. Client-defined. The Android app 3.3.2 never sends `add_obj` or any other list or comet method, so it defines no values (READ, bounded search). A client SHOULD preserve values it did not write |
| `coord` | `[ra, dec]` numbers | -999, -999 | Opaque to the device: stored and returned unchanged, with no conversion or range check, and never used by goto, plans or any other device feature. READ. RA in hours and Dec in degrees by client convention. INFERRED |

R1. `add_obj` replaces an existing object of the same name in the same list. READ. A client
MUST NOT rely on `add_obj` to detect duplicates.

R2. `coord` MUST be an array of at least two numbers. A short or non-numeric array gives 108. An
object-shaped `coord` such as `{ra, dec}` is silently ignored and the sentinel is stored. READ.
A client MUST send the array form.

R3. `add_obj` ignores the result of the XML write. Code 0 does not prove the object was stored.
READ. A client SHOULD confirm with `get_obj`.

R4. `get_list` never returns an error. It may create a per-list lock file in the device's
temporary directory as a side effect. READ.

R5. Code 234 (`xml file name is empty`) means the device's list store has no file configured; it
is not caused by the list name. Any string, including an empty one, is accepted as a list name,
and names are stored as data rather than as XML element names, so they need not be valid XML
identifiers. A duplicate name gives 225. READ. A client SHOULD reject empty names itself.

## Comets

| Method | Purpose |
|---|---|
| [`get_comet_position`](../../docs/control/methods/get_comet_position.md) | compute current comet positions |
| [`update_comet_txt`](../../docs/control/methods/update_comet_txt.md) | install a staged comet-element file |

R6. `get_comet_position` takes an optional bare string. A string is an exact, case-sensitive
name filter. An empty string is a real filter, not "all". Any other params, or none, return all
comets. READ.

R7. The result is a non-empty array of `{id, name, mag, ra, dec, size}`. READ. `ra` is parsed
from an h:m:s text and is in hours; `dec` is from d:m:s text and is in degrees. INFERRED. The
positions are computed on the device for the saved site at the current time. READ. `ra` and
`dec` are apparent coordinates of date (not J2000) and `size` is the apparent diameter in
arcseconds. INFERRED (from the ephemeris library the device uses). A client that needs J2000
MUST convert. The imager only echoes `size`; no device feature reads it. The plan runner
uses only the comet's `ra` and `dec` (as the target coordinates of a plan target whose name
matches a comet). READ.

R8. `id` is the zero-based position of the comet among records the device parsed in this call,
counted before the name filter. It is not a stable catalog id. READ. A client MUST NOT store `id`
across calls; it SHOULD key comets by `name`.

R9. No match is an error (207), not an empty array. READ. The device runs an ephemeris script
with the user's location. If no location is saved it asks the mount controller, which can change
mount and LED state. READ. Errors: 214 script not started, 258 output not opened, 207 bad output
or empty list. READ. A partial parse can still return code 0 with fewer rows. READ.

R10. `update_comet_txt` takes `{md5: string}`. The device checks the MD5 of a comet file already
staged in its update area and, on match, moves it into place. A mismatch or a missing file gives
207. Wrong type gives 105. READ. How a client stages the file is outside this chapter.

## Sun and Moon positions

R11. [`get_planet_position`](../../docs/control/methods/get_planet_position.md) takes no params
and returns `{moon: [ra, dec], sun: [ra, dec]}`. Both values are in **degrees**, RA included.
READ. A client MUST convert RA to hours itself if it needs hours.

Firmware 9.75: `get_planet_position` differs from 9.31 in callees and strings (a new numeric-value
regular expression appears); it was not read, so R11 and R12 are unverified for 9.75.

R12. The device computes the positions with a script from the saved longitude, latitude and UTC
offset. Errors: 214 if the script cannot start, 207 on failure. READ. Malformed script output can
produce a reply that is not valid JSON. READ. A client SHOULD treat a parse failure as an error.

## Constellation overlay

R13. [`get_constellations`](../../docs/control/methods/get_constellations.md) takes no params. It
reads the device's temporary WCS file and runs a constellation-drawing tool on it. READ. The WCS
file comes from the last plate solve (INFERRED; see
[Solving](solving-and-annotation.md#solve-results-and-star-detection-details)).

R14. The result always has `image_size: [width, height]`. The two values are the integer
`IMAGEW` and `IMAGEH` keywords of the last plate solve's WCS file, and both must be greater than
zero, or the reply is 207 `bad IMAGEW/IMAGEH %dx%d`. READ. Confirmed unchanged in firmware 9.75,
both the 64-bit and 32-bit builds. The unit is pixels. INFERRED. It has `annotations`
(an array) only when the drawing tool printed one. The array is copied raw, without validation.
READ. Each element is an object passed through from the device's sky-annotation tool; the vendor
app reads `type`, `name`, `names`, `pixelx`, `pixely`, `radius`, `bounds`, `matrix` and
`points`. READ (app consumer). Pixel members refer to `image_size`. INFERRED. A client MUST
tolerate missing members and a reply with `image_size` alone, and SHOULD ignore unknown members.

R15. Errors: 255 `file not exist` when the tool reports a missing file, 214 if the tool cannot run,
207 when the image size is unavailable. READ. This getter does not emit `image_id`; the related
[`Annotate`](../../docs/control/events/Annotate.md) event from the solve worker can. READ.

## Target-name matching

In star view the device can propose a catalog name for the current target and then apply it.
The two steps are separate. READ.

```text
client                                  device
  | iscope_match_target_name              |
  |-------------------------------------->|  look up the current target
  | {original_name, matched_name, changed}|  store the proposal
  |<--------------------------------------|
  | iscope_accept_target_name             |
  |-------------------------------------->|  apply the proposal
  | 0                                     |
  |<--------------------------------------|
  |  Event ViewTargetNameChanged          |
  |  {original_name, updated_name}        |
  |<--------------------------------------|
```

R16. [`iscope_match_target_name`](../../docs/control/methods/iscope_match_target_name.md) takes no
params and returns `{original_name, matched_name, changed}`. `matched_name` can be `"Unknown"`.
READ. It stores a pending proposal, so it is not a pure read. READ.

R17. Both methods require view mode 0 (star) and the main camera; otherwise they return 100. In
dual-camera routes the request is relayed to the wide process. READ.

R18. [`iscope_accept_target_name`](../../docs/control/methods/iscope_accept_target_name.md) with
no pending proposal returns 100. READ. A client MUST call match first and SHOULD call accept only
when `changed` is true. INFERRED.

R19. Accept emits [`ViewTargetNameChanged`](../../docs/control/events/ViewTargetNameChanged.md)
with `original_name`, `updated_name` and sometimes `route`. It has no `state`. READ. A client
SHOULD update its displayed name from this event.

R20. The ViewPlan target name of the wide camera is set separately with
[`set_view_plan_target_name`](../../docs/control/methods/set_view_plan_target_name.md); see
[legacy-plans-and-sequences.md](legacy-plans-and-sequences/events-and-observation.md#viewplan-wide-camera-helpers).

## Open questions

- The vendor app's values for the object `type` integer and its units for list `coord`. The
  device stores and echoes both without interpreting them (READ), so these are client
  conventions only. The Android app 3.3.2 has no emitter for the list or comet methods, so the app
  cannot settle this (READ, bounded search). unresolved/UNANSWERABLE. Checked again for firmware
  9.75 app 3.4.0: no app-side emitter was found there either.
- Units of comet `size` (INFERRED only). The device only echoes it (READ); the value comes from
  the ephemeris output: the device's `comets.py`/`planet.py` scripts print the PyEphem library's
  own size field unchanged. Those two scripts are byte-identical across all four build/version
  combinations checked (firmware 9.31 and 9.75, 64-bit and 32-bit), and the PyEphem library itself
  does not ship in the firmware package, so its unit convention cannot be read from the package.
  unresolved/UNANSWERABLE; stays INFERRED, not upgraded.
- Meaning of each `annotations` element member.
- The catalog and rules behind `matched_name`.
- How the comet file is staged before `update_comet_txt`.

## Appendix: How to validate on a live device (non-normative)

1. `add_list "t1"`, then `add_obj {list:"t1", object:"o1", coord:[1.5, 20]}`; `get_obj "t1"`
   should list `o1` with the same coordinates.
2. Repeat `add_obj` with `coord:{ra:1, dec:2}`; `get_obj` should show the sentinel.
3. `get_planet_position`; compare RA with an ephemeris in degrees.
4. `del_list "t1"`.
