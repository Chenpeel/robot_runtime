"""Phase 1 全仓职责域目录迁移合同。"""

from pathlib import Path
import unittest
from xml.etree import ElementTree


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SOURCE_ROOT = REPOSITORY_ROOT / 'src'
PACKAGE_LOCATIONS = (
    ('motion_msgs', 'interfaces/motion_msgs'),
    ('perception_msgs', 'interfaces/perception_msgs'),
    ('servo_msgs', 'interfaces/servo_msgs'),
    ('speech_msgs', 'interfaces/speech_msgs'),
    ('task_api_msgs', 'interfaces/task_api_msgs'),
    ('parallel_3dof_controller', 'control/parallel_3dof_controller'),
    ('speech_interface', 'speech/speech_interface'),
    ('vision_perception', 'perception/vision_perception'),
    ('execution_manager', 'execution/execution_manager'),
    ('sensor_hardware', 'execution/sensor_hardware'),
    ('servo_hardware', 'execution/servo_hardware'),
    ('robot_hardware', 'hardware'),
    ('sim_joint_bridge_cpp', 'bridges/sim_joint_bridge_cpp'),
    ('simulation_bridge', 'bridges/simulation_bridge'),
    ('task_service_bridge', 'bridges/task_service_bridge'),
    ('websocket_bridge', 'bridges/teleoperation_bridge'),
    ('mjc_viewer', 'description/mjc_viewer'),
    ('robot_description', 'description/robot_description'),
    ('record_load_action', 'tools/record_load_action'),
    ('robot_bringup', 'bringup/robot_bringup'),
)
LEGACY_PACKAGE_ROOTS = (
    'motion_msgs',
    'perception_msgs',
    'servo_msgs',
    'speech_msgs',
    'task_api_msgs',
    'parallel_3dof_controller',
    'speech_interface',
    'vision_perception',
    'execution_manager',
    'sensor_hardware',
    'sim_joint_bridge_cpp',
    'simulation_bridge',
    'task_service_bridge',
    'websocket',
    'mjc_viewer',
    'robot_description',
    'record_load_action',
    'robot_bringup',
)


class TestPhase1DirectoryBoundary(unittest.TestCase):
    """固定全部 ROS 包的物理职责域，不改变任何包身份。"""

    def test_all_packages_live_under_their_responsibility_domains(self):
        self.assertEqual(20, len(PACKAGE_LOCATIONS))
        for package_name, relative_path in PACKAGE_LOCATIONS:
            with self.subTest(
                package_name=package_name,
                relative_path=relative_path,
            ):
                package_root = SOURCE_ROOT / relative_path
                self.assertTrue(package_root.is_dir())
                self.assertTrue((package_root / 'package.xml').is_file())

    def test_legacy_root_package_directories_are_absent(self):
        for relative_path in LEGACY_PACKAGE_ROOTS:
            with self.subTest(relative_path=relative_path):
                self.assertFalse((SOURCE_ROOT / relative_path).exists())

    def test_package_names_are_unchanged(self):
        for package_name, relative_path in PACKAGE_LOCATIONS:
            with self.subTest(
                package_name=package_name,
                relative_path=relative_path,
            ):
                manifest = ElementTree.parse(
                    SOURCE_ROOT / relative_path / 'package.xml'
                ).getroot()
                self.assertEqual(package_name, manifest.findtext('name'))

    def test_repository_has_no_duplicate_ros_package_names(self):
        package_locations = {}
        for manifest_path in SOURCE_ROOT.rglob('package.xml'):
            package_name = ElementTree.parse(manifest_path).getroot().findtext(
                'name'
            )
            self.assertTrue(package_name)
            package_locations.setdefault(package_name, []).append(manifest_path)

        duplicates = {
            package_name: paths
            for package_name, paths in package_locations.items()
            if len(paths) > 1
        }
        self.assertEqual({}, duplicates)
        self.assertEqual(
            {name for name, unused_path in PACKAGE_LOCATIONS},
            set(package_locations),
        )


if __name__ == '__main__':
    unittest.main()
