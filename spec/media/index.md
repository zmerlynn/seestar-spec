# Media channels

This chapter covers the channels that carry images, files and video rather than control: the
image sockets 4800/4804, the album/file socket 4801, HTTP 80, RTSP 4554/4555 and the
RTMP/AVI functions. Ports, connection order and the remote tunnel map are in
[ports.md](../transport/ports.md). The control stream and its handshake are in
[session-handshake.md](../control/session-handshake.md); events are in the
[events chapter](../control/events-overview.md).

## Conventions

MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119 and RFC 8174. Sentences about what "the
device" or "the app" does are descriptions, not requirements.

Labels follow `CONVENTIONS.md`: **READ** (static analysis of firmware 9.31 or app 3.3.2),
**OBSERVED** (date given), **INFERRED**, **unresolved**. READ claims are for the 64-bit imager
build unless stated. No code was executed and no device was contacted for this chapter.

Files in this chapter:

| File | Covers |
|---|---|
| [image-sockets.md](image-sockets.md) | 4800/4804 image stream: request names, reply framing, streaming start/stop, readiness gating |
| [files-and-album.md](files-and-album.md) | 4801 album/file socket, file endpoints, album methods on 4700, HTTP 80 |
| [video.md](video.md) | RTSP 4554/4555, RTMP pipeline, AVI recording and playback |
| [smb.md](smb.md) | SMB file sharing on 445 (not used by the app) |

## Channel overview

Basis: static analysis of firmware 9.31 / app 3.3.2, with firmware 9.75 / app 3.4.0 deltas tagged. The BLE daemon is byte-identical across the two versions.

| Channel | Port | Served by | Request form | Reply form | Catalog service | Label |
|---|---:|---|---|---|---|---|
| Main image socket | 4800/TCP | imager, main process | JSON line, CRLF | binary or text per method | files | READ |
| Wide image socket | 4804/TCP | imager, process 2 | JSON line, CRLF | binary or text per method | files | READ |
| Album/file socket | 4801/TCP | imager, main process | JSON line, CRLF | binary or text per method | files | READ |
| HTTP album/FITS | 80/TCP | HTTP file server (separate process) | HTTP GET; upload routes | HTTP | none | READ |
| RTSP main | 4554/TCP | imager, main process (while streaming) | RTSP (`rtsp://` URL) | RTP over interleaved TCP or UDP | video (no entries) | READ |
| RTSP wide | 4555/TCP | auxiliary imager, S30 Plus-class only | RTSP (`rtsp://` URL) | RTP over interleaved TCP or UDP | video (no entries) | READ |
| SMB file share | 445/TCP | Samba (base system) | SMB (SMB1 disabled) | SMB | none | READ (start), OBSERVED |
| Control-side media methods | 4700/TCP | imager | JSON-RPC | JSON envelope | control | READ |
| Media events | 4700 (and 4702 relayed) | imager | n/a | JSON events | control | READ |

R1. 4800, 4804 and 4801 are not event channels. They carry no `Event` objects. READ (see
[envelope.md](../control/events/envelope.md)).

R2. Replies on 4800, 4804 and 4801 are not ordinary JSON result envelopes. A client MUST NOT
parse them as such. READ. Every reply is an 80-byte big-endian header followed by the payload
([image-sockets.md: Reply framing](image-sockets.md#reply-framing)). READ.

R3. 4800, 4804 and 4801 are outside the client-auth port set. There is no challenge-response on
them, and they perform no other client authentication or verification; those checks run only
on 4040, 4400 and 4700 to 4702. READ. A client SHOULD still complete the 4700 handshake first, because the app gates the
image sockets on the control socket (INFERRED requirement; app behaviour READ).

R4. The device closes an external client on 4800, 4804 or 4801 after more than 15000 ms
without received bytes. READ. A client MUST send at least one request (for example the
`test_connection` heartbeat) within every 15 s on each open media socket.

## Which catalog service documents what

| Material | Catalog service | Notes | Label |
|---|---|---|---|
| Image socket methods (4800/4804) | `files` | Registration and handler behaviour READ | READ |
| File socket methods (4801) | `files` | Seven firmware cards with READ params; three APK-side cards | READ |
| `test_connection` heartbeat on media sockets | `control` card | The same name is registered on every socket table | READ |
| `stop_send`, album methods, `fits_to_jpg` | `control` | Sent on 4700 | READ |
| `start_record_avi`, `stop_record_avi`, `start_avi_rtmp`, `stop_avi_rtmp` | `control` | Sent on 4700 | READ |
| RTSP stream | `video` | No entries; RTSP is not JSON | READ |
| [`RTSP`](../../docs/control/events/RTSP.md), [`AviRecord`](../../docs/control/events/AviRecord.md), [`AviRtmp`](../../docs/control/events/AviRtmp.md), [`SaveImage`](../../docs/control/events/SaveImage.md) events | `control` events | Sent on 4700 | READ |

R5. A method name is unique across the catalog. The guider's own image server (port 4500)
registers `test_connection`, `begin_streaming` and `stop_streaming` too. The `files` cards
describe the imager tables only. READ.

## Method registration summary

Basis: static analysis of firmware 9.31 (imager dispatch tables, 64-bit and 32-bit builds).

| Method | 4800/4804 table | 4801 table | 32-bit build | Card |
|---|:-:|:-:|:-:|---|
| `test_connection` | yes | yes | yes | [control](../../docs/control/methods/test_connection.md) |
| `get_current_img` | yes | | yes | [files](../../docs/files/methods/get_current_img.md) |
| `get_camera_img` | yes | | yes | [files](../../docs/files/methods/get_camera_img.md) |
| `begin_streaming` | yes | | yes | [files](../../docs/files/methods/begin_streaming.md) |
| `stop_streaming` | yes | | yes | [files](../../docs/files/methods/stop_streaming.md) |
| `get_stacked_img` | yes | | yes | [files](../../docs/files/methods/get_stacked_img.md) |
| `get_auto_focus_img` | yes | | yes | [files](../../docs/files/methods/get_auto_focus_img.md) |
| `get_photometry_img` | yes | | yes | [files](../../docs/files/methods/get_photometry_img.md) |
| `get_img_page_thumbnail` | | yes | yes | [files](../../docs/files/methods/get_img_page_thumbnail.md) |
| `get_batch_stack_thumbnail` | | yes | yes | [files](../../docs/files/methods/get_batch_stack_thumbnail.md) |
| `get_img_file_in_jpg` | | yes | yes | [files](../../docs/files/methods/get_img_file_in_jpg.md) |
| `get_img_file` | | yes | yes | [files](../../docs/files/methods/get_img_file.md) |
| `get_fits_file` | | yes | yes | [files](../../docs/files/methods/get_fits_file.md) |
| `get_img_thumbnail` | | yes | yes | [files](../../docs/files/methods/get_img_thumbnail.md) |
| `get_server_log` | | yes | yes | [files](../../docs/files/methods/get_server_log.md) |
| `get_user_log` | | yes | yes | [files](../../docs/files/methods/get_user_log.md) |

"yes" means the name is in that table. READ. All sixteen names are also registered in the
32-bit build's image and file tables. READ.

## Open questions

None at the chapter level. The serving processes are answered in the chapter files: RTSP
4554/4555 by the imager ([video.md R3](video.md#rtsp-endpoints)) and HTTP 80 by a separate
HTTP file server process ([files-and-album.md R19](files-and-album.md#http-80)). Per-file open
questions are listed in each file.

## Appendix: How to validate on a live device (non-normative)

- Connect 4700 and verify, then open 4800. Send the `test_connection` heartbeat and confirm the
  socket stays open past 15 s.
- Request `get_current_img` and check the first 80 bytes of the reply against the header table.
- Repeat on 4804 and 4801. Compare the reply prefixes.
