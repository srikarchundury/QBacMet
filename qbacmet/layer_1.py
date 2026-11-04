# qbacmet/layer_1.py
from .layer import Layer
import inspect


class AlgLayer(Layer):
	def __init__(self):
		super().__init__()

	def auto_collect(self, algo_obj=None, **kwargs):
		self.metrics = {}
		self.features = {}

		var = self._variational_payload(**kwargs)
		if var is not None:
			self.metrics["variational"] = var

		obj = algo_obj if algo_obj is not None else self._find_algo_obj_in_frames()
		if obj is None:
			return self.get_payload()

		m = self.get_metrics(obj, **kwargs)
		if isinstance(m, dict) and m:
			if "error" in m:
				self.metrics["error"] = m.get("error")
			else:
				self.metrics.update(m)

		return self.get_payload()

	def merge_metrics(self, new):
		"""Update with a fresh measurement without replacing known values by None (e.g. shots set by the
		caller before transpile, when the transpile call itself carries no shots)."""
		if not isinstance(new, dict) or not new:
			return
		if not isinstance(self.metrics, dict):
			self.metrics = {}
		for k, v in new.items():
			if v is None and self.metrics.get(k) is not None:
				continue
			self.metrics[k] = v

	def _variational_payload(self, optimizer=None, iterations=None, repetitions=None, classical_time=None, **kwargs):
		if optimizer is None and iterations is None and repetitions is None and classical_time is None:
			return None
		return {
			"optimizer": optimizer,
			"iterations": iterations,
			"repetitions": repetitions,
			"classical_optimizer_time": classical_time,
		}

	def _find_algo_obj_in_frames(self):
		frame = inspect.currentframe().f_back
		while frame:
			for v in (frame.f_locals or {}).values():
				try:
					if self._is_qiskit_circuit(v) or self._is_pennylane_obj(v):
						return v
				except Exception:
					continue
			frame = frame.f_back
		return None

	def get_metrics(self, algo_obj, shots=None, **kwargs):
		try:
			if self._is_qiskit_circuit(algo_obj):
				return self._qiskit_metrics(algo_obj, shots)
			if self._is_pennylane_obj(algo_obj):
				return self._pennylane_metrics(algo_obj, shots)
		except Exception as e:
			return {"error": str(e)}
		return {}

	def _is_qiskit_circuit(self, obj):
		try:
			from qiskit import QuantumCircuit
			return isinstance(obj, QuantumCircuit)
		except Exception:
			return False

	def _qiskit_metrics(self, qc, shots):
		from qiskit.converters import circuit_to_dag

		gc = self.safe_call(qc, "count_ops", default={}) or {}
		w = self.safe_call(qc, "num_qubits")
		d = self.safe_call(qc, "depth")
		ncl = self.safe_call(qc, "num_clbits")
		nops = self.safe_call(qc, "size")
		nparams = self.safe_call(qc, "num_parameters")

		# critical path (dag depth)
		cpl = None
		try:
			dag = circuit_to_dag(qc)
			cpl = self.safe_call(dag, "depth")
		except Exception:
			cpl = None

		cc = self.qiskit_circuit_connected_components(qc)

		cliff = {"h", "s", "sdg", "x", "y", "z", "cx", "cz", "swap", "sx", "sxdg"}
		num_cliff = sum(int(gc.get(g, 0) or 0) for g in cliff)
		num_2q = self.count_2q_by_arity(qc)
		num_noncliff = int(sum(int(v or 0) for v in gc.values()) - num_cliff)

		return {
			"framework": "qiskit",
			"width": w,
			"depth": d,
			"num_clbits": ncl,
			"num_ops": nops,
			"gate_counts": dict(gc) if isinstance(gc, dict) else {},
			"num_parameters": nparams,
			"shots": shots,
			"critical_path_length": cpl,
			"connected_components": cc,
			"num_cliffords": num_cliff,
			"num_non_cliffords": num_noncliff,
			"num_2q_gates": num_2q,
		}

	def _is_pennylane_obj(self, obj):
		try:
			import pennylane as qml
			return isinstance(obj, qml.QNode) or (hasattr(obj, "operations") and hasattr(obj, "wires"))
		except Exception:
			return False

	def _pennylane_metrics(self, obj, shots):
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
			return {"framework": "pennylane", "error": "No tape found/constructed for QNode."}

		ops = getattr(tape, "operations", []) or []
		wires = getattr(tape, "wires", None)
		wire_list = list(wires) if wires is not None else []

		depth = self._pl_depth(ops, wire_list)
		gc = self._pl_gate_counts(ops)
		nparams = len(tape.get_parameters()) if hasattr(tape, "get_parameters") else None

		num_cliff = self._pl_count_cliffords(ops)
		num_2q = self._pl_count_2q(ops)

		return {
			"framework": "pennylane",
			"width": len(wire_list) if wire_list is not None else None,
			"depth": depth,
			"num_ops": len(ops),
			"gate_counts": gc,
			"num_parameters": nparams,
			"shots": shots if shots is not None else getattr(tape, "shots", None),
			"critical_path_length": depth,
			"connected_components": None,
			"num_cliffords": num_cliff,
			"num_non_cliffords": (len(ops) - num_cliff) if num_cliff is not None else None,
			"num_2q_gates": num_2q,
		}

	def _construct_pl_tape_best_effort(self, qnode):
		try:
			import pennylane as qml
			import inspect as _inspect

			sig = _inspect.signature(qnode)
			dummy = []
			for p in sig.parameters.values():
				if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
					continue
				if p.default is not p.empty:
					dummy.append(p.default)
				else:
					dummy.append(0.0)

			construct_tape = getattr(getattr(qml, "workflow", None), "construct_tape", None)
			if construct_tape is not None:
				try:
					tape = construct_tape(qnode)(*dummy)
					if tape is not None and hasattr(tape, "operations") and hasattr(tape, "wires"):
						return tape
				except Exception:
					pass

			make_tape = getattr(getattr(qml, "transforms", None), "make_tape", None)
			if make_tape is not None:
				try:
					tape = make_tape(qnode)(*dummy)
					if tape is not None and hasattr(tape, "operations") and hasattr(tape, "wires"):
						return tape
				except Exception:
					pass

			try:
				_ = qnode(*dummy)
				for name in ["tape", "qtape", "_tape", "_qtape"]:
					cand = getattr(qnode, name, None)
					if cand is not None and hasattr(cand, "operations") and hasattr(cand, "wires"):
						return cand
			except Exception:
				pass

		except Exception:
			return None
		return None

	def _pl_depth(self, operations, wires):
		try:
			if not wires:
				return None
			wire_idx = {w: i for i, w in enumerate(wires)}
			layers = [0] * len(wires)
			for op in operations:
				op_ws = [wire_idx[w] for w in op.wires]
				m = max((layers[i] for i in op_ws), default=0)
				for i in op_ws:
					layers[i] = m + 1
			return max(layers) if layers else 0
		except Exception:
			return None

	def _pl_gate_counts(self, operations):
		out = {}
		for op in operations:
			name = getattr(op, "name", None) or op.__class__.__name__
			out[name] = out.get(name, 0) + 1
		return out

	def _pl_count_cliffords(self, operations):
		cliff = {"Hadamard", "PauliX", "PauliY", "PauliZ", "CNOT", "CZ", "SWAP", "S", "SX", "SXdg"}
		return sum(1 for op in operations if (getattr(op, "name", None) in cliff))

	def _pl_count_2q(self, operations):
		two = {"CNOT", "CZ", "SWAP"}
		return sum(1 for op in operations if (getattr(op, "name", None) in two))
