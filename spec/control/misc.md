# Miscellaneous control methods

This index points to the topic chapters that own control methods. Only `set_page` and `get_fov` are specified here.

Basis: static analysis of firmware 9.31 (64-bit build; 32-bit build probable) and app 3.3.2, unless a line says otherwise. Labels follow [CONVENTIONS.md](../../CONVENTIONS.md).

| Methods | Primary chapter |
|---|---|
| controls, subframe, `set_isp_fps` | [viewing-and-exposure.md](viewing-and-exposure.md#camera-and-isp-settings) |
| `start_view_star_sleep`, `format_emmc`, `charge_only` | [power-and-storage.md](power-and-storage.md) |
| `test_connection`, `get_phone_list` | [session-handshake.md](session-handshake.md) |
| `pi_station_list` | [network.md](network.md#station-wi-fi-client) |
| `stop_send` | [../media/image-sockets.md](../media/image-sockets.md#streaming-start-and-stop) |
| solve, find star, AI processing | [solving-and-annotation.md](solving-and-annotation.md) |
| `get_merid_delta` | [mount-and-motion.md](mount-and-motion/tracking-park-and-state.md#meridian-flip) |
| albums, `fits_to_jpg`, favourites | [../media/files-and-album.md](../media/files-and-album.md#album-methods-on-4700) |
| `start_create_hpc` | [calibration-frames.md](calibration-frames/frames-and-interactions.md#hot-pixel-correction-hpc) |
| `is_downgraded`, `play_sound`, `get_pcdid`, factory and diagnostic methods | [maintenance.md](maintenance.md) |


## Pages

### Page selection

R1. [`set_page`](../../docs/control/methods/set_page.md) takes a bare string page name,
case-insensitive. READ.

| Page | Code | Side effects (READ) |
|---|---|---|
| `preview` | 0 | |
| `focus` | 1 | |
| `autosave` | 2 | |
| `pa` | 3 | |
| `stack` | 4 | |
| `rtmp` | 5 | starts the live stream |
| `plan` | 6 | plan page; affects legacy plan getters |

Changing page can change exposure mode and binning, and can stop the stream or polar alignment.
READ. Errors: 105 not a string, 109 unknown page, 318 camera closed, 268 busy. READ.


## Field of view

R2. [`get_fov`](../../docs/control/methods/get_fov.md) returns `[horizontal, vertical]` in
degrees (INFERRED), from pixel size, binning, sensor size and focal length. It fails (207 or a
camera error) for focal length <= 1 or bad camera data. READ.


## Open questions

See the owning chapters above for their open questions, including [relay routing](session-handshake/relay-routing.md#open-questions).

## Relocated sections

These anchors retain navigation from generated cards; the linked sections are the primary text.

<a id="21-pages"></a>

- [Page selection](misc.md#page-selection)

<a id="3-connectivity-helpers"></a>

- [Connectivity helpers](session-handshake.md#connectivity-helpers); saved-network listing is in [Network](network.md#saved-network-listing-details).

<a id="41-plate-solve"></a>

- [Plate solve](solving-and-annotation.md#plate-solve)

<a id="43-field-of-view-and-meridian"></a>

- [Field of view](misc.md#field-of-view); meridian handling (`get_merid_delta`) is in
  [mount-and-motion.md](mount-and-motion/tracking-park-and-state.md#meridian-flip).

