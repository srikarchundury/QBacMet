import unittest
from qbacmetc import collector
from qiskit import QuantumCircuit
import pennylane as qml
import numpy as np

class TestEndToEndCollector(unittest.TestCase):
    def test_qiskit_end_to_end(self):
        collector.collector.start_collecting()
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure_all()
        collector.collector.collect_alg_metrics(qc, shots=512)
        # Simulate transpile and backend objects
        class DummyTranspile: error_mitigation_level=1; optimization_level=2
        class DummyBackend: name='QiskitAer'; version='1.3'; max_bond_dim=8
        collector.collector.collect_transpile_metrics(transpile_obj=DummyTranspile())
        collector.collector.collect_backend_metrics(backend_obj=DummyBackend(), transpile_obj=DummyTranspile())
        collector.collector.collect_execution_metrics(queue_info={'queue_time': 1.1}, exec_info={'execution_time': 2.2})
        collector.collector.collect_postprocess_metrics(mitigation_info={'mitigation_overhead': 0.5})
        collector.collector.stop_collecting()
        metrics = collector.collector.metrics
        self.assertIn('algorithm', metrics)
        self.assertIn('transpile', metrics)
        self.assertIn('backend', metrics)
        self.assertIn('execution', metrics)
        self.assertIn('postprocess', metrics)
        collector.collector.print_metrics()

    def test_pennylane_end_to_end(self):
        collector.collector.start_collecting()
        dev = qml.device('default.qubit', wires=2)
        @qml.qnode(dev)
        def circuit(x):
            qml.Hadamard(wires=0)
            qml.CNOT(wires=[0, 1])
            qml.RX(x, wires=1)
            return qml.expval(qml.PauliZ(0))
        circuit(0.5)
        collector.collector.collect_alg_metrics(circuit, shots=100)
        class DummyTranspile: error_mitigation_level=1; optimization_level=2
        class DummyBackend: name='PennyLaneSim'; version='0.35'; max_bond_dim=4
        collector.collector.collect_transpile_metrics(transpile_obj=DummyTranspile())
        collector.collector.collect_backend_metrics(backend_obj=DummyBackend(), transpile_obj=DummyTranspile())
        collector.collector.collect_execution_metrics(queue_info={'queue_time': 0.9}, exec_info={'execution_time': 1.8})
        collector.collector.collect_postprocess_metrics(mitigation_info={'mitigation_overhead': 0.3})
        collector.collector.stop_collecting()
        metrics = collector.collector.metrics
        self.assertIn('algorithm', metrics)
        self.assertIn('transpile', metrics)
        self.assertIn('backend', metrics)
        self.assertIn('execution', metrics)
        self.assertIn('postprocess', metrics)
        collector.collector.print_metrics()

if __name__ == "__main__":
    unittest.main()
