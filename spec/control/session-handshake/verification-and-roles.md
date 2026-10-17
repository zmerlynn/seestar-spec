# Control session: verification, guest and master

Part of the [session handshake](../session-handshake.md) chapter. It specifies client
verification (`get_verify_str` / `verify_client`) and the guest/master roles on the JSON control
servers. Below it are the connection, framing and envelope rules of the
[main chapter](../session-handshake.md); beside it are
[liveness and ordering](liveness-and-ordering.md). Labels and RFC 2119 usage follow
[Conventions](../session-handshake.md#conventions) of the main chapter. Basis: static analysis of
firmware 9.31 and app 3.3.2; wire observations of 2026-10-12. Firmware 9.75 (app 3.4.0) deltas
are static analysis only and are marked "firmware 9.75"; the layer they belong to is specified in
[secure communication](../secure-communication.md).

## Client verification

### Exchange

```text
{"id":N,"method":"get_verify_str"}\r\n
{"id":M,"method":"verify_client","params":{"sign":"<base64 signature>","data":"<challenge>"}}\r\n
```

1. `get_verify_str`: the device ignores params, generates a fresh 32-character challenge for
   this socket, stores it, and replies `result: {"str": "<challenge>"}` with code 0. It does not
   clear an existing verified flag. READ.
2. The client signs the challenge bytes and base64-encodes the signature with no line
   wrapping. READ (app).
3. `verify_client`: params are an object with string `sign` and optional string `data`, or the
   positional array `[sign, data]`. Extra members and array elements are ignored; with duplicate
   object members the first wins. READ. The device decodes `sign`, checks it over the `data`
   bytes (exact length, no terminator added) with its built-in RSA public key and SHA-1, and
   requires `data` to equal this socket's current challenge. On success it sets the socket's
   verified flag and replies `result: 0`, code 0. READ. PKCS#1 v1.5 padding is INFERRED from the
   default behaviour of the verification utility the device calls.

Firmware 9.75 changes steps 1 and 3 (R28a to R28c): the challenge is built from random bytes,
`get_verify_str` and `verify_client` reset the socket's verification and crypto session, and a
normal success returns `result.key_envelope` instead of `result: 0`. The statements in this
section describe firmware 9.31 unless a firmware 9.75 sentence says otherwise.

| Outcome | code | Label |
|---|---|---|
| Success, firmware 9.31 | 0, `result` 0 | READ |
| Success, firmware 9.75 | 0, `result` an object with `key_envelope` | READ |
| `sign` or `data` of the wrong type | 105 | READ |
| Missing `id` | 200, `id` null | READ |
| Bad signature, wrong or missing challenge | 207 | READ |

R25. The signature scheme authenticates the **client application**, not the user. The private
signing key is held by the official app's native code; the device holds only the public key.
Neither key is part of this specification. A client that cannot produce a valid signature cannot
use an external connection. INFERRED. The app's native signing routine, like the keys, is outside this specification.

R26. A client MUST send `data`. Omitting it makes the device verify against hardware serial
bytes instead, a factory path that can switch the whole process into factory mode; it is not
the normal handshake. READ.

R27. Verification is per socket. A challenge from one connection does not verify another, and
each new connection starts unverified. A relay MUST forward both requests and both replies on
the same upstream connection. READ / INFERRED.

R28. Firmware 9.31: a failed `verify_client` does not clear an existing verified flag, and an error reply that
is sent successfully does not by itself close the socket; a failure in the authentication
preprocessor or in sending the reply can close it. READ.

R28a. Firmware 9.75: `get_verify_str` clears the socket's verification state and replaces the
challenge, and invalidates any crypto session already attached. The challenge is the base64 of
24 random bytes (32 characters); firmware 9.31 used a pseudo-random character generator. A
client MUST treat the challenge as opaque and MUST NOT expect a socket to stay verified across a
new `get_verify_str`. READ (64-bit imager and guider; the 32-bit builds contain the same
functions with parity of every branch not established).

R28b. Firmware 9.75: a well-typed `verify_client` clears the verification state and the session
before checking the signature, so a failed attempt leaves the socket unverified. Rejection of a
mistyped `sign` or `data` (105) occurs before that reset. READ (64-bit imager).

R28c. Firmware 9.75: a normal success replies with code 0 and
`result: {"key_envelope": {...}}` ([VerifyClientResult](../../../catalog/control/schemas/VerifyClientResult.yaml),
[KeyEnvelope](../../../catalog/control/schemas/KeyEnvelope.yaml)); a client MUST NOT require
`result` to equal 0 but SHOULD accept 0 as well. Creating the session behind the envelope is a
condition of success: if it fails the reply is 207. The wrapped secret, the key derivation and what
the session protects are in [secure communication](../secure-communication.md#handshake-changes-and-the-key-envelope).
READ.

R29. The app requires code 0. If the very first `get_verify_str` gets code 103, the app treats
the device as a legacy device without verification and continues. Any other failure ends its
session. READ (app). A client SHOULD do the same.

### Enforcement

R30. Firmware 9.31, and firmware 9.75 whenever enforcement is on (R33a): while unverified, an external connection's valid requests (including getters and
`test_connection`) and whole batches are **consumed silently**: no dispatch, no reply, no close.
READ. This applies while the device's factory mode is off; factory mode bypasses the silent
consumption. READ. Factory mode was never observed. Invalid JSON still gets a 101 reply. READ. The idle clock still runs ([Heartbeats and the idle clock](liveness-and-ordering.md#heartbeats-and-the-idle-clock)), so a
silent connection is eventually closed. READ.

R31. Internal connections (exact `localhost` match, [R3](../session-handshake.md#connection-lifecycle)) are treated as verified. READ. The
Kalay tunnel daemon on the device connects over loopback, so requests arriving through the
remote tunnel are served without `verify_client`. OBSERVED 2026-10-12 (`pi_get_time`, keyed
`get_device_state` and `pi_set_time` answered with code 0 and no verification). The iOS app
still verifies on every connection, tunnel included. OBSERVED.

R32. A client MUST complete verification before any other request on a LAN connection, and
SHOULD do so on every connection. The silent-consumption behaviour of R30 is READ only; see
below for the one same-LAN observation to date.

OBSERVED (2026-10-17), firmware 9.75, LAN (not loopback, not the remote tunnel): three
unverified connections through a LAN proxy each got an ordinary code-0 dispatch —
`pi_get_time`, keyless `get_device_state`, and keyed `get_device_state {"keys":["client"]}` —
while a fourth connection (the official app, same device) verified normally. This is the first
observation of plain same-LAN use without verification, and it contradicts silent consumption
for at least these three methods on this device at this time. It does not establish whether the
device's `secure_communication` switch ([R33a](#enforcement)) was off, or whether these three
methods are specifically exempt from the gate; either would explain the result, and this sample
cannot distinguish them.

R33. Ports subject to verification: 4700, 4701, 4702, 4400 and 4040. READ (port predicate).
The guider process listens on 4040 with a small control server for its serial-to-network bridge
(setting the serial line parameters and disconnecting); the raw bridge itself listens on 4030.
READ. Both follow the common server rules; 4040 requires verification. READ. A control client
has no need to use either port. INFERRED.

R33a. Firmware 9.75, 64-bit builds: enforcement is conditional. Verification is demanded only
when the device configuration key `secure_communication` is enabled (shipped value: enabled; the
single character `0` disables it) and the port is one of the R33 ports. With it off, an external
connection is served without verification, but `get_verify_str` and `verify_client` are still
answered, and the Wi-Fi password methods still need a crypto session. The 32-bit builds have no
switch and keep the port-only rule of firmware 9.31. READ. The parity of the 32-bit builds and guiders is tabulated in [secure communication](../secure-communication.md#firmware-975-parity-matrix-32-bit-imager-and-guider). See
[secure communication](../secure-communication.md#the-configuration-switch).

R34. `pi_is_verified` reports device activation status, not this socket's verification. READ.
See [pi_is_verified](../../../docs/control/methods/pi_is_verified.md).

## Guest and master

R35. Guest mode is a device setting. With it off, at most 2 distinct external IPs may connect;
with it on, 8 ([R4](../session-handshake.md#connection-lifecycle)). READ.

R36. The device picks the method table per request. It uses the **guest table** only when all
hold: guest mode is on, a guest table exists, the client is not the master, and the connection
is external. Otherwise it uses the main table. READ. The guest table has exactly five methods:
[`get_device_state`](../../../docs/control/methods/get_device_state.md),
[`get_phone_list`](../../../docs/control/methods/get_phone_list.md),
[`set_setting`](../../../docs/control/methods/set_setting.md) (a restricted guest variant),
[`test_connection`](../../../docs/control/methods/test_connection.md) and
[`iscope_get_app_state`](../../../docs/control/methods/iscope_get_app_state.md). Every other method
returns 103 for a guest, and the guider relay is off. READ.

R37. **Master identity.** The device looks up the client's MAC address from its source IP and
groups connections by MAC: a new connection inherits the UUID of an existing same-MAC
connection. With guest mode on, the first external client becomes master; a stored MAC can
restore master status after reconnect. A client is master when its connection UUID equals the
non-empty master UUID. READ. An internal routine changes master ownership explicitly only when
guest mode is on and there is no master or an existing master, and it refuses internal
connections. READ. The app sets its identity with `set_setting` members `cli_uuid` and
`cli_name`. READ.

R37a. A client claims master status with `set_setting` `{"master_cli": true}` and releases it
with `false`. This succeeds only with guest mode on, when no master exists or the caller already
is master, and never for internal connections; the errors are 210, 300 and 200 respectively.
READ. A change of master is announced with a `Client` event. READ. A non-master client's
`set_setting` accepts only the identity members (`master_cli`, `cli_name`, `cli_uuid` and the
SOCKS5 support flag). READ. Switching guest mode itself is `set_setting` `guest_mode`
([device-state-and-settings.md](../device-state-and-settings.md) R17a). READ.

R38. A client learns its role from `get_device_state` with `{"keys":["client"]}` (member
`client.is_master`) and from [`Client`](../../../docs/control/events/Client.md) events, which list connected client names, the master
index and a per-recipient `is_master`. READ. OBSERVED (2026-10-12) on a tunnel-path session: the
`client` section came back as an empty object. OBSERVED (2026-10-17), firmware 9.75, LAN (not
tunnel): the same empty object, from a second, unverified connection, while the official app was
connected and verified elsewhere and no `Client` event had appeared in the app's first ~80 s.
The emptiness is therefore not specific to the tunnel path. A client MUST NOT rely on that
section for client enumeration.

R39. The device tracks each TCP connection separately, one entry per socket, and decides
master status by the connection UUID the client sets, not by source address. READ. Clients
behind one proxy therefore stay distinct as long as each sets its own `cli_uuid`; a client
SHOULD set a unique `cli_uuid` per connection. READ / INFERRED. Whether the address-based master
restore (R37) can misattribute master status behind a proxy is unresolved.

