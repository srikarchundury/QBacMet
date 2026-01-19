# This is for Layer-1 in README.md

from .layer import Layer
import inspect


class AlgLayer(Layer):
	def __init__(self):
		super().__init__()

	def auto_collect(self, algo_obj=None, **kwargs):
		if algo_obj is not None:
			return self.get_metrics(algo_obj, **kwargs)

		frame = inspect.currentframe().f_back
		while frame:
			for var in frame.f_locals.values():
				try:
					if self._is_qiskit_circuit(var) or self._is_pennylane_obj(var):
						return self.get_metrics(var, **kwargs)
				except Exception:
					continue
			frame = frame.f_back

		return {}

	def get_metrics(self, algo_obj, shots=None, optimizer=None, iterations=None, repetitions=None):
		try:
			if self._is_qiskit_circuit(algo_obj):
				return self._extract_qiskit_metrics(algo_obj, shots)
			if self._is_pennylane_obj(algo_obj):
				return self._extract_pennylane_metrics(algo_obj, shots)
		except Exception as e:
			return {"error": str(e)}
		return {}

	def get_variational_metrics(self, optimizer=None, iterations=None, repetitions=None, classical_time=None):
		return {
			"optimizer": optimizer,
			"iterations": iterations,
			"repetitions": repetitions,
			"classical_optimizer_time": classical_time
		}

	def _is_qiskit_circuit(self, obj):
		try:
			from qiskit import QuantumCircuit
			return isinstance(obj, QuantumCircuit)
		except Exception:
			return False

	def _extract_qiskit_metrics(self, qc, shots):
		from qiskit.converters import circuit_to_dag

		def safe_call(obj, attr):
			val = getattr(obj, attr, None)
			if callable(val):
				try:
					return val()
				except Exception:
					return None
			return val

		gate_counts = safe_call(qc, "count_ops")
		if gate_counts is None:
			gate_counts = {}

		metrics = {
			"framework": "qiskit",
			"width": safe_call(qc, "num_qubits"),
			"depth": safe_call(qc, "depth"),
			"num_clbits": safe_call(qc, "num_clbits"),
			"num_ops": safe_call(qc, "size"),
			"gate_counts": dict(gate_counts) if isinstance(gate_counts, dict) else {},
			"num_parameters": safe_call(qc, "num_parameters"),
			"shots": shots
		}

		try:
			dag = circuit_to_dag(qc)
			metrics["critical_path_length"] = safe_call(dag, "depth")
			if hasattr(dag, "connected_components"):
				metrics["connected_components"] = len(list(dag.connected_components()))
			else:
				metrics["connected_components"] = None
		except Exception:
			metrics["critical_path_length"] = None
			metrics["connected_components"] = None

		# Heuristic classification (document as such)
		clifford_gates = {"h", "s", "sdg", "x", "y", "z", "cx", "cz", "swap", "sx", "sxdg"}
		non_clifford_gates = set(metrics["gate_counts"].keys()) - clifford_gates

		metrics["num_cliffords"] = sum(metrics["gate_counts"].get(g, 0) for g in clifford_gates)
		metrics["num_non_cliffords"] = sum(metrics["gate_counts"].get(g, 0) for g in non_clifford_gates)
		metrics["num_2q_gates"] = sum(metrics["gate_counts"].get(g, 0) for g in ["cx", "cz", "swap"])

		return metrics

	def _is_pennylane_obj(self, obj):
		try:
			import pennylane as qml
			return isinstance(obj, qml.QNode) or (hasattr(obj, "operations") and hasattr(obj, "wires"))
		except Exception:
			return False

	def _extract_pennylane_metrics(self, obj, shots):
		import pennylane as qml

		tape = None

		# Case A: already a tape / quantum script-like
		if hasattr(obj, "operations") and hasattr(obj, "wires"):
			tape = obj

		# Case B: QNode - try many common attribute names
		if tape is None and isinstance(obj, qml.QNode):
			for name in ["tape", "qtape", "_tape", "_qtape", "_tape_cached", "_qscript"]:
				cand = getattr(obj, name, None)
				if cand is not None and hasattr(cand, "operations") and hasattr(cand, "wires"):
					tape = cand
					break

		# Case C: QNode - construct tape without executing (best effort)
		if tape is None and isinstance(obj, qml.QNode):
			tape = self._construct_pl_tape_best_effort(obj)

		if tape is None:
			return {
				"framework": "pennylane",
				"error": "No tape found/constructed for QNode."
			}

		operations = getattr(tape, "operations", []) or []
		wires = getattr(tape, "wires", None)
		wire_list = list(wires) if wires is not None else []

		metrics = {
			"framework": "pennylane",
			"width": len(wire_list) if wire_list is not None else None,
			"depth": self._get_pennylane_depth_from_ops(operations, wire_list),
			"num_ops": len(operations),
			"gate_counts": self._get_pennylane_gate_counts_from_ops(operations),
			"num_parameters": len(tape.get_parameters()) if hasattr(tape, "get_parameters") else None,
			"shots": shots if shots is not None else getattr(tape, "shots", None),
			"critical_path_length": self._get_pennylane_depth_from_ops(operations, wire_list),
			"connected_components": None,
			"num_cliffords": self._count_pennylane_cliffords_from_ops(operations),
			"num_non_cliffords": len(operations) - self._count_pennylane_cliffords_from_ops(operations),
			"num_2q_gates": self._count_pennylane_2q_gates_from_ops(operations)
		}
		return metrics

	def _construct_pl_tape_best_effort(self, qnode):
		# Try modern helpers first; fall back to older ones if present.
		try:
			import pennylane as qml
			import numpy as np

			# Make dummy args based on signature: fill with 0.0
			import inspect as _inspect
			sig = _inspect.signature(qnode)
			dummy_args = []
			for p in sig.parameters.values():
				if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
					continue
				if p.default is not p.empty:
					dummy_args.append(p.default)
				else:
					dummy_args.append(0.0)

			# Try qml.workflow.construct_tape(qnode)(*args)
			try:
				construct_tape = getattr(qml.workflow, "construct_tape", None)
				if construct_tape is not None:
					tape = construct_tape(qnode)(*dummy_args)
					if tape is not None and hasattr(tape, "operations") and hasattr(tape, "wires"):
						return tape
			except Exception:
				pass

			# Try qml.transforms.make_tape(qnode)(*args)
			try:
				make_tape = getattr(qml.transforms, "make_tape", None)
				if make_tape is not None:
					tape = make_tape(qnode)(*dummy_args)
					if tape is not None and hasattr(tape, "operations") and hasattr(tape, "wires"):
						return tape
			except Exception:
				pass

			# Last resort: attempt a cheap call (may execute)
			try:
				_ = qnode(*dummy_args)
				for name in ["tape", "qtape", "_tape", "_qtape"]:
					cand = getattr(qnode, name, None)
					if cand is not None and hasattr(cand, "operations") and hasattr(cand, "wires"):
						return cand
			except Exception:
				pass

		except Exception:
			return None

		return None

	def _get_pennylane_depth_from_ops(self, operations, wires):
		try:
			if not wires:
				return None
			wire_indices = {w: i for i, w in enumerate(wires)}
			layers = [0] * len(wires)
			for op in operations:
				op_wires = [wire_indices[w] for w in op.wires]
				max_layer = max(layers[i] for i in op_wires) if op_wires else 0
				for i in op_wires:
					layers[i] = max_layer + 1
			return max(layers) if layers else 0
		except Exception:
			return None

	def _get_pennylane_gate_counts_from_ops(self, operations):
		counts = {}
		for op in operations:
			name = getattr(op, "name", None) or op.__class__.__name__
			counts[name] = counts.get(name, 0) + 1
		return counts

	def _count_pennylane_cliffords_from_ops(self, operations):
		clifford_gates = {"Hadamard", "PauliX", "PauliY", "PauliZ", "CNOT", "CZ", "SWAP", "S", "SX", "SXdg"}
		return sum(1 for op in operations if getattr(op, "name", None) in clifford_gates)

	def _count_pennylane_2q_gates_from_ops(self, operations):
		two_qubit_gates = {"CNOT", "CZ", "SWAP"}
		return sum(1 for op in operations if getattr(op, "name", None) in two_qubit_gates)
