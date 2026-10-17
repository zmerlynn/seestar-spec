# seestar-spec

An independent, clean-room description of the control protocol of ZWO Seestar smart telescopes
(Kalay/IOTC tunnel transport, LAN control on TCP 4700, JSON-RPC-style methods, events).
Baseline: static analysis of firmware 9.31 and app 3.3.2, plus on-device observation.
Version-tagged extensions cover firmware 9.75 and app 3.4.0 (including iOS app 3.4.0 where stated).
No code or documentation from other implementations was used.

Layout. Prose chapters (`spec/`) explain behaviour; the catalog (`catalog/`) is the machine-readable source of truth for catalogued methods and events, and each entry links back to its chapter section.

| Path | What |
|---|---|
| `spec/00-overview.md` | [Start here](spec/00-overview.md): stack diagram, process/port table, reading guide, glossary, open questions. |
| `spec/transport/` | Below the JSON layer: Kalay IOTC session (`iotc/`), RDT reliable streams (`rdt/`), the P2P port tunnel (`p2p-tunnel/`), LAN discovery and the port map (`ports.md`); separately, the [BLE activation boundary](spec/transport/ble.md), a local provisioning path unrelated to the IOTC/P2P remote-access stack above. |
| `spec/auth/` | Cloud allocation and master/relay servers (`cloud-auth/`), account login (`account-login/`). |
| `spec/control/` | The imager's TCP 4700 JSON protocol: session handshake, errors, events, and topic chapters (viewing, stacking, mount, plans, system, ...). |
| `spec/guider/`, `spec/updater/`, `spec/media/` | The guider on 4400 and its serial bridge; the updater on 4350/4361; image, file and video channels. |
| `catalog/index.yaml` | Top-level index: the list of services. An entry id is `<service>/<name>`; names are unique across services. |
| `catalog/<service>/` | One service: `index.yaml` (entries, envelope rules, transport notes), `methods/`, `events/`, `schemas/`. Services: `control` (TCP 4700), `guider` (TCP 4400), `files` (image/file sockets), `serial-bridge`, `updater` (TCP 4350), `discovery`, `video`, `cloud`. The cloud and video indexes intentionally have no entries: their protocols are documented in prose. |
| `catalog/<service>/{methods,events}/` | Source of truth: one JSON Schema (2020-12) YAML file per method or event. |
| `catalog/common/schemas/` | Shared definitions: ids, timestamps, request/reply/event envelopes. |
| `docs/<service>/{methods,events}/` | Generated per-method and per-event pages, [indexed by service](docs/index.md). Do not edit by hand. |
| `tools/` | Generator, lint and the permalink checker. |
| `CONVENTIONS.md` | [Keywords, confidence labels, side-effect tiers](CONVENTIONS.md), and the rules for editing this repository. |

## Versions and links

Link to the `v1` branch, e.g. `blob/v1/spec/00-overview.md#reading-guide`. Links on `v1` keep working: content that moves or is withdrawn leaves a notice at its old location. For a citation that never changes, use a commit permalink (press `y` on GitHub). `main` is development; don't link to it. If a version 2 ships, `v1` stays frozen and `v2` starts.

Covered: spec chapters, reference cards and their indexes, catalog files, README and CONVENTIONS, by file and by section heading. Not covered: line links, query strings, raw/download views and other files. See [Permalink compatibility](CONVENTIONS.md#permalink-compatibility).

License: CC0 1.0 (see LICENSE).
