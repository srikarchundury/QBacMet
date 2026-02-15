import unittest
from qbacmet import AlgLayer


class TestAlgLayer(unittest.TestCase):
	def test_payload_shape_no_obj(self):
		layer = AlgLayer()
		payload = layer.auto_collect(None)

		self.assertIsInstance(payload, dict)
		self.assertIn("metrics", payload)
		self.assertIn("features", payload)
		self.assertIsInstance(payload["metrics"], dict)
		self.assertIsInstance(payload["features"], dict)

	def test_qiskit_metrics_basic(self):
		try:
			from qiskit import QuantumCircuit
		except Exception:
			self.skipTest("Qiskit not installed")

		qc = QuantumCircuit(3)
		qc.h(0)
		qc.cx(0, 1)
		qc.cx(1, 2)

		layer = AlgLayer()
		payload = layer.auto_collect(qc, shots=1024)

		m = payload["metrics"]
		self.assertEqual(m.get("framework"), "qiskit")
		self.assertEqual(m.get("width"), 3)
		self.assertIsInstance(m.get("gate_counts"), dict)
		self.assertEqual(m.get("shots"), 1024)

		# connected components: this circuit connects all three qubits
		self.assertEqual(m.get("connected_components"), 1)

	def test_qiskit_connected_components_disconnected(self):
		try:
			from qiskit import QuantumCircuit
		except Exception:
			self.skipTest("Qiskit not installed")

		qc = QuantumCircuit(4)
		qc.cx(0, 1)  # component A: {0,1}
		qc.cx(2, 3)  # component B: {2,3}

		layer = AlgLayer()
		payload = layer.auto_collect(qc)

		self.assertEqual(payload["metrics"].get("connected_components"), 2)

	def test_variational_attaches_only_when_provided(self):
		layer = AlgLayer()

		p0 = layer.auto_collect(None)
		self.assertTrue("variational" not in p0["metrics"])

		p1 = layer.auto_collect(None, optimizer="Adam", iterations=10, repetitions=2)
		self.assertIn("variational", p1["metrics"])
		self.assertEqual(p1["metrics"]["variational"]["optimizer"], "Adam")
		self.assertEqual(p1["metrics"]["variational"]["iterations"], 10)
		self.assertEqual(p1["metrics"]["variational"]["repetitions"], 2)

	def test_pennylane_basic(self):
		try:
			import pennylane as qml
		except Exception:
			self.skipTest("PennyLane not installed")

		dev = qml.device("default.qubit", wires=2)

		@qml.qnode(dev)
		def circuit(x):
			qml.Hadamard(wires=0)
			qml.CNOT(wires=[0, 1])
			qml.RX(x, wires=1)
			return qml.expval(qml.PauliZ(0))

		# build tape best-effort
		try:
			circuit(0.5)
		except Exception:
			pass

		layer = AlgLayer()
		payload = layer.auto_collect(circuit)

		m = payload["metrics"]
		self.assertEqual(m.get("framework"), "pennylane")
		self.assertTrue(m.get("width") in [2, None])  # depends on tape construction success
		self.assertIsInstance(m.get("gate_counts"), dict)


if __name__ == "__main__":
	unittest.main(verbosity=2)
