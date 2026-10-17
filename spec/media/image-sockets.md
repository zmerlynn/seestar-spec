# Image sockets 4800 and 4804

This file specifies the imager's binary image sockets: 4800 (main camera) and 4804 (wide
camera). It covers request names, the reply framing, streaming start and stop,
and how a client gates these sockets on the control stream. Overview and catalog mapping:
[index.md](index.md). File socket 4801: [files-and-album.md](files-and-album.md). RTSP and
recording: [video.md](video.md). Ports and order: [ports.md](../transport/ports.md).

## Conventions

As in [index.md: Conventions](index.md#conventions). READ claims are for the 64-bit imager build of
firmware 9.31 unless stated; app claims are for app 3.3.2.

## Endpoints

Basis: static analysis of firmware 9.31 / app 3.3.2.

| Port | Process | Camera | Label |
|---:|---|---|---|
| 4800 | imager, main process | main (telescope) camera | READ (process), INFERRED (camera) |
| 4804 | imager, process 2 (wide/auxiliary) | wide camera | READ (process), INFERRED (camera) |

R1. Both ports are served by the same handler class and dispatch table. READ. The camera split
is INFERRED from the app: its 4800 manager is flagged as telephoto and its 4804 manager as not
telephoto (READ).

R2. In `REMOTE` mode the app reaches 4800 and 4804 through the second tunnel session on the same
local port numbers. READ. See [ports.md: Remote tunnel port mapping](../transport/ports.md#remote-tunnel-port-mapping).

## Requests

### Grammar

Requests are JSON objects, one per line, as on 4700. READ.

```abnf
request-line = json-object line-end
line-end     = CRLF / CR / LF      ; device accepts CR or LF; app sends CRLF
json-object  = <JSON object with members "id" and "method", optional "params">
```

R3. A client SHOULD terminate each request with CRLF. READ (app behaviour).

R4. A client MUST send `method` as a JSON string from [Registered methods](#registered-methods). An unrecognised method gets an error
reply ([Reply framing](#reply-framing), text, dataType 1) reading `unknown mothod` (spelled so) with the request id. A
malformed request gets an error reply with id 0 and one of the texts `can't parse`, `invalid
method type`, `invalid id type`, `can't find method field` or `can't find id field`. READ. The
same holds on 4801. READ. These are the same texts the guider image server uses
([guider R1a](../guider/index.md#endpoints)).

R4a. Before each handler runs, the device clears the stop-sending flag set by `stop_send` (R12).
READ.

### Registered methods

Basis: static analysis of firmware 9.31, imager image dispatch table (8 entries).

| Method | App emitter | Params sent by app | Handler behaviour | Card | Label |
|---|---|---|---|---|---|
| `test_connection` | heartbeat | none | text reply (see [files-and-album.md: Summary](files-and-album.md#summary)) | [control card](../../docs/control/methods/test_connection.md) | READ (registered) |
| `begin_streaming` | yes | none | continuous exposure only; replies `done`, then pushes one image per new preview frame ([Streaming start and stop](#streaming-start-and-stop)) | [card](../../docs/files/methods/begin_streaming.md) | READ |
| `stop_streaming` | yes | none | leaves the stream; always replies `done` ([Streaming start and stop](#streaming-start-and-stop)) | [card](../../docs/files/methods/stop_streaming.md) | READ |
| `get_current_img` | yes | none | current preview frame; optional `compress`, `img_type` (R6) | [card](../../docs/files/methods/get_current_img.md) | READ |
| `get_stacked_img` | yes | none | stacked image; JPEG in Jpg mode, else zip-compressed raw (R6a) | [card](../../docs/files/methods/get_stacked_img.md) | READ |
| `get_photometry_img` | yes | none | photometry image; same encoding rule as `get_stacked_img` (R6a) | [card](../../docs/files/methods/get_photometry_img.md) | READ |
| `get_camera_img` | none found | n/a | params not read; sends the current camera image as uncompressed raw, or a text error | [card](../../docs/files/methods/get_camera_img.md) | READ |
| `get_auto_focus_img` | none found | n/a | params not read; uncompressed raw | [card](../../docs/files/methods/get_auto_focus_img.md) | READ |

R5. The app sends `begin_streaming`, `stop_streaming`, `get_current_img`, `get_stacked_img` and
`get_photometry_img` with no `params` member. READ. Of these, only `get_current_img` reads
`params` (R6). A client SHOULD omit `params` for the others.

R6. `get_current_img` returns the current preview frame. It accepts optional `compress`
(boolean, default true) and `img_type`; `img_type` `"Raw"` forces raw output. READ. Without
`"Raw"`, Jpg mode (R10) returns JPEG (imgType 4). Otherwise the frame is sent raw, zip-compressed
(dataType 3) unless `compress` is false (dataType 2). READ. With no frame available it returns the
error text `there is no image now`. READ.

R6a. `get_stacked_img` returns the stacked image as JPEG in Jpg mode (error text `convert jpg
failed` if conversion fails) and otherwise always as zip-compressed raw. `get_photometry_img`
follows the same rule with the photometry image. `get_camera_img` and `get_auto_focus_img` send
uncompressed raw. READ.

R6b. Zip compression of raw output (`get_current_img` with `compress` true, and the raw path of
`get_stacked_img` and `get_photometry_img`) goes through a fixed-name scratch file on device
storage, which the device deletes before replying. JPEG conversion for these methods writes no file.
READ. These methods are therefore MUTATORs with observation-safe (tier B) effects. Because the
scratch name is fixed, two compressed raw requests served at the same time could interfere
(INFERRED); a client SHOULD NOT have more than one compressed raw request outstanding. INFERRED.

R7. `get_camera_img` sends the current camera image or the error text "there is no image now".
READ. Its error is textual, not a JSON code member.

## Reply framing

Basis: static analysis of firmware 9.31 (shared result writer) / app 3.3.2 (image socket reader).

Every reply on 4800 and 4804, text or binary, is an 80-byte header followed by the payload.
There is no trailer. READ. Multi-byte header fields are big-endian. READ. The same header is used
on 4801 ([files-and-album.md R2](files-and-album.md#endpoint)).

| Offset | Size | Field | Value or meaning | Label |
|---:|---:|---|---|---|
| 0 | 2 | magic | `0x03C3` (bytes `03 C3`) | READ |
| 2 | 2 | version | 2 (bytes `00 02`) | READ |
| 4 | 2 | header length | 80 | READ |
| 6 | 4 | payload length | unsigned 32-bit count of payload bytes after the header | READ |
| 10 | 1 | first payload byte | copy of payload byte 0 | READ |
| 11 | 1 | quirk byte | copy of the byte at index (payload length − 1) | READ |
| 12 | 1 | reserved | 0 | READ |
| 13 | 1 | imgType | 0 = 1 byte/pixel, 1 = 2 bytes/pixel, 2 and 3 = 3 bytes/pixel, 4 = JPEG, 5 = 6 bytes/pixel, 6 = binary file; text replies use 0 | READ |
| 14 | 1 | dataType | text: 0 = ok, 1 = error; binary: 2 = plain, 3 = zip-compressed | READ |
| 15 | 1 | id | low byte of the request `id` | READ |
| 16 | 2 | width | pixels | READ |
| 18 | 2 | height | pixels | READ |
| 20 | 2 | hfdX | unsigned 16-bit; default 0. The app names it hfdX; no writer was identified in a bounded search | READ (layout), INFERRED (meaning) |
| 22 | 2 | hfdY | unsigned 16-bit; default 0. The app names it hfdY; no writer was identified in a bounded search | READ (layout), INFERRED (meaning) |
| 24 | 2 | hfd | unsigned 16-bit; default 1000. For the autofocus star image it is the star HFD × 100, truncated toward zero | READ |
| 26 | 2 | canDebayer | debayer flag | READ |
| 28 | 2 | image id | signed; −1 when not set | READ |
| 30 | 50 | reserved | 0 | READ |

The first four bytes `03 C3 00 02` are the magic and version as two big-endian 16-bit fields.
Read as one little-endian 32-bit word they are `0x0200C303`, the form used for the guider image
server in [ports.md: Guider image server (4500)](../transport/ports.md#guider-image-server-4500); both describe the
same bytes. READ.

R8. A reply on 4800/4804 is not an ordinary JSON envelope. READ. A client MUST NOT assume a
`{"id":..,"result":..}` object precedes or follows the image data.

R8a. A client MUST read the 80-byte header, check the magic, then read exactly payload length
bytes; the payload length is the only delimiter. READ (app behaviour). The app treats a wrong
magic, or a payload length that is negative when read as signed, as a broken connection and
reconnects. READ. A client SHOULD do the same. INFERRED.

R8b. A client SHOULD match a reply to its request by the id byte, which holds only the low 8
bits of the request `id`. INFERRED. Pushed stream images reuse the `begin_streaming` id ([Streaming start and stop](#streaming-start-and-stop)).
READ.

R8c. A client MUST inflate a dataType 3 payload (zip) before use. READ (app behaviour; the app
skips this for one internal request id). The app stores an imgType 4 payload as `.jpg` and any
other image as `.raw`. READ. A client SHOULD ignore offsets 10 and 11 and the reserved bytes.
INFERRED.

R9. Error replies are text (imgType 0, dataType 1); the payload is the error text selected by a
numeric code inside the device. They carry no JSON `code` member. READ. The texts are listed in
[files-and-album.md R9](files-and-album.md#parameter-rules-read-handlers). A client SHOULD use
dataType, not payload length, to tell an error from data. INFERRED.

R10. `set_setting` on 4700 has an `image_transfer_mode` member
([card](../../docs/control/methods/set_setting.md)). Value 0 is named `Jpg` and value 1 `Raw`.
READ. It chooses JPEG (Jpg) or raw (Raw) output for `get_current_img`, `get_stacked_img`,
`get_photometry_img` and `begin_streaming` on 4800 and 4804. READ. The built-in default is `Raw`,
overridden by the stored configuration at start-up. READ. It does not affect RTSP
([video.md](video.md#stream-control-from-4700)). INFERRED.

R10a. The guider image server on 4500 uses the same 80-byte base header. READ. It fills the
fields behind offsets 20 to 24 from the same image-data fields as the imager, but with the guide
star: x and y in pixels at 20 and 22, and at 24 a flag that is 1 when the star HFD is positive.
It adds the star HFD × 100 at offset 30, the size of a second image (the star crop) at 26 and 28,
and a star list after the images. In the star list the first entry's third value is the HFD × 100
and further entries (multi-star guiding) carry 1000. With no locked star, x and y are −1 and
the HFD is 0. READ (64-bit build; 32-bit not checked). The full layout is in
[guider R1a](../guider/index.md#endpoints).

## Streaming start and stop

Basis: static analysis of firmware 9.31 / app 3.3.2.

```text
client                       4700 (control)                4800/4804 (image)
  |-- verified session ---------->|                               |
  |== connect =================================================>|
  |-- {"method":"begin_streaming","id":n} CRLF ----------------->|
  |<================================= header + text "done" =====|
  |<======================= header + image (id byte n), per frame|
  |   ... one image per new preview frame; heartbeat every 3000 ms
  |-- {"method":"stop_streaming","id":m} CRLF ------------------>|
  |<================================= header + text "done" =====|
  |                                                               |
  |-- stop_send ------------------>|-- aborts current 4800 write->|
```

R11. `begin_streaming` is accepted only in continuous exposure; otherwise it returns the error
text `only available for continuous exposure`. READ. On success the device registers the
connection with the request id and replies `done`. It then pushes one framed image per new
preview frame, reusing that id: JPEG in Jpg mode, otherwise uncompressed raw (dataType 2). READ.
The streaming thread waits up to 500 ms for each new frame and sends nothing without one; there
is no separate throttle. READ. The stream rate is therefore the preview frame rate. INFERRED.
Sending continues until `stop_streaming` or a write error; a connection whose write fails is
dropped from the stream. READ.

R11a. `stop_streaming` removes the calling connection from the stream and always replies `done`.
When no streaming connection remains, the streaming thread stops. READ. A client SHOULD discard
image replies that arrive before the `done`. INFERRED.

R12. `stop_send` on 4700 sets a per-process stop flag and returns 0 at once, without waiting.
READ. The flag aborts an image transfer in progress on 4800, so the payload may be shorter than
the header's payload length. READ. Large replies are written in chunks of 512 KiB; the device
waits up to 5000 ms for the socket to accept each chunk and abandons the reply after more than
five such waits time out. READ. The next request on the socket clears the flag (R4a). READ.
`stop_send` does not end `begin_streaming`; stream registrations are untouched. READ. 4804 is
served by imager process 2 (which also serves 4702), while the main process serves 4800, 4801,
4700, 4701 and 4720. READ. `stop_send` on 4700 therefore does not affect 4804. INFERRED. The app
does not send `stop_send` (READ). See the [stop_send card](../../docs/control/methods/stop_send.md).

R13. A client MUST stop a stream with `stop_streaming` on the same socket. `stop_send` is not a
substitute. A client that uses `stop_send` MUST treat the aborted reply as truncated and SHOULD
reconnect the socket, because the remaining payload bytes never arrive. INFERRED.

Stream state (device behaviour READ except where marked):

| State | Event | Next state | Action |
|---|---|---|---|
| Closed | TCP connect succeeds | Idle | start 3000 ms heartbeat |
| Idle | send `begin_streaming`, continuous exposure | Streaming | read `done`, then image replies |
| Idle | send `begin_streaming`, other mode | Idle | read error text |
| Streaming | send `stop_streaming` | Idle | read `done`; discard images before it (INFERRED) |
| Streaming | device write fails | Idle (device side) | connection dropped from stream |
| Idle, Streaming | send `get_current_img` / `get_stacked_img` / `get_photometry_img` | same | read one reply |
| any | no bytes sent for > 15000 ms | Closed | device closes socket (READ) |
| any | control host changes | Closed | app disconnects (READ) |

Firmware 9.75 note (app 3.4.0): the imager gains an image-send rate limiter, a token bucket in front
of the image sends, with `stop_streaming` now waking it. It is not controlled on the local JSON-RPC
channel but through the cloud remote-command channel, which sets a rate (65536 to 67108864 bytes per
second) and an on/off flag; the setting is written to a shared flag file that the file server also
reads. Both readers fall back to 1 MiB per second when the file is missing or invalid, and the
effective limit depends on the relay mode. Firmware 9.31 has none of this. READ. The 32-bit build has
the flag file and handler. Whether the 4800/4804 sockets are limited in direct (non-relay) use is
unresolved.

R11a. Firmware 9.75 limiter details (64-bit). READ. The range is 65536 to 67108864 bytes per
second, the default 1 MiB per second, and the bucket holds rate/20 bytes clamped to 4096..65536.
The rate is set by the cloud remote command `set_send_rate` (the cloud value is shifted left by 10,
so it is in KiB per second; values above 2097151 are rejected), by the relay handler that carries a
rate and a limit-on flag, and by the relay-mode handler; slave imagers refresh it. The HTTP file
server reads the flag file `/tmp/zwo/http_download_rate_limit` (decimal bytes per second, written
by the imager through a temporary file and rename, removed when the limit is disabled) with a 20 s
cache; an unreadable or out-of-range file gives 1 MiB per second.

R11b. Firmware 9.75: a preview setting `preview.raw_bin2` produces a 2x2-binned raw preview. The
80-byte header width, height and image type of `get_current_img`, `get_stacked_img` and
`begin_streaming` then describe the binned image, not the full frame. READ.
The setting is a boolean, default false. It applies only to raw 16-bit Bayer data (image type 1) and
48-bit RGB data (image type 5), and only when the frame has more than one column and row; the raw
frame is 2x2-averaged preserving the Bayer pattern, the RGB frame is resized to half size. The header
width and height are halved (integer floor), header bytes 20 to 23 (hfdX, hfdY) are halved, and the
image type is unchanged. If binning fails the unbinned frame is sent. It is applied on the non-JPEG
path of `get_current_img` and `get_stacked_img` and in the streaming thread that serves
`begin_streaming` (also used by the autofocus stream). READ (64-bit); the 32-bit build was not
checked. A client MUST read the dimensions from the header. That bytes 20 to 23 hold hfdX and hfdY is
INFERRED from the app's names. The FITS and JSON headers gain keys, listed in
[files-and-album.md R16b](files-and-album.md#album-methods-on-4700); the claim that the firmware
version in them comes from the OTA version record was not verified.

### Stop flag and rate limiter

Basis: static analysis of firmware 9.31 (64-bit build; 32-bit build probable) and app 3.3.2, unless a line says otherwise.

[`stop_send`](../../docs/control/methods/stop_send.md) sets a stop flag for the image sender
and returns 0 at once. It does not wait. READ. The affected service is INFERRED to be the image
send port. Firmware 9.75: it also wakes the image sender's rate limiter so a waiting sender stops
at once. READ.

## Readiness gating and liveness

Basis: static analysis of app 3.3.2 (socket managers) and firmware 9.31 (socket worker).

R14. The app requests 4800 and 4804 right after 4700, but defers while 4700 is not connected and
retries every 3000 ms. READ. A client MUST open 4700 and complete the handshake before relying
on the image sockets. INFERRED (see [ports.md R6](../transport/ports.md#client-connection-order-and-readiness)).

R15. The app uses a 10000 ms connect timeout and UTF-8 text. READ.

R16. The app sends `{"method": "test_connection", "id": 1}` CRLF every 3000 ms on each image
socket. READ. The device closes an external client after more than 15000 ms without received
bytes. READ. A client MUST send something at least every 15 s and SHOULD use 3000 ms.

R17. The app disconnects an image socket when the control host address changes, and discards
callbacks from a socket whose configured host differs from the current control host. READ. A
client SHOULD open 4800 and 4804 to the same host as 4700.

R18. No challenge-response applies on 4800 or 4804, and the device performs no other client
authentication or verification on them. READ. Firmware 9.75: client authentication is a per-port
property that is true only for 4040, 4400 and 4700 to 4702, and only when `secure_communication` is
on (64-bit; the 32-bit build decides by port only); it is false for 4800, 4801, 4804 and 4500, so
this rule still holds. See [secure-communication.md](../control/secure-communication.md).

## Open questions

- Header bytes 20 to 25: settled in [Reply framing](#reply-framing) (hfdX, hfdY, hfd). The meaning of hfdX and hfdY
  is INFERRED from the app's names only.
- 4500 payload layout: settled in R10a and [guider R1a](../guider/index.md#endpoints).
- That `stop_send` on 4700 has no effect on 4804 is INFERRED from the process split; not
  confirmed.

## Appendix: How to validate on a live device (non-normative)

- Open 4700, verify, open 4800. Send `get_current_img`; check the 80-byte header against [Reply framing](#reply-framing).
- In continuous exposure send `begin_streaming`; compare image cadence with the preview frame
  rate; send `stop_streaming` and check that images stop after `done`.
- Send `stop_send` on 4700 during a large `get_current_img` transfer; check for a truncated
  payload and that a stream on 4804 continues.
- Repeat on 4804 with the wide camera active.
