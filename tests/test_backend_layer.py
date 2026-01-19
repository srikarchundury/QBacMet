import unittest
from qbacmetc.backend_layer import BackendLayer

class DummyTranspileObj:
	optimization_level = 2
	error_mitigation = "enabled"

class DummyBackendObj:
	name = "QiskitAer"
	version = "0.11.0"
	max_bond_dim = 16

class TestBackendLayer(unittest.TestCase):
	def test_set_simulator_features(self):
		layer = BackendLayer()
		layer.set_simulator_features(optimization_level=2, error_mitigation="enabled")
		self.assertEqual(layer.features["optimization_level"], 2)
		self.assertEqual(layer.features["error_mitigation"], "enabled")

	def test_set_backend_details(self):
		obj = DummyBackendObj()
		layer = BackendLayer()
		layer.set_backend_details(obj)
		self.assertEqual(layer.features["backend_name"], "QiskitAer")
		self.assertEqual(layer.features["backend_version"], "0.11.0")
		# If you want max_bond_dim tracked, store it as simulator feature:
		layer.set_simulator_features(max_bond_dim=obj.max_bond_dim)
		self.assertEqual(layer.features["max_bond_dim"], 16)

	def test_set_run_dependent_features(self):
		run_config = {"cost": 100, "scheduling_policy": "FIFO"}
		layer = BackendLayer()
		layer.set_run_dependent_features(run_config)
		self.assertEqual(layer.features["cost"], 100)
		self.assertEqual(layer.features["scheduling_policy"], "FIFO")

if __name__ == "__main__":
	unittest.main()
