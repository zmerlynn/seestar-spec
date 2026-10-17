# Album and file socket 4801

This file specifies the album/file socket 4801 and the imager's file endpoints, the album
methods sent on 4700, and the HTTP 80 download path. Overview: [index.md](index.md). Image
sockets 4800/4804: [image-sockets.md](image-sockets.md). Video files and recording:
[video.md](video.md). Ports and the remote map: [ports.md](../transport/ports.md).

App names: “My Album” and “Seestar Gallery” are the album listing and download. The album categories
(“Solar System Album”, “Scenery Album”, “Stargazing Album”, “Milky Way Album”, “Star Trail Album”)
need not equal the wire group names (INFERRED). “Export” and “Export RAW” save to the phone and are
not the device's `start_export_image` (INFERRED). Names are the English strings of iOS app 3.4.0;
links are READ (app call sites) unless marked.

## Conventions

As in [index.md: Conventions](index.md#conventions). READ claims are for the 64-bit imager build of
firmware 9.31 unless stated; app claims are for app 3.3.2.

## Endpoint

Basis: static analysis of firmware 9.31 / app 3.3.2.

R1. Port 4801/TCP is served by the imager main process with the file handler class and its own
dispatch table (9 entries). READ.

R2. Requests use the same JSON-line grammar as the image sockets
([image-sockets.md: Grammar](image-sockets.md#grammar)), including the error replies for
unknown methods and malformed requests (image-sockets R4). Replies are binary or text, not JSON
envelopes. READ. Every reply uses the 80-byte header of
[image-sockets.md: Reply framing](image-sockets.md#reply-framing). File content is sent as imgType 6,
dataType 2 (plain) or 3 (zip-compressed). READ.

R2a. There is no end-of-file marker or trailer. The header's payload length delimits each reply,
and a client MUST read exactly that many bytes. READ. A read past the end of a file returns a
reply with payload length 0 (R7). READ.

R3. No challenge-response applies on 4801. The device closes an external client after more than
15000 ms without received bytes. READ.

## Methods

Basis: static analysis of firmware 9.31 (file table and handlers) / app 3.3.2 (emitters).

### Summary

| Method | Params | Reply | App emitter | Card | Label |
|---|---|---|---|---|---|
| `test_connection` | none | text `server connected!` (imgType 0, dataType 0) | heartbeat | [control card](../../docs/control/methods/test_connection.md) | READ (registered) |
| `get_img_page_thumbnail` | `{page:int}` or `[page]` | thumbnail, or text error | none found | [card](../../docs/files/methods/get_img_page_thumbnail.md) | READ |
| `get_batch_stack_thumbnail` | optional `{frame_type:string}` (R4b) | thumbnail, or text "no image" error | none found | [card](../../docs/files/methods/get_batch_stack_thumbnail.md) | READ |
| `get_img_file_in_jpg` | `{name:string}` (app) | JPEG (imgType 4) of a FITS file or of one AVI frame; 102 for other types | yes | [card](../../docs/files/methods/get_img_file_in_jpg.md) | READ |
| `get_img_file` | `{name, offset:int}` or `[name, offset]` | image data from offset, or text error | none found | [card](../../docs/files/methods/get_img_file.md) | READ |
| `get_fits_file` | `{name, compress}` or `[name, compress]` | raw or compressed file, or text error | none found | [card](../../docs/files/methods/get_fits_file.md) | READ |
| `get_img_thumbnail` | `{name:string}` (app) | the file's thumbnail, or a folder's thumbnail for a folder | yes | [card](../../docs/files/methods/get_img_thumbnail.md) | READ |
| `get_server_log` | none (app) | ZIP of system and network logs (imgType 6, dataType 3) | yes | [card](../../docs/files/methods/get_server_log.md) | READ |
| `get_user_log` | not read | ZIP archive (dataType 3) | none found | [card](../../docs/files/methods/get_user_log.md) | READ |

R4. The app sends `get_img_file_in_jpg` and `get_img_thumbnail` with an object
`{"name": <remote file path>}`. READ. A client SHOULD use the app's shape.

R4a. `get_img_file_in_jpg` converts a FITS file to JPEG, or one frame of an AVI file to JPEG,
and replies with JPEG (imgType 4); any other file type gives error 102. READ. For a FITS file it
also writes a reduced-size thumbnail beside the file (the file name with a `_thn` suffix and a
`.jpg` extension) when none exists there, and keeps it; an AVI frame leaves no file. READ. The
method is therefore a MUTATOR with observation-safe (tier B) effects.
`get_img_thumbnail` resolves `name` under the image root and returns the stored thumbnail of
the file, or of the folder when `name` is a folder. READ. `test_connection` on this socket replies
with the text `server connected!`. READ. `get_server_log` collects kernel, DHCP-client (last 5000
journal lines) and DNS/DHCP-server logs, zips the log folders in 40 MB split parts, and sends the
archive as a binary reply with dataType 3. READ. The archive and log captures are scratch files
written on device storage, so the method is a MUTATOR with observation-safe (tier B) effects. READ.

R4b. `get_batch_stack_thumbnail` takes optional params. Absent or null params select light
frames. Params that are present and not an object give 107; an object without a string
`frame_type` gives 105. READ. `frame_type` names: `light`, `dark`, `bias`, `flat`. READ. The
behaviour for other names is unresolved. A client SHOULD send only these four.

R5. The app sends `get_server_log` on the 4801 file socket, through the same queue it uses for
album file requests. The request is a fixed line with `id` 4, no `params` and a CRLF terminator.
The app saves the binary reply as a local `.zip` file. Its log-upload and feedback pages then use
that file. READ (app 3.3.2). The name is registered only on the 4801 table. READ. A client SHOULD
send it on 4801.

### Parameter rules (READ handlers)

| Method | Member | Type | Default | Missing or wrong type | Label |
|---|---|---|---|---|---|
| `get_fits_file` | `name` | string | none | error 105 | READ |
| `get_fits_file` | `compress` | boolean or integer | true | default applies | READ |
| `get_img_file` | `name` | string | none | error 105 | READ |
| `get_img_file` | `offset` | integer | 0 | default applies | READ |
| `get_img_page_thumbnail` | `page` | integer | none | error 104 | READ |

R6. The array form passes members in the order shown (`[name, compress]`, `[name, offset]`,
`[page]`). READ.

R7. `get_img_file` sends the file from `offset`. The offset and length are clamped to the
file; an offset beyond the end gives an empty payload (payload length 0), not an error.
READ. The unit is bytes. INFERRED. A client SHOULD NOT send a negative offset. INFERRED.

R8. `get_fits_file` takes `name` and `compress`. When `name` contains one of the known image
folder names it is used as given; otherwise it is taken relative to the image root. READ. The
device does not normalise the path and does not reject `..` components. READ. Path confinement
to the image store is therefore not enforced. INFERRED. A client SHOULD send names exactly as
returned by `get_albums`. A client or alternative implementation SHOULD NOT rely on the device to
confine file names to the image store; a server implementation SHOULD reject names that
resolve outside it. INFERRED.

R9. On 4800, 4801 and 4804 an error number selects a fixed text, sent as a text reply
(dataType 1), not as a JSON object with a `code` member. READ. The texts are those of the
control error table ([errors.md: Code table](../control/errors.md#code-table)) for the codes below;
any other code gives `fail to operate`. READ.

| Codes | Texts as in errors.md |
|---|---|
| 100 to 109 | `invalid request` ... `unexpected param` |
| 201 to 204 | `fail to connect`, `already connected`, `equipment is moving`, `out of limit` |
| 207 | `fail to operate` |
| 248 to 260 | `invalid buffer size` ... `stack error, wrong format` |
| 300 | `internal error` |

The media table is a subset of the control table: for example 268 has a control text but gives
`fail to operate` here. READ. A client SHOULD treat the text as display-only. INFERRED.

R10. `get_user_log` deletes any earlier `user_log.*` scratch archive, zips the `Autorun_Log*.txt`
files under the configured log path into `user_log.zip` through shell commands, and sends the
archive. READ. The effect is a scratch archive on device storage. The shell and zip descendants are
not fully read, so the card keeps tier D. INFERRED (candidate tier B).

## App download queue on 4801

Basis: static analysis of app 3.3.2 (album file socket manager).

R11. The app opens 4801 when the device service reports ready and when album work needs it.
READ.

R12. The app holds a queue of download requests and runs one at a time. READ.

R13. Each reply refreshes a response-inactivity timer. If it expires, the app marks the current
download failed and disconnects 4801. READ. The timer is 30000 ms. INFERRED (constant value).

R14. The app sends the `test_connection` heartbeat every 3000 ms. READ. A client MUST send
something at least every 15 s.

```text
app                                                  device 4801
 |== connect (service ready / album work) =========>|
 |-- get_img_thumbnail {name} CRLF ---------------->|
 |<============= header + thumbnail ================|   timer refreshed
 |-- get_img_file_in_jpg {name} CRLF -------------->|
 |   ... no reply within timer ...                   |
 |-- close; mark download failed ------------------>|
```

Client download state (app behaviour READ; device framing READ, image-sockets [App download queue on 4801](#app-download-queue-on-4801)):

| State | Event | Next state | Action |
|---|---|---|---|
| Idle | queue not empty | Waiting | send head request, start timer |
| Waiting | reply bytes | Waiting | refresh timer, append data |
| Waiting | reply complete | Idle | deliver file, pop queue |
| Waiting | timer expires | Closed | mark failed, disconnect |
| Closed | album work requested | Idle | reconnect |

A reply is complete when payload length bytes have arrived after the header (R2a). READ.

Firmware 9.75 note (app 3.4.0): file downloads share the image-send rate limit set through the
cloud remote-command channel (rate 65536 to 67108864 bytes per second, on/off flag) and stored in a
flag file read by the file server and the imager; the default on a missing or invalid file is 1 MiB per
second, and the effective limit depends on the relay mode. See
[image-sockets.md](image-sockets.md#streaming-start-and-stop). Firmware 9.31 has no such limit. READ.
Firmware 9.75 details of the file server: the flag file is `/tmp/zwo/http_download_rate_limit`, re-read at most every 20 s; it holds a decimal rate in bytes per second (trailing whitespace allowed) in the range 65536 to 67108864, an invalid value falls back to 1048576, and a missing file, or any other error checking it, disables the limiter. The limiter is a token bucket of capacity rate/20 bytes shared with the imager's send limiter. The server starts a 16-thread worker pool; the route table is unchanged and no authorization was added. READ (64-bit); the 32-bit server matches on routes, absence of authorization, limiter and chunk size, and the thread pool was not checked. Which transfers are throttled in direct (non-relay) use is unresolved.

## Album methods on 4700

Basis: static analysis of firmware 9.31 / app 3.3.2. These are sent on the control socket and
return JSON envelopes. See the `control` cards for full schemas.

| Method | Purpose | Card | Label |
|---|---|---|---|
| `get_albums` | List album groups and files | [card](../../docs/control/methods/get_albums.md) | READ |
| `get_img_file_info` | Metadata for one file (`name`) | [card](../../docs/control/methods/get_img_file_info.md) | READ |
| `get_img_file_page_number` | Page count for a path | [card](../../docs/control/methods/get_img_file_page_number.md) | READ |
| `get_img_file_page_name` | File names on a page | [card](../../docs/control/methods/get_img_file_page_name.md) | READ |
| `fits_to_jpg` | Convert a FITS file; result `{jpg_name}` | [card](../../docs/control/methods/fits_to_jpg.md) | READ |
| `delete_image` | Delete images | [card](../../docs/control/methods/delete_image.md) | READ |
| `remove_file` | Remove a file | [card](../../docs/control/methods/remove_file.md) | READ |
| `set_is_favorite` | Mark a file favourite | [card](../../docs/control/methods/set_is_favorite.md) | READ |
| `is_img_file_annotated` | Annotation flag for a file | [card](../../docs/control/methods/is_img_file_annotated.md) | READ |
| `file_rename` | Rename a file and its accessory files ([File edits on 4700](#file-edits-on-4700)) | [card](../../docs/control/methods/file_rename.md) | READ |
| `set_img_file_info` | Write planet-stack sharpen values into a FITS header ([File edits on 4700](#file-edits-on-4700)) | [card](../../docs/control/methods/set_img_file_info.md) | READ |

R15. `get_albums` returns `{path, list}`. Each list item is `{group_name, files}`. Each file is
either `{name, thn, type, date, is_favorite}` with optional `duration_sec` and `cant_stack`, or a
directory `{name, thn, count, type: 0}`. READ.

R16. The `get_albums` filter accepts `stack`, `stacked`, `startrail` and `meteor` on the 64-bit
build. The 32-bit build accepts only `stack` and `stacked`. READ (firmware 9.31). Firmware 9.75: the
64-bit filter accepts `stack`, `stacked`, `startrail`, `meteor`, `comet` and `video_stack`; any
other string selects the generic listing, and a filter that is not a string gives 106. READ. `stack`
and `comet` list the DeepSky group with separate predicates, `stacked` lists the MilkyWay group
(with `_sub` suffix filtering) and `video_stack` lists video-stack files found through the
AVI-to-MP4 name mapping (which file the lookup returns is unresolved). Whether the 32-bit filter
accepts `stack`, `stacked`, `video_stack` and `comet` is unresolved. `SolarSystem`, `Starfield`,
`Scenery`, `DeepSky`, `MilkyWay`, `MyWorks` and `Startrails` were already album groups in firmware
9.31, so `SolarSystem` is not a new category. Whether `PhotoMetry` is an album group is unresolved
(the string exists in both builds but is not used as a group by the listing). INFERRED: an item
named like the `Scenery` group plus `_video` is grouped under `SolarSystem`, otherwise under
`Scenery`. Sky replay (stacking.md) writes `*_stack_replay.mp4`, whose file type code is 13. READ
(file names), unresolved (the sky replay event name).

R16a. Motion recording (firmware 9.75, 64-bit; the 32-bit build has no motion-monitor strings other
than `can_motion_monitor`). READ. The AVI writer saves under `MyWorks/Scenery_motion/` with a base name
`Scenery_Motion_Capture`, or `Scenery_Motion_Tracking` when the motion-record type is 1, followed by a
timestamp (`YYYY-MM-DD-HHMMSS` pattern) and the extension `-RAW.avi`; an `.mp4` is also produced
(config key `motion_pre_record_mp4_fps` sets its frame rate). The separator between base name and
timestamp, and which of the two files is the album entry, are unresolved.

R16b. FITS and JSON header additions (firmware 9.75). READ (64-bit; 32-bit as noted at the end). The
FITS header gains five keywords: `OB_CU` (integer, "whether the object is user-defined", written
when the value is not negative), `W_FM_MD` (integer, wide-field framing mode, when not negative),
`T_FM_RO`, `T_FM_ZM` and `T_FM_PS` (reals: telephoto framing rotation in degrees, zoom ratio, and
frame position angle on the star map, written when the value differs from the unset sentinel
-999.0). The JSON header printed for `get_stack_info` gains `star_type_custom` (from the `OB_CU`
value), `W_FM_MD` and `mosaic` {`angle`, `scale`, `star_map_angle`} with the same conditions (the
quoting of `star_type_custom` and the `mosaic` nesting are INFERRED). What populates these values is
unresolved. Other FITS keywords are unchanged and the creator string is still `ZWO `. A reader MUST
treat unknown keywords and members as optional. Whether the firmware version in the headers comes
from the OTA version record is unresolved.

In the 32-bit build of firmware 9.75 the FITS writer and reader handle the same five keywords, and
the JSON header has `W_FM_MD` and `mosaic` {`angle`, `scale`, `star_map_angle`} but no
`star_type_custom` member; the members it does have use the same emission conditions as the
64-bit build. READ (32-bit).

R17. A client SHOULD take file names for 4801 requests and HTTP URLs from `get_albums` replies.
INFERRED.

### Album result and conversion details

Basis: static analysis of firmware 9.31 (64-bit build; 32-bit build probable) and app 3.3.2, unless a line says otherwise.

[`get_albums`](../../docs/control/methods/get_albums.md) takes `{name, filter}`, a bare
`name`, or `[name, filter]`. Empty or unknown `name` selects the default works folder. `filter`
`stack`=1, `stacked`=2, `startrail`=3, `meteor`=4 (64-bit build; the 32-bit build knows only the
first two); other strings mean no filter. READ. Firmware 9.75 adds the filters `comet` and
`video_stack`; their numeric mapping is unconfirmed.

The album result is `{path, list: [{group_name, files: [...]}]}`. Each entry has `name` and
`thn`. Files add `type`, `date`, `is_favorite`, and for videos `duration_sec` and possibly
`cant_stack: true`. Directories add `count` and `type: 0`. READ. `date` is the file's modification
time in device local time, formatted `YYYY-MM-DD HH:MM:SS`. READ. File `type` codes (values READ,
meanings INFERRED from the name tests): 1 sub-frame FITS, 2 stacked FITS, 3 deep-sky stacked, 4
video-stacked, 5–8 video (timelapse or normal, with or without an AVI copy), 9 other, 10 still
image, 11 photometry, 12 meteor. Firmware 9.75: 13 for a `_stack_replay.mp4` file (READ).

[`get_img_file_page_number`](../../docs/control/methods/get_img_file_page_number.md) takes
`{dir, page_num, size, date, skip_avi}` or `[dir]` and returns a page count. `page_num` defaults
to 20; <= 0 gives 209. Errors 105, 209, 102. READ.

[`set_is_favorite`](../../docs/control/methods/set_is_favorite.md) takes
`{storage?, name, is_favorite}`. `name` is a string or array of strings (non-strings skipped).
`is_favorite` MUST be a JSON boolean; 0/1 give 102. `storage` is `emmc`, `sd` or `udisk`; an
unknown storage gives 204. Database failure gives 531. READ.

[`fits_to_jpg`](../../docs/control/methods/fits_to_jpg.md) takes a file name ending
`.fit`, `.fits` or `.fts` (any case) and returns `{jpg_name}`. An existing JPEG is returned
without re-conversion, even if the FITS changed. READ. `jpg_name` is usually relative but not
always. READ. Errors 105, 207, 258, 218, 300 (metadata write failed after the JPEG was written).
READ. Firmware 9.75: the firmware version written to the JPEG metadata comes from the OTA version
information. READ.

## HTTP 80

Basis: static analysis of firmware 9.31 / app 3.3.2.

R18. The app builds album and FITS URLs on the control host with no explicit port (port 80) on
the LAN. In `REMOTE` mode it uses a local loopback listener on 8080 mapped to device port 80.
READ.

R18a. HTTP paths are relative to the image root. The app builds them from the `get_albums`
reply (top-level `path`; per-file `name` and `thn`). READ:

| Resource | URL |
|---|---|
| file or MP4 | `http://<host>/<path>/<name>` |
| thumbnail | `http://<host>/<path>/<thn>` |
| star-trail folder cover | `http://<host>/<path>/<name>/<thn>` |
| JPG companion of a FITS file | as the file URL, with `.fit` replaced by `.jpg` |

`<path>/` is omitted when `path` is empty. READ.

R18b. Escaping differs by app path. The album browser joins the parts as plain strings and does no
percent-encoding. The background download queue first drops a leading `/`. It then
percent-encodes each `/`-separated segment as UTF-8, writing a space as `%20` and not `+`, and
appends a `task_id` query member holding the app's own download id. READ (app 3.3.2). A client SHOULD
percent-encode each segment the same way. INFERRED.

R19. HTTP 80 is served by a separate HTTP file server process, outside the common socket worker.
It is built on the cpp-httplib library and listens on `<unspecified-IPv4>:80`. READ (64-bit build; the
32-bit server was not examined). The library version is unresolved. The server is set up with
the library's defaults: at most 5 requests per keep-alive connection, a 5 s keep-alive timeout,
and 5 s read and write timeouts; no setting overrides were found. INFERRED (values READ; their
mapping to these settings INFERRED).

Routes (READ, route strings; method assignment for the upload routes INFERRED):

| Method | Path pattern | Purpose |
|---|---|---|
| GET | `/(.*)` | Download a file under the user image store `/boot/Image` |
| POST | `/ai_process` | Multipart upload, form field `file`; missing field gives "No file uploaded" |
| PUT | `/ai_process/(.*)` | Streamed upload |

Uploads are written under `/tmp/zwo/Image`, with a path-traversal check. READ.

R19a. GET resolution (READ). The captured path is appended to `/boot/Image`. Then, in order:

1. A path that escapes the base directory gives 403, `text/plain` body `Access forbidden`.
2. A path that cannot be `stat`ed gives 404, `text/plain` body `File not found`.
3. The file is opened for binary reading; failure gives 404 as above.
4. Otherwise the reply is 200 with `Content-Type: application/octet-stream`,
   `Accept-Ranges: bytes`, `Content-Length` = the size found by seeking to the end, and
   `ETag` = the resolved path, then the decimal size, then the decimal modification time in
   seconds, concatenated with no separator and sent without quotes.
5. `Range` and `If-Range` are read; when `If-Range` does not match the current ETag the full
   file is sent.

The body is produced in chunks of at most 4096 bytes (firmware 9.31) or 32768 bytes (firmware 9.75).
If a read fails, the server stops writing and closes the connection, even if fewer than
`Content-Length` bytes were sent. READ.

R19b. A request for a directory, including `/`, is not a supported request. A directory passes
the checks in R19a, so the server sends 200 headers with the directory's size as
`Content-Length`, then fails on the first read and closes with no body. READ (code path);
INFERRED (that the read fails on a directory). OBSERVED over the REMOTE tunnel on 2026-10-10,
2026-10-11 and 2026-10-12: `GET /` and `HEAD /` gave 200, `Content-Length: 131072`,
`Connection: close`, an ETag starting with `/boot/Image/`, then zero body bytes and a clean
close.

R19c. A client MUST request only file names taken from `get_albums` (R17), and MUST treat a
body shorter than `Content-Length` as a failed download, not as a complete file. INFERRED. A
client SHOULD treat the ETag as opaque. INFERRED.

R19d. No authentication code was found in the server; the HTTP layer applies no access control
of its own. READ (bounded string search); INFERRED (absence). Any authorization comes only from
the transport (LAN reachability or the remote tunnel).

### HTTP download limiting (firmware 9.75)

R15. The HTTP file server (TCP 80) gains a download rate limit in both builds. READ. It reads an
integer from the file `/tmp/zwo/http_download_rate_limit`, cached for 20 s, and feeds a token
bucket. Values below 65536 or above 67108864 are rejected and a default rate is used when the file
is unreadable or invalid. The unit is bytes per second (INFERRED). No new HTTP route was found
(INFERRED from a strings comparison); the route table was not enumerated, so 9.75 route and
authorization parity with the statements in the media chapter is not established. The binary also
carries OTA manifest strings, the secure-session library name and its error strings, and other
strings from code shared with the updater and imager; these are not a new route.

## File edits on 4700

Basis: static analysis of firmware 9.31 (64-bit imager build; the 32-bit handlers are
registered and their strings were compared, helper parity probable). No app emitter was found
for either method in app 3.3.2 (READ, bounded search). Both are synchronous, have no timeout
and emit no event that was established.

R20. [`file_rename`](../../docs/control/methods/file_rename.md) (MUTATOR / established, tier C)
takes `{src, dst}` or positional `[src, dst]`, both strings (105 otherwise). `src` is resolved
under the image root; `dst` is placed in the source's parent directory. No path, emptiness or
traversal check is made. READ. If the source has a suffix and `dst` has none, the source suffix
is appended; two non-empty, different suffixes give 300. An inaccessible source gives 255; a
failed rename gives 515. READ. The handler renames the main file, then each accessory file by
regular-expression replacement of the source stem with the destination stem, unescaped. READ.
Consequences a client MUST allow for:

- a failure partway leaves earlier renames in place (no rollback); READ;
- regular-expression metacharacters in names act as regex; a client SHOULD rename only names
  made of letters, digits, `_`, `-` and one `.` before the suffix (INFERRED);
- an existing destination is not rejected and may be replaced (INFERRED from the rename call);
  a client SHOULD check `get_albums` for the destination name first.

R21. [`set_img_file_info`](../../docs/control/methods/set_img_file_info.md) (MUTATOR /
probable, tier C) requires an object (107) with `file_name` (string under the image root, 105)
and `planet_stack_sharpen` (array of integers; 102 if absent or not an array, 104 for a
non-integer element; empty allowed, no bound). READ. It opens the FITS file for update, writes
the values to the `SHARPEN` string key as a comma-terminated list, and closes it. If the
matching thumbnail is found and removed, it is regenerated; a thumbnail failure after the FITS
write is ignored and the reply is still 0. READ. If the FITS file cannot be opened the reply is
258 (`open file failed`); if the `SHARPEN` key cannot be written or the file cannot be closed it
is 256 (`fit operation failed`). READ. One open-failure path gives 268, which is sent with the
text `fail to operate`; the condition for it is INFERRED. Positional params are not accepted.
READ.

## Open questions

- Album file `type` values and date format.

- `get_batch_stack_thumbnail` with a `frame_type` other than the four names: see
  [R4b](#summary).
- Firmware 9.75 open points: `PhotoMetry` as an album group, the file returned by the `video_stack`
  lookup, the final Scenery_motion album entry, the sources of the new header fields, and the 32-bit
  status of `get_albums` filters, `raw_bin2`, the header keys and the file-server thread pool.
- HTTP server library version: see [R19](#http-80). POST/PUT assignment of the upload routes
  (INFERRED in the route table). unresolved.

## Appendix: How to validate on a live device (non-normative)

- Call `get_albums` on 4700 to get a file name. Send `get_img_thumbnail {name}` on 4801; record
  the reply prefix and total length.
- Send `get_img_file` with offset 0, a non-zero offset and an offset past the end; compare
  payload lengths to confirm the unit and the empty reply.
- Send `get_fits_file` with `compress` false and true; compare the replies.
