"""将 task admission ROS pub/sub 场景接入 pytest/colcon 自动发现。"""

from task_admission_ros_smoke import run_scenario


def test_task_admission_ros_pub_sub() -> None:
    result = run_scenario()

    assert result['task_lease_nonempty']
    assert result['ordinary_motion_blocked']
    assert result['ordinary_motion_restored']
    assert result['teleop_rejection'] == 'task_active'
    assert result['task_command_rejection'] == 'task_lease_mismatch'
    assert result['finish_status'] == 'finished'
    assert result['cancel_status'] == 'cancelled'
    assert result['timeout_status'] == 'expired'
    assert result['estop_status'] == 'blocked'
    assert result['estop_status_after_release'] == 'blocked'
    assert result['replay_rejection'] == 'task_control_replay'
