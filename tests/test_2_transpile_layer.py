import unittest
from qbacmet import TranspileLayer


class TestTranspileLayer(unittest.TestCase):
	def test_transpile_features(self):
		layer = TranspileLayer()
		layer.set_transpile_features(error_mitigation_level=2, optimization_level=3)
		self.assertEqual(layer.features["error_mitigation_level"], 2)
		self.assertEqual(layer.features["optimization_level"], 3)

	def test_compiled_circuit_metrics_dummy(self):
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
			# Note: no .data, no find_bit -> graph metrics will be None (expected)

		hw_circ = DummyHwCirc()
		layer = TranspileLayer()
		layer.set_compiled_circuit_metrics(hw_circ)

		self.assertEqual(layer.metrics["hw_circ_width"], 5)
		self.assertEqual(layer.metrics["hw_circ_depth"], 10)
		self.assertEqual(layer.metrics["hw_circ_swaps"], 4)
		self.assertEqual(layer.metrics["hw_circ_num_2q_gates"], 11)

		# New keys should exist
		self.assertIn("hw_circ_connected_components", layer.metrics)
		self.assertIn("hw_circ_connectivity_degree_max", layer.metrics)
		self.assertIn("hw_circ_connectivity_degree_avg", layer.metrics)

		# With no .data, no edges observed => each qubit is its own component
		self.assertEqual(layer.metrics["hw_circ_connected_components"], 5)
		self.assertEqual(layer.metrics["hw_circ_connectivity_degree_max"], 0)
		self.assertEqual(layer.metrics["hw_circ_connectivity_degree_avg"], 0.0)

	def test_compiled_circuit_metrics_qiskit_optional(self):
		# Optional: if Qiskit is installed, verify graph metrics populate
		try:
			from qiskit import QuantumCircuit
		except Exception:
			self.skipTest("Qiskit not installed")

		qc = QuantumCircuit(4)
		qc.cx(0, 1)
		qc.cx(2, 3)  # disconnected from (0,1)

		layer = TranspileLayer()
		layer.set_compiled_circuit_metrics(qc)

		self.assertEqual(layer.metrics["hw_circ_width"], 4)
		self.assertEqual(layer.metrics["hw_circ_connected_components"], 2)

		# degrees: each qubit has degree 1 in this graph
		self.assertEqual(layer.metrics["hw_circ_connectivity_degree_max"], 1)
		self.assertTrue(abs(layer.metrics["hw_circ_connectivity_degree_avg"] - 1.0) < 1e-9)


if __name__ == "__main__":
	unittest.main(verbosity=2)
