"""执行层纯逻辑仲裁器。"""

from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional
import uuid


@dataclass(frozen=True)
class ArbitrationResult:
    """单次命令或控制权仲裁结果。"""

    accepted: bool
    mode: str
    reason: str
    active_source: Optional[str]


class CommandArbitrator:
    """统一仲裁 task、teleop 与普通 motion 三类执行入口。"""

    TELEOP_CONTROL_ACTIONS = {'claim', 'keepalive', 'release'}
    TASK_CONTROL_ACTIONS = {'start', 'keepalive', 'finish', 'cancel'}

    def __init__(
        self,
        teleop_timeout_sec: float = 0.8,
        motion_timeout_sec: float = 0.5,
        task_timeout_sec: float = 5.0,
        task_tombstone_limit: int = 256,
        lease_id_factory: Callable[[], str] | None = None,
        task_lease_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.teleop_timeout_sec = max(float(teleop_timeout_sec), 0.0)
        self.motion_timeout_sec = max(float(motion_timeout_sec), 0.0)
        self.task_timeout_sec = max(float(task_timeout_sec), 0.0)
        self.task_tombstone_limit = max(int(task_tombstone_limit), 1)
        self.lease_id_factory = lease_id_factory or self._default_lease_id_factory
        self.task_lease_id_factory = (
            task_lease_id_factory or self._default_lease_id_factory
        )

        self.mode = 'idle'
        self.active_source: Optional[str] = None
        self.estop_active = False
        self.estop_reason = ''

        self.teleop_holder_id = ''
        self.teleop_lease_id = ''
        self.last_teleop_control_time: Optional[float] = None

        self.task_id = ''
        self.task_trace_id = ''
        self.task_session_id = ''
        self.task_lease_id = ''
        self.last_task_control_time: Optional[float] = None
        self.task_terminal_identities = deque()
        self.task_terminal_identity_set = set()

        self.last_motion_time: Optional[float] = None

        self.last_teleop_control_action = ''
        self.last_teleop_control_accepted = False
        self.last_teleop_control_reason = ''
        self.teleop_control_accepted_count = 0
        self.teleop_control_rejected_count = 0

        self.last_task_control_action = ''
        self.last_task_control_task_id = ''
        self.last_task_control_trace_id = ''
        self.last_task_control_session_id = ''
        self.last_task_control_accepted = False
        self.last_task_control_reason = ''
        self.task_control_accepted_count = 0
        self.task_control_rejected_count = 0

        self.last_task_command_requester_id = ''
        self.last_task_command_accepted = False
        self.last_task_command_reason = ''

        self.accepted_counts = {'teleop': 0, 'motion': 0, 'task': 0}
        self.rejected_counts = {'teleop': 0, 'motion': 0, 'task': 0}
        self.last_rejection_reason = ''

    def receive_command(
        self,
        source: str,
        now_sec: float,
        requester_id: str = '',
        lease_id: str = '',
    ) -> ArbitrationResult:
        """处理一条 task、teleop 或普通 motion 执行请求。"""
        self._validate_source(source)
        self._refresh_mode(now_sec)
        normalized_requester_id = str(requester_id).strip()
        normalized_lease_id = str(lease_id).strip()

        if self.estop_active:
            return self._reject(
                source,
                'estop',
                requester_id=normalized_requester_id,
            )

        if source == 'task':
            rejection_reason = self._task_command_rejection_reason(
                now_sec,
                normalized_requester_id,
                normalized_lease_id,
            )
            if rejection_reason:
                return self._reject(
                    source,
                    rejection_reason,
                    requester_id=normalized_requester_id,
                )

        if source == 'teleop' and self._is_task_control_active(now_sec):
            return self._reject(source, 'task_active')

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

        if source == 'motion' and self._is_task_control_active(now_sec):
            return self._reject(source, 'task_active')

        if source == 'motion' and self._is_source_active('teleop', now_sec):
            return self._reject(source, 'teleop_active')

        if source == 'motion':
            self.last_motion_time = now_sec

        if source == 'task':
            self.last_task_command_requester_id = normalized_requester_id
            self.last_task_command_accepted = True
            self.last_task_command_reason = 'accepted'

        self.accepted_counts[source] += 1
        self._refresh_mode(now_sec)
        return ArbitrationResult(
            accepted=True,
            mode=self.mode,
            reason='accepted',
            active_source=self.active_source,
        )

    def receive_task_control(
        self,
        action: str,
        now_sec: float,
        task_id: str = '',
        trace_id: str = '',
        session_id: str = '',
        lease_id: str = '',
    ) -> ArbitrationResult:
        """处理正式任务执行租约的 start/keepalive/finish/cancel。"""
        normalized_action = str(action).strip().lower()
        normalized_task_id = str(task_id).strip()
        normalized_trace_id = str(trace_id).strip()
        normalized_session_id = str(session_id).strip()
        normalized_lease_id = str(lease_id).strip()
        self._refresh_mode(now_sec)
        self.last_task_control_action = normalized_action
        self.last_task_control_task_id = normalized_task_id
        self.last_task_control_trace_id = normalized_trace_id
        self.last_task_control_session_id = normalized_session_id

        if normalized_action not in self.TASK_CONTROL_ACTIONS:
            return self._reject_task_control(
                normalized_action,
                normalized_task_id,
                'unsupported_task_control_action',
            )

        if not normalized_task_id:
            return self._reject_task_control(
                normalized_action,
                normalized_task_id,
                'task_id_required',
            )

        if not normalized_trace_id:
            return self._reject_task_control(
                normalized_action,
                normalized_task_id,
                'task_trace_id_required',
            )

        if not normalized_session_id:
            return self._reject_task_control(
                normalized_action,
                normalized_task_id,
                'task_session_id_required',
            )

        if self.estop_active:
            return self._reject_task_control(
                normalized_action,
                normalized_task_id,
                'estop',
            )

        if normalized_action == 'start':
            if self._is_task_control_active(now_sec):
                mismatch = self._task_identity_mismatch_reason(
                    normalized_task_id,
                    normalized_trace_id,
                    normalized_session_id,
                )
                if mismatch:
                    return self._reject_task_control(
                        normalized_action,
                        normalized_task_id,
                        mismatch,
                    )
                if not normalized_lease_id:
                    return self._reject_task_control(
                        normalized_action,
                        normalized_task_id,
                        'task_lease_required',
                    )
                if not self._is_task_lease_holder(normalized_lease_id):
                    return self._reject_task_control(
                        normalized_action,
                        normalized_task_id,
                        'task_lease_mismatch',
                    )
            else:
                task_identity = (
                    normalized_task_id,
                    normalized_trace_id,
                    normalized_session_id,
                )
                if task_identity in self.task_terminal_identity_set:
                    return self._reject_task_control(
                        normalized_action,
                        normalized_task_id,
                        'task_control_replay',
                    )
                self.task_id = normalized_task_id
                self.task_trace_id = normalized_trace_id
                self.task_session_id = normalized_session_id
                self.task_lease_id = str(self.task_lease_id_factory())
                self._clear_teleop_control()
                self.last_motion_time = None

            self.last_task_control_time = now_sec
            return self._accept_task_control(
                normalized_action,
                normalized_task_id,
                now_sec,
            )

        if not self._is_task_control_active(now_sec):
            return self._reject_task_control(
                normalized_action,
                normalized_task_id,
                'task_control_not_granted',
            )

        mismatch = self._task_identity_mismatch_reason(
            normalized_task_id,
            normalized_trace_id,
            normalized_session_id,
        )
        if mismatch:
            return self._reject_task_control(
                normalized_action,
                normalized_task_id,
                mismatch,
            )
        if not normalized_lease_id:
            return self._reject_task_control(
                normalized_action,
                normalized_task_id,
                'task_lease_required',
            )
        if not self._is_task_lease_holder(normalized_lease_id):
            return self._reject_task_control(
                normalized_action,
                normalized_task_id,
                'task_lease_mismatch',
            )

        if normalized_action == 'keepalive':
            self.last_task_control_time = now_sec
        else:
            self._remember_task_identity()
            self._clear_task_control()

        return self._accept_task_control(
            normalized_action,
            normalized_task_id,
            now_sec,
        )

    def reject_command(
        self,
        source: str,
        now_sec: float,
        requester_id: str,
        reason: str,
    ) -> ArbitrationResult:
        """记录 execution_manager 外层安全门禁拒绝的执行命令。"""
        self._validate_source(source)
        self._refresh_mode(now_sec)
        return self._reject(
            source,
            str(reason).strip(),
            requester_id=str(requester_id).strip(),
        )

    def reject_task_control(
        self,
        action: str,
        now_sec: float,
        task_id: str,
        trace_id: str,
        session_id: str,
        reason: str,
    ) -> ArbitrationResult:
        """记录 execution_manager 外层安全门禁拒绝的 task 控制请求。"""
        self._refresh_mode(now_sec)
        self.last_task_control_action = str(action).strip().lower()
        self.last_task_control_task_id = str(task_id).strip()
        self.last_task_control_trace_id = str(trace_id).strip()
        self.last_task_control_session_id = str(session_id).strip()
        return self._reject_task_control(
            self.last_task_control_action,
            self.last_task_control_task_id,
            str(reason).strip(),
        )

    def validate_task_operation(
        self,
        now_sec: float,
        task_id: str,
        trace_id: str,
        session_id: str,
        lease_id: str,
    ) -> ArbitrationResult:
        """只校验 task 身份与租约，不改变命令或控制事件计数。"""
        self._refresh_mode(now_sec)
        normalized_task_id = str(task_id).strip()
        normalized_trace_id = str(trace_id).strip()
        normalized_session_id = str(session_id).strip()
        normalized_lease_id = str(lease_id).strip()

        if self.estop_active:
            reason = 'estop'
        elif not self._is_task_control_active(now_sec):
            reason = 'task_control_not_granted'
        elif not normalized_task_id:
            reason = 'task_id_required'
        elif not normalized_trace_id:
            reason = 'task_trace_id_required'
        elif not normalized_session_id:
            reason = 'task_session_id_required'
        else:
            reason = self._task_identity_mismatch_reason(
                normalized_task_id,
                normalized_trace_id,
                normalized_session_id,
            )
            if not reason and not normalized_lease_id:
                reason = 'task_lease_required'
            if (
                not reason
                and not self._is_task_lease_holder(normalized_lease_id)
            ):
                reason = 'task_lease_mismatch'

        return ArbitrationResult(
            accepted=not bool(reason),
            mode=self.mode,
            reason=reason or 'accepted',
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
            if self._is_task_control_active(now_sec):
                return self._reject_teleop_control(
                    normalized_action,
                    'task_active',
                )
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

    def set_estop(
        self,
        active: bool,
        now_sec: float,
        reason: str = 'estop',
    ) -> dict:
        """设置急停状态。"""
        self._clear_expired_task_control(now_sec)
        task_was_active = self._is_task_control_active(now_sec)
        self.estop_active = bool(active)
        if self.estop_active:
            self.estop_reason = str(reason).strip() or 'estop'
        if self.estop_active:
            if task_was_active:
                self._remember_task_identity()
                self.last_task_control_action = 'estop'
                self.last_task_control_task_id = self.task_id
                self.last_task_control_trace_id = self.task_trace_id
                self.last_task_control_session_id = self.task_session_id
                self.last_task_control_accepted = False
                self.last_task_control_reason = 'estop'
            self._clear_task_control()
            self._clear_teleop_control()
            self.last_motion_time = None
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
            'task_id': self.task_id,
            'task_trace_id': self.task_trace_id,
            'task_session_id': self.task_session_id,
            'task_lease_id': self.task_lease_id,
            'estop_active': self.estop_active,
            'estop_reason': self.estop_reason,
            'teleop_active': self._is_source_active('teleop', now_sec),
            'motion_active': self._is_source_active('motion', now_sec),
            'task_active': self._is_task_control_active(now_sec),
            'teleop_timeout_sec': self.teleop_timeout_sec,
            'motion_timeout_sec': self.motion_timeout_sec,
            'task_timeout_sec': self.task_timeout_sec,
            'teleop_control_remaining_sec': self._teleop_control_remaining_sec(
                now_sec
            ),
            'task_control_remaining_sec': self._task_control_remaining_sec(
                now_sec
            ),
            'last_teleop_control_action': self.last_teleop_control_action,
            'last_teleop_control_accepted': self.last_teleop_control_accepted,
            'last_teleop_control_reason': self.last_teleop_control_reason,
            'teleop_control_accepted_count': self.teleop_control_accepted_count,
            'teleop_control_rejected_count': self.teleop_control_rejected_count,
            'last_task_control_action': self.last_task_control_action,
            'last_task_control_task_id': self.last_task_control_task_id,
            'last_task_control_trace_id': self.last_task_control_trace_id,
            'last_task_control_session_id': self.last_task_control_session_id,
            'last_task_control_accepted': self.last_task_control_accepted,
            'last_task_control_reason': self.last_task_control_reason,
            'task_status': self._task_status(now_sec),
            'task_state_reason': (
                self.estop_reason
                if self.estop_active
                else self.last_task_control_reason
            ),
            'task_recoverable': self._task_recoverable(),
            'task_control_accepted_count': self.task_control_accepted_count,
            'task_control_rejected_count': self.task_control_rejected_count,
            'last_task_command_requester_id': (
                self.last_task_command_requester_id
            ),
            'last_task_command_accepted': self.last_task_command_accepted,
            'last_task_command_reason': self.last_task_command_reason,
            'accepted_counts': dict(self.accepted_counts),
            'rejected_counts': dict(self.rejected_counts),
            'last_rejection_reason': self.last_rejection_reason,
        }

    def _task_command_rejection_reason(
        self,
        now_sec: float,
        requester_id: str,
        lease_id: str,
    ) -> str:
        if not self._is_task_control_active(now_sec):
            return 'task_control_not_granted'
        if not requester_id:
            return 'task_requester_id_required'
        if requester_id != self.task_id:
            return 'task_control_not_holder'
        if not lease_id:
            return 'task_lease_required'
        if not self._is_task_lease_holder(lease_id):
            return 'task_lease_mismatch'
        return ''

    def _task_identity_mismatch_reason(
        self,
        task_id: str,
        trace_id: str,
        session_id: str,
    ) -> str:
        if task_id != self.task_id:
            return 'task_control_held_by_other_task'
        if trace_id != self.task_trace_id:
            return 'task_control_trace_mismatch'
        if session_id != self.task_session_id:
            return 'task_control_session_mismatch'
        return ''

    def _reject(
        self,
        source: str,
        reason: str,
        requester_id: str = '',
    ) -> ArbitrationResult:
        self.rejected_counts[source] += 1
        self.last_rejection_reason = reason
        if source == 'task':
            self.last_task_command_requester_id = str(requester_id).strip()
            self.last_task_command_accepted = False
            self.last_task_command_reason = reason
        return ArbitrationResult(
            accepted=False,
            mode=self.mode,
            reason=reason,
            active_source=self.active_source,
        )

    def _accept_task_control(
        self,
        action: str,
        task_id: str,
        now_sec: float,
    ) -> ArbitrationResult:
        self.task_control_accepted_count += 1
        self.last_task_control_action = action
        self.last_task_control_task_id = task_id
        self.last_task_control_accepted = True
        self.last_task_control_reason = 'accepted'
        self._refresh_mode(now_sec)
        return ArbitrationResult(
            accepted=True,
            mode=self.mode,
            reason='accepted',
            active_source=self.active_source,
        )

    def _reject_task_control(
        self,
        action: str,
        task_id: str,
        reason: str,
    ) -> ArbitrationResult:
        self.task_control_rejected_count += 1
        self.last_task_control_action = action
        self.last_task_control_task_id = task_id
        self.last_task_control_accepted = False
        self.last_task_control_reason = reason
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
        self._clear_expired_task_control(now_sec)
        self._clear_expired_teleop_control(now_sec)

        if self.estop_active:
            self.mode = 'estop'
            self.active_source = None
            return

        if self._is_task_control_active(now_sec):
            self.mode = 'task_active'
            self.active_source = 'task'
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

    def _is_task_control_active(self, now_sec: float) -> bool:
        if self.last_task_control_time is None:
            return False
        return (now_sec - self.last_task_control_time) <= self.task_timeout_sec

    def _is_holder(self, requester_id: str) -> bool:
        return str(requester_id).strip() == self.teleop_holder_id

    def _is_lease_holder(self, lease_id: str) -> bool:
        return str(lease_id).strip() == self.teleop_lease_id

    def _is_task_lease_holder(self, lease_id: str) -> bool:
        return str(lease_id).strip() == self.task_lease_id

    def _clear_expired_task_control(self, now_sec: float) -> None:
        if self.last_task_control_time is None:
            return
        if (now_sec - self.last_task_control_time) <= self.task_timeout_sec:
            return
        expired_task_id = self.task_id
        expired_trace_id = self.task_trace_id
        expired_session_id = self.task_session_id
        self._remember_task_identity()
        self._clear_task_control()
        self.last_task_control_action = 'timeout'
        self.last_task_control_task_id = expired_task_id
        self.last_task_control_trace_id = expired_trace_id
        self.last_task_control_session_id = expired_session_id
        self.last_task_control_accepted = False
        self.last_task_control_reason = 'task_lease_expired'

    def _clear_task_control(self) -> None:
        self.task_lease_id = ''
        self.last_task_control_time = None

    def _remember_task_identity(self) -> None:
        """保存近期终态身份，用于关联终态并拒绝延迟 start 重放。"""
        identity = (
            self.task_id,
            self.task_trace_id,
            self.task_session_id,
        )
        if not all(identity) or identity in self.task_terminal_identity_set:
            return
        if len(self.task_terminal_identities) >= self.task_tombstone_limit:
            expired_identity = self.task_terminal_identities.popleft()
            self.task_terminal_identity_set.discard(expired_identity)
        self.task_terminal_identities.append(identity)
        self.task_terminal_identity_set.add(identity)

    def _clear_expired_teleop_control(self, now_sec: float) -> None:
        if self.last_teleop_control_time is None:
            return
        if (now_sec - self.last_teleop_control_time) <= self.teleop_timeout_sec:
            return
        self.last_teleop_control_time = None
        self.teleop_holder_id = ''
        self.teleop_lease_id = ''

    def _clear_teleop_control(self) -> None:
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

    def _task_control_remaining_sec(self, now_sec: float) -> float:
        if self.last_task_control_time is None:
            return 0.0
        remaining_sec = self.task_timeout_sec - (
            now_sec - self.last_task_control_time
        )
        return max(0.0, float(remaining_sec))

    def _task_status(self, now_sec: float) -> str:
        if self.estop_active:
            return 'blocked'
        if self._is_task_control_active(now_sec):
            return 'active'
        if (
            self.last_task_control_accepted
            and self.last_task_control_action == 'finish'
        ):
            return 'finished'
        if (
            self.last_task_control_accepted
            and self.last_task_control_action == 'cancel'
        ):
            return 'cancelled'
        if self.last_task_control_action == 'timeout':
            return 'expired'
        if self.last_task_control_action == 'estop':
            return 'blocked'
        if self.last_task_control_reason and not self.last_task_control_accepted:
            return 'rejected'
        return 'idle'

    def _task_recoverable(self) -> bool:
        if self.estop_active:
            return self.estop_reason == 'estop'
        if self.last_task_control_accepted:
            return False
        return self.last_task_control_reason in {
            'estop',
            'task_active',
            'task_control_not_granted',
            'task_control_held_by_other_task',
            'task_control_trace_mismatch',
            'task_control_session_mismatch',
            'task_id_required',
            'task_trace_id_required',
            'task_session_id_required',
            'task_lease_required',
            'task_lease_mismatch',
            'task_lease_expired',
            'task_control_replay',
            'task_stop_pending',
        }

    @staticmethod
    def _validate_source(source: str) -> None:
        if source not in ('teleop', 'motion', 'task'):
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
