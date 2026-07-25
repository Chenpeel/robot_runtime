"""Controller parameter-file contracts."""

from pathlib import Path
import unittest

import yaml


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class TestControllerConfigContract(unittest.TestCase):
    """Keep single-instance parameters valid when launch renames the node."""

    def test_default_parameters_use_ros_wildcard_node_selector(self):
        config_path = PACKAGE_ROOT / 'config' / 'parallel_3dof_params.yaml'
        config = yaml.safe_load(config_path.read_text(encoding='utf-8'))

        self.assertEqual({'/**'}, set(config))
        parameters = config['/**']['ros__parameters']
        self.assertEqual(0.02, parameters['l0'])
        self.assertEqual(0.01, parameters['l1'])
        self.assertEqual(0.03, parameters['l2'])


if __name__ == '__main__':
    unittest.main()
