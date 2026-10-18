# Control session: connection, framing, envelopes and verification

This chapter specifies the JSON control stream on TCP 4700 of the main imager process: how a
connection is admitted, how lines are framed, the request and reply envelopes, the dispatcher,
client verification, guest/master roles, heartbeats and ordering. Below it sits either a plain
LAN TCP connection or a forwarded tunnel channel ([transport](../transport/),
[LAN discovery](../transport/lan-discovery.md)). Above it sit the per-method cards
(`docs/<service>/methods/`), the event stream ([events overview](events-overview.md)) and the
error codes ([errors](errors.md)). [Plan scheduling](plan-scheduling.md) is one worked feature.

## Conventions

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119 and RFC 8174. They bind
clients. Sentences that say what "the device" does are descriptions, not obligations.

Labels follow `CONVENTIONS.md`: **READ** (seen in firmware 9.31 or app 3.3.2 by static
analysis), **OBSERVED** (seen on a device, date given; the live build was never matched to 9.31),
**INFERRED**, **unresolved**. "Firmware" means bundled 9.31; the 64-bit imager build is the
reference and the 32-bit build is corroborating unless stated. "The app" means Android 3.3.2;
iOS behaviour is only what was OBSERVED.

Basis: static analysis of firmware 9.31 (the imager common socket server and dispatcher)
and app 3.3.2 (control socket, verification and initialization actions), plus wire
observations of 2026-10-12.

Firmware 9.75 (app 3.4.0) was read statically for the verification step only. Its framing,
envelopes and dispatcher are unchanged; what changed is that verification is configurable on the
64-bit builds, the `verify_client` success reply carries a key envelope and a few Wi-Fi password
fields are encrypted. Those deltas are in the verification part and in
[secure communication](secure-communication.md). Unless a sentence names firmware 9.75, this
chapter describes firmware 9.31.

## Endpoints

| Port | Server | Role | Label |
|---|---|---|---|
| TCP 4700 | main imager | Control requests, replies and the default event stream. | READ |
| TCP 4701 | main imager, secondary server | Separate request/reply server with its own connection map and the same method table as 4700. Not a subscription to the 4700 broadcast. | READ |
| TCP 4702 | auxiliary (wide-camera) imager process | That process's own control/event server. Its events are forwarded onto 4700 by the main process. | READ |
| TCP 4400 | guider process | Guider command/event server. Reached directly, or through the 4700 relay ([Relay of unknown methods to the guider](#relay-of-unknown-methods-to-the-guider)). | READ |
| UDP 4720 | main imager | UDP JSON server for LAN discovery ([LAN discovery](../transport/lan-discovery.md)). | READ |
| TCP 4030, 4040 | guider process | Serial-to-network bridge (4030) and its JSON control server (4040). Not needed by a control client. | READ |
| TCP 4500 | guider process | Guide-camera image server ([ports](../transport/ports.md)). | READ |

R1. The same common server code serves 4700, 4701, 4702 and the guider's 4400. Framing,
envelopes, verification, guest/master and the idle clock in this chapter apply to each of them
unless a section says otherwise. READ.

R1a. Per-port differences, READ:

- 4701: the guest/master restriction, the connect greeting and the close side effects do not
  apply. Framing, envelopes, verification and the idle clock do. Requests are dispatched
  directly against the main table; the guider relay is not used (INFERRED from the simplified
  input path).
- 4702: behaves like 4700 in every respect, with the same method and guest tables, in the
  auxiliary process. The main process does not listen on 4702; it connects to it as a client.
- 4400: runs in the guider process on the same common server.

The device also has the UDP discovery server on 4720 and guider-side ports 4030, 4040 and 4500.
READ. A control client does not need 4030 or 4040. INFERRED.

R2. The image/file sockets (4800, 4801, 4804) run on the same common socket worker as the
control socket, but their port is not an authentication port, so no verification is required
there; they share the idle clock of [Heartbeats and the idle clock](session-handshake/liveness-and-ordering.md#heartbeats-and-the-idle-clock) and use their own binary output framing. The
updater (4350, 4361), HTTP and RTSP use separate serving paths. This chapter describes only the
control sockets. READ.

## Connection lifecycle

```text
  TCP accept
     |
     v
  insert into connection map ---- distinct external IPs > limit? --yes--> Alert 429, close
     |no
     v
  Version greeting (to this socket only)
     |
     v
  UNVERIFIED --(get_verify_str, verify_client ok)--> VERIFIED   (9.75: resets state, adds key envelope)
     |                                                   |
     |  ordinary requests silently consumed              |  ordinary dispatch (main or guest table)
     v                                                   v
  idle > 15 s with no received bytes  ----------------> close
```

R3. **Admission.** The device accepts the TCP connection at once; accept does not wait for
verification. READ. Internal connections are those whose source address equals the first
address the device resolves for `localhost` (an exact string match, not a loopback range).
Every other connection is external. READ.

R4. **Connection limit.** After inserting the new socket, the device counts distinct external
source-IP strings among the retained connections of that server, verified or not. Internal
connections count zero; several sockets from one IP count once. The maximum is 2 with guest
mode off and 8 with guest mode on. If the count exceeds the maximum, the device attempts to
send this event to the new socket only and then closes it (READ):

```json
{"Event":"Alert","Timestamp":"1234.123456789","code":429,"Type":"error","Msg":"Exceed the maximum number of connections"}
```

Existing sockets are kept. Delivery of the Alert is not guaranteed. The 429 code appears only in
this event, never in an RPC reply. READ. A client that reads EOF right after connecting SHOULD
treat it as a possible connection-limit rejection. See
[Alert](../../docs/control/events/Alert.md).

R5. **Greeting.** On arrival the device sends a `Version` event to the arriving socket only.
The imager form carries `name`, `firmware_ver_int`, `firmware_ver_string` and `is_verified`,
plus downgrade members on some models. Firmware 9.75 adds `main_version` and
`modules[{name, version}]` from the update manifest when present (the presence condition is
INFERRED); framing is unchanged. READ. Its order relative to the client's first request
is not established, and the greeting says nothing about the verification gate. A client MUST NOT
wait for it before sending. INFERRED. On TCP 4350 the updater greeting (name only) was OBSERVED
(2026-10-12). OBSERVED (2026-10-17), firmware 9.75: across four separate 4700 connections (one
official app, three passive), no `Version` event reached the client before its first request;
the app's own first reply (to `get_verify_str`) took 3.37 s to arrive and was the first bytes
seen on that socket. This does not separate "no greeting on this path" from "greeting sent but
not before the first request"; both remain open. See
[Version](../../docs/control/events/Version.md).

R6. **Close.** Either side may close at any time. The device has no request-level reply on EOF;
an unterminated trailing line is discarded ([Line framing](#line-framing)). READ.

## Line framing

Both directions carry one JSON text per physical line. There is no length prefix. READ.

**Device to client.** Before sending a reply or event the device deletes every LF byte from the
serialized text, keeps CR bytes, and appends CR LF. READ. JSON serialization does not put raw
newlines inside strings, so in practice each message is exactly one line ending in CR LF.

**Client to device.** The device reads in chunks of 1024 bytes and accumulates partial input
across reads. READ. Rules:

- Either CR or LF ends a line, independently. CR LF therefore produces a line and an empty line.
- A line of four bytes or fewer is ignored. This drops the empty lines above.
- Several complete lines in one read are all processed, in order.
- Unterminated input is never dispatched, even at EOF.
- The completion buffer keeps at most 2 097 151 bytes per line. Excess bytes are discarded with
  no error and no close; the next line ending dispatches the truncated prefix.
- Bytes above 0x7F inside strings are copied without UTF-8 validation.

R7. A client MUST send each request (or each batch array) on one physical line, with no raw CR
or LF inside it. A pretty-printed request is split at its newlines and fails to parse. READ.

R8. A client SHOULD end each line with CR LF, as the app does. A bare LF or bare CR is also
accepted. READ.

R9. A client MUST keep each line well under 2 MiB. INFERRED from the clipping rule (READ).

R10. A client MUST accept CR LF line endings and SHOULD also tolerate a bare LF. It MUST split the
received byte stream on line endings, not on TCP segment or read boundaries: one read can carry
several messages or part of one. INFERRED.

```abnf
; Client-to-device stream as the device parses it (READ).
c2d-stream   = *( c2d-line / short-line ) [ partial ]
c2d-line     = 5*line-octet line-end          ; dispatched
short-line   = 0*4line-octet line-end         ; ignored
line-end     = CR / LF                        ; each one ends a line
partial      = 1*line-octet                   ; never dispatched
line-octet   = %x00-09 / %x0B-0C / %x0E-FF    ; any octet except CR and LF

; What a conforming client sends (R7, R8).
client-line  = json-text CRLF                 ; json-text: RFC 8259, no raw CR or LF

; Device-to-client stream (READ).
d2c-stream   = *d2c-line
d2c-line     = d2c-text CRLF
d2c-text     = *( %x00-09 / %x0B-FF )         ; serialized JSON with all LF removed
```

## Request envelope

```json
{"id":17,"method":"test_connection"}
{"id":18,"method":"get_device_state","params":{"keys":["client"]}}
```

| Member | Rule | Label |
|---|---|---|
| `id` | Required. Any JSON type is accepted and echoed as parsed. A missing `id` gets code 200. Zero, negative, string, null, boolean and composite ids are all treated as real requests, not notifications. | READ |
| `method` | Required string. A missing or non-string `method` gets code 100. Names are matched exactly (case-sensitive). | READ |
| `params` | Optional. Each handler decides what it accepts (object, positional array, or none). | READ |
| `jsonrpc` | Optional and ignored. The app does not send it. | READ |

R11. A client MUST include `id` in every request. It SHOULD use integers or strings and SHOULD
keep ids unique among its outstanding requests: the device does not deduplicate reused ids, and
replies are matched only by `id`. READ / INFERRED. The id type tolerance in the table above applies to the
common main-command dispatch only; the image/file socket handlers separately require integer
ids. READ.

R12. With duplicate members the device uses the last `id`, the last `params`, and the last
string-valued `method`; a later `"method":null` does not replace an earlier string. A client
MUST NOT send duplicate members. READ.
Firmware 9.75, control port 4700: both the last-string-method rule and the null clause were OBSERVED on the wire (2026-10-17, read-only getters). Other ports, a trailing method that is neither a string nor null, and duplicate `id` or `params` were not tested.

R13. Integers are stored as signed 32-bit values and reals with 32-bit float precision. A
client SHOULD keep numbers within those ranges. READ. The device does not reject out-of-range
numbers. Integers outside the signed 32-bit range wrap silently, and reals are rounded to 32-bit
float precision. READ. Very large reals may become infinite. INFERRED. A client MUST keep
integers within the signed 32-bit range.

R14. **Batches.** A JSON array of requests on one line is a batch. A verified client gets a
reply array, including error elements for members without an id. READ. Unknown methods inside
a batch are not guaranteed to reach the guider relay ([Relay of unknown methods to the guider](#relay-of-unknown-methods-to-the-guider)). READ. Batches from an
unverified external client are consumed silently. READ. The app does not send batches
(INFERRED); a client SHOULD send single requests.

## Reply envelope

Success:

```json
{"jsonrpc":"2.0","Timestamp":"1234.123456789","method":"test_connection","result":"server connected!","code":0,"id":17}
```

Failure:

```json
{"jsonrpc":"2.0","Timestamp":"1234.123456789","method":"get_solve_result","error":"no solve data","code":215,"id":19}
```

| Member | Presence | Meaning | Label |
|---|---|---|---|
| `jsonrpc` | Normally present | Always `"2.0"`. Added by the socket layer, not the handler. | READ; OBSERVED 2026-10-12 |
| `Timestamp` | Normally present | String `<seconds>.<9 digits>` read from clock id 1 (READ). That id is `CLOCK_MONOTONIC` on Linux, so the value is not wall-clock or Unix time (INFERRED). | READ; OBSERVED (format) |
| `method` | Present except on early dispatcher errors | The request's method, echoed. | READ |
| `result` | Success only | Any JSON type; method-specific. | READ |
| `error` | Failure only | A flat string from the error table. Never an object. | READ |
| `code` | Normally present | Integer. 0 means accepted; nonzero is an error code. | READ |
| `id` | Always | The request id, echoed with its JSON type (integer stays integer, string stays string). `null` on early dispatcher errors. | READ; OBSERVED |

R15. Member order OBSERVED (2026-10-12): `jsonrpc`, `Timestamp`, `method`, `result` or `error`,
`code`, `id`. A receiver MUST NOT depend on member order. INFERRED.

R16. A receiver MUST match replies to requests by `id` alone. It MUST NOT require `jsonrpc`,
`Timestamp` or `method`: some paths omit them (early dispatcher errors; a `stop_func` relay
failure; see [errors](errors.md)). READ.

R17. `code` 0 means the device accepted the request, not that a long operation finished.
Completion is reported by events. READ. A receiver SHOULD treat a reply with neither `result`
nor `code` as "accepted with no data" (a few handlers produce such metadata-only replies). READ /
INFERRED. Exceptions to "result xor error" are listed in [errors](errors.md#replies-with-extra-or-missing-members).

R18. Replies and events share the stream. An event has `Event` and `Timestamp`; a reply has
`id` and no `Event`. A receiver MUST classify a line as an event when it has an `Event` member,
not by the absence of `id`: the envelope adds no `id`, but some events carry an event-specific
`id` member (for example the sequence id of `Sequence`). READ.

## Dispatcher

### Processing order for one line

```text
line ──> JSON parse ──fail──> reply 101 (parser text)           [even when unverified]
           │ok
           v
        auth preprocessor ── get_verify_str / verify_client ──> dedicated reply
           │ other request
           ├── unverified external, factory mode off ──> consumed, no reply, no close
           v
        table selection (guest or main, see Guest and master)
           v
        no id ──> 200, id null, no method
        no string method ──> 100, id null, no method
        name not in table ──> 103 ──(main table, relay enabled)──> guider relay (7.4)
        handler ──> result or error
```

R19. The early errors are READ:

| Condition | code | `error` | `id` | `method` member |
|---|---|---|---|---|
| Line is not valid JSON | 101 | parser explanation (not necessarily `parse failed`) | `null` | absent |
| No `id`, or empty request | 200 | `invalid id` | `null` | absent |
| `id` present, no string `method` | 100 | `invalid request` | `null` | absent |
| `method` not registered in the selected table, no relay | 103 | `method not found` | echoed | present |

R20. Registration only means the name is recognised. Parameter validation belongs to each
handler, and a recognised name says nothing about authorization or success. READ.

### Method tables

The main imager table registers 269 names (64-bit build) or 264 (32-bit build). The guest table
registers five names served by guest handlers. Two names, `get_verify_str` and
`verify_client`, are matched by the auth preprocessor before any table. READ. Per-method
detail: `docs/control/methods/`.

### Handler replies

A handler writes `result` with `code` 0, or `error` with a nonzero `code`. A handler error with
no specific code becomes 207 `fail to operate`. READ. See [errors](errors.md).

### Relay of unknown methods to the guider

R21. On the main imager (not the auxiliary process), when the main table has no handler for a
name, the device passes the **original request text** to the guider on TCP 4400 and waits up to
10 000 ms. The guider's reply text is sent back as the reply unchanged, without parsing. READ. So a client can
reach guider methods such as `scope_goto`, `scope_park` or `pi_set_time` through 4700. READ.

R22. The relay is disabled for clients served from the guest table ([Guest and master](session-handshake/verification-and-roles.md#guest-and-master)). Such clients
get 103 for guider names. READ.

R23. Relay timeout, refused connection and a malformed guider reply are specified in
[mount-and-motion.md R3](mount-and-motion.md#where-a-call-is-executed). A relayed request can also trigger a guider reconnect that re-sends
mount speed and LED settings, so even a guider getter is not side-effect free when relayed.

R23a. Firmware 9.75: the main imager's check before relaying a request to the second-camera
(slave) process asks it `is_func_work ["AviRecord","MotionMonitor"]` and returns 524 if either is
running; the existing mount-occupied check (203) is unchanged. READ. The full conditions and
the callers are in [session dispatch R31a](session-handshake/relay-routing.md#second-camera-relay-routing) and the mount chapters. Closing a connection invalidates its
crypto session ([secure communication](secure-communication.md)). READ.
READ.

R24. A client SHOULD allow at least 10 s for a reply to a relayed method. INFERRED.

### Connectivity helpers

Many methods ignore `params` entirely. For them, any `params` value, or none, behaves the same. READ. A client SHOULD omit `params` for these methods.

Basis: static analysis of firmware 9.31 (64-bit build; 32-bit build probable) and app 3.3.2, unless a line says otherwise.

[`test_connection`](../../docs/control/methods/test_connection.md) returns the string
`"server connected!"`. It is pure. The app sends it as a heartbeat; an OTA control channel sends
it every 4000 ms. READ. A client MAY use it as a keep-alive.

[`get_phone_list`](../../docs/control/methods/get_phone_list.md) returns
`[{ip, support_socks5}]`. It is pure. READ. The entries are the connected client devices.
INFERRED.

## Further sections

The chapter continues in three files; requirement numbers continue across them:

- [Second-camera relay routing](session-handshake/relay-routing.md#second-camera-relay-routing): dispatcher relay of second-camera requests (R31a).
- [Verification and roles](session-handshake/verification-and-roles.md): [Client verification](session-handshake/verification-and-roles.md#client-verification)
  (R25 to R34) and [Guest and master](session-handshake/verification-and-roles.md#guest-and-master) (R35 to R39).
- [Liveness and ordering](session-handshake/liveness-and-ordering.md): [Heartbeats and the idle clock](session-handshake/liveness-and-ordering.md#heartbeats-and-the-idle-clock),
  [Initialization after verification](session-handshake/liveness-and-ordering.md#initialization-after-verification), [Ordering](session-handshake/liveness-and-ordering.md#ordering),
  [Message flow](session-handshake/liveness-and-ordering.md#message-flow), [Secondary servers 4701 and 4702](session-handshake/liveness-and-ordering.md#secondary-servers-4701-and-4702),
  [Open questions](session-handshake/liveness-and-ordering.md#open-questions) and the live-validation appendix.

Related chapter, with its own requirement numbering:

- [Secure communication](secure-communication.md): the firmware 9.75 key envelope, the enforcement
  switch and the encrypted Wi-Fi fields (R1 to R26 of that chapter).
