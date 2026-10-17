# Account login: boundaries and open questions

Part of [Account login](../account-login.md). Requirement numbers continue across the chapter; basis and conventions are in the index.

## Captcha, binding and crypto

R56. The email/password login has no captcha, proof-of-work, SMS/email challenge, device serial
or device binding step. Code sending and third-party binding are separate optional flows (section
5). READ. A server could still demand extra checks; none are handled by the app. Whether it does is
unresolved (server-side).

R57. The only cryptography is TLS, negotiated by the platform. No application key, IV, nonce or
fixed TLS profile is involved. READ.

R58. A client MUST NOT reuse the account password or the access token as a Kalay/IOTC tunnel
password or derive tunnel keys from them. INFERRED (no link between the layers was found).

## Firmware boundary

R59. The account exchange runs between the app and the account API host only. The telescope is
not a party. INFERRED. The firmware contains no account API. A literal scan of every firmware
9.31 binary (64- and 32-bit imager, guider, updater, file server and BLE daemon) found none of the
account paths or token field names (`/v1/user/login`, `accessToken`, `authKey`, `device_uuid`,
and others); the only near matches are log strings inside the Kalay SDK. The firmware's own HTTP
endpoints are device and network ones. READ.

The device exposes these remote-access control methods (TCP 4700). Their relation to the account
token is limited:

| Method | Role | Relation to this chapter |
|---|---|---|
| [`remote_join`](../../../docs/control/methods/remote_join.md) | joins the device to the cloud relay with relay credentials (host, product key, device name, device secret, port) and stores them | takes relay credentials, not the account token or password. READ (param list). How the app obtains them is in [cloud-auth.md](../cloud-auth.md). |
| [`remote_disjoin`](../../../docs/control/methods/remote_disjoin.md) | leaves the relay and deletes the stored join | sent only from the device-management screen's "remove" action, after the app's login and network checks and a confirmation dialog, with no parameters and a 10 s timeout; no cloud request accompanies it. No account-logout path sends it. READ (app 3.3.2) |
| [`remote_disconnect`](../../../docs/control/methods/remote_disconnect.md) | stops the tunnel server, keeps the join | the app has no request for this method and never sends it (the name occurs only as part of a UI string identifier). READ (app 3.3.2) |
| [`remote_rebind_device_user`](../../../docs/control/methods/remote_rebind_device_user.md) | reports a `userId` string to the cloud as the device owner | the value is the installed account profile's `id` ([R25](login.md#installation-and-profile-fetch)), sent from the device-management screen's "rebind to account" action after the same login and network checks; a null `id` is treated as blank and a blank `id` is not sent. READ (app 3.3.2) |

## Open questions

1. Token format, whether it already contains a scheme, its lifetime, the units of
   `accessExpire`/`refreshAfter`, and revocation rules. unresolved (server-side).
2. Envelope success code and the codes for bad credentials, lockout, region, code expiry and
   challenges. unresolved (server-side).
3. Does the server still accept automatic re-login with `category` 0 and no application headers?
   unresolved (server-side).
4. Concurrent renewal, process restarts, and remote 401 before profile installation. Answered
   app side: unsynchronized per-process session tokens over one shared stored token. See
   [lifecycle R43a](lifecycle.md#account-client-401-driven-credential-replay)
   (READ (app 3.3.2); consequences INFERRED) and, for listener registration and an early remote
   401, [lifecycle: Remote client: token-expired event](lifecycle.md#remote-client-token-expired-event).
5. Third-party provider flows beyond the request shapes. unresolved. (`sign` generation is answered in
   [endpoints R29](endpoints.md).)
6. Does the server revoke an active relay session on account logout? unresolved (server-side). App side, READ
   (app 3.3.2): `remote_disconnect` is never sent and `remote_disjoin` is sent only by the
   device-remove action ([Firmware boundary](#firmware-boundary)). The relay stop request is sent on every deliberate remote
   disconnect when a `conId` is known, including the logout action of the account screen, which
   disconnects an open remote session (sending stop) before clearing the stored credentials. Logout
   through the web view bridge and logout caused by a 401 clear credentials without disconnecting
   or sending stop. Transport-loss recovery never sends stop.
7. `srcId` behaviour across backup/restore and storage reset. Answered app side: the store is
   included in default auto backup and device transfer, and a storage reset creates a new value.
   See [login R39a](lifecycle.md#storage-startup-and-source-identifier) (READ (app
   3.3.2); restore effects INFERRED from platform defaults).
8. Interoperability as a whole: no live login was performed. unresolved.
9. iOS app 3.4.0: the WeChat login-ticket response keys and request method (INFERRED), whether
   `apple` is the wire `authType` (INFERRED) and its `sign` computation
   ([endpoints R31a](endpoints.md#additions-seen-in-ios-app-340)), and the iOS
   headers, `x-params` and signing (encrypted main executable). unresolved.
10. Whether a remote-API 401 ends the whole account session or only the older of two concurrent
    tokens ([lifecycle R47](lifecycle.md#token-renewal-expiry-and-logout)). unresolved
    (server-side).
11. The verification code's lifetime and resend rate limit
    ([endpoints R32](endpoints.md#side-flows)). unresolved (server-side).

## Appendix: How to validate on a live device (non-normative)

Use an account, device and network you own. Never record passwords, tokens, emails, user ids or
`srcId` values; record only shapes, presence, status codes and same/different results.

1. Passively watch one normal app login, remote connection, restart and logout. Note only
   destination origins, order and timing. Expect the account host and the remote API host to
   differ.
2. If endpoint-side inspection is authorized, check in memory that field names, `category`,
   `language` and header presence match profiles A and B. Emit pass/fail only.
3. Let a session expire naturally. Compare account replay (7.1) with remote expiry (7.2): count
   attempts, note status codes. Do not force expiry with bad passwords.
4. Check that `srcId` is unchanged across restart, logout and login (equality only).
5. Test an independent client offline first with synthetic bodies, escaped characters, missing
   tokens and 401/403/400 replies, then make one real login.
