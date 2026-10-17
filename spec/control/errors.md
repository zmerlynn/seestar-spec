# Control errors: codes, wire shapes and irregular replies

This chapter lists the error codes used in replies on the JSON control servers of the imager
(TCP 4700, 4701, 4702) and the guider (TCP 4400), and how errors appear on the wire. It sits on
the envelope defined in [session handshake](session-handshake.md); per-method error lists are in
the cards under `docs/control/methods/` and `docs/guider/methods/`. Event payloads that reuse
these codes are covered in the [events overview](events-overview.md). Transport-level and
cloud errors are in [transport](../transport/) and [auth](../auth/).

## Conventions

RFC 2119 keywords bind clients. Labels are **READ**, **OBSERVED(date)**, **INFERRED** and
**unresolved**, as in `CONVENTIONS.md`. Basis: static analysis of firmware 9.31 (the imager
and guider error-string tables and the reply formatter), with the firmware 9.75 / app 3.4.0 additions tagged in [Code table](#code-table) and per-method analysis summarised in
the catalog. The 32-bit imager table was decoded separately and agrees on every shared entry.

## Errors on the wire

R1. An error reply carries a flat string `error` and an integer `code`, with no `result`, plus
the usual `jsonrpc`, `Timestamp`, `method` and `id`. READ.

```json
{"jsonrpc":"2.0","Timestamp":"1234.123456789","method":"get_solve_result","error":"no solve data","code":215,"id":19}
```

R2. `error` is not a JSON-RPC error object. A client MUST read the code from the top-level `code`
member. READ.

R3. The text is looked up from the code in a fixed table ([Code table](#code-table)). An unknown code gets the
text `fail to operate`. READ. A client MUST branch on `code`, not on the text; the text is for
logs and display. INFERRED.

R4. A handler that fails with code 0 is sent as code 207. READ. So a nonzero `code` is always
present on a handler error.

R5. Dispatcher errors (100, 101, 200, 103) are described in
[session handshake: Dispatcher](session-handshake.md#dispatcher). 100 and 200 replies have
`id: null` and no `method` member. READ.

R6. A table entry only proves the text exists. It does not prove any method can return that
code. The "Typical methods" column below lists methods whose catalog cards record the code from
per-method analysis. READ (per card).

## Code table

The imager and the guider carry **identical** tables: 166 entries with the same code and text
in both. READ. The 32-bit imager build has 165 entries: it lacks 545. READ. In firmware 9.75 the 32-bit and 64-bit tables (imager and guider) differ only by 545, 549 and 9000 to 9005, which exist only in the 64-bit build; the 32-bit tables still contain 546 to 565, 570 to 573, 436 and 437. READ. Firmware 9.75
extends the imager table; the rows from 546 are tagged accordingly (`errors` text taken from the 64-bit
imager table; see the preceding sentence for the 32-bit and guider tables). READ. Codes are grouped as: 1xx request/params, 2xx operation, 3xx guider and
equipment, 43x stacking, 5xx device operation. Gaps (for example 287 to 299, 324 to 430,
538 to 542) are unassigned in firmware 9.31; 553 to 559 and 566 to 569 are unused in firmware 9.75 too. The guider still emits 540 and 541 ([Codes outside the table](#codes-outside-the-table)).

| Code | `error` text | Meaning / notes | Typical methods |
|---:|---|---|---|
| 0 | `no error` | Success. A handler error with code 0 is sent as 207. | all |
| 100 | `invalid request` | Dispatcher: `id` present but no string `method`. `id` null, no `method` member. | any (dispatcher) |
| 101 | `parse failed` | Dispatcher: line is not valid JSON. The `error` text is the parser message, not this label. `id` null, no `method` member; sent to that socket only. | any (dispatcher) |
| 102 | `invalid params` | Params present but structurally wrong for the handler. | [`check_ai_process`](../../docs/control/methods/check_ai_process.md), [`get_img_file_page_number`](../../docs/control/methods/get_img_file_page_number.md), [`iscope_start_view`](../../docs/control/methods/iscope_start_view.md) (+15 more) |
| 103 | `method not found` | Name not in the selected table. On the main table the request may be relayed to the guider instead; a relay timeout or connection failure also gives 103 ([mount and motion R3](mount-and-motion.md#where-a-call-is-executed)). | any (dispatcher) |
| 104 | `expected int param` | A param that must be an integer is missing or has another type. | [`check_ai_process`](../../docs/control/methods/check_ai_process.md), [`check_internet`](../../docs/control/methods/check_internet.md), [`delete_sequence`](../../docs/control/methods/delete_sequence.md) (+36 more) |
| 105 | `expected string param` | Same, string. Also `verify_client` with a non-string `sign`/`data`. | [`add_list`](../../docs/control/methods/add_list.md), [`check_ai_process`](../../docs/control/methods/check_ai_process.md), [`clear_app_state`](../../docs/control/methods/clear_app_state.md) (+58 more) |
| 106 | `expected bool param` | Same, boolean. | [`clear_autosave_err`](../../docs/control/methods/clear_autosave_err.md), [`pi_set_5g`](../../docs/control/methods/pi_set_5g.md), [`pi_station_set`](../../docs/control/methods/pi_station_set.md) (+21 more) |
| 107 | `expected object param` | Same, object. | [`add_obj`](../../docs/control/methods/add_obj.md), [`del_batch_stack_file`](../../docs/control/methods/del_batch_stack_file.md), [`delete_plan`](../../docs/control/methods/delete_plan.md) (+39 more) |
| 108 | `expected float param` | Same, number. | [`add_obj`](../../docs/control/methods/add_obj.md), [`get_sensor_temperature`](../../docs/control/methods/get_sensor_temperature.md), [`import_plan`](../../docs/control/methods/import_plan.md) (+14 more) |
| 109 | `unexpected param` | A param value or member is not accepted. | [`get_control_value`](../../docs/control/methods/get_control_value.md), [`get_focuser_value`](../../docs/control/methods/get_focuser_value.md), [`iscope_start_view`](../../docs/control/methods/iscope_start_view.md) (+15 more) |
| 200 | `invalid id` | Dispatcher: no `id` (or empty request). `id` null, no `method` member. Client socket and master lookup failures in the guest-mode handlers reuse this code. | any (dispatcher) |
| 201 | `fail to connect` |  | [`close_focuser`](../../docs/control/methods/close_focuser.md), [`open_focuser`](../../docs/control/methods/open_focuser.md) |
| 202 | `already connected` |  | [`open_wheel`](../../docs/control/methods/open_wheel.md), [`guider/set_connected`](../../docs/guider/methods/set_connected.md) |
| 203 | `equipment is moving` | Mount, focuser or wheel already moving. Firmware 9.75, 64-bit build: also returned by the relay-to-slave check (see [session dispatch R31a](session-handshake/relay-routing.md#second-camera-relay-routing)) when a mount-occupying function runs locally or on the peer process, for requests that start object tracking, smart follow, a function start or a planet scan. READ. | [`calibrate_wheel`](../../docs/control/methods/calibrate_wheel.md), [`iscope_start_view`](../../docs/control/methods/iscope_start_view.md), [`set_setting`](../../docs/control/methods/set_setting.md) (+9 more) |
| 204 | `out of limit` | Index, range or limit exceeded. Also an event code for a skipped plan item. Firmware 9.75: the comet batch frame limit of 200 (stored as the thread error at start and in the batch worker; whether it reaches a reply or event is unresolved, see [stacking.md R20c](stacking.md#batch-stack)); `set_setting` motion-monitor and other limits. | [`check_pa_alt`](../../docs/control/methods/check_pa_alt.md), [`clear_plan`](../../docs/control/methods/clear_plan.md), [`delete_image`](../../docs/control/methods/delete_image.md) (+29 more) |
| 205 | `fail to disconnect` |  | none catalogued |
| 206 | `capture is active` | Refused while an exposure or capture runs. | [`delete_image`](../../docs/control/methods/delete_image.md), [`reset_sequence_progress`](../../docs/control/methods/reset_sequence_progress.md), [`start_create_dark`](../../docs/control/methods/start_create_dark.md) (+3 more) |
| 207 | `fail to operate` | Generic failure; also the substitute for a zero thread-local error value ([Thread-local error forwarding](#thread-local-err_code-forwarding)). | [`charge_only`](../../docs/control/methods/charge_only.md), [`check_pa_alt`](../../docs/control/methods/check_pa_alt.md), [`clear_plan`](../../docs/control/methods/clear_plan.md) (+86 more) |
| 208 | `disk is full` | Storage full. | [`set_plan`](../../docs/control/methods/set_plan.md), [`set_sequence`](../../docs/control/methods/set_sequence.md), [`start_exposure`](../../docs/control/methods/start_exposure.md) (+3 more) |
| 209 | `invalid value` |  | [`clear_plan`](../../docs/control/methods/clear_plan.md), [`delete_plan`](../../docs/control/methods/delete_plan.md), [`get_calib_frame`](../../docs/control/methods/get_calib_frame.md) (+27 more) |
| 210 | `not supported` | Not supported by this model, build or process (for example a wide-camera method on the main process). | [`calibrate_wheel`](../../docs/control/methods/calibrate_wheel.md), [`format_emmc`](../../docs/control/methods/format_emmc.md), [`get_camera_16bit`](../../docs/control/methods/get_camera_16bit.md) (+45 more) |
| 211 | `plate solve is already running` |  | none catalogued |
| 212 | `fail to create thread` | Worker thread could not start. | [`iscope_start_stack`](../../docs/control/methods/iscope_start_stack.md), [`iscope_start_view`](../../docs/control/methods/iscope_start_view.md), [`pi_reboot`](../../docs/control/methods/pi_reboot.md) (+15 more) |
| 213 | `image is already saved` | Extra top-level `fullname` member ([Replies with extra or missing members](#replies-with-extra-or-missing-members)). | [`save_image`](../../docs/control/methods/save_image.md), [`save_stack`](../../docs/control/methods/save_stack.md) |
| 214 | `fail to run command` |  | [`clear_downgrade`](../../docs/control/methods/clear_downgrade.md), [`format_emmc`](../../docs/control/methods/format_emmc.md), [`get_comet_position`](../../docs/control/methods/get_comet_position.md) (+16 more) |
| 215 | `no solve data` | No plate-solve result yet. | [`get_goto_solve_result`](../../docs/control/methods/get_goto_solve_result.md), [`get_last_solve_result`](../../docs/control/methods/get_last_solve_result.md), [`get_solve_result`](../../docs/control/methods/get_solve_result.md) |
| 216 | `fail to set timezone` |  | [`pi_set_time`](../../docs/guider/methods/pi_set_time.md) |
| 217 | `string is empty` |  | [`pi_encrypt`](../../docs/control/methods/pi_encrypt.md), [`pi_station_remove`](../../docs/control/methods/pi_station_remove.md) |
| 218 | `fail to write file` |  | [`fits_to_jpg`](../../docs/control/methods/fits_to_jpg.md), [`restore_factory_calib_frame`](../../docs/control/methods/restore_factory_calib_frame.md), [`set_batch_stack_setting`](../../docs/control/methods/set_batch_stack_setting.md) (+3 more) |
| 219 | `fail to read serial number` |  | none catalogued |
| 220 | `fail to read file` |  | none catalogued |
| 221 | `fail to find words` |  | [`pi_get_ap`](../../docs/control/methods/pi_get_ap.md) |
| 222 | `fail to verify SN` |  | [`pi_encrypt`](../../docs/control/methods/pi_encrypt.md) |
| 223 | `no result from command` |  | [`pi_get_ap`](../../docs/control/methods/pi_get_ap.md), [`pi_get_ap_channel`](../../docs/control/methods/pi_get_ap_channel.md), [`pi_station_list`](../../docs/control/methods/pi_station_list.md) (+2 more) |
| 224 | `cannot edit sequence unless reset the progress` | Plan or sequence must be reset first. | [`clear_plan`](../../docs/control/methods/clear_plan.md), [`clear_sequence`](../../docs/control/methods/clear_sequence.md), [`delete_plan`](../../docs/control/methods/delete_plan.md) (+6 more) |
| 225 | `xml item already exists` |  | [`add_list`](../../docs/control/methods/add_list.md), [`rename_list`](../../docs/control/methods/rename_list.md) |
| 226 | `fail to create xml key` |  | [`add_list`](../../docs/control/methods/add_list.md), [`add_obj`](../../docs/control/methods/add_obj.md) |
| 227 | `fail to write xml value` |  | none catalogued |
| 228 | `fail to read xml value` |  | none catalogued |
| 229 | `fail to open xml key` |  | [`del_list`](../../docs/control/methods/del_list.md), [`del_obj`](../../docs/control/methods/del_obj.md), [`get_obj`](../../docs/control/methods/get_obj.md) (+1 more) |
| 230 | `fail to delete xml item` |  | [`del_list`](../../docs/control/methods/del_list.md), [`del_obj`](../../docs/control/methods/del_obj.md) |
| 231 | `xml is not opened` |  | [`get_obj`](../../docs/control/methods/get_obj.md) |
| 232 | `unexpected xml type` |  | none catalogued |
| 233 | `wrong xml size` |  | none catalogued |
| 234 | `xml file name is empty` |  | [`add_list`](../../docs/control/methods/add_list.md), [`add_obj`](../../docs/control/methods/add_obj.md), [`del_list`](../../docs/control/methods/del_list.md) (+2 more) |
| 235 | `wrong xml path` |  | none catalogued |
| 236 | `xml item is not found` |  | [`add_obj`](../../docs/control/methods/add_obj.md), [`del_list`](../../docs/control/methods/del_list.md), [`del_obj`](../../docs/control/methods/del_obj.md) (+4 more) |
| 237 | `wait signal error` |  | none catalogued |
| 238 | `exposure failed` | Legacy `Exposure` `fail` when frame retries run out while the exposure worker still runs. READ | none catalogued |
| 239 | `settle timeout` |  | none catalogued |
| 240 | `settle error` |  | none catalogued |
| 241 | `send request to guider error` | Imager could not reach the guider. | [`scope_sync_planet`](../../docs/control/methods/scope_sync_planet.md) |
| 242 | `cannot dither when guide settling` |  | none catalogued |
| 243 | `run dither failed` |  | none catalogued |
| 244 | `guide settle done` |  | none catalogued |
| 245 | `run guide failed` |  | none catalogued |
| 246 | `not implemented` |  | none catalogued |
| 247 | `set shutterspeed failed` |  | none catalogued |
| 248 | `invalid buffer size` |  | none catalogued |
| 249 | `malloc buffer failed` |  | [`files/get_img_file`](../../docs/files/methods/get_img_file.md) |
| 250 | `dslr operation error` |  | none catalogued |
| 251 | `solve failed` |  | none catalogued |
| 252 | `auto goto failed` |  | none catalogued |
| 253 | `aborted` | Also an event code for a cancelled operation. Client stop commands (`stop_exposure`, `iscope_stop_view`, `stop_stack`, `stop_create_dark` and similar) record it first, so an exposure stopped by a client fails with 253. READ | none catalogued |
| 254 | `mount operation failed` |  | [`start_polar_align`](../../docs/control/methods/start_polar_align.md) |
| 255 | `file not exist` |  | [`file_rename`](../../docs/control/methods/file_rename.md), [`get_constellations`](../../docs/control/methods/get_constellations.md), [`get_disk_volume`](../../docs/control/methods/get_disk_volume.md) (+3 more) |
| 256 | `fit operation failed` |  | none catalogued |
| 257 | `create directory failed` |  | [`upload_refstar_info`](../../docs/control/methods/upload_refstar_info.md) |
| 258 | `open file failed` |  | [`fits_to_jpg`](../../docs/control/methods/fits_to_jpg.md), [`get_comet_position`](../../docs/control/methods/get_comet_position.md), [`set_batch_stack_setting`](../../docs/control/methods/set_batch_stack_setting.md) (+2 more) |
| 259 | `stack is already running` |  | [`clear_batch_stack`](../../docs/control/methods/clear_batch_stack.md), [`iscope_start_stack`](../../docs/control/methods/iscope_start_stack.md), [`remote_join`](../../docs/control/methods/remote_join.md) (+4 more) |
| 260 | `stack error, wrong format` |  | none catalogued |
| 261 | `invalid size` |  | none catalogued |
| 262 | `stack error, calibrate failed` |  | none catalogued |
| 263 | `stack error, too few stars` |  | none catalogued |
| 264 | `stack error, transform failed` |  | none catalogued |
| 265 | `stack error, align failed` |  | none catalogued |
| 266 | `stack paused` |  | none catalogued |
| 267 | `no image` |  | [`get_stack_info`](../../docs/control/methods/get_stack_info.md), [`save_stack`](../../docs/control/methods/save_stack.md), [`set_setting`](../../docs/control/methods/set_setting.md) (+1 more) |
| 268 | `operation is in progress` | Busy: another operation of the same kind runs. | [`get_enabled_plan`](../../docs/control/methods/get_enabled_plan.md), [`get_plan`](../../docs/control/methods/get_plan.md), [`import_plan`](../../docs/control/methods/import_plan.md) (+22 more) |
| 269 | `usb disk is not connected` |  | none catalogued |
| 270 | `below horizon` | Target is below the horizon. | [`start_auto_goto`](../../docs/control/methods/start_auto_goto.md), [`start_auto_goto_pixel`](../../docs/control/methods/start_auto_goto_pixel.md) |
| 271 | `file already exist` |  | none catalogued |
| 272 | `meridian flip failed` |  | none catalogued |
| 273 | `GPIO operation failed` |  | [`pi_output_get`](../../docs/control/methods/pi_output_get.md), [`pi_output_get2`](../../docs/control/methods/pi_output_get2.md), [`pi_output_set`](../../docs/control/methods/pi_output_set.md) (+1 more) |
| 274 | `calculation failed` |  | none catalogued |
| 275 | `EFW calculate threshold failed` |  | none catalogued |
| 276 | `EFW sample analysis failed` |  | none catalogued |
| 277 | `EFW move to position failed` |  | none catalogued |
| 278 | `focuser operation failed` |  | none catalogued |
| 279 | `no star is detected` |  | none catalogued |
| 280 | `exceed max iteration step` |  | none catalogued |
| 281 | `auto focus algorithm error` |  | none catalogued |
| 282 | `HFD is too large` |  | none catalogued |
| 283 | `start iginx failed` |  | none catalogued |
| 284 | `close file failed` |  | none catalogued |
| 285 | `file system limit` |  | none catalogued |
| 286 | `disk is disconnected` |  | none catalogued |
| 300 | `internal error` | Internal failure. | [`check_ai_process`](../../docs/control/methods/check_ai_process.md), [`file_rename`](../../docs/control/methods/file_rename.md), [`fits_to_jpg`](../../docs/control/methods/fits_to_jpg.md) (+39 more) |
| 301 | `cannot connect equipment when capture is active` |  | none catalogued |
| 302 | `cannot disconnect equipment when capture is active` |  | none catalogued |
| 303 | `could not start looping` |  | [`guider/loop`](../../docs/guider/methods/loop.md) |
| 304 | `could not set lock position when calibrate or guide` |  | [`guider/set_lock_position`](../../docs/guider/methods/set_lock_position.md) |
| 305 | `could not set lock position` |  | [`guider/set_lock_position`](../../docs/guider/methods/set_lock_position.md) |
| 306 | `all equipment must be connected first` |  | none catalogued |
| 307 | `dither error` |  | none catalogued |
| 308 | `cannot initiate dither while guide is in progress` |  | none catalogued |
| 309 | `cannot initiate dither while dither is in progress` |  | none catalogued |
| 310 | `cannot initiate guide while guide is in progress` |  | none catalogued |
| 311 | `cannot initiate guide while dither is in progress` |  | none catalogued |
| 312 | `cannot select if equipment are connected` |  | [`guider/select_mount_list_index`](../../docs/guider/methods/select_mount_list_index.md), [`guider/set_camera_idx`](../../docs/guider/methods/set_camera_idx.md) |
| 313 | `could not select scope` |  | none catalogued |
| 314 | `no serial device is found` |  | none catalogued |
| 315 | `mount is not connected` | Guider has no mount connection. | [`pi_set_time`](../../docs/guider/methods/pi_set_time.md), [`guider/scope_abort_slew`](../../docs/guider/methods/scope_abort_slew.md), [`guider/scope_fine_move`](../../docs/guider/methods/scope_fine_move.md) (+25 more) |
| 316 | `could not find star` |  | [`guider/find_star`](../../docs/guider/methods/find_star.md) |
| 317 | `no star selected` |  | none catalogued |
| 318 | `device not connected` | Camera or accessory not open. | [`calibrate_wheel`](../../docs/control/methods/calibrate_wheel.md), [`can_abort_expose`](../../docs/control/methods/can_abort_expose.md), [`check_photometry`](../../docs/control/methods/check_photometry.md) (+42 more) |
| 319 | `cannot issue guide pulse while calibrating or guiding` |  | [`guider/guide_pulse`](../../docs/guider/methods/guide_pulse.md) |
| 320 | `move failed` |  | [`guider/guide_pulse`](../../docs/guider/methods/guide_pulse.md) |
| 321 | `history is empty now` |  | [`guider/get_ra_dec_history`](../../docs/guider/methods/get_ra_dec_history.md) |
| 322 | `could not set param` |  | [`guider/set_algo_param`](../../docs/guider/methods/set_algo_param.md) |
| 323 | `could not get param` |  | [`guider/get_algo_param`](../../docs/guider/methods/get_algo_param.md) |
| 431 | `Dark library does not match the camera or incomplete` |  | none catalogued |
| 434 | `Save stack discrete image disabled` |  | none catalogued |
| 435 | `reference star insufficient` |  | none catalogued |
| 436 | `detected star insufficient` | Firmware 9.75 only (app 3.4.0, 64-bit build). The photometry worker stores this code in its output result on one of its internal failure branches. READ. | none catalogued |
| 437 | `reference star unavailable` | Firmware 9.75 only (app 3.4.0, 64-bit build). As 436, a sibling failure branch of the same photometry worker. READ. | none catalogued |
| 500 | `mount get coord failed` |  | none catalogued |
| 501 | `mount goto failed` | Substituted when a mount goto reply has no `code` member ([Thread-local error forwarding](#thread-local-err_code-forwarding)). READ | none catalogued |
| 502 | `mount sync failed` |  | [`scope_sync_planet`](../../docs/control/methods/scope_sync_planet.md) |
| 503 | `mount set pierside failed` |  | none catalogued |
| 504 | `save image failed` |  | none catalogued |
| 505 | `set exp failed` |  | none catalogued |
| 506 | `set bin failed` |  | none catalogued |
| 507 | `get efw pos failed` |  | none catalogued |
| 508 | `set efw pos failed` |  | none catalogued |
| 509 | `auto exp failed` |  | none catalogued |
| 510 | `calibration failed` |  | none catalogued |
| 511 | `plan time out` |  | none catalogued |
| 512 | `dawn` |  | none catalogued |
| 513 | `target time out` | Also an event code for a plan target timeout. | none catalogued |
| 514 | `interrupt` | A running operation (stacking, auto-exposure, star finding, saving, or a view plan) was interrupted inside the device, usually because the mode or page changed or another command superseded it (for star finding, also `stop_find_star` outside a capture abort; an exposure stopped by a client stop command reports 253 instead). Only these application workers produce it; the camera layer never does, so it does not indicate a camera or sensor fault. READ (producers); which internal stops occur live is INFERRED | none catalogued |
| 515 | `rename failed` | Firmware 9.75 (64-bit build): also returned by `upload_refstar_info` when the final rename of its temporary file fails (the temporary file is removed). READ. | [`file_rename`](../../docs/control/methods/file_rename.md) |
| 516 | `invalid FD` |  | none catalogued |
| 517 | `FD select fail` |  | none catalogued |
| 518 | `FD time out` |  | none catalogued |
| 519 | `FD read error` |  | none catalogued |
| 520 | `FD write error` |  | none catalogued |
| 521 | `over exposure` |  | none catalogued |
| 522 | `too few frame` |  | none catalogued |
| 523 | `too few ap` |  | none catalogued |
| 524 | `function conflict` | Conflicts with a running function (view, stack, record, calibration). Firmware 9.75, 64-bit build: also returned by the relay-to-slave check when AVI recording or the motion monitor runs locally or on the peer process (see [session dispatch R31a](session-handshake/relay-routing.md#second-camera-relay-routing)), by the updater when a module receive or script is already running ("is already updating", "is already receiving", "is already running script", a held legacy update lock), by `set_setting` when `preview.rtsp_quality` changes during AVI recording, and by the start of motion detection, motion monitor and smart follow against each other. READ. | [`iscope_start_view`](../../docs/control/methods/iscope_start_view.md), [`restore_factory_calib_frame`](../../docs/control/methods/restore_factory_calib_frame.md), [`restore_view_plan_wide_setting`](../../docs/control/methods/restore_view_plan_wide_setting.md) (+11 more) |
| 525 | `fail to read data` |  | none catalogued |
| 526 | `no bias frame` |  | none catalogued |
| 527 | `alt exceed limit` |  | none catalogued |
| 528 | `rtmp fail` |  | none catalogued |
| 529 | `decompress fail` |  | none catalogued |
| 530 | `star trails` |  | none catalogued |
| 531 | `operate database fail` |  | [`format_emmc`](../../docs/control/methods/format_emmc.md), [`set_is_favorite`](../../docs/control/methods/set_is_favorite.md) |
| 532 | `move upper limit` | Guider `Alert` event at a speed-move axis limit ([R26a](mount-and-motion/goto-and-manual-motion.md#joystick-moves-scope_speed_move)). | none catalogued |
| 533 | `move lower limit` | Guider `Alert` event at a speed-move axis limit ([R26a](mount-and-motion/goto-and-manual-motion.md#joystick-moves-scope_speed_move)). | none catalogued |
| 534 | `stack exp time too long` |  | none catalogued |
| 535 | `initialise fail` |  | none catalogued |
| 536 | `view plan is already running` | A view plan is running. | [`iscope_start_view`](../../docs/control/methods/iscope_start_view.md), [`iscope_stop_view`](../../docs/control/methods/iscope_stop_view.md), [`set_setting`](../../docs/control/methods/set_setting.md) (+7 more) |
| 537 | `shut down` | Also an event code when a plan stops for shutdown. | none catalogued |
| 543 | `8k stitch disk is full` |  | none catalogued |
| 544 | `photo metry fail` |  | none catalogued |
| 545 | `no landscap detected` |  | none catalogued |
| 546 | `ota timeout` | Firmware 9.75 only. Produced by the updater, not the imager: when an announced module binary has not arrived on the binary port within 15 s of the pending-receive mark, the updater fails that module's receive with this code and the text `ota module binary connection timeout` (the check runs about once per 5 s loop, so it fires up to about 5 s late). READ, both the 64-bit and 32-bit updater; the 32-bit build's checking function uses the identical 15000 ms and 546 constants. See [updater](../updater/index.md). | none catalogued |
| 547 | `value exceeds upper limit` | Firmware 9.75 only (64-bit build). The calibration-frame creation worker stores this code and logs it (with the catalogued error string) on one of its range-check failure paths. READ. | none catalogued |
| 548 | `value below lower limit` | Firmware 9.75 only (64-bit build). As 547, the adjacent range-check failure path of the same worker. READ. | none catalogued |
| 549 | `too few matched feature points` | Firmware 9.75 only (64-bit build). The stacking worker and the stacking library's image-setting and staged-stitching steps each compare their internal status against this code on a feature-matching failure path. READ. | none catalogued |
| 550 | `dark capture failed` | Firmware 9.75 only. The dark-creation worker returns it when a non-abort failure occurs while the temperature dark library is in use ([calibration frames R6k](calibration-frames/dark-library.md#temperature-dark-library-firmware-975)); READ for the producer, the exact failure conditions are those of that chapter. | none catalogued |
| 551 | `sky replay disk is full` | Firmware 9.75 only. Raised as an `Alert` by the sky replay worker when a session begins with less than 200 MB free ([function states R13](function-states.md#sky-replay)). READ. | none catalogued |
| 552 | `sky replay video is too short to save` | Firmware 9.75 only. Sky replay worker, when too few frames were recorded (the 20-frame minimum; link INFERRED). The feature is force-disabled in 9.75, so a live occurrence is unresolved. | none catalogued |
| 560 | `compass communication failed, check device connection` | Firmware 9.75 only. Automatic compass calibration ([polar alignment R18c](polar-alignment.md#automatic-compass-calibration-firmware-975)): reading the mount's current right-ascension angle failed during the automatic rotation. Event `CompassCalibration` `fail` carries the integer. READ. | [`start_compass_auto_calibration`](../../docs/control/methods/start_compass_auto_calibration.md) |
| 561 | `compass rotation failed, check whether the mount is blocked` | Firmware 9.75 only. Set when the choice of a safe rotation direction fails, and by the sampling timer when the automatic rotation failed with nothing stored; event `CompassCalibration` `fail`. READ. | none catalogued |
| 562 | `compass rotation timeout, check whether the mount is rotating` | Firmware 9.75 only. Event `CompassCalibration` `fail` when more than 65 s have passed since the start; stored only if no earlier failure code is stored. READ. | none catalogued |
| 563 | `compass sector coverage is insufficient, rotate the mount through a full circle` | Firmware 9.75 only. Event `CompassCalibration` `fail`. Used when the sampling gate fails or the sector coverage is still too low at the end (the stored code if any, else 563). The fit-failure classifier never returns 563: it returns 564 for interference or field instability, else the stored code, else 565. READ. | none catalogued |
| 564 | `magnetic interference detected, remove magnetic objects and retry` | Firmware 9.75 only. Event `CompassCalibration` `fail` when the interference flag is set or field instability is detected (three consecutive field-vector jumps over 300 from the baseline, or a median absolute deviation over 8.0 across the last 50 samples; units INFERRED). READ. | none catalogued |
| 565 | `compass calibration failed, please retry` | Firmware 9.75 only. Event `CompassCalibration` `fail`, the generic fallback when no stored failure code exists, also used for fewer than 10 de-duplicated samples and for a failed write of the result. READ. The first stored failure code wins. | none catalogued |
| 570 | `encrypted session required` | Firmware 9.75 only. Protected Wi-Fi password fields without an active crypto session. Detail: [secure communication](secure-communication.md). `get_device_state` does not return it for a missing session (it omits the password); only `pi_get_ap` and `pi_station_set` do. | [`pi_get_ap`](../../docs/control/methods/pi_get_ap.md), [`pi_set_ap`](../../docs/control/methods/pi_set_ap.md), [`pi_station_set`](../../docs/control/methods/pi_station_set.md) |
| 571 | `invalid encrypted data` | Firmware 9.75 only. As 570; `get_device_state` can return 571 to 573 for an actual encoding failure. | as 570, [`get_device_state`](../../docs/control/methods/get_device_state.md) |
| 572 | `encrypted data replay rejected` | Firmware 9.75 only. As 570. | as 570 |
| 573 | `cryptographic operation failed` | Firmware 9.75 only. As 570. | as 570 |
| 9000 | `comet label not found` | Firmware 9.75 table (imager). Raised by the comet stacking steps that locate prepared and all frames (label not found). READ (text and raisers). | none catalogued |
| 9001 | `comet label invalid` | As 9000 (label invalid, same two steps). | none catalogued |
| 9002 | `comet center fail` | As 9000. Raised by reference-frame choice, registration (empty temporary read), no valid centre, the dual-stack split detector initialisation, locating all frames, and the new batch preflight when its detector cannot initialise. | none catalogued |
| 9003 | `comet register fail` | As 9000. Raised when the registration reference patch fails. | none catalogued |
| 9004 | `comet too few frame` | As 9000; the code was already used in firmware 9.31 ([Codes outside the table](#codes-outside-the-table)), where it had no table text. Raised when too few frames remain at stacking, registration, centre location or selection, and by the batch worker when too few candidates remain. | none catalogued |
| 9005 | `comet not found` | As 9000; the code was already used in firmware 9.31 ([Codes outside the table](#codes-outside-the-table)), where it had no table text. Firmware 9.75: now also raised by the new batch comet preflight when it finds no frame containing a comet. | none catalogued |

Methods shown without a `guider/` prefix are imager methods on 4700; `guider/` methods are
served on 4400 and reach 4700 clients through the relay. `files/` methods are on the file
socket (4801), which uses a different framing ([media](../media/)).

## Codes outside the table

| Code | Where | Text | Label |
|---|---|---|---|
| 1 | Reply of a command-execution helper method when the shell call fails. | `runPopen error` (explicit text) | READ |
| 429 | [`Alert`](../../docs/control/events/Alert.md) event only, connection limit. Never an RPC reply. | `Msg`: `Exceed the maximum number of connections` | READ |
| 540, 541 | Guider [`Alert`](../../docs/control/events/Alert.md) event at a speed-move axis limit ([R26a](mount-and-motion/goto-and-manual-motion.md#joystick-moves-scope_speed_move)). Not in the table. | `fail to operate` (fallback text) | READ |
| 101 text | Parse failure. Code is in the table but the text is the parser's message. | dynamic | READ |
| -1 | Mount command path when the mount controller does not reply. | `fail to operate` | READ |
| any mount value | Numeric `result` or `code` copied from a mount-controller reply ([Thread-local error forwarding](#thread-local-err_code-forwarding)). | `fail to operate` unless the number is in the table | READ |
| 9004, 9005 | Batch-stack file check; 9004 also in comet stacking. Firmware 9.31: not in the table. Firmware 9.75: in the table (rows 9004 and 9005 of [Code table](#code-table)). | `fail to operate` in 9.31 | READ |
| 9000 to 9005 | Firmware 9.75: listed in the 64-bit tables with the texts in [Code table](#code-table); absent from the 32-bit tables. | table text | READ |

## Thread-local `err_code` forwarding

Here "TLS" means the firmware's thread-local error variable, not Transport Layer Security.

R7. Many handlers do not choose a code themselves. They call deeper helpers (equipment drivers, file
and XML helpers, the stacker) which set the thread-local error value, and the handler then replies
with that value through the common error formatter. READ. Consequences:

- The code a client sees can come from any helper on the call path, so the set of codes per method
  is wider than the method's own logic. READ.
- A helper that fails without setting the thread-local error value leaves 0, which is sent as 207.
  READ.
- Vendor camera, focuser and peripheral library return codes are internal. The device collapses each
  one to success or failure and reports a fixed application code, typically 318, never the library's
  own value; the library code appears only in device logs. A client therefore never sees a negative
  or library-specific code. READ (64-bit build, every camera-library call site), INFERRED (32-bit
  build, same design).

R7a. Two sources can put codes outside the table into the thread-local error value. READ.

- Mount-controller replies. The device forwards the mount's numeric result or error code,
  uses 501 when a goto reply has no code, and uses -1 when the mount does not reply. Any value
  the mount firmware sends can therefore reach the client. READ.
- Imager-internal codes, such as 9004 and 9005 from batch and comet stacking (firmware 9.75: 9005 also from the comet preflight; the comet frame limit stores 204). READ.

Both kinds get the text `fail to operate`. READ. Image-buffer and stacker results are also copied
into the thread-local error value. They stay inside the table: image-buffer reallocation sets 248 or
249, and the stacked-image results of the live, mosaic, starry, star-trail, batch and comet stackers
are 0, 249, 260, 261 or 267. READ (64-bit build; 32-bit not checked). A lock failure there is not
reported as a code.

R8. A client MUST handle any code on any method, at minimum as a generic failure with the given
text. INFERRED.

## Replies with extra or missing members

These shapes are READ unless marked. Each is a reason for R16 of the
[session handshake](session-handshake.md#reply-envelope): match by `id`, tolerate anything
else.

| Method | Shape | Label |
|---|---|---|
| [`save_image`](../../docs/control/methods/save_image.md), [`save_stack`](../../docs/control/methods/save_stack.md) | Code 213 adds a top-level string `fullname` (the existing file), no `result`. | READ |
| [`check_pa_alt`](../../docs/control/methods/check_pa_alt.md) | Some failure paths carry both `error`/`code` and `result`, with two `code` members: the failure code, then 0. A parser that keeps the last duplicate sees code 0 although `error` is present, so a receiver MUST treat any reply with `error` as a failure. | READ |
| [`start_create_hpc`](../../docs/control/methods/start_create_hpc.md) | After a relay failure the reply can contain `error` and `code` twice (duplicate members). A parser keeping the last value sees the later pair. | READ |
| [`stop_func`](../../docs/control/methods/stop_func.md) | A failure relaying to the auxiliary process replaces the whole reply with `error`, `code` and `id` only: no `jsonrpc`, `Timestamp` or `method`. | READ |
| [`get_pcdid`](../../docs/control/methods/get_pcdid.md) | If the command fails, the reply has only envelope metadata: no `result`, `error` or `code`. | READ |
| [`start_func`](../../docs/control/methods/start_func.md) | The go-to-pixel variant with invalid coordinates replies with metadata only. | READ |
| [`get_wheel_state`](../../docs/control/methods/get_wheel_state.md) | Envelope `code` 0 with `error` and `code` members inside `result`. | READ |
| [`get_view_plan_stack_result`](../../docs/control/methods/get_view_plan_stack_result.md) | `result` contains an `error_code` data member; it is not a reply error. | READ |
| Dispatcher 100 / 200 | `id: null`, no `method`. | READ |

R9. A reply with no `code` and no `result` SHOULD be treated as completed with no data, not as
an error. INFERRED.

R10. A client MUST NOT reject a reply because of duplicate members; it SHOULD keep the last
value. INFERRED.

## Error codes in events

Several events reuse table codes in their own `code` and `error` members, usually with a
failure `state`. In plan and target events: 204 (item skipped), 253 (cancelled), 513 (target
timed out), 537 (stopped for shutdown). READ. Feature events report failures as
`state: "fail"` with `code` and `error`. READ. See [events overview](events-overview.md) and
[plan scheduling](plan-scheduling.md).

## Open questions

- The set of numeric codes the mount firmware can send (R7a).
- Whether codes 211, 219, 220 and the other table entries with no catalogued method are
  reachable in 9.31.
- Exact parity with the 32-bit build for entries the 32-bit decode did not cover.
