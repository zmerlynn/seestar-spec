# Cloud auth: device cloud link and remote commands

Part of [Cloud authentication and relay authorization](../cloud-auth.md). This file describes how
the device itself talks to the vendor's cloud: the MQTT link, the remote commands that arrive on it,
the status the device reports back, the `remote_*` RPCs that set the link up, and the P2P monitor
timers. The ZWO HTTP side that a client uses is in [http-api.md](http-api.md); the SDK start that
a `p2p_init` command triggers is in [sdk-licence.md](sdk-licence.md#device-side-sdk-start). Requirement numbers continue the R46 series of that file.

Basis: static analysis of the 64-bit imager of firmware 9.31 and 9.75. The 32-bit imager was checked for
symbol and string presence only (stated per item). Statements are tagged "firmware 9.31" or "firmware
9.75"; an untagged statement holds for both. Nothing was run on a device and no server was contacted.

## Transport

R46d. The device keeps an MQTT session to the vendor's IoT platform and exchanges JSON messages
over it. READ (both versions).
- Session parameters: clean session, a maximum in-flight window of 65535, and a keepalive of 60 s.
  The keepalive is READ as a configuration value; its key number is INFERRED from the platform
  SDK's enumeration. TLS is used when the configured port string contains the secure MQTT port
  number (8883), otherwise a plain TCP connection. The client identifier has the form
  device identifier, `_0_`, an authentication-mode digit and a timestamp.
- The broker address and port, the product key, the device name and the device secret are per-device
  inputs supplied by the `remote_join` request ([The remote_* RPCs](#the-remote_-rpcs)). They are not constants. A fixed vendor
  platform endpoint host name (carrying an instance identifier) is also present in read-only data in
  both versions; it is a vendor cloud host, not a crash-report server. The instance identifier is not
  reproduced here.
- Downlink: the device subscribes with QoS 1 to the platform's per-device system-message topic
  (`$oc/devices/<deviceId>/sys/messages/down`). Each downlink message is JSON dispatched as in [Remote commands](#remote-commands).
- Firmware 9.75 adds a duplicate filter on the downlink message's `message_id`: a message whose
  identifier was already seen is ignored and logged. READ. Firmware 9.31 had no filter, so a
  redelivered message would be handled twice. A stand-in cloud MUST NOT rely on redelivery of the same `message_id`
  being processed.
- Uplink: the device reports attributes through the platform's message-data report with the service
  names `updateP2PStatus` (member `p2pId`) and `attribute/update`. It also reports the OTA version and an
  OTA status (`success` or `failed`) through the same client. READ.
- The 32-bit build has the same strings and symbols (the duplicate-message text among them). Its logic was not diffed.

## The remote_* RPCs

These control-port methods start and stop the device's membership of the cloud link. They are
unchanged between firmware 9.31 and 9.75 in logic (READ; code sizes differ only by compilation). Their
cards are [remote_join](../../../docs/control/methods/remote_join.md),
[remote_disjoin](../../../docs/control/methods/remote_disjoin.md) and
[remote_disconnect](../../../docs/control/methods/remote_disconnect.md); the enrolment flow is in
[network.md](../../control/network.md#remote-access-enrolment).

R46e. `remote_join`. An optional `timeout_sec` (integer, default 2 s) bounds the wait; a non-integer value gives error
104. The credential members `host`, `port`, `productKey`, `deviceName` and `deviceSecret` are parsed
first; a parse failure gives 259. The device then calls its join routine with the timeout converted to
milliseconds; a nonzero result gives 207. On success it stores the request in the remote-join file, logs the
join, broadcasts the joined state as true and replies with a bare success. READ.

R46f. Connect and leave behaviour (READ). The join routine's wait polls every 100 ms for up to
`timeout_ms/100` tries (with a minimum of 1000 ms) and still returns success when the wait expires, so a short
timeout does not by itself fail the RPC. Leaving the network (used by `remote_disjoin`) stops the P2P server,
then reports the join status `join_remove` as the device's IoT status, then disconnects from the cloud.
`remote_disjoin` then broadcasts the joined state as false and a failure of the leave step gives 207.
`remote_disconnect` stops the P2P tunnel server only and gives 207 on failure. The joined cloud link keeps its
`remote_join` file in the second case.

R46f1. Firmware 9.75: after enrolment the imager's cloud enrolment calls the OTA version-information function
before it reports the OTA version to the platform
([updater R12f](../../updater/ota-package-handling.md#ota-package-handling)). Firmware 9.31 reported the
legacy firmware version directly. READ.

## Remote commands

R46g. Every downlink message is passed to a command dispatcher that maps the message's `action` string to a
command type (READ, both versions; firmware 9.75 adds type 6 and a larger handler):

| Type | Action | Parameters |
|---:|---|---|
| 1 | log (including the `device_log_file` action; the exact action-to-type mapping of log actions is INFERRED) | not traced |
| 2 | `reboot_device` | none |
| 3 | `remove` | none read |
| 5 | `set_send_rate` | `rate`, `rateLimit` (R46h) |
| 6 | relay mode (firmware 9.75 only; the action string was not recorded) | `isRelayMode` (R46i) |

Any other action is logged as an unknown remote command type and fails. Note that type 3 is `remove` and that
no "3 = set rate" form exists; the rate command is type 5.

R46h. `set_send_rate` (firmware 9.75, READ). `rate` is an integer in KiB/s (the value is shifted left 10 to
bytes per second), greater than 0 and at most 2097151. `rateLimit` is a boolean. At least one of the two is
required. Rejections are logged with these texts: rate or rateLimit required; rate must be a positive
integer in kB/s; rate exceeds the maximum; rateLimit must be a boolean; invalid rate in bytes per second. The
downstream limiter then accepts 65536 to 67108864 bytes per second ([media/image-sockets.md](../../media/image-sockets.md)).

R46i. Relay mode (firmware 9.75, READ). The command's `params` MUST be an object with a boolean `isRelayMode`;
otherwise it is refused ("isRelayMode must be bool") and fails. The device keeps two flags: the configured
`rateLimit` and the relay flag. The effective limiter state is `rateLimit AND relay`. It is applied to the image
send rate limiter and written, with the rate, to the file the HTTP file server reads
(`/tmp/zwo/http_download_rate_limit`, [updater R15](../../media/files-and-album.md#http-download-limiting-firmware-975)); if the file write fails the command rolls
back. Lifecycle: 60 s after a P2P connect the relay flag is set to whether the connection's `natMode` is `RelayMode`;
when the P2P connection drops the flag is cleared before the status of R46k is reported. The firmware 9.31 build has
no relay command and no limiter. The meaning of the process-type test and the success return value of the relay
handler were not traced. The 32-bit build has the strings and symbols; its logic was not diffed.

R46j. The P2P message handler (`p2p_message`, the downlink the cloud sends to a device) accepts these
`action` values (READ; firmware 9.75, with the 9.31 differences marked):
- `p2p_init`: members `deviceUid`, `username`, `password`, `conId`, `srcId`. Firmware 9.75 renames the licence
  override to the optional string `changSdkLicenseKey` (a non-string value fails with a log message; in firmware 9.31
  the member was `sdkLicenseKey`, [sdk-licence.md R46a](sdk-licence.md#device-side-sdk-start)) and accepts
  optional `rate` and `rateLimit`, which it dispatches as `set_send_rate` after the tunnel server has started (a dispatch
  failure is logged and does not fail `p2p_init`).
- `app_stop`: member `conId`; stops the session for that connection identifier.
- `force_stop`: stops the P2P server.
- `reboot_process`: logs and terminates the imager process with SIGKILL.
- Anything else goes to the command dispatcher of R46g, and a failure there is logged with the action and result.

## P2P status report

R46k. The device reports its P2P state to the platform as an attribute report ([Transport](#transport)). READ. Firmware 9.31
used a function of three strings; firmware 9.75 uses a single report structure. The JSON members are:
- `conId`: string, always present.
- `p2pStatus`: string, one of `initialize` (state 0), `idle` (1), `connected` (2), `occupied` (3), `recovery` (4)
  and `initFailed` (5); any other state is reported as `unknown`. The state names are the same as in firmware 9.31.
- `natMode`: string, only when non-empty (set with `connected`).
- `code`: integer, only when set. It appears only with `initFailed` and carries the return value of the tunnel server start.

A report that is identical to the previous one is not uploaded (logged as a duplicate). "Code 3" in the device logs is state 3,
`occupied`, not a `code` member.

R46l. Which event reports which state (READ, firmware 9.75): stopping the P2P server and the cloud disconnect report
`recovery`; a failed tunnel server start reports `initFailed` with `code`; a refused different-`srcId` request reports `occupied`;
a successful start reports `initialize`; the P2P connection dropping reports `idle`; and a connect reports `connected` with `natMode`.
The 32-bit build has the report symbols; the layout was not verified.

## P2P monitor and occupy timers

R46m. The P2P monitor thread counts idle ticks. If a P2P session is connected the counter resets to 0; otherwise it
increments. READ (64-bit and 32-bit builds, which agree):

| | Firmware 9.31 | Firmware 9.75 |
|---|---|---|
| Tick | 60 s | 300 s |
| Stop the P2P server at | count 30 (about 30 min) | count 12 (60 min) |
| Exit the monitor after | count above 60 | count above 24 (about 125 min) |

The 9.75 constructor arguments are 5, 12 and 24 (a 60 s wait unit multiplied by 5) where 9.31 used 60, 30 and 60.

R46n. Occupy timeout. When a request with a different `srcId` is refused as occupied, a timeout thread sleeps 65 s in
firmware 9.75 (70 s in firmware 9.31). If the stored token is unchanged, the occupied flag is still set and no session is
connected, it logs that the session is still not connected and clears the device's connected-status flag. READ (both builds).
The 65 s gate of [http-api.md: `srcId` stability and the busy window](http-api.md#srcid-stability-and-the-busy-window) is the same value;
that both are one mechanism is INFERRED. The larger thread body in 9.75 is string-optimisation inlining only.
