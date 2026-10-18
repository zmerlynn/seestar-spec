# Control dispatch: second-camera relay routing

Part of [Control session](../session-handshake.md), dispatcher [Dispatcher](../session-handshake.md#dispatcher). Basis: static analysis of firmware 9.75, 64-bit build.

## Second-camera relay routing

R31a. Firmware 9.75, 64-bit build: the relay-to-slave check. Several handlers call it before
acting. It returns "proceed locally" or "handled or relayed". The conditions, READ:

- Gating. The check does nothing (proceed locally) unless the process is the main process of a
  dual-camera device (the global that selects this is INFERRED). With view mode 0 it also proceeds
  locally unless the wide camera can view stars; with a view mode above 5 it proceeds locally.
- Mount check (request types 1 and 3). If the mount-occupying state is true locally, the reply is
  203 (`equipment is moving`). Otherwise the main process asks the second process
  `is_func_occupy_mount` with a 10 s wait; a reply that contains `"result":true` gives 203.
- Recording-conflict check (request types 2 and 3). If an AVI recording or the motion monitor
  runs locally, the reply is 524 (`function conflict`). Otherwise the main process asks the second
  process `is_func_work` for the keys `AviRecord` and `MotionMonitor` with a 10 s wait; a reply
  that contains `"result":true` gives 524.
- Relay step. If the caller's relay flag is false, or a global that marks the process as already
  the slave side is set, the request proceeds locally. Otherwise it is relayed to the second
  process and the local handler stops. A second flag selects a relay variant that carries the main
  stack's explicit context.
- Type 0 (no check) only decides between local handling and relay; it returns neither 203 nor 524.

Callers and their request types: `start_track_object` (type 1, and a second call whose type is true
only when object tracking is not already running), `start_smart_follow` and the generic function
start (type 1), `start_scan_planet` (type 1, relay flag false), `start_motion_monitor` (type 3),
`start_record_avi` (type 2), and `set_setting` (type 0; see the settings qualifications below). Handlers that use
the type-0 form include `is_stacked`, `iscope_match_target_name`, `iscope_accept_target_name`,
`clear_app_state`, `stop_motion_monitor`, `stop_record_avi`, `start_auto_focuse`,
`stop_auto_focuse`, `save_image`, `check_ai_process`, `start_ai_process`, `iscope_start_stack`,
`iscope_stop_view`, `get_annotate_result`, `get_stack_info` and `move_focuser`; for these the relay variant was not always checked. The 9.31 behaviour of the check
was not diffed; the 32-bit build has an older four-argument form whose conditions were not traced.

Firmware 9.31 D64 and firmware 9.75 D64: the `set_setting` branches for `ae_bri_percent`, `isp_exp_ms`, `manual_exp`, `isp_gain`, `rtsp_roi_index` and `rtsp_roi_scale` use five type-0 call sites and select ordinary relay when the existing relay gates permit forwarding. Their variant flag is false, so these calls do not select the variant carrying the main stack exposure. The `planet_correction` branch disables relaying and passes type 1 when enabling correction or type 0 when disabling it; its variant flag is also false. Firmware 9.31 D32 and firmware 9.75 D32 have no relay-variant argument: the five reduced calls select ordinary relay, and the planet-correction caller likewise disables relaying and supplies the boolean-derived request type. READ. These caller findings do not resolve every other caller's variant, broader D32 limiter arithmetic or all relay-condition version differences.

## Open questions

- The meaning of the two globals in R31a, its 9.31 behaviour and its 32-bit conditions.
