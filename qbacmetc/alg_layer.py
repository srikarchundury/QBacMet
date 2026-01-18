# This is for Layer-1 in README.md

from .layer import Layer



class AlgLayer(Layer):
	def __init__(self):
		super().__init__()

	def get_metrics(self, algo_obj, shots=None, optimizer=None, iterations=None, repetitions=None):
		"""
		Extracts circuit and variational metrics from Qiskit or PennyLane objects.
		algo_obj: Qiskit QuantumCircuit or PennyLane QNode/QuantumTape
		"""
		try:
			if self._is_qiskit_circuit(algo_obj):
				return self._extract_qiskit_metrics(algo_obj, shots)
			if self._is_pennylane_obj(algo_obj):
				return self._extract_pennylane_metrics(algo_obj, shots)
		except Exception as e:
			return {'error': str(e)}
		return {}

	def get_variational_metrics(self, optimizer=None, iterations=None, repetitions=None):
		"""Return variational algorithm metrics."""
		return {
			'optimizer': optimizer,
			'iterations': iterations,
			'repetitions': repetitions
		}

	def _is_qiskit_circuit(self, obj):
		try:
			from qiskit import QuantumCircuit
			return isinstance(obj, QuantumCircuit)
		except ImportError:
			return False

	def _extract_qiskit_metrics(self, qc, shots):
		from qiskit.converters import circuit_to_dag
		metrics = {
			'framework': 'qiskit',
			'width': qc.num_qubits,
			'depth': qc.depth(),
			'num_clbits': qc.num_clbits,
			'num_ops': qc.size(),
			'gate_counts': qc.count_ops(),
			'num_parameters': qc.num_parameters,
			'shots': shots if shots is not None else None
		}
		dag = circuit_to_dag(qc)
		metrics['critical_path_length'] = dag.depth()
		metrics['connected_components'] = len(list(dag.connected_components())) if hasattr(dag, 'connected_components') else None
		clifford_gates = {'h', 's', 'sdg', 'x', 'y', 'z', 'cx', 'cz', 'swap'}
		non_clifford_gates = set(metrics['gate_counts'].keys()) - clifford_gates
		metrics['num_cliffords'] = sum(metrics['gate_counts'].get(g, 0) for g in clifford_gates)
		metrics['num_non_cliffords'] = sum(metrics['gate_counts'].get(g, 0) for g in non_clifford_gates)
		metrics['num_2q_gates'] = sum(metrics['gate_counts'].get(g, 0) for g in ['cx', 'cz', 'swap'])
		return metrics

	def _is_pennylane_obj(self, obj):
		try:
			import pennylane as qml
			return isinstance(obj, qml.QNode) or (hasattr(obj, 'operations') and hasattr(obj, 'wires'))
		except ImportError:
			return False

	def _extract_pennylane_metrics(self, obj, shots):
		import pennylane as qml
		tape, wires, operations = None, None, None
		if isinstance(obj, qml.QNode):
			# Call QNode with zeros for all parameters, try both scalar and array
			num_params = getattr(obj, 'num_params', 1)
			params = [0.0] * num_params
			called = False
			try:
				_ = obj(*params)
				called = True
			except Exception:
				pass
			if not called:
				import numpy as np
				try:
					_ = obj(*[np.array([0.0] * num_params)])
				except Exception:
					pass
			tape = getattr(obj, 'qtape', None) or getattr(obj, 'tape', None)
			wires = getattr(obj.device, 'wires', None) if hasattr(obj, 'device') else None
			if tape is not None and hasattr(tape, 'wires'):
				wires = tape.wires
			operations = tape.operations if tape and hasattr(tape, 'operations') else []
		elif hasattr(obj, 'operations') and hasattr(obj, 'wires'):
			tape = obj
			wires = tape.wires
			operations = tape.operations if hasattr(tape, 'operations') else []
		# Make wires always a list for consistent length calculation
		if wires is not None:
			if isinstance(wires, (set, tuple)):
				wires = list(wires)
		if tape is not None and operations and wires is not None:
			metrics = {
				'framework': 'pennylane',
				'width': len(wires),
				'depth': self._get_pennylane_depth_from_ops(operations, wires),
				'num_ops': len(operations),
				'gate_counts': self._get_pennylane_gate_counts_from_ops(operations),
				'num_parameters': len(tape.get_parameters()) if tape and hasattr(tape, 'get_parameters') else None,
				'shots': shots if shots is not None else getattr(tape, 'shots', None),
				'critical_path_length': self._get_pennylane_depth_from_ops(operations, wires),
				'connected_components': None,
				'num_cliffords': self._count_pennylane_cliffords_from_ops(operations),
				'num_non_cliffords': len(operations) - self._count_pennylane_cliffords_from_ops(operations),
				'num_2q_gates': self._count_pennylane_2q_gates_from_ops(operations)
			}
			return metrics
		# Debug info if metrics are empty
		return {
			'debug_tape': str(tape),
			'debug_wires': str(wires),
			'debug_operations': str(operations),
			'error': 'Could not extract PennyLane metrics. Tape/wires/operations missing.'
		}

	def _get_pennylane_depth_from_ops(self, operations, wires):
		try:
			if wires is None:
				return None
			wire_indices = {w: i for i, w in enumerate(wires)}
			layers = [0] * len(wires)
			for op in operations:
				op_wires = [wire_indices[w] for w in op.wires]
				max_layer = max(layers[i] for i in op_wires)
				for i in op_wires:
					layers[i] = max_layer + 1
			return max(layers)
		except Exception:
			return None

	def _get_pennylane_gate_counts_from_ops(self, operations):
		counts = {}
		for op in operations:
			counts[op.name] = counts.get(op.name, 0) + 1
		return counts

	def _count_pennylane_cliffords_from_ops(self, operations):
		clifford_gates = {'Hadamard', 'PauliX', 'PauliY', 'PauliZ', 'CNOT', 'CZ', 'SWAP', 'S', 'SX', 'SXdg'}
		return sum(1 for op in operations if op.name in clifford_gates)

	def _count_pennylane_2q_gates_from_ops(self, operations):
		two_qubit_gates = {'CNOT', 'CZ', 'SWAP'}
		return sum(1 for op in operations if op.name in two_qubit_gates)
	



