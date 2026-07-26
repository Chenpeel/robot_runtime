"""Latch driver safety stops and reject commands older than the stop fence."""

import threading


_STOP_COMMANDS = frozenset(("move_stop", "motion_stop", "stop_motion"))
_MOTION_COMMANDS = frozenset(
    (
        "move",
        "send_position",
        "move_command",
        "move_time_write",
        "move_time_wait_write",
        "move_start",
        "motion_continue",
        "continue_motion",
    )
)


def normalize_protocol_command(command: str) -> str:
    """Normalize driver protocol commands and aliases."""
    normalized = str(command or "").strip().lower()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    if normalized.startswith("encode_"):
        normalized = normalized[len("encode_"):]
    if normalized.startswith("servo_"):
        normalized = normalized[len("servo_"):]
    return normalized


def is_stop_command(command: str) -> bool:
    """Return whether a protocol command is a safety stop."""
    return normalize_protocol_command(command) in _STOP_COMMANDS


def is_motion_command(command: str) -> bool:
    """Return whether a protocol command can start or resume motion."""
    return normalize_protocol_command(command) in _MOTION_COMMANDS


class DriverSafetyLatch:
    """Gate driver commands around an authoritative safety stop."""

    def __init__(self):
        self._lock = threading.Lock()
        self._latched = False
        self._fence_ns = 0
        self._last_authority_ns = 0

    @property
    def latched(self) -> bool:
        with self._lock:
            return self._latched

    @property
    def fence_ns(self) -> int:
        with self._lock:
            return self._fence_ns

    def activate(self, now_ns: int) -> None:
        """Latch safety and advance the local command fence."""
        with self._lock:
            self._latched = True
            self._fence_ns = max(self._fence_ns, int(now_ns))

    def observe_authority(self, active: bool, stamp_ns: int, now_ns: int) -> bool:
        """Apply an authoritative safety state from execution_manager.

        Active states always latch. A release must be newer than both the local
        fence and the previous authoritative state.
        """
        authority_ns = int(stamp_ns)
        with self._lock:
            if active:
                self._last_authority_ns = max(
                    self._last_authority_ns,
                    authority_ns,
                )
                self._latched = True
                authority_fence_ns = authority_ns if authority_ns > 0 else int(now_ns)
                self._fence_ns = max(self._fence_ns, authority_fence_ns)
                return True
            if authority_ns <= self._last_authority_ns:
                return False
            self._last_authority_ns = authority_ns
            if authority_ns <= self._fence_ns:
                return False
            changed = self._latched
            self._latched = False
            return changed

    def admit(self, stamp_ns: int, is_stop: bool = False, now_ns: int = 0) -> bool:
        """Return whether a stamped command may enter the driver.

        Stops always pass after advancing the fence. Motion is rejected while
        latched and remains rejected after release when its stamp is stale.
        """
        if is_stop:
            self.activate(int(now_ns))
            return True
        command_ns = int(stamp_ns)
        with self._lock:
            if self._latched:
                return False
            if self._fence_ns == 0:
                return True
            return command_ns > self._fence_ns

    def admit_protocol_command(
        self,
        command: str,
        now_ns: int,
        stamp_ns: int = 0,
    ) -> bool:
        """Gate a generic protocol command while always allowing stops."""
        if is_stop_command(command):
            return self.admit(stamp_ns=0, is_stop=True, now_ns=now_ns)
        if not is_motion_command(command):
            return True
        return self.admit(stamp_ns=stamp_ns, now_ns=now_ns)


def ros_time_to_ns(stamp) -> int:
    """Convert a ROS-compatible time value to nanoseconds."""
    if stamp is None:
        return 0
    try:
        return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)
    except (AttributeError, TypeError, ValueError):
        return 0
