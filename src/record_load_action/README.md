# Action Resource Package

This package stores action resources and playback helpers (BVH now, more modes later).

## Layout

- config/bvh_action_map.json: BVH action config
- config/bvh/*.bvh: BVH files
- config/bvh/*.json: per-action frame data (for example `walking.json`)
- config/bvh/name.json: BVH skeleton bones list

## BVH Config (bvh_action_map.json)

Key fields:
- bvh_list: action list (index or name triggers)
- bvh_dir: BVH directory (relative to this config)
- bvh_action_files: action file map, supports `action_name -> action.json` and `name.bvh -> name.json`
- bvh_data: inline action map (legacy fallback, still supported)
- joint_alias: BVH bone name to robot joint key alias
- joint_map: robot joint key to servo ID mapping
- servo_limits: per-servo min/max (override defaults)

Directory default:

```
config/bvh/
```

Runtime playback now resolves `config/bvh_action_map.json` from
`record_load_action` by default. `robot_bringup` and `websocket_bridge`
no longer expose `bvh_action_file` as a public launch/config parameter.

Example:

```json
{
  "bvh_dir": "bvh",
  "bvh_list": [null, "walking"],
  "bvh_action_files": {
    "walking.bvh": "walking.json"
  },
  "joint_alias": { "pelvis.L": "hip.L" },
  "joint_map": { "hip.L": { "left_hip_joint": "3" } },
  "servo_limits": { "3": { "min": 700, "max": 2300 } }
}
```

Action file (`config/bvh/walking.json`) example:

```json
{
  "bvh_file": "walking.bvh",
  "frame_delay_ms": 33.0,
  "frames": [
    [{ "id": 1, "position": 1500, "speed": 33, "servo_type": "bus" }]
  ]
}
```

## Runtime Behavior

- BVH/demo playback publishes `MotionCommand` to `/execution/motion/command`.
- It does not reuse the teleop command entry.
- If teleop is currently active, a new BVH playback request is rejected.
- If teleop becomes active during playback, the current BVH playback is stopped.
- `BvhPlaybackRuntime` creates and owns `BvhActionPlayer`, and serializes play,
  blocked-state changes, and close operations. Transport adapters hold the
  runtime, not the player itself.
- Entering blocked state closes admission before stopping current playback.
  If that stop is incomplete, a repeated `set_blocked(True)` retries it even
  though the blocked state itself did not change. Once stopping completes,
  repeated blocked calls do not stop again. The bool result still reports only
  whether the blocked state changed. Explicit stop requests remain valid while
  blocked or closed.
- `close()` enters the closed/blocked terminal state and stops the player. If
  stopping fails, close remains incomplete so a later `close()` can retry.
- Each player worker generation has its own `threading.Event`. `play()` and
  `stop()` return bool results, and a replacement worker is started only after
  the previous worker is confirmed stopped. A timed-out live worker remains
  tracked and causes replacement playback to be rejected.
- The accepted `bvh_play_ack` shape, `TELEOP_CONTROL_REJECTED` category for
  teleop blocking, and `ROS_CALLBACK_FAILED` category for player operation
  failures remain transport-owned and stable. The motion output topic, timing
  field forwarding, and teleop interlock also remain stable.
- A player result of explicit `False` is now surfaced through the existing
  `ROS_CALLBACK_FAILED` category. The old player API did not expose that bool
  failure, so this is an intentional, observable safety tightening.

## Play Request Contract

`record_load_action.bvh_player.normalize_bvh_play_request` owns the
transport-independent normalization of explicit `bvh_play` requests. The
accepted direct fields are:

- `action`: action name, or `null` to stop playback
- `loop`
- `speed_ms`
- `playback_rate`
- `frame_ms`

Legacy nested `action.bvh` payloads and the top-level `bvh` alias are not
accepted. Transport adapters such as `websocket_bridge` remain responsible
for their own acknowledgement and error response formats.

## Static Conversion (optional)

Runtime playback parses BVH directly in `record_load_action/bvh_player.py`.
Use `bvh_static_convert` when you want offline conversion to pre-baked frames.

Use the built-in converter:

```
ros2 run record_load_action bvh_static_convert --in-place
```

Or write to a new file (default):

```
ros2 run record_load_action bvh_static_convert
```

Notes:
- `--in-place` updates source files directly.
- For decoupled config, action files in `config/bvh/*.json` are updated in-place.
- Without `--in-place`, output is a merged JSON file with converted `bvh_data`.

Optional flags:

- `--output ./bvh_action_map.frames.json`
- `--force` re-generate existing frames
- `--drop-bvh-file` remove bvh_file/path fields
- `--only walking,strafing` convert specific actions
