# Secure communication: session key envelope and encrypted Wi-Fi fields

This chapter specifies the secure-communication layer that firmware 9.75 adds to the JSON
control servers: the configuration switch that makes client verification conditional on the
64-bit build, the key envelope returned by a successful `verify_client`, the per-connection
crypto session derived from it, and the one use the imager makes of that session, the encrypted
Wi-Fi password strings. It extends [client verification](session-handshake/verification-and-roles.md#client-verification)
and touches the [network methods](network.md) and the `ap` section of
[`get_device_state`](device-state-and-settings.md).

## Conventions

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119 and RFC 8174 and bind
clients. Labels follow `CONVENTIONS.md`.

Everything in this chapter is new in firmware 9.75 (app 3.4.0 is the matching app release).
Firmware 9.31 has no key envelope, no crypto session and no encrypted fields, and the 9.31
statements in the session-handshake chapter stay as written for that firmware. READ claims are
for the 64-bit imager build of firmware 9.75 unless a section says otherwise; [Guider](#guider) and
[32-bit builds and guider parity](#32-bit-builds-and-guider-parity) give the guider and the 32-bit builds.

Basis: static analysis of firmware 9.75 (imager and guider, 64-bit and 32-bit builds), compared
with firmware 9.31. No device running 9.75 was used to confirm any wire behaviour in this
chapter; nothing here is OBSERVED. No private key, secret or per-session value is part of this
specification.

## What is and is not protected

R1. Firmware 9.75 does not encrypt the JSON-RPC stream. Framing, request and reply envelopes,
events and every method other than the four Wi-Fi methods in [Encrypted Wi-Fi strings](#encrypted-wi-fi-strings) stay plaintext, exactly as
in [the session chapter](session-handshake.md). There is no secure record layer and no
whole-stream decrypt failure state. READ.

R2. The crypto session protects selected string fields only. In the imager the only fields that
use it are the Wi-Fi passwords of `pi_get_ap`, `pi_set_ap`, `pi_station_set` and
`get_device_state` ([Encrypted Wi-Fi strings](#encrypted-wi-fi-strings)). READ.

R3. The ports that run client verification are unchanged: 4700, 4701, 4702, 4400 and 4040.
The image/file sockets, the updater and HTTP are outside this layer. READ.

## The configuration switch

R4. On the 64-bit builds of the imager and the guider, client verification is enforced when both
hold: the `secure_communication` switch is enabled and the connection's port is one of the
verification ports (R3). In firmware 9.31 only the port test existed, so verification was always
enforced on those ports. READ.

R5. The switch is a key in the device configuration file. The shipped 9.75 64-bit configuration
sets it to 1, and the built-in default is also enabled. The single character `0` disables it;
a missing key or any other value leaves it enabled. READ. A client cannot read or change it over
the control protocol as far as the inspected methods show. INFERRED.

R6. With the switch off, an external connection is served without verification: the silent
consumption of R30 in the [verification chapter](session-handshake/verification-and-roles.md#enforcement)
does not apply. READ. This is not a return to 9.31 Wi-Fi behaviour: the Wi-Fi handlers
independently need a crypto session (R22), and a connection that skips verification has none.
READ.

R7. `get_verify_str` and `verify_client` are intercepted by the fixed port set even when the
switch is off, so a client can still complete the handshake and obtain a session on a device
with the switch off. READ (interception); the consequence for a client that probes for a legacy
device (the app treats code 103 on `get_verify_str` as "no verification", R29 of the verification
chapter) is INFERRED: such a device answers the handshake instead of returning 103.

R8. Internal (loopback) connections count as verified for dispatch whatever the switch says, but
they have no crypto session unless they ran the handshake themselves (R12). READ. Requests
reaching the device through the remote tunnel arrive over loopback, so by this rule the Wi-Fi
password operations are not usable through the tunnel without a handshake on that stream.
INFERRED.

## Handshake changes and the key envelope

The wire exchange (`get_verify_str`, then `verify_client` with `sign` and `data`) keeps its
request shapes. Failure still returns 207, wrong parameter types still 105 and a missing id 200.
No new method name and no new event exists. READ.

R9. **Challenge.** The challenge is still a 32-character string returned as `result.str`. In 9.75
the device builds it from 24 random bytes encoded as base64; firmware 9.31 drew 32 characters
from a C-library pseudo-random generator. A client MUST treat it as opaque. READ.

R10. Firmware 9.75: **Session reset.** `get_verify_str` resets the socket: the verification state is
cleared, the stored challenge is replaced and any earlier crypto session is invalidated and
detached. A well-typed `verify_client` attempt also resets the verification state and the session
before it validates the signature, so a failed attempt leaves the socket unverified rather than
keeping an earlier verified state. A parameter-type rejection (105) happens before this reset and is
a different path. READ for the 64-bit imager and guider; the 32-bit builds contain the same
functions, but parity of every failure branch was not established. A client that re-authenticates on
an open connection MUST therefore expect to lose its session and MUST unwrap the new envelope. READ.

R11. **Success reply.** A successful `verify_client` replies with code 0 and a `result` object
that holds a single member `key_envelope`, replacing the numeric `result: 0` of firmware 9.31
([KeyEnvelope](../../catalog/control/schemas/KeyEnvelope.yaml),
[VerifyClientResult](../../catalog/control/schemas/VerifyClientResult.yaml)):

```json
{"jsonrpc":"2.0","Timestamp":"1234.123456789","method":"verify_client",
 "result":{"key_envelope":{"version":1,"wrap":"RSA-OAEP-SHA256","kdf":"HKDF-SHA256",
 "cipher":"AES-128-GCM","data":"<base64>"}},"code":0,"id":2}
```

A receiver MUST NOT require `result` to equal 0 and SHOULD accept a numeric 0 as success, because
the code retains an empty-envelope branch that returns the number 0 for alternate verification
paths. That branch is not the normal challenge handshake. READ.

OBSERVED (2026-10-17), firmware 9.75, official iOS app over a LAN proxy: a live `key_envelope`
carried exactly the five members `version`, `wrap`, `kdf`, `cipher`, `data`, in that order, and
nothing else, matching the shape above. The `verify_client` reply followed `get_verify_str`'s by
0.31 s; the app's next request (`get_device_state`) followed the `verify_client` reply by 62 ms.

R12. **Session creation is part of success.** The device attaches the session and marks the socket
verified only when the session was created. If creation fails, the reply is the ordinary
authentication failure 207. A client that never uses the envelope is not affected beyond losing
the Wi-Fi password operations; the device does not close the socket for ignoring it. READ
(creation required for success); INFERRED (no close).

R13. **Wrapping.** `key_envelope.data` is the base64 of an RSA-OAEP ciphertext of a freshly
generated 48-byte random secret. READ.

| Property | Value | Label |
|---|---|---|
| Key | An RSA public key of at least 1024 bits, fixed in the firmware | READ |
| Padding | OAEP | READ |
| OAEP digest and MGF1 digest | SHA-256 | READ |
| OAEP label | the ASCII string `seestar-rpc-envelope-v1:` followed directly by the 32-character challenge of this socket | READ |
| Plaintext | 48 random bytes | READ |

R14. A fixed public RSA key is embedded in the firmware; a client needs it for interoperability
and the device uses it for the wrapping. Where the key and its fingerprint are recorded is the
business of the embedded-constants chapter ([embedded constants](../auth/cloud-auth/embedded-constants.md));
this chapter does not reproduce it. Unwrapping the ciphertext needs the matching private key,
which is not part of the firmware and not part of this specification. A client without it can
verify but cannot read or write the protected fields. INFERRED.

R15. Because the label contains the challenge, an envelope is bound to one `get_verify_str` /
`verify_client` pair; a client MUST use the challenge it signed as the label when unwrapping.
READ.

R16. **Key derivation.** The 48-byte secret splits into a 16-byte salt (bytes 0 to 15) and 32 bytes of
input key material (bytes 16 to 47). HKDF with SHA-256 produces 20 bytes for each direction:
the first 16 bytes are an AES-128 key and the last 4 are the nonce prefix of that direction.
The HKDF info string is the ASCII text `seestar-rpc-v1/`, the first context string of the field
(for the Wi-Fi fields `wifi`), the character `/`, and the direction name: `s2c` for device to
client, `c2s` for client to device. READ. Both directions therefore have separate keys, and the
keys differ by field context. This corrects a shorter form (prefix plus direction only) that
omits the context string.

## Encrypted Wi-Fi strings

### Token format

R17. A protected string is the ASCII prefix `enc1:` followed by the base64 of a binary envelope.
The longer text `seestar-rpc-envelope-v1:` is the OAEP label prefix of R13, not the prefix of a
field string. READ.

```text
offset  length  content
0       16      session identifier (taken from the first 16 bytes of a buffer the session generates at creation)
16      8       sequence number, big-endian
24      4       nonce prefix (the 4 derived bytes of the direction)
28      8       sequence number again, big-endian (nonce suffix)
36      N       AES-128-GCM ciphertext
36+N    16      GCM tag
```

R18. The AES-GCM nonce is the 12 bytes at offsets 24 to 35 (prefix then sequence). READ. The
associated data is the concatenation of: the 16 ASCII bytes `seestar-field-v1` (exactly 16 bytes, no
terminating NUL); one direction byte (0 for data the device receives, 1 for data it sends); the 36
header bytes at offsets 0 to 35; and four context strings, each as a 2-byte big-endian length
followed by the bytes, each at most 256 bytes. READ (64-bit imager); the 32-bit imager has the same
16-byte prefix boundary, but its callers' context strings were not decoded. The four context strings
of each Wi-Fi field are, in order, READ:

| Field | Context strings |
|---|---|
| `pi_get_ap` output | `wifi`, `pi_get_ap`, `passwd`, the AP SSID |
| `pi_set_ap` input | `wifi`, `pi_set_ap`, `key`, the SSID supplied in the same request |
| `pi_station_set` input | `wifi`, `pi_station_set`, `psk`, the SSID supplied in the same request |
| `get_device_state` output | `wifi`, `get_device_state`, `ap.passwd`, the AP SSID |

The string `wifi` is therefore a cipher context, not a JSON member (R22). Which exact bytes of an
SSID are used (for example after any trimming) was not decoded; a client SHOULD use the SSID
string it sends or received unchanged. INFERRED.

R19. A field is bound to its method and field context by the context strings, so a ciphertext
from one field is not valid in another even on the same connection. READ.

R20. **Limits.** The device encodes plaintext of at most 128 bytes. A token it decodes must be
non-empty, at most 512 bytes, start with exactly `enc1:`, be valid base64 whose canonical
re-encoding equals the input, and decode to between 52 and 180 bytes. READ.

R21. **Sequence numbers and replay.** The device's outbound counter increments for each encoded
field; when it is exhausted the session is invalidated. Inbound, the sequence MUST be strictly
greater than the last accepted one for that session; the watermark advances only after the tag
verifies. A client MUST use a fresh increasing sequence for each protected string it sends and
MUST NOT resend an earlier token. READ. The session identifier MUST match that of the session.
READ.

### Methods and members

R22. The imager decodes or encodes Wi-Fi strings in exactly these places. The member names of
firmware 9.31 survive and hold the token in place of the plaintext; no `wifi` object is built or
read in these paths. READ (64-bit imager); the 32-bit handlers exist and their schema parity is
unverified:

| Method | Direction | Member | Notes |
|---|---|---|---|
| [`pi_get_ap`](../../docs/control/methods/pi_get_ap.md) | device to client | `result.passwd` (a flat `{ssid, passwd}` result) | A missing or inactive session is rejected with 570. |
| [`get_device_state`](../../docs/control/methods/get_device_state.md) | device to client | `ap.passwd` | The handler selects the `ap` section (when the selection list is empty or contains `ap`). With an active session it adds the encoded `passwd`; without one it still returns the section and omits `passwd`. A real encoding failure is returned as an error reply. |
| [`pi_set_ap`](../../docs/control/methods/pi_set_ap.md) | client to device | `params.key` | Decode failure returns the wrapper code 570 to 573 (R24). |
| [`pi_station_set`](../../docs/control/methods/pi_station_set.md) | client to device | `psk` in the object selected by `params.para` | Session activity is checked first, then the token is decoded. |

Neither "every state request needs a session" nor "selecting `ap` fails without one" is correct.
A client MUST NOT send these passwords in plaintext to a device that has a session: plaintext is
rejected as invalid encrypted data (R23). Plaintext values do not survive beside the tokens: the
members hold only tokens.


### Statuses and errors

R23. The decoder and encoder report one of five statuses, and the Wi-Fi wrapper maps them to
reply codes (listed in [errors](errors.md)). READ:

| Status | Meaning | Code | Error text |
|---:|---|---:|---|
| 0 | success | 0 | none |
| 1 | session inactive (a missing session also gives this) | 570 | `encrypted session required` |
| 2 | invalid encrypted data or context (includes plaintext) | 571 | `invalid encrypted data` |
| 3 | replayed or non-increasing sequence | 572 | `encrypted data replay rejected` |
| 4 | cryptographic operation failed | 573 | `cryptographic operation failed` |

An inactive session never passes plaintext through. A client MUST NOT assume that an absent or plaintext value is
accepted for compatibility with firmware 9.31; the decoder contradicts that.

R24. A wrapper failure is returned as the wrapper's own code, 570 to 573, as an ordinary error
reply: by `pi_get_ap` (570 for a missing or inactive session), by `pi_station_set`, by `pi_set_ap`
(decode failure; READ on both architectures) and by `get_device_state` (encoding failure only). Code
105 remains the separate wrong-type branch of `pi_set_ap`. A text-validation failure of the supplied
SSID or key (`pi_set_ap`) gives 102, READ in one inspection and not re-confirmed.

## Guider

R25. On the 64-bit guider the switch, the predicate and the challenge and session lifecycle
mirror the imager (R4 to R15), including the default of enabled. The guider creates a crypto
session but nothing in it calls the field encoder or decoder, so no guider field is encrypted. READ.
The session's role there is client authentication on 4400 and 4040.

R25a. The 64-bit guider's serial-bridge control socket (the ser2net service) applies its client
authorisation check only while the switch is enabled. Firmware 9.31 did not gate that check on a
switch, and the 32-bit guider's version still does not. This is a firmware 9.75 difference of the
64-bit guider alone. READ.

## 32-bit builds and guider parity

R26. The 32-bit imager and guider have the crypto stack and create the key envelope on a
successful verification, but they have no `secure_communication` key and their predicate is the
port test alone. Verification is therefore always enforced on 4700, 4701, 4702, 4400 and 4040
(with the existing internal and factory exemptions), and there is no configured way to turn it
off. READ. The 32-bit imager encodes and decodes the Wi-Fi fields; the 32-bit guider does not.
READ. Parity of every malformed-input branch with the 64-bit build was not established.

R27. The challenge is 24 random bytes encoded as base64 (32 characters) on all four binaries
(imager and guider, 64-bit and 32-bit). The key envelope has the same fields on all four: version 1,
RSA-OAEP-SHA256 wrapping with the label of R13, HKDF-SHA256 and AES-128-GCM. The embedded
client-authentication key is a public key present in the 64-bit imager and in the 32-bit imager
and guider; no private key was found. READ.

R28. The decode statuses map to 570 to 573 identically in both imager builds; Wi-Fi password
encoding is used by `pi_get_ap` and `get_device_state`, and decoding by `pi_set_ap` and
`pi_station_set`. The guiders create sessions but encrypt no field. READ.

### Firmware 9.75 parity matrix: 32-bit imager and guider

Legend: READ means the disassembly was read; INFERRED a deduction; unresolved not traced. "D64" is
the 64-bit imager, "D32" the 32-bit imager, "G64" and "G32" the guiders. Firmware 9.75 throughout.

| Feature | 64-bit | 32-bit imager / guider | Verdict and label |
|---|---|---|---|
| Challenge (`get_verify_str`), 24 random bytes as base64 | yes | same in D32 and G32 | parity, READ |
| `verify_client` key envelope and crypto session | yes | same flow in D32 and G32 | parity, READ |
| Client authentication ports 4040, 4400, 4700, 4701, 4702 | port test and `secure_communication` flag | port test only; the layer is always on | differs, READ |
| `secure_communication` configuration key | honoured | does not exist in D32 or G32 | differs, READ |
| Serial-bridge client authorisation | G64 gated by the flag (new in 9.75) | G32 not gated | differs, READ |
| Wi-Fi password field encryption (`enc1:`) and 570 to 573 | D64 | D32 same behaviour; guiders encrypt nothing | parity, READ |
| Error-code table | full | identical except 545, 549 and 9000 to 9005, which are 64-bit only; D32 has 546 to 565, 570 to 573, 436 and 437 | subset, READ |
| `reset_setting` | 18 resettable descriptors, busy gating (259, 536) | D32 10 keys, no busy gating; transaction structure the same | partial parity, READ |
| `get_setting`/`set_setting` new keys | see [device-state-and-settings.md](device-state-and-settings.md) | `include_sensitive`, `sky_replay`, `can_encrypt`, `enable_dark_library` and `preview.raw_bin2` present with logic identical to D64 (traced to the address level); `comet_max_frame_num`, `motion_monitor`, `exp_ms.more_exposure` and `stack.startrail_mode`/`startrails_duration_min` confirmed absent (no matching string anywhere in the binary); the `annotation` string exists in the binary, but no setting branch for it (or its four sub-members) was found | parity for the traced keys, READ |
| Motion monitor, motion detection | yes | absent in D32 | 64-bit only, READ |
| Smart follow (`start_smart_follow`) | detection loop, error 254, motion-detection checks, stages `detecting`, `starting_track`, `tracking` | older worker with no 254 and no motion-detection checks, stage strings `waiting_target` and `starting_track`, log "wait for next target" | differs, READ (strings); semantics INFERRED |
| Sky replay getter and setter | force-disabled | identical in D32 | parity, READ |
| Temperature dark library | yes, with dark-library refresh during capture, `can_dark_correction` always true, and handling of a misplaced dark directory | library present; keeps the old dark-directory migration script; lacks the refresh during capture, the dark-correction check and the misplaced-directory handling; fit-failure log differs | older behaviour, READ (inventory); constants and `get_dark_files` shape not traced in D32 |
| `can_*` capability flags | the capability lookup recognises 7 models (S30, S50, S30P, S30Plus, S50P, S50N, S80), each with its own non-zero mask | the same flag names and bit order; the capability lookup recognises only 2 models (S30 and S50, exact board-name match), mask 0x14 (bits 2 and 4: `can_4k_quality`, `can_comet_post_stack`) for either; every other model string (S30P, S30Plus, S50P, S50N, S80) falls through to mask 0x00, losing all six flags | differs, READ: a real functional divergence, not just a documentation gap |
| Version greeting (`main_version`, `modules` from the local manifest) | yes | same shape in D32 and G32 | parity, READ |
| `clear_view_plan` failure code 218 | yes, and the power LED view-plan indicator is cleared | code 218 set; the LED call is absent; the file removal is INFERRED | partial parity, READ/INFERRED |
| Relay-to-slave check (conflict 203 and 524) | five-argument signature | four-argument signature; conditions not traced | partial, READ (signature) |
| Image send rate limiter | yes | same class and methods; the 32-bit build uses 32-bit sizes; bucket arithmetic not traced | present, READ (inventory) |
| Updater `ota_*` methods | six methods | same six in the 32-bit updater; no selective temporary-file cleanup | same set, READ; handler bodies and pending-receive timeout not traced |
| Network script Wi-Fi state check (`COMPLETED`) | yes | same | parity, READ |
| Source-id busy gate (65 s) | yes | present; constant unverified (INFERRED) | partial, INFERRED |
| Peer-to-peer rate limit and licence-key change | the rate setter clamps to [65536, 67108864] B/s, bucket capacity to [4096, 65536]; `set_send_rate` rejects values above 2097151 kB/s; `changSdkLicenseKey` must be a JSON string or init fails | identical numeric bounds and error strings traced to the address level; `changSdkLicenseKey` type-gate and fallback-to-embedded-default logic match; no licence value is recorded here | parity, READ |
| Guider: closing of unauthorised connections | the unauthorised-connection sweep sweeps every ~5s; skips factory mode and already-verified IPs; additionally skips the whole sweep unless the secure-communication gate | same sweep mechanism and skip conditions (factory mode, verified IP); the secure-communication gate does not exist in G32 at all (no symbol) — G32 sweep-closes any unverified, non-factory connection unconditionally | differs, READ: 32-bit guider has no secure-communication gate on this sweep |

## Open questions

- The exact SSID bytes bound into the associated data (R18), the context strings of the 32-bit
  callers, and whether a client can therefore build a valid token from this chapter alone.
  unresolved.
- Whether the 32-bit imager's Wi-Fi handlers have the same member names and error codes as the
  64-bit ones (R22, R24). `pi_set_ap`, `pi_get_ap` and `pi_station_set` confirmed identical (same
  member names `key`/`passwd`/`psk`, same cipher-context strings, same 105 wrong-type split). READ.
  `get_device_state`'s `ap.passwd` member is unverified at the address level; given the other three
  match and all four share the same cipher-context machinery, it is INFERRED rather than READ.
- Whether the matching private key is obtainable by a third-party client, and how an independent
  client could unwrap the envelope. unresolved; outside this specification.
- The imager contains an error text suggesting that an old client use a new verify method; no code
  that returns it was found. unresolved.
- The 32-bit relay-to-slave conditions and the 32-bit rate-limiter bucket arithmetic ([Firmware 9.75
  parity matrix: 32-bit imager and guider](#firmware-975-parity-matrix-32-bit-imager-and-guider)).
  unresolved. The `get_setting`/`set_setting` keys checked, the peer-to-peer rate logic and the
  guiders' unauthorised-connection closing are specified ([Firmware 9.75 parity matrix: 32-bit
  imager and guider](#firmware-975-parity-matrix-32-bit-imager-and-guider)); `sky_replay` in D32 is now traced: as in D64 (firmware 9.75), its getter returns false, and its boolean setter ignores the requested value, attempts to clear any stored enabled value and ends the replay session when the clear succeeds or is unnecessary; a failed clear makes the setter fail. READ.
- Behaviour of the 4700 tunnel path (loopback) with respect to sessions is INFERRED only.
