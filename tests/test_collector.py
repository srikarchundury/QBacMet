import unittest


class TestEndToEndCollector(unittest.TestCase):
	def test_qiskit_end_to_end(self):
		try:
			from qbacmetc import collector
			import qiskit
			from qiskit import QuantumCircuit
			from qiskit_aer import AerSimulator
		except Exception as e:
			raise unittest.SkipTest(f"Qiskit/Aer not available: {e}")

		with collector.collect():
			qc = QuantumCircuit(2)
			qc.h(0)
			qc.cx(0, 1)
			qc.measure_all()

			backend = AerSimulator()
			tqc = qiskit.transpile(qc, backend=backend, optimization_level=1)
			job = backend.run(tqc, shots=256)
			_ = job.result()

		metrics = collector.metrics
		for k in ["slurm", "algorithm", "transpile", "backend", "execution", "postprocess"]:
			self.assertIn(k, metrics)

		self.assertEqual(metrics["algorithm"]["metrics"].get("framework"), "qiskit")
		self.assertIn("hw_circ_width", metrics["transpile"]["metrics"])
		self.assertIn("execution_time", metrics["execution"]["metrics"])

	def test_pennylane_end_to_end(self):
		try:
			from qbacmetc import collector
			import pennylane as qml
		except Exception as e:
			raise unittest.SkipTest(f"PennyLane not available: {e}")

		with collector.collect():
			dev = qml.device("default.qubit", wires=2)

			@qml.qnode(dev)
			def circuit(x):
				qml.Hadamard(wires=0)
				qml.CNOT(wires=[0, 1])
				qml.RX(x, wires=1)
				return qml.expval(qml.PauliZ(0))

			circuit(0.5)

		metrics = collector.metrics
		for k in ["slurm", "algorithm", "transpile", "backend", "execution", "postprocess"]:
			self.assertIn(k, metrics)

		self.assertEqual(metrics["algorithm"]["metrics"].get("framework"), "pennylane")
		self.assertIn("execution_time", metrics["execution"]["metrics"])


if __name__ == "__main__":
	unittest.main(verbosity=2)
