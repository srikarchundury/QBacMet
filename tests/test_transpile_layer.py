import unittest
from qbacmetc.transpile_layer import TranspileLayer

class TestTranspileLayer(unittest.TestCase):
	def test_transpile_features(self):
		layer = TranspileLayer()
		layer.set_transpile_features(error_mitigation_level=2, optimization_level=3)
		self.assertEqual(layer.features["error_mitigation_level"], 2)
		self.assertEqual(layer.features["optimization_level"], 3)

	def test_compiled_circuit_metrics(self):
		# Build a dummy circuit-like object matching what TranspileLayer expects
		class DummyHwCirc:
			def __init__(self):
				self.num_qubits = 5
			def depth(self):
				return 10
			def size(self):
				return 123
			def count_ops(self):
				return {"swap": 4, "cx": 7}

		hw_circ = DummyHwCirc()
		layer = TranspileLayer()
		layer.set_compiled_circuit_metrics(hw_circ)

		self.assertEqual(layer.metrics["hw_circ_width"], 5)
		self.assertEqual(layer.metrics["hw_circ_depth"], 10)
		self.assertEqual(layer.metrics["hw_circ_swaps"], 4)
		self.assertEqual(layer.metrics["hw_circ_num_2q_gates"], 11)

if __name__ == "__main__":
	unittest.main()
