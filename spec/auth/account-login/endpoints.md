# Account login: endpoint catalogue

Scope: every account HTTP endpoint the app declares ([Account endpoint catalogue](#account-endpoint-catalogue)), with request and response members. Representation rules are in the index ([Endpoint selection](../account-login.md#endpoint-selection), [HTTP representation](../account-login.md#http-representation)); the login exchange itself is detailed in [login.md](login.md). Telescope ownership and relay endpoints are in [cloud-auth.md](../cloud-auth.md).

Part of [Account login](../account-login.md): [interactive login](login.md) | [endpoint catalogue](endpoints.md) | [storage, token lifecycle and errors](lifecycle.md). [Boundaries and open questions](boundaries.md). Requirement numbers (R1..) are shared across these files; conventions and labels are in [the index: Conventions](../account-login.md#conventions).

## Account endpoint catalogue

All paths are relative to the account API base URL, profile A headers, JSON bodies per
[HTTP representation](../account-login.md#http-representation). Labels: endpoints and member names READ; whether the server accepts each shape is
unresolved (server-side). A minimal email client needs only login and (optionally) current-profile.

### Endpoints

| Method | Path | Request | Response `data` | Label |
|---|---|---|---|---|
| POST | `/v1/user/login` | auth-request body ([Request](login.md#request)) | token reply | READ |
| POST | `/v1/user/send-code` | auth-request body: `authKey`, `authType`, `category`, `language`=0 | bare envelope (`code`, `msg`; no typed `data`) | READ |
| POST | `/v1/user/verify-code` | as send-code plus `code` | bare envelope (`code`, `msg`; no typed `data`) | READ |
| POST | `/v1/user/register` | auth-request body: `authKey`, `authType`, `nickname`, `password`, `code`, `category`=3, `language` (R30) | token reply | READ |
| POST | `/v1/user/reset-password` | auth-request body: `authKey`, `authType`, `password`, `code`, `category`=2 | bare envelope (`code`, `msg`; no typed `data`) | READ |
| PATCH | `/v1/user/password` | `{oldPassword: string, newPassword: string}` | unspecified object | READ |
| POST | `/v1/user/password` | `{password: string}` | unspecified object | READ |
| GET | `/v1/user/oauth/verify` | query `unionid`, `airId`, `sign`, `platform`; no body | token reply | READ |
| POST | `/v1/user/oauth/login-register` | third-party registration body ([Request bodies](#request-bodies)) | token reply | READ |
| POST | `/v1/setting/check-bind-limit` | `{authType: string}` | unspecified object | READ |
| POST | `/v1/setting/bind-mobile-email` | `{authType, authKey, oldCode?, code}` (all strings) | bind-result reply, new form ([Binding responses](#binding-responses)) | READ |
| POST | `/v1/setting/bind-thirdpart` | third-party bind body, legacy form ([Request bodies](#request-bodies)); a newer client sends the same members under a differently-typed request | bind-result reply, legacy form ([Binding responses](#binding-responses)); a newer client wraps an unspecified object | READ |
| POST | `/v1/setting/unbind-thirdpart` | older: third-party bind body, legacy form ([Request bodies](#request-bodies)); newer: `{platform}` only | older: base data; newer: unspecified object | READ |
| GET | `/v1/user/current-profile` | none | profile reply ([Current profile reply](#current-profile-reply)) | READ |

Telescope ownership, sharing and the remote online-link request are not account endpoints; see
[cloud-auth.md](../cloud-auth.md).

### Request bodies

| Body | Members | Label |
|---|---|---|
| Auth-request body | `authKey` string, `authType` string, `password` string, `category` int, `language` int, `code` string, `interval` int (nullable; never set by the app), `nickname` string | READ |
| Third-party registration body | strings `platform`, `sign`, `unionid`, `openid`, `authKey`, `authType`, `code`, `nickname`, `avatar`; int `language` | READ |
| Third-party bind body, legacy form | strings `platform`, `unionId`, `openId`, `airId` | READ |

Note the spelling difference: lowercase `unionid`/`openid` in register and verify, camel case
`unionId`/`openId` in bind. READ.

R28. `category` values: LOGIN=1, FORGET=2, REGISTER=3, BIND=4, UNBIND=5,
AFK=6, sent as integers. READ. `authType` values: `mobile`, `email`, `facebook`, `wechat`. READ.

R29. `sign` on `/v1/user/oauth/verify` is HMAC-MD5 over the UTF-8 bytes of the `unionid` value
sent in the same request, keyed with the UTF-8 bytes of a fixed key embedded in the app
([embedded-constants.md: Third-party login `sign` key (app)](../cloud-auth/embedded-constants.md#third-party-login-sign-key-app)), written as 32 lowercase hexadecimal digits
(two per byte, zero-padded). If the MAC cannot be computed the app sends an empty string. READ
(app 3.3.2). The app calls verify only after a WeChat login, with `unionid` set to the WeChat
union ID, `airId` empty and `platform` `wechat`. READ (app 3.3.2). A client MUST NOT substitute a
password hash for it. INFERRED.

R29a. `sign` in the third-party registration body (`/v1/user/oauth/login-register`) is not a MAC: the app
sends the provider user identifier unchanged, the same value as `unionid` (WeChat: the union ID,
empty if unknown; Facebook: the `token_for_business` value from the Facebook profile). The app
first fills `authKey` with a fixed placeholder and `authType` `email`, then overwrites them with
the entered email or mobile number and the matching `authType`. READ (app 3.3.2). Whether the
server checks this `sign` is unresolved.

R30. Registration `language` is 0 for Chinese, 1 for English, -1 otherwise. READ. (Login always
sends 0, [Request](login.md#request).)

### Binding responses

| Reply | Members | Label |
|---|---|---|
| Bind-result reply, new form | `bindResult` bool; `failReason` {`reason` string, `existUser` {`id` string, `nickname` string, `avatar` string, `createTime` 64-bit int}} | READ |
| Bind-result reply, legacy form | same shape, but `createTime` is a 32-bit int | READ |

R31. The app treats a bind as successful only if HTTP is 200 and `bindResult` is true; otherwise
it passes `existUser` (if any) to the UI. `reason` is free text, not an enum. READ.

### Current profile reply

| Members | Type | Label |
|---|---|---|
| `id`, `name`, `nickname`, `email`, `mobile`, `avatar`, `signature` | string | READ |
| `followingCount`, `fansCount`, `gotStarCount` | int | READ |
| `following`, `isDeny`, `hasPwd`, `hasFactoryMode` | bool | READ |
| `whitelistFunctions` | array of string | READ |
| `country` | {`code`, `group`, `icon`, `name` strings; `id`, `createTime` ints} | READ |
| `facebook`, `wechat` | {`id`, `nickname` strings} | READ |

These are accepted members; not every response need carry all of them. INFERRED. Only `id` and
the object as a whole take part in login installation. READ.

Null handling: a null `data` means no user is stored, and completion still runs
([login: Installation and profile fetch](login.md#installation-and-profile-fetch), R25). READ. `id` is saved without a null
check; the later user-service comparison is null-safe, but hashing the profile with a null `id`
would fail (INFERRED). Effect of a null `id` (READ, app 3.3.2): the stored `user_id` is set to
null and the profile is stored; the user service then installs it, notifying its login listeners
with the null id only if a non-null id was installed before, and the analytics login that
follows rejects a null id. Either rejection raises an error inside the reply handler, so the
remaining installation steps are skipped. The error is passed to the request's error handler,
which still runs completion (INFERRED from standard RxJava error routing). The result is a
logged-in state with a null user id and partly updated listeners, so a server MUST always send
`id`. INFERRED. `country` and `whitelistFunctions` are nullable. The app never reads
`whitelistFunctions` (its only accessor has no callers), so a null list or null entries have no
effect. READ (app 3.3.2). OBSERVED (2026-10-12): `country` was null,
`whitelistFunctions` an array, and the reply carried further members that the app ignores.

### Additions seen in iOS app 3.4.0

R31a. iOS app 3.4.0 contains a WeChat QR ticket path and an Apple provider path. The examined main account header and metadata builders are statically readable and are summarized in the [boundaries chapter](boundaries.md) (item 9); [Application headers](../account-login.md#application-headers) in the index remains Android 3.3.2. READ. Android app 3.3.2 is a separate implementation; the first iOS release containing either path remains unresolved. The iOS main executable declares encryption over only one 4 KiB page; the routines below lie outside it and were read directly (READ, iOS app 3.4.0).
- WeChat login ticket. The app calls `/v1/user/oauth/wechat/login-ticket`. The examined main account request uses GET with no arguments. It extracts the response envelope's data member and maps ticket and accessToken to string properties and expiresIn to a signed integer property using those JSON member names. READ for request construction and client parsing; actual server responses, requiredness and expiry semantics remain unresolved. When WeChat is absent, the examined provider-selection path opens QR login, whose SDK authentication uses ticket. READ. The examined main third-party verification builder populates platform, sign and unionid, adding airId only for a nonempty related provider identifier. READ. Android app 3.3.2 uses a provider callback and GET verification in its examined source; a matching ticket step was not found in the scoped source search, and its existence elsewhere remains unresolved.

  The iOS app then runs the WeChat QR
  SDK with scope `snsapi_userinfo` and signs a string made of `appid`, `noncestr`, `sdk_ticket` and
  `timestamp` as name=value pairs joined by `&`, with SHA-1 (READ for the string layout). The SDK's
  authorization callback yields a code, which the app sends to `/v1/user/oauth/login-register`
  (R29a) with `platform`, `sign`, `unionid`, `openid`, `nickname`, `avatar`, `authType`, `authKey`,
  `code` and `language`, and to `/v1/user/oauth/verify` (R29)
  as before. READ (member names).
- Apple, iOS app 3.4.0 main application: the traced main login path uses the main account service and POST third-party registration builder. It sends platform=apple and authType=email, the provider user identifier as unionid, the provider profile name as nickname and email as authKey, empty openid, avatar and code members, and language. Its registration sign and the examined main third-party verification sign use HMAC-MD5 over unionid, keyed with the same fixed string as Android's verification sign ([embedded-constants.md: Third-party login `sign` key (app)](../cloud-auth/embedded-constants.md#third-party-login-sign-key-app)), formatting the digest as lowercase hexadecimal. READ. Android app 3.3.2's examined WeChat verification uses HMAC-MD5, whereas its examined WeChat registration constructor stores the supplied union identifier directly as sign. READ for those separate source paths; Android Apple behavior and backend acceptance remain unresolved.
- Apple, iOS app 3.4.0 bundled account framework: the third-party registration request to `/v1/user/oauth/login-register` uses `platform` = `apple` and `authType` = `email`. It supplies the Apple user identifier as `unionid`, the assembled name as `nickname`, and returned, synthesized or cached email as `authKey`; `openid`, `avatar` and `code` are empty strings. The request also includes the common `language` member. If Apple supplies no email, the fallback address uses the MD5 representation of the user identifier as its local part at the Apple-ID domain; cached profile values for that user can replace the assembled name/email. READ.

  The `sign` is HMAC-SHA256 with `unionid` as the message and the account-registration signing key selected by project configuration as the key. Both inputs are converted to ASCII C strings and measured with C-string lengths; the digest is encoded as 64 lowercase hexadecimal characters. READ. No signing-key value is specified here. The main application's installed project configuration, alternative entry paths and backend acceptance remain unresolved in this trace. This is iOS app 3.4.0 account-client behavior, separate from Android app 3.3.2 and firmware 9.31/9.75.
- The new remote endpoints are in [http-api.md: Optional remote-feature catalogue](../cloud-auth/http-api.md#optional-remote-feature-catalogue).

### Side flows

R32. Code sending: after HTTP 200 the app records the account, a "sent" flag and a timestamp in
seconds, and starts a 60 s resend countdown (UI only). READ. The code lifetime and rate limit
are unresolved (server-side).

R33. Password reset: on success the app runs the normal login ([Interactive email/password login](login.md#interactive-emailpassword-login)) with the new password.
READ.

R34. Registration success quirk: the app stores the **nickname** (not `authKey`) as the saved
username, so a later automatic re-login (7.1) would send the nickname as `authKey`. READ.
Consequence INFERRED; server behaviour unresolved (server-side). A client SHOULD store `authKey` instead.

R35. Third-party verify: HTTP 200 with an empty `accessToken` means "account not yet bound" and
leads to the binding UI; a non-empty token is installed. Third-party token installs do not save
an email/password for automatic re-login. READ.

R36. Password change (`PATCH`) and set (`POST /v1/user/password`) send trimmed strings. On HTTP
200 the app saves the **untrimmed** UI value as the stored password and refreshes the profile;
it does not obtain a new token. READ. A client SHOULD store exactly the value it sent (INFERRED).
