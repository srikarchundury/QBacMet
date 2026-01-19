import unittest
from qbacmetc import collector
from qiskit import QuantumCircuit
import pennylane as qml


class TestEndToEndCollector(unittest.TestCase):
	def test_qiskit_end_to_end(self):
		from qiskit import transpile
		from qiskit_aer import AerSimulator

		with collector.collector.collect():
			qc = QuantumCircuit(2)
			qc.h(0)
			qc.cx(0, 1)
			qc.measure_all()
			backend = AerSimulator()
			tqc = transpile(qc, backend, optimization_level=1)
			job = backend.run(tqc, shots=512)
			_ = job.result()

		metrics = collector.collector.metrics
		self.assertIn("algorithm", metrics)
		self.assertIn("transpile", metrics)
		self.assertIn("backend", metrics)
		self.assertIn("execution", metrics)
		self.assertIn("postprocess", metrics)

		collector.collector.print_metrics()

	def test_pennylane_end_to_end(self):
		with collector.collector.collect():
			dev = qml.device("default.qubit", wires=2)

			@qml.qnode(dev)
			def circuit(x):
				qml.Hadamard(wires=0)
				qml.CNOT(wires=[0, 1])
				qml.RX(x, wires=1)
				return qml.expval(qml.PauliZ(0))

			circuit(0.5)

		metrics = collector.collector.metrics
		self.assertIn("algorithm", metrics)
		self.assertIn("transpile", metrics)
		self.assertIn("backend", metrics)
		self.assertIn("execution", metrics)
		self.assertIn("postprocess", metrics)

		collector.collector.print_metrics()


if __name__ == "__main__":
	unittest.main()
