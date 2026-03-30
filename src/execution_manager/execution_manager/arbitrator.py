"""执行层纯逻辑仲裁器。"""

from dataclasses import dataclass
from typing import Callable, Optional
import uuid


@dataclass(frozen=True)
class ArbitrationResult:
    """单次命令仲裁结果。"""

    accepted: bool
    mode: str
    reason: str
    active_source: Optional[str]


class CommandArbitrator:
    """最小执行仲裁器。"""

    TELEOP_CONTROL_ACTIONS = {'claim', 'keepalive', 'release'}

    def __init__(
        self,
        teleop_timeout_sec: float = 0.8,
        motion_timeout_sec: float = 0.5,
        lease_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.teleop_timeout_sec = max(float(teleop_timeout_sec), 0.0)
        self.motion_timeout_sec = max(float(motion_timeout_sec), 0.0)
        self.lease_id_factory = lease_id_factory or self._default_lease_id_factory

        self.mode = 'idle'
        self.active_source: Optional[str] = None
        self.estop_active = False
        self.teleop_holder_id = ''
        self.teleop_lease_id = ''

        self.last_teleop_control_time: Optional[float] = None
        self.last_motion_time: Optional[float] = None

        self.last_teleop_control_action = ''
        self.last_teleop_control_accepted = False
        self.last_teleop_control_reason = ''
        self.teleop_control_accepted_count = 0
        self.teleop_control_rejected_count = 0

        self.accepted_counts = {'teleop': 0, 'motion': 0}
        self.rejected_counts = {'teleop': 0, 'motion': 0}
        self.last_rejection_reason = ''

    def receive_command(
        self,
        source: str,
        now_sec: float,
        requester_id: str = '',
        lease_id: str = '',
    ) -> ArbitrationResult:
        """处理一条执行请求。"""
        self._validate_source(source)
        self._refresh_mode(now_sec)
        normalized_requester_id = str(requester_id).strip()
        normalized_lease_id = str(lease_id).strip()

        if self.estop_active:
            return self._reject(source, 'estop')

        if source == 'teleop' and not self._is_teleop_control_active(now_sec):
            return self._reject(source, 'teleop_control_not_granted')

        if source == 'teleop' and not normalized_requester_id:
            return self._reject(source, 'teleop_requester_id_required')

        if source == 'teleop' and not self._is_holder(normalized_requester_id):
            return self._reject(source, 'teleop_control_not_holder')

        if source == 'teleop' and self.teleop_lease_id and not normalized_lease_id:
            return self._reject(source, 'teleop_control_lease_required')

        if source == 'teleop' and not self._is_lease_holder(normalized_lease_id):
            return self._reject(source, 'teleop_control_lease_mismatch')

        if source == 'motion' and self._is_source_active('teleop', now_sec):
            return self._reject(source, 'teleop_active')

        if source == 'motion':
            self.last_motion_time = now_sec

        self.accepted_counts[source] += 1
        self._refresh_mode(now_sec)
        return ArbitrationResult(
            accepted=True,
            mode=self.mode,
            reason='accepted',
            active_source=self.active_source,
        )

    def receive_teleop_control(
        self,
        action: str,
        now_sec: float,
        requester_id: str = '',
        lease_id: str = '',
    ) -> ArbitrationResult:
        """处理 teleop 控制权动作。"""
        normalized_action = str(action).strip().lower()
        normalized_requester_id = str(requester_id).strip()
        normalized_lease_id = str(lease_id).strip()
        self.last_teleop_control_action = normalized_action
        self._refresh_mode(now_sec)

        if normalized_action not in self.TELEOP_CONTROL_ACTIONS:
            return self._reject_teleop_control(
                normalized_action,
                'unsupported_teleop_control_action',
            )

        if normalized_action == 'claim':
            if self.estop_active:
                return self._reject_teleop_control(normalized_action, 'estop')
            if self._is_teleop_control_active(now_sec) and not self._is_holder(
                normalized_requester_id
            ):
                return self._reject_teleop_control(
                    normalized_action,
                    'teleop_control_held_by_other',
                )
            self.teleop_holder_id = normalized_requester_id
            self.teleop_lease_id = self._claim_lease_id(
                now_sec,
                normalized_requester_id,
                normalized_lease_id,
            )
            self.last_teleop_control_time = now_sec
            return self._accept_teleop_control(
                normalized_action,
                now_sec,
                holder_id=normalized_requester_id,
                lease_id=self.teleop_lease_id,
            )

        if normalized_action == 'keepalive':
            if not self._is_teleop_control_active(now_sec):
                return self._reject_teleop_control(
                    normalized_action,
                    'teleop_control_not_granted',
                )
            if not self._is_holder(normalized_requester_id):
                return self._reject_teleop_control(
                    normalized_action,
                    'teleop_control_not_holder',
                )
            if normalized_lease_id and not self._is_lease_holder(normalized_lease_id):
                return self._reject_teleop_control(
                    normalized_action,
                    'teleop_control_lease_mismatch',
                )
            self.last_teleop_control_time = now_sec
            return self._accept_teleop_control(
                normalized_action,
                now_sec,
                holder_id=normalized_requester_id,
                lease_id=self.teleop_lease_id,
            )

        if not self._is_teleop_control_active(now_sec):
            return self._reject_teleop_control(
                normalized_action,
                'teleop_control_not_granted',
            )
        if not self._is_holder(normalized_requester_id):
            return self._reject_teleop_control(
                normalized_action,
                'teleop_control_not_holder',
            )
        if normalized_lease_id and not self._is_lease_holder(normalized_lease_id):
            return self._reject_teleop_control(
                normalized_action,
                'teleop_control_lease_mismatch',
            )
        self.teleop_holder_id = ''
        self.teleop_lease_id = ''
        self.last_teleop_control_time = None
        return self._accept_teleop_control(
            normalized_action,
            now_sec,
            holder_id='',
            lease_id='',
        )

    def set_estop(self, active: bool, now_sec: float) -> dict:
        """设置急停状态。"""
        self.estop_active = bool(active)
        self._refresh_mode(now_sec)
        return self.snapshot(now_sec)

    def tick(self, now_sec: float) -> dict:
        """周期性刷新模式。"""
        self._refresh_mode(now_sec)
        return self.snapshot(now_sec)

    def snapshot(self, now_sec: float) -> dict:
        """获取当前状态快照。"""
        self._refresh_mode(now_sec)
        return {
            'mode': self.mode,
            'active_source': self.active_source,
            'teleop_holder_id': self.teleop_holder_id,
            'teleop_lease_id': self.teleop_lease_id,
            'estop_active': self.estop_active,
            'teleop_active': self._is_source_active('teleop', now_sec),
            'motion_active': self._is_source_active('motion', now_sec),
            'teleop_timeout_sec': self.teleop_timeout_sec,
            'motion_timeout_sec': self.motion_timeout_sec,
            'teleop_control_remaining_sec': self._teleop_control_remaining_sec(
                now_sec
            ),
            'last_teleop_control_action': self.last_teleop_control_action,
            'last_teleop_control_accepted': self.last_teleop_control_accepted,
            'last_teleop_control_reason': self.last_teleop_control_reason,
            'teleop_control_accepted_count': self.teleop_control_accepted_count,
            'teleop_control_rejected_count': self.teleop_control_rejected_count,
            'accepted_counts': dict(self.accepted_counts),
            'rejected_counts': dict(self.rejected_counts),
            'last_rejection_reason': self.last_rejection_reason,
        }

    def _reject(self, source: str, reason: str) -> ArbitrationResult:
        self.rejected_counts[source] += 1
        self.last_rejection_reason = reason
        return ArbitrationResult(
            accepted=False,
            mode=self.mode,
            reason=reason,
            active_source=self.active_source,
        )

    def _accept_teleop_control(
        self,
        action: str,
        now_sec: float,
        holder_id: str,
        lease_id: str,
    ) -> ArbitrationResult:
        self.teleop_control_accepted_count += 1
        self.last_teleop_control_action = action
        self.last_teleop_control_accepted = True
        self.last_teleop_control_reason = 'accepted'
        self.teleop_holder_id = str(holder_id)
        self.teleop_lease_id = str(lease_id)
        self._refresh_mode(now_sec)
        return ArbitrationResult(
            accepted=True,
            mode=self.mode,
            reason='accepted',
            active_source=self.active_source,
        )

    def _reject_teleop_control(
        self,
        action: str,
        reason: str,
    ) -> ArbitrationResult:
        self.teleop_control_rejected_count += 1
        self.last_teleop_control_action = action
        self.last_teleop_control_accepted = False
        self.last_teleop_control_reason = reason
        return self._reject('teleop', reason)

    def _refresh_mode(self, now_sec: float) -> None:
        self._clear_expired_teleop_control(now_sec)

        if self.estop_active:
            self.mode = 'estop'
            self.active_source = None
            return

        if self._is_teleop_control_active(now_sec):
            self.mode = 'teleop_active'
            self.active_source = 'teleop'
            return

        if self._is_source_active('motion', now_sec):
            self.mode = 'motion_active'
            self.active_source = 'motion'
            return

        self.mode = 'idle'
        self.active_source = None

    def _is_source_active(self, source: str, now_sec: float) -> bool:
        if source == 'teleop':
            last_time = self.last_teleop_control_time
            timeout_sec = self.teleop_timeout_sec
        else:
            last_time = self.last_motion_time
            timeout_sec = self.motion_timeout_sec

        if last_time is None:
            return False
        return (now_sec - last_time) <= timeout_sec

    def _is_teleop_control_active(self, now_sec: float) -> bool:
        return self._is_source_active('teleop', now_sec)

    def _is_holder(self, requester_id: str) -> bool:
        return str(requester_id).strip() == self.teleop_holder_id

    def _is_lease_holder(self, lease_id: str) -> bool:
        return str(lease_id).strip() == self.teleop_lease_id

    def _clear_expired_teleop_control(self, now_sec: float) -> None:
        if self.last_teleop_control_time is None:
            return
        if (now_sec - self.last_teleop_control_time) <= self.teleop_timeout_sec:
            return
        self.last_teleop_control_time = None
        self.teleop_holder_id = ''
        self.teleop_lease_id = ''

    def _teleop_control_remaining_sec(self, now_sec: float) -> float:
        if self.last_teleop_control_time is None:
            return 0.0
        remaining_sec = self.teleop_timeout_sec - (
            now_sec - self.last_teleop_control_time
        )
        return max(0.0, float(remaining_sec))

    @staticmethod
    def _validate_source(source: str) -> None:
        if source not in ('teleop', 'motion'):
            raise ValueError(f'unsupported source: {source}')

    def _claim_lease_id(
        self,
        now_sec: float,
        requester_id: str,
        lease_id: str,
    ) -> str:
        if (
            self._is_teleop_control_active(now_sec)
            and self._is_holder(requester_id)
            and self.teleop_lease_id
        ):
            return self.teleop_lease_id
        del lease_id
        return str(self.lease_id_factory())

    @staticmethod
    def _default_lease_id_factory() -> str:
        return uuid.uuid4().hex
