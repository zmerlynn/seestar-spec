# seestar-spec

An independent, clean-room description of how clients talk to ZWO Seestar smart telescopes: the
remote path through the ZWO cloud and the Kalay/IOTC peer-to-peer service (the app's "Telescope
Network": account login, relay authorization, IOTC session, RDT streams, P2P port tunnel), the
direct local-network path, the JSON control protocol on TCP 4700 with its methods and events, and
the guider, media, serial-bridge, updater and BLE activation interfaces.

Basis: static analysis of firmware 9.31 (64-bit build as reference, 32-bit as corroboration) and the
Android app 3.3.2, plus observation of a real device and of the iOS app. Firmware 9.75 and app 3.4.0
(Android, and iOS where stated) are covered as version-tagged extensions. No code or documentation
from other implementations was used.

Layout. Prose chapters (`spec/`) explain behaviour; the catalog (`catalog/`) is the machine-readable source of truth for catalogued methods and events, and each entry links back to its chapter section.

| Path | What |
|---|---|
| `spec/00-overview.md` | [Start here](spec/00-overview.md): stack diagram, process/port table, reading guide, glossary, open questions. |
| `spec/transport/` | Below the JSON layer: the port map, LAN discovery, the Kalay IOTC session (detail in `iotc/`), RDT reliable streams, the P2P port tunnel, and the BLE activation boundary, a local provisioning path separate from remote access. [Contents](spec/transport/index.md). |
| `spec/auth/` | Account login and token handling (`account-login/`); cloud allocation, licence, master and relay servers (`cloud-auth/`). [Contents](spec/auth/index.md). |
| `spec/control/` | The imager's TCP 4700 JSON protocol: session handshake, errors, events, and topic chapters (viewing, stacking, mount, plans, system, ...). [Contents](spec/control/index.md). |
| `spec/guider/`, `spec/media/`, `spec/updater/` | The guider on 4400, its mount serial command set and the serial bridge; image sockets, the album and file socket, video and SMB; the updater on 4350 and 4361, update-package processing and the firmware 9.75 package contents. Contents: [guider](spec/guider/index.md), [media](spec/media/index.md), [updater](spec/updater/index.md). |
| `catalog/index.yaml` | Top-level index: the list of services. An entry id is `<service>/<name>`; names are unique across services. |
| `catalog/<service>/` | One service: `index.yaml` (entries, envelope rules, transport notes), `methods/`, `events/`, `schemas/`. Services: `control` (TCP 4700), `guider` (TCP 4400), `files` (image/file sockets), `serial-bridge`, `updater` (TCP 4350), `discovery`, `video`, `cloud`. The cloud and video indexes intentionally have no entries: their protocols are documented in prose. |
| `catalog/<service>/{methods,events}/` | Source of truth: one JSON Schema (2020-12) YAML file per method or event. |
| `catalog/common/schemas/` | Shared definitions: ids, timestamps, request/reply/event envelopes. |
| `docs/` | Generated per-method and per-event cards under `docs/<service>/{methods,events}/`, [indexed by service](docs/index.md). Do not edit by hand. |
| `tools/` | Generator, lint and the permalink checker. |
| `CONVENTIONS.md` | [Keywords, confidence labels, side-effect tiers](CONVENTIONS.md), and the rules for editing this repository. |

## AI use

This specification was created by AI, guided by a human. AI models (Anthropic's Claude and OpenAI's
GPT models) did the static analysis of firmware and app binaries, wrote the prose, catalog and
tools, and cross-checked each other's findings. A human maintainer set the scope and the clean-room
rules, made the design decisions, provided the device used for observations and approves what is
published. Every claim carries a confidence label (READ, OBSERVED, INFERRED, unresolved) so you can
tell what the evidence supports; treat anything not labelled READ or OBSERVED with care, and report
errors as issues.

## Affiliation and warranty

This project is not affiliated with, endorsed by or supported by ZWO or ThroughTek. Seestar, ZWO,
Kalay and other names are trademarks of their owners and are used only to identify what is
described.

It is provided as is, without warranty of any kind (see section 4 of the CC0 1.0 legal code in
[LICENSE](LICENSE)). It describes specific firmware and app versions; others may differ. Talking to
a device is at your own risk: some methods move the mount, change settings, erase data or install
firmware (see the side-effect tiers in [CONVENTIONS](CONVENTIONS.md)), and use of vendor cloud
services is subject to their terms.

## Versions and links

Link to the `v1` branch, e.g. `blob/v1/spec/00-overview.md#reading-guide`. Links on `v1` keep working: content that moves or is withdrawn leaves a notice at its old location. For a citation that never changes, use a commit permalink (press `y` on GitHub). `main` is development; don't link to it. If a version 2 ships, `v1` stays frozen and `v2` starts.

Covered: spec chapters, reference cards and their indexes, catalog files, README and CONVENTIONS, by file and by section heading. Not covered: line links, query strings, raw/download views and other files. See [Permalink compatibility](CONVENTIONS.md#permalink-compatibility).

License: CC0 1.0 (see [LICENSE](LICENSE)).
