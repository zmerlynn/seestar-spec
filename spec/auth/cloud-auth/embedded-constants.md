# Cloud auth: embedded constants

Part of [Cloud authentication and relay authorization](../cloud-auth.md). This file reproduces
the fixed constants compiled into the ThroughTek SDKs (the two public keys, the legacy transform phrase and the master host-name
suffixes) and into the vendor app (the third-party login `sign` key, described but withheld, and the activation request key) that a compatible client or device needs for interoperability. They are compiled into
the libraries and app inspected and are not specific to any account, device or licence. Per-account values (licences, the licence `keyMask`, tunnel
credentials, tokens) are not reproduced and MUST NOT be published.

Basis: static analysis of app 3.3.2 (client IOTC library, SDK 4.3.8) and firmware 9.31 (device
SDK 4.3.6 inside the imager, 64-bit build; the 32-bit imager carries the same device SDK build, the same [Licence-verification public key](#licence-verification-public-key) licence-key
fingerprint and the [Master host-name suffixes](#master-host-name-suffixes) suffix strings, READ; the [Legacy transform phrase](#legacy-transform-phrase) phrase there is rebuilt from two 32-byte arrays
XORed byte-wise, the same technique as the client SDK, rather than stored as a plain literal; [Master-query public key](#master-query-public-key) is
client-only). Firmware 9.75 embeds the same keys: the
fingerprints of the licence-verification and master-query keys are identical in 9.31 and 9.75, in
both builds (READ). Fingerprints are SHA-256 over the stated
bytes.

## Licence-verification public key

RSA, 1024-bit modulus, as a DER `SubjectPublicKeyInfo` (162 bytes). Used to check and decode the
SDK licence envelope ([sdk-licence.md: Licence envelope](sdk-licence.md#licence-envelope)) with a raw RSA
public operation (no padding scheme). Both SDKs pass this same key to their licence installer.
READ.

```text
-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDQXw9rYBtx25rSHy3kNotbSoys
Cb+DqSieB7PhXgJENqOqa2Z+nlcRbgQ+lnptlVYelWPR5phmkW2OSWwoQByvXVkh
Nuiz5CAMNV+6WCYF84DQNstarDLwt7L6YhS8fTHt5ODv1uwArchCJp67+cS+gRK4
95wiu9ejOoqiDmQGYwIDAQAB
-----END PUBLIC KEY-----
```

Fingerprint of the DER bytes:
`75063ce243f456370dea2efa502d42f18d8c6a817c989f569d22b0bb5f6fb45d`. READ (computed from the
embedded key).

## Master-query public key

RSA, 2048-bit modulus, as a DER `SubjectPublicKeyInfo` (294 bytes), embedded in the client SDK.
Used to encrypt the record-form master query ([master-record.md: Master query (record type 1)](master-record.md#master-query-record-type-1)).
READ.

```text
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAn8roKGV4ukAPhiOD+Asz
eCXWjBIycEIJplBpiDcNRzfoJLXwLXCYSYsH812HaD5NnzpH7jPh/FAORNXoBkGJ
dnje299ddL7CXU1bCasSAes6FXI1XlLsBOzEW2IdM9DCyhWBx9EUOCgYHA6A+KmG
msfVOXF5eNbT6Nk7fSjGrpRGj6wDuyyhrAPuLw+yMCsyoOVMlNpziBQJqcRO5xrP
3/xHsT9f5ww/udb4+fAIlrGwv4zAkg+D2mm353G9MFoQhvd+odoa8CVrGvsetXul
pfbMkBfvgKTj7UJRb78PJQJj9WmixJc7KDKgqJNGZ1tkMwWdFfYcZH3I3kmlu6mt
hwIDAQAB
-----END PUBLIC KEY-----
```

Fingerprint of the DER bytes:
`ec8f2dbd0933aa6dd3dc3c383c6532f720e7767ba75cd8df2ddb5b4188cda8ab`. READ (computed from the
embedded key).

## Legacy transform phrase

A 32-byte ASCII phrase, built by both SDKs at initialization:

```text
Charlie is the designer of P2P!!
```

Fingerprint of the 32 bytes:
`34a672db0239cae3b78f313bf330f19f377828106681cc042535965b638115cf`. READ.

The device SDK's 64-bit build stores the phrase as a plain literal, loaded as two 16-byte halves
during initialization. The device SDK's 32-bit build has no such literal: the plain phrase does not
occur as a byte sequence in the 32-bit imager, and its initialization routine instead rebuilds the
same 32-byte phrase from two 32-byte arrays, stored 32 bytes apart, XORed byte-wise — the same
technique the client SDK uses. READ (both device builds and the client SDK). The iOS app 3.4.0
network framework embeds the phrase as a plain literal: a NUL-terminated 36-byte string whose first
32 bytes are exactly the phrase above, followed by four more printable ASCII bytes, which are not
repeated here. READ (iOS app 3.4.0, byte comparison). That 36-byte string does not occur in either
64-bit imager. Whether the iOS code reads the four extra bytes is unresolved; the transform below, as
read in the Android client SDK and the device SDK, uses only the first 16.

Only the first 16 bytes (`Charlie is the d`) are used. XORed byte-wise with the licence's
16-byte `keyMask` (all zero when the licence has none), they form the scrambling key `K` of
[IOTC framing: Key](../../transport/iotc/framing.md#key) and the `mask` of
[master-legacy.md](master-legacy.md). The last 16 bytes are unused by the transform. READ.

## Master host-name suffixes

Used when the licence realm contains no dot ([IOTC connect](../../transport/iotc/connect.md)).
READ.

| Case | Suffix |
|---|---|
| Client (`c-master`) and device (`d-master`) masters | `.iotcplatform.com` |
| `p2pod-master` | `.kalayservice.com` |
| Region exactly `cn` (any service) | `.kalay.net.cn` |

A licence `standalone` entry for the region overrides the constructed name
([sdk-licence.md: Licence JSON](sdk-licence.md#licence-json)). READ.

## Third-party login `sign` key (app)

The fixed HMAC-MD5 key for `sign` on `/v1/user/oauth/verify` ([endpoints.md
R29](../account-login/endpoints.md)) is a 7-byte UTF-8 string. Its value is deliberately not given
here: only the app's WeChat login verification uses it. It is the app's default key for its signing
helper and is the same in every installation. READ (app 3.3.2). It is a shared constant, not an
account secret; it does not authenticate a user. INFERRED.

## Activation request public key (app)

RSA, 1024-bit modulus, as a DER `SubjectPublicKeyInfo` (162 bytes). The app encrypts `sn` and
`cpuId` in the `/v1/activation` request body with it, using RSA/ECB with PKCS#1 v1.5 padding,
then Base64 ([maintenance.md R15a](../../control/maintenance.md)). It is a different key from [Licence-verification public key](#licence-verification-public-key). READ (app 3.3.2).

```text
-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDRsuHZIML9s8t9wTOOx1RtpmbD
GKurd1rPsv/OrrhQYQXrpuECRdd2KBHQm5N5Nevy17ryrCMSV1Gp4I+VuiNXqtib
jO2KRq/AtsjrWCE7J11d3tjmbRB/mCcpRRRXA1JBpL9xhDuYG4VvqdNM9B328saL
D1vnd/TYKsES7kXm2wIDAQAB
-----END PUBLIC KEY-----
```

Fingerprint of the DER bytes:
`ddf27b66f69f0f3484f20de37a992b91bf2af3ea69f285a585d15c0b1b685c3f`. READ (computed from the embedded key).

## Device-side client-authentication public key (location only)

The firmware carries a third public RSA key besides the two SDK keys above (licence verification and master query): a 1024-bit
`SubjectPublicKeyInfo` PEM in read-only data, returned by the imager's client-authentication
helper. It verifies the signature in `verify_client`
([verification-and-roles.md](../../control/session-handshake/verification-and-roles.md)) and, in
firmware 9.75, is the key under which the session secret is wrapped
([secure communication](../../control/secure-communication.md)). It is public key material. It is
identical in firmware 9.31 and 9.75 and is present in the 64-bit imager, the 9.75 guider and the
32-bit imager (READ: the same content in every one of these). Two other
PEM public keys sit beside it in the 64-bit imager, also public and unchanged between 9.31 and
9.75. Its use in firmware 9.31 is client-signature verification only (READ): the 9.31 function that
marks a connection verified writes the key to a temporary file and runs a shell pipeline that
Base64-decodes the signature and checks it with the system `openssl` tool; the full flow is
INFERRED from the callees and strings. The shell strings are still present in 9.75. The wrap use is
new in 9.75. Two further embedded values exist in 9.75 and are not reproduced here: a default SDK
licence string (role: the default licence, [sdk-licence.md R46a](sdk-licence.md#device-side-sdk-start))
and a fixed vendor IoT-platform instance identifier inside an endpoint host name (role: the
device's MQTT cloud link, [device-cloud-link.md](device-cloud-link.md)). The matching private key is not in the firmware and is held by the official app; it is
never reproduced. This chapter records only the key's existence, size and role. Its value and
fingerprint are not reproduced here. Placement note for the maintainers: this key belongs to the
control-channel authentication chapters rather than to the Kalay SDK constants above, and is
listed here only so the three device-side keys are not confused.

## Update-package signing public key (device)

RSA, 1024-bit modulus, as a DER `SubjectPublicKeyInfo` (162 bytes). It verifies update packages:
the legacy transfer in [updater R5c](../../updater/index.md#legacy-upload-flow-begin_recv) and,
in firmware 9.75, the per-module signature inside an OTA package
([OTA package handling R12a](../../updater/ota-package-handling.md#ota-package-handling)). The
updater writes the key out to a temporary `my_public.pem` file and checks a detached
`update-package.sign` signature over a SHA-1 digest of the package with the system `openssl` tool
(`openssl dgst -sha1 -verify`); a failing check gives the `verify_fail` / `verify_fail: sign`
outcomes already listed in updater R7a. It is identical, byte for byte, in both the 32-bit and
64-bit updater binaries and in both firmware 9.31 and 9.75 (READ, all four binaries). It is a
different key from the licence-verification, master-query, activation-request and device-side
client-authentication keys.

```text
-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDtEuy6oWJ30D9r57O7GRPLOH1f
0CU79bmrEP9L8YLmwXQgfRPTeegfmmUsVH9zPJFOxdGPqZgjb/U/cwcwu37uOEiW
DIANiICTqxnumsS8k68ZmFF6bIAuhyupXxwlCxSji6x19FkviCoJvteLx5wO/tyH
NyyMyvzq8hpLaYL14QIDAQAB
-----END PUBLIC KEY-----
```

Fingerprint of the DER bytes:
`22e96ba2ac12ae0c53a54cb3a92e246e377fcd9602641703d5d1ec535ad43877`. READ (computed from the
embedded key). The matching private key is held by the vendor and is never reproduced.

## ZWO vendor HTTP API hosts (app)

Real values for "the ZWO account API host"
([account-login.md: Endpoint selection](../account-login.md#endpoint-selection)) and "the ZWO remote API host"
([http-api.md: Host, transport and headers](http-api.md#host-transport-and-headers)). Each is a fixed origin selected by a
bundled JSON environment asset in the app rather than negotiated at runtime; a development
switch that would pick an alternate set of hosts is hard-coded off in the release build. READ (app
3.3.2). These are ordinary vendor-operated HTTPS hosts, not SDK-level constants like the SDK constants
above; they are recorded here, next to the Kalay master-host suffixes, because a client cannot
interoperate without a starting origin and nothing about the protocol depends on the names
themselves. A client implementation MAY use any compatible host instead.

| Role | Host |
|---|---|
| Account login and profile endpoints ([account-login.md: Account endpoint catalogue](../account-login/endpoints.md#account-endpoint-catalogue)) | `api.seestar.com` |
| Remote-session allocation (`online-link`) and the rest of the remote API ([http-api.md](http-api.md)) | `api-ithings.zwoastro.com` |
| Account H5 web pages (browser-rendered; not a JSON API host) | `account.seestar.com` |
| "common" app endpoint group (connectivity check) | `api.zwoastro.com` |
| H5 share links (NFC pairing, plan sharing) | `app.zwoastro.com` |
| Bluetooth-related API | `bt.zwoastro.com` (also seen as `eo-api-bt.zwoastro.com`) |

All hosts are HTTPS. The app also bundles development hosts for some roles, reached
over plain HTTP; they are not listed because no release client uses them. READ (app 3.3.2, from the bundled environment asset).

Separately, both firmware builds (the D32 and D64 imager) run a `curl` connectivity check against
the production "common" host's `/common/v1/network-available` path. READ (firmware 9.31 and 9.75
imager). This is one of the three rotating probe targets of
[`check_internet`](../../control/network.md#internet-check) (R30b); the `edge-api.zwoastro.com`
host seen alongside it is a separate probe target in the same rotation, reached by ping rather
than HTTPS, not an alternate host for this path. The check is firmware-initiated, distinct from
the app-side hosts in the table above, and runs both on demand (the `check_internet` RPC) and on
the device's own initiative from at least two background workers, independent of any RPC call;
see [network.md R30e](../../control/network.md#internet-check) for what triggers the
self-initiated calls and what is still unresolved there (whether either background worker is
timer-driven, and at what interval).
