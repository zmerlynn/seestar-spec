# Account login: interactive login

Scope: the email/password exchange with the account API host ([Interactive email/password login](#interactive-emailpassword-login)): input preparation, request and response bodies, token installation, the profile fetch. Storage, startup and the source identifier `srcId` are in [lifecycle: Storage, startup and source identifier](lifecycle.md#storage-startup-and-source-identifier). HTTP representation and headers are in the index ([Endpoint selection](../account-login.md#endpoint-selection), [HTTP representation](../account-login.md#http-representation)); the token is consumed by [cloud-auth.md](../cloud-auth.md).

Part of [Account login](../account-login.md): [interactive login](login.md) | [endpoint catalogue](endpoints.md) | [storage, token lifecycle and errors](lifecycle.md). [Boundaries and open questions](boundaries.md). Requirement numbers (R1..) are shared across these files; conventions and labels are in [the index: Conventions](../account-login.md#conventions).

## Interactive email/password login

### Flow

```
Client                                   Account API host
  |  prepare input (4.2)                         |
  |  POST /v1/user/login  {profile A headers}    |
  |--------------------------------------------->|
  |  HTTP 200  E<token reply>                    |
  |<---------------------------------------------|
  |  store token, set session token,             |
  |  loginStatus = true, save username/password  |
  |  GET /v1/user/current-profile  {Authorization: token}
  |--------------------------------------------->|
  |  HTTP 200  E<profile reply>                  |
  |<---------------------------------------------|
  |  save profile id as user_id, publish user    |
  |  completion callback                         |
```

### Input preparation

R15. The app's input fields drop every literal U+0020 SPACE as the user types, in both the
account and password fields. Other whitespace characters are kept at this step. READ.

R16. The account string is then trimmed at both ends. The trim works on UTF-16 code units and
removes a unit if it is Java whitespace or a Unicode space character (`isWhitespace || isSpaceChar`).
Interior characters are kept. There is no lowercasing or other normalization. READ. The password
is trimmed the same way. READ. The exact character set depends on the Android runtime's Unicode
tables, so other trims are not established as equivalent. INFERRED.

R17. If the trimmed account contains `@`, `authType` is `email`; otherwise it is `mobile`. READ.

R18. Local checks before sending (all READ):

- email form must match `^\w+([-+.]\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*$`;
- password length 8 to 32 UTF-16 code units, no character-class rule (a supplementary-plane
  character counts as 2);
- the user has accepted the terms (UI gate only, nothing is sent).

R19. A replacement client MAY apply its own input preparation, but SHOULD apply R15-R16 if it
wants to match the official app byte for byte. INFERRED.

### Request

`POST /v1/user/login`, profile A headers, body the auth-request body (members below). READ.

| Member | JSON type | Interactive login | Automatic re-login (7.1) |
|---|---|---|---|
| `authKey` | string | prepared email or mobile number | saved username, verbatim |
| `authType` | string | `email` or `mobile` (R17) | `mobile` if the saved username matches the mobile pattern (R40), else `email` |
| `password` | string | prepared password, plaintext | saved password, verbatim |
| `category` | integer | `1` | `0` (never set) |
| `language` | integer | `0`, on every UI language | `0` |
| `code` | string | omitted | omitted |
| `interval` | integer | omitted | omitted |
| `nickname` | string | omitted | omitted |

R20. The password is sent as a plain JSON string inside TLS. There is no hash, salt, KDF,
nonce, RSA wrap or other application crypto. READ. A client MUST use HTTPS and MUST NOT hash or
transform the password.

Synthetic example (not a real request; INFERRED from the DTO and callers):

```json
{"authKey":"user@example.invalid","authType":"email","category":1,"language":0,"password":"Example-Only-123"}
```

### Response

`E<token reply>`. READ.

| `data` member | JSON type | Use in the app |
|---|---|---|
| `accessToken` | string | stored and sent verbatim |
| `accessTokenType` | string | declared, never read |
| `accessExpire` | integer (signed 32-bit) | declared, never read; unit and meaning unresolved (server-side) |
| `refreshAfter` | integer (signed 32-bit) | declared, never read; as `accessExpire` |

All three non-token members may be absent or null without effect: no reader of them was found in
any of the app's code files (READ; reflection not excluded), and no timer uses them (READ,
[lifecycle: Account client: 401-driven credential replay](lifecycle.md#account-client-401-driven-credential-replay)). OBSERVED
(2026-10-12): the server sent `accessExpire` and `refreshAfter` as integers and a string member
named **`tokenType`**, not `accessTokenType`, so the app's `accessTokenType` stays unset.
INFERRED from the name difference. A client SHOULD accept either name and MUST NOT require one.

R21. There is no refresh token, refresh endpoint, cookie token or device identifier in the
response. Member names are not OAuth names (`access_token` etc.). READ.

R22. The app treats the login as successful when the HTTP status is **200**; it does not compare
the envelope `code` with any success value, and it dereferences `data.accessToken` without a
null check. READ. The numeric envelope success code is unresolved (server-side); R23 does not depend on it.

R23. A client SHOULD accept a login only on a 2xx HTTP status with a non-empty string
`data.accessToken`, and MUST NOT change stored credentials otherwise. It SHOULD keep the envelope
`code` and `msg` for diagnosis. INFERRED (defensive policy, not a server rule).

### Installation and profile fetch

R24. On HTTP 200 the app, in this order: stores the token persistently, sets the in-memory
session token, publishes `loginStatus = true`, saves the prepared username and password, then
requests `GET /v1/user/current-profile`. READ.

R25. Profile outcomes. READ. The table assumes the result is delivered; if the screen's lifecycle
cancels the request first, that is not a completion and the callback is not called (INFERRED).

| Profile event | Installation | Completion callback |
|---|---|---|
| saved token empty when the fetch starts | no request sent | not called |
| HTTP 200 with non-null `data` | save `data.id` as `user_id`; publish the user and run the user-service login transition (R26) | called afterwards |
| HTTP 200 without `data`, or HTTP 201/204 | none | called |
| HTTP 401 | session-expired handling ([Errors](lifecycle.md#errors)) | not called |
| other non-2xx (e.g. 403, 404, 500) | error shown | not called |
| exception (network, parse) | none | called |

R26. The user-service login transition stores the profile and, only if the profile id differs
from the previous one, records the id and notifies login listeners. Logout of that service
clears the user always, but notifies listeners only if an id was set. Saving `user_id` or the
token alone does not run this transition. READ. Token, saved user id and listener state are
three separate stores. READ.

R27. A client MUST decide explicitly whether a token is usable when the profile fetch fails;
the official app does not guarantee a profile before completion. INFERRED. No profile field is
needed as a credential by the remote layer (see [cloud-auth.md](../cloud-auth.md)). INFERRED.


