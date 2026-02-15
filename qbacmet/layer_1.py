# This is for Layer-1 in README.md

from .layer import Layer
import inspect


class AlgLayer(Layer):
	def __init__(self):
		super().__init__()

	def auto_collect(self, algo_obj=None, **kwargs):
		# Always return standardized payload shape.
		self.metrics = {}
		self.features = {}

		# Attach variational metrics even if there's no circuit object.
		var = self._maybe_variational_payload(**kwargs)
		if var is not None:
			self.metrics["variational"] = var

		obj = algo_obj
		if obj is None:
			obj = self._find_algo_obj_in_frames()

		if obj is None:
			return self.get_payload()

		metrics = self.get_metrics(obj, **kwargs)
		if isinstance(metrics, dict):
			if "error" in metrics:
				self.metrics["error"] = metrics.get("error")
			else:
				self.metrics.update(metrics)

		return self.get_payload()

	def _find_algo_obj_in_frames(self):
		frame = inspect.currentframe().f_back
		while frame:
			for var in frame.f_locals.values():
				try:
					if self._is_qiskit_circuit(var) or self._is_pennylane_obj(var):
						return var
				except Exception:
					continue
			frame = frame.f_back
		return None

	def _maybe_variational_payload(self, optimizer=None, iterations=None, repetitions=None, classical_time=None, **kwargs):
		if optimizer is None and iterations is None and repetitions is None and classical_time is None:
			return None
		return {
			"optimizer": optimizer,
			"iterations": iterations,
			"repetitions": repetitions,
			"classical_optimizer_time": classical_time
		}

	def get_metrics(self, algo_obj, shots=None, **kwargs):
		try:
			if self._is_qiskit_circuit(algo_obj):
				return self._extract_qiskit_metrics(algo_obj, shots)
			if self._is_pennylane_obj(algo_obj):
				return self._extract_pennylane_metrics(algo_obj, shots)
		except Exception as e:
			return {"error": str(e)}
		return {}

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

		# Critical path
		try:
			dag = circuit_to_dag(qc)
			metrics["critical_path_length"] = safe_call(dag, "depth")
		except Exception:
			metrics["critical_path_length"] = None

		# Connected components computed from qubit interaction graph
		metrics["connected_components"] = self._connected_components_from_qiskit_circuit(qc)

		# Heuristic classification (document as such)
		clifford_gates = {"h", "s", "sdg", "x", "y", "z", "cx", "cz", "swap", "sx", "sxdg"}
		non_clifford_gates = set(metrics["gate_counts"].keys()) - clifford_gates

		metrics["num_cliffords"] = sum(metrics["gate_counts"].get(g, 0) for g in clifford_gates)
		metrics["num_non_cliffords"] = sum(metrics["gate_counts"].get(g, 0) for g in non_clifford_gates)
		metrics["num_2q_gates"] = sum(metrics["gate_counts"].get(g, 0) for g in ["cx", "cz", "swap"])

		return metrics

	def _connected_components_from_qiskit_circuit(self, qc):
		try:
			n = getattr(qc, "num_qubits", None)
			if n is None:
				return None
			n = int(n)
			if n <= 0:
				return 0

			adj = [set() for _ in range(n)]

			# Qiskit 1.2+: CircuitInstruction with named attributes
			for ci in getattr(qc, "data", []) or []:
				try:
					qargs = getattr(ci, "qubits", None)
					if not qargs:
						continue

					# Robust qubit index resolution across Qiskit versions
					qs = []
					for q in qargs:
						try:
							idx = qc.find_bit(q).index
						except Exception:
							# last-ditch fallbacks
							idx = getattr(q, "index", None)
							if idx is None:
								idx = getattr(q, "_index", None)
							if idx is None:
								try:
									idx = list(qc.qubits).index(q)
								except Exception:
									idx = None
						if idx is not None:
							qs.append(int(idx))

					if len(qs) < 2:
						continue

					# connect all-to-all within multi-qubit op
					for i in range(len(qs)):
						for j in range(i + 1, len(qs)):
							a = qs[i]
							b = qs[j]
							if 0 <= a < n and 0 <= b < n:
								adj[a].add(b)
								adj[b].add(a)
				except Exception:
					continue

			seen = [False] * n
			cc = 0
			for i in range(n):
				if seen[i]:
					continue
				cc += 1
				stack = [i]
				seen[i] = True
				while stack:
					u = stack.pop()
					for v in adj[u]:
						if not seen[v]:
							seen[v] = True
							stack.append(v)
			return cc
		except Exception:
			return None

	def _is_pennylane_obj(self, obj):
		try:
			import pennylane as qml
			return isinstance(obj, qml.QNode) or (hasattr(obj, "operations") and hasattr(obj, "wires"))
		except Exception:
			return False

	# ---- PennyLane code unchanged from your version below ----

	def _extract_pennylane_metrics(self, obj, shots):
		import pennylane as qml

		tape = None

		if hasattr(obj, "operations") and hasattr(obj, "wires"):
			tape = obj

		if tape is None and isinstance(obj, qml.QNode):
			for name in ["tape", "qtape", "_tape", "_qtape", "_tape_cached", "_qscript"]:
				cand = getattr(obj, name, None)
				if cand is not None and hasattr(cand, "operations") and hasattr(cand, "wires"):
					tape = cand
					break

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

		depth = self._get_pennylane_depth_from_ops(operations, wire_list)

		metrics = {
			"framework": "pennylane",
			"width": len(wire_list) if wire_list is not None else None,
			"depth": depth,
			"num_ops": len(operations),
			"gate_counts": self._get_pennylane_gate_counts_from_ops(operations),
			"num_parameters": len(tape.get_parameters()) if hasattr(tape, "get_parameters") else None,
			"shots": shots if shots is not None else getattr(tape, "shots", None),
			"critical_path_length": depth,
			"connected_components": None,
			"num_cliffords": self._count_pennylane_cliffords_from_ops(operations),
			"num_non_cliffords": len(operations) - self._count_pennylane_cliffords_from_ops(operations),
			"num_2q_gates": self._count_pennylane_2q_gates_from_ops(operations)
		}
		return metrics

	def _construct_pl_tape_best_effort(self, qnode):
		try:
			import pennylane as qml
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

			try:
				construct_tape = getattr(qml.workflow, "construct_tape", None)
				if construct_tape is not None:
					tape = construct_tape(qnode)(*dummy_args)
					if tape is not None and hasattr(tape, "operations") and hasattr(tape, "wires"):
						return tape
			except Exception:
				pass

			try:
				make_tape = getattr(qml.transforms, "make_tape", None)
				if make_tape is not None:
					tape = make_tape(qnode)(*dummy_args)
					if tape is not None and hasattr(tape, "operations") and hasattr(tape, "wires"):
						return tape
			except Exception:
				pass

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
