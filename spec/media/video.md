# Video: RTSP, RTMP pipeline and AVI recording

This file specifies the RTSP live streams on 4554 and 4555, the device's internal RTMP image
pipeline as far as clients see it, AVI/MP4 recording, and AVI playback into the stream.
Overview: [index.md](index.md). Still images: [image-sockets.md](image-sockets.md). Recorded
files in the album: [files-and-album.md](files-and-album.md). Events:
[events chapter](../control/events-overview.md). Ports: [ports.md](../transport/ports.md).

App names: “Photo”, “Video” and “Time-lapse” capture and “RAW format enabled” map to the snapshot
and AVI recording methods here. Names are the English strings of iOS app 3.4.0; links are READ (app
call sites) unless marked.

## Conventions

As in [index.md: Conventions](index.md#conventions). READ claims are for the 64-bit imager build of
firmware 9.31 unless stated; app claims are for app 3.3.2. "RTMP" is the device's own name for
its live image/stream pipeline. That it speaks the RTMP protocol on any port is not established.

## RTSP endpoints

Basis: static analysis of app 3.3.2 (URL builder) / firmware 9.31 (event formatter).

| Port | URL | Camera | Remote-map label | Label |
|---:|---|---|---|---|
| 4554 | `rtsp://<host>:4554/stream` | main imager process | RTMP | READ |
| 4555 | `rtsp://<host>:4555/stream` | auxiliary (wide) imager process, S30 Plus-class models only | RTMP_WIDE | READ |

URL grammar (READ):

```abnf
rtsp-url = "rtsp://" host ":" port "/stream"
port     = "4554" / "4555"
```

R1. A client MUST use the path `/stream`. READ (app URL).

R2. In `REMOTE` mode the app reaches 4554 and 4555 through the second tunnel session on the same
local port numbers, with host `<loopback>`. READ.

R3. RTSP is served from inside the imager process. The imager's stream thread configures the
vendor camera SDK's video-stream functions with the port and path `/stream`; the SDK in turn
calls an RTSP/RTP server whose code (request handling, SDP, H.264/H.265 packetisation) is
built into the imager executable and exported to it. READ (the SDK library imports those
functions; the imager defines them). The
main imager uses 4554. An imager started as the auxiliary process (command-line option `-a`,
honoured only when the model check for S30 Plus-class hardware succeeds) uses 4555. READ (64-bit
build; the 32-bit build has the same option, strings and symbols). On other models nothing
serves 4555. INFERRED. A client SHOULD request interleaved TCP when it runs over the remote
tunnel, because the tunnel maps TCP ports only. INFERRED.

R3a. `SETUP` accepts RTP over TCP (interleaved, `RTP/AVP/TCP`) and RTP over UDP (`RTP/AVP`
with `client_port`). READ. Any other transport is answered 461; a `SETUP` that fails inside the
server is answered 500. READ. The
session has a video track `track1`; the server also names an audio track `track2`. READ.
`DESCRIBE` requires `Accept: application/sdp`. READ. The SDP has this form (READ):

```text
v=0
o=- 0 0 IN IP4 <unspecified-IPv4>
s=rtsp_demo
t=0 0
a=control:<url>
a=range:npt=0-
m=video 0 RTP/AVP 96
c=IN IP4 <unspecified-IPv4>
a=rtpmap:96 H264/90000
a=fmtp:96 packetization-mode=1[;sprop-parameter-sets=<sets>]
a=control:<url>/track1
```

`rtpmap` reads `H265/90000` instead when the stream is created as H.265. READ. The imager
creates the preview stream with H.264 encoding and the RTSP protocol with the H.264 codec, so the
SDP reads `H264/90000`. READ (64-bit build; 32-bit not checked). A client MUST still take the
codec from the SDP `rtpmap` line.

R3b. The preview stream is 640×360 for quality index 0 and 1920×1080 for quality index 1; other
indexes give error 204. READ. That index 0 is `Smooth` and 1 is `HighQuality` (R6) is INFERRED.

Firmware 9.75: the video pipeline adds H.264 SPS/PPS handling and BT.709 colour handling. READ
(64-bit); the 32-bit build was not checked. The RTSP server code is unchanged from 9.31 (equal
normalised hashes on both builds).

R3c. RTSP requires no authentication: the server never challenges and never answers 401. READ.
There is no idle timeout: the `Session` header has the form `Session: <8 hex digits>` with no
`timeout=` parameter, and the server keeps no per-connection timer. READ. A session ends only when
the client closes the connection, a receive on it fails, the client sends `TEARDOWN`, or the device
stops the stream (R5a). READ. A client need not send keepalives. If it sends one, it MUST use
`OPTIONS`: `GET_PARAMETER`, `SET_PARAMETER`, `RECORD`, `ANNOUNCE` and `REDIRECT` are answered 501.
READ.

R3d. The server validates each request in this order. READ.

1. A request without `CSeq` is answered 400.
2. On a connection already bound to a session, a wrong `Session` id is answered 454 and a stream
   path other than the bound one is answered 451.
3. On a connection not bound to a session, any request other than `OPTIONS` whose path names no
   stream is answered 454.

Other method-level responses: `DESCRIBE` can be answered 406 (see the `Accept` rule in R3a); `PLAY` or
`PAUSE` in the wrong session state gives 455. READ. A client MUST send `CSeq` on every request
and, after `SETUP`, MUST repeat the returned session id and the same stream path.

R4. RTSP is not JSON. The `video` catalog service has no entries. READ.

## Stream control from 4700

Basis: static analysis of firmware 9.31 / app 3.3.2.

R5. `set_page` with page 5 starts the RTMP pipeline. READ. See the
[set_page card](../../docs/control/methods/set_page.md). Sequence (READ):

1. `set_page` 5 starts the stream thread unless it is already running; view mode 6 is first
   switched to view mode 1.
2. The thread checks that the camera is open; otherwise it stops with error 318.
3. It creates the camera streams, starts the video stream, starts raw capture, and emits `RTSP`
   `working` ([RTSP event](#rtsp-event)).
4. It loops until stopped. Changing away from page 5 (or stopping disk-writing functions)
   stops it; it then emits the terminal `RTSP` state (`cancel`), stops and destroys the
   streams.

R5a. RTSP is therefore available only while the stream thread runs. A connection to 4554 or
4555 before `set_page` 5, or after leaving page 5, is refused. INFERRED from R5; OBSERVED
2026-10-10 and 2026-10-11 with the device idle and parked (both ports refused through the
remote tunnel).

R6. `set_setting` carries the stream settings below. READ. See the
[set_setting card](../../docs/control/methods/set_setting.md).

| Member | Values | Meaning | Label |
|---|---|---|---|
| `rtsp_quality` | `Smooth`, `HighQuality` | stream quality preset | READ |
| `rtsp_roi_index` | 0, 1, 2 | zoom 1x, 2x, 4x | READ |
| `rtsp_roi_scale` | about 0.9999 to 4.0001 | continuous zoom | READ |
| `image_transfer_mode` | `Jpg`, `Raw` | image-socket encoding; not read by the RTSP code | READ (values), INFERRED (no RTSP effect) |

### RTSP event

The device reports stream state with the [`RTSP`](../../docs/control/events/RTSP.md) event on 4700. READ.

| Member | Type | Presence | Label |
|---|---|---|---|
| `state` | string | always: `idle`, `working`, `complete`, `fail`, `cancel` | READ |
| `roi_index` | integer | 64-bit build: only when the zoom scale is close to 1, 2 or 4; 32-bit build: see R7a | READ |
| `roi_scale` | number | 64-bit build only, always present there | READ |
| `port` | integer | configured RTSP port (default 4554), both builds | READ |
| `route` | array of string | on zoom-change events | READ |

R7. `RTSP` `state: working` is emitted after the start-stream call, whatever its result: a
failed start is only logged. READ. `working` is therefore the earliest point to connect, not
proof that the listener is up. The RTSP socket binds and listens when the stream is created,
which happens before the start-stream call; a server already listening on the same port is
reused. READ (64-bit build and its camera SDK; 32-bit not checked). A client SHOULD open the URL
after `working` and SHOULD retry a refused connection a few times before reporting failure.
INFERRED. The event was seen with
`state: working` during Scenery playback (OBSERVED 2026-10-12; full payload not captured).

R7a. Both builds take `port` from the configured RTSP port setting, default 4554. READ. On the
64-bit build `roi_index` 0, 1 and 2 correspond to scales 1, 2 and 4 (READ for presence; the
index values for 2 and 4 INFERRED). The 32-bit build sends `roi_index` and `port` and no
`roi_scale`; both are written as integers. READ. A client MUST treat `roi_scale` as optional. READ
(builds differ).

R7b. The app 3.3.2 parses the `RTSP` event with a JSON object mapper that reads `roi_index` and
`port` as integers, and `lapse_ms` as an integer. It drops an event that has no `route`, and it
uses `route` to tell the telescope stream from the wide stream. It maps `roi_index` 0, 1 and 2
to 1×, 2× and 4× zoom, and any other value to 1×. It never reads `port` or `roi_scale`: it always
dials `rtsp://<host>:4554/stream` for the telescope camera and `rtsp://<host>:4555/stream` for
the wide camera. A parse failure is only logged. READ (app 3.3.2). The app therefore matches the
index-to-scale mapping above but does not settle the 32-bit build's value types.

R8. The event channel and the media channel are separate. A client MUST NOT expect events on
4554/4555. READ.

## AVI and MP4 recording

Basis: static analysis of firmware 9.31 / app 3.3.2.

```text
client                          4700 (imager)                        storage
  |-- start_record_avi {raw,timelapse} -->|                               |
  |<- result 0 (worker started) ----------|                               |
  |<- AviRecord start {fps} --------------|-- write frames -------------->|  Video/MyWorks
  |<- AviRecord working {saved_frames..} -|                               |
  |-- stop_record_avi ------------------->|  stop flags set               |
  |<- result 0 (no wait) -----------------|-- close file ---------------->|
  |<- AviRecord cancel -------------------|  (after the file is closed)   |
```

### Requests

| Method | Params | Result | Card | Label |
|---|---|---|---|---|
| `start_record_avi` | `{raw?, timelapse?{enable, delay_sec, src_dura_min}}` | `0` | [card](../../docs/control/methods/start_record_avi.md) | READ |
| `stop_record_avi` | ignored | `0` | [card](../../docs/control/methods/stop_record_avi.md) | READ |

R9. `raw` accepts a boolean or an integer (non-zero is true). Omitting `raw` selects a
different recording format from `raw: false`. READ. A client SHOULD send `raw` explicitly.

R10. `timelapse` is an optional object. `enable` defaults to false. `delay_sec` and
`src_dura_min` keep their saved values when absent. A wrong member type is ignored. READ.

R11. `start_record_avi` requires a running RTMP image pipeline. READ. A client MUST start the
stream (R5) before recording. INFERRED.

R12. `stop_record_avi` returns 0 before the file is closed. READ. A client MUST wait for the
terminal [`AviRecord`](../../docs/control/events/AviRecord.md) event before reading the file. INFERRED. In some view modes the main process
relays the stop to its process-2 peer and waits up to 10000 ms for the peer's reply. READ.

R12a. `AviRecord` uses the function-event family
([families.md: F states](../control/events/families.md#f-states)). After `stop_record_avi` the
writer closes the AVI file and the recording ends in `state: cancel`, which carries no `code` or
`error` (the internal stop code 253 is not sent). `complete` or `fail` occur only when the
recording ends by itself. The file is closed before the terminal event is sent. READ for the
inspected start paths; INFERRED for all. One timelapse start path runs the writer without the
function-event wrapper and sends no terminal event. READ. A client SHOULD therefore also apply
a timeout and check `get_albums` after stopping. INFERRED.

| Code | Trigger | Label |
|---:|---|---|
| 207 | RTMP image pipeline not running | READ |
| 208 | disk full | READ |
| 209 | timelapse enabled with `delay_sec` <= 0 | READ |
| 212 | worker thread start failed | READ |
| 268 | recording already running | READ |
| 524 | function conflict (planet stacking active) | READ |

### AviRecord event

| Member | Type | Presence | Label |
|---|---|---|---|
| `state` | string | `start`, `working`, `complete`, `fail`, `cancel` (after `stop_record_avi`), `idle` | READ |
| `fps` | number | start event | READ |
| `saved_frames` | integer | writer updates | READ |
| `raw` | boolean | writer updates | READ |
| `file_saved` | boolean | when output is valid | READ |
| `duration_sec` | number | only when saved and > 0.01 s | READ |
| `name` | string | when an output name exists | READ |
| `note` | string | MP4 writer: `mp4 record` | READ |
| `timelapse` | object `{enable, delay_sec, src_dura_min}` | timelapse writer | READ |
| `write_file_fps` | number | writer loop | READ |
| `code` | integer | `fail` only (not `cancel`); 218 when the file cannot be created | READ |

R13. There is no fixed interval between `AviRecord` updates. READ.

### Additional recording rules

Basis: static analysis of firmware 9.31 (64-bit build; 32-bit build probable) and app 3.3.2, unless a line says otherwise.


[`start_record_avi`](../../docs/control/methods/start_record_avi.md) takes an optional
object `{raw, timelapse}`. Arrays are not positional. READ.

| Member | Type | Effect |
|---|---|---|
| `raw` | bool or integer | Wide camera: format 0. Other cameras: false gives 0, true gives 2. Absent gives 1. READ |
| `timelapse.enable` | bool or integer | Default false; an absent value clears a saved true. READ |
| `timelapse.delay_sec` | number | Seconds between frames (INFERRED). Must be > 0 when enabled, else 209. READ |
| `timelapse.src_dura_min` | integer | Recording source duration, minutes: the stored value is used unscaled at the one internal debug-log site that names it "minutes". READ |

Recording format 0 records MP4 from the camera's processed (YUV) stream; formats 1 and 2 both
record a raw-frame AVI, and 1 is chosen when the request has no raw flag. READ. How 2 differs
from 1 is unresolved. A client MUST NOT
assume that omitting `raw` equals `raw: false`. READ.

In dual routes the device
first asks the peer whether `AviRecord` runs, waiting up to 10 s. READ. Settings can change even
when start fails; there is no rollback. READ.

[`AviRecord`](../../docs/control/events/AviRecord.md) events: a simple `start` event with
`fps` (number); a `fail` event with code 218 when the file cannot be created; and function events
whose members are `saved_frames`, `raw`, `file_saved`, `duration_sec` and `name` (only when
saved), `timelapse {enable, delay_sec, src_dura_min}`, and for MP4 a `note`. READ. In the
inspected formatter call `raw` and `timelapse.enable` are written as literal true. READ. A client
SHOULD NOT take them as the request values.

[`stop_record_avi`](../../docs/control/methods/stop_record_avi.md) sets stop flags and
returns 0 without waiting. Code 0 does not mean the file is closed. READ. A client SHOULD wait for
the `AviRecord` end event or `file_saved`. In dual routes the stop is relayed to the peer
(10 s wait). READ.

## AVI playback into the stream

Basis: static analysis of firmware 9.31.

| Method | Params | Result | Card | Label |
|---|---|---|---|---|
| `start_avi_rtmp` | `{name}`, `[name]` or a bare string | `0` | [card](../../docs/control/methods/start_avi_rtmp.md) | READ |
| `stop_avi_rtmp` | ignored | `0` | [card](../../docs/control/methods/stop_avi_rtmp.md) | READ |

R14. `name` is required; a missing or non-string name gives error 105. A bare file name is
looked up under `Video/`. The path is truncated at 255 bytes. READ.

R15. Result 0 means the playback worker started, not that the file opened. READ. Open errors
arrive later as an [`AviRtmp`](../../docs/control/events/AviRtmp.md) event. A client MUST wait for `AviRtmp` before assuming playback.

R16. `stop_avi_rtmp` waits for the playback worker to exit. READ. It has no timeout.

| Code | Where | Trigger | Label |
|---:|---|---|---|
| 105 | reply | `name` missing or not a string | READ |
| 212 | reply | worker start failed | READ |
| 268 | reply | playback already running | READ |
| 524 | reply | planet stacking active | READ |
| 258 | `AviRtmp` fail | file open failed | READ |
| 220 | `AviRtmp` fail | not a video, or size outside 1..20000 | READ |
| 283 | `AviRtmp` fail | stream output init failed | READ |

`AviRtmp` transitions (READ):

| State | Event | Next state | Emitted |
|---|---|---|---|
| none | `start_avi_rtmp` accepted | Opening | `AviRtmp` `start` |
| Opening | open/format/init fails | Failed | `AviRtmp` `fail` with `code`, `error` |
| Opening | file opens | Playing | none |
| Playing | end of file or `stop_avi_rtmp` | Complete | `AviRtmp` `complete` |

R17. `AviRtmp` carries no file name, result or fps member. READ.

R17a. App 3.3.2 defines command names for `start_avi_rtmp` and `stop_avi_rtmp` but never sends
them; it only consumes the `AviRtmp` event. READ.

### Playback observations and stop error

Basis: static analysis of firmware 9.31 (64-bit build; 32-bit build probable) and app 3.3.2, unless a line says otherwise.

RTSP `working` was seen during scenery playback. OBSERVED(2026-10-12).
If stopped before the file opens, the `AviRtmp` fail event can report 253 `aborted`. READ.
`stop_avi_rtmp` always returns 0. READ.

## Snapshots from the stream

R18. [`save_image`](../../docs/control/methods/save_image.md) on 4700 (relayed to process 2 in
some view modes) saves a still. READ:

- with exposure mode 2 it returns error 210;
- while the video stream (RTSP/RTMP pipeline) runs, the still is captured from the stream and
  reported with a [`SaveImage`](../../docs/control/events/SaveImage.md) event;
- otherwise the normal image save runs;
- with no frame available it returns 207.

## Open questions

- Terminal `AviRecord` behaviour on start paths other than those inspected. unresolved.

## Appendix: How to validate on a live device (non-normative)

- Start the stream with `set_page` 5. Wait for `RTSP` `working`. Run an RTSP client with
  interleaved TCP against `rtsp://<host>:4554/stream`; record the SDP `rtpmap` line.
- Call `start_record_avi` with `raw: false`, then `stop_record_avi`. Expect `AviRecord`
  `cancel` without `code`; log the time the file appears in `get_albums`.
- Call `start_avi_rtmp` with a missing file name; expect result 0 then `AviRtmp` `fail` 258.
