# This is Layer-2 in README.md

from .layer import Layer


class TranspileLayer(Layer):
	"""
	Collects transpilation features (inputs/knobs) and compiled-circuit metrics.
	Populated reliably by collector hooks; can also be set manually.
	"""
	def __init__(self):
		super().__init__()

	def set_transpile_features(self, **kwargs):
		# Vendor-agnostic: capture knobs without forcing a schema
		for k, v in kwargs.items():
			self.features[k] = v

	def _connected_components_and_degree(self, qc):
		# Works best for Qiskit QuantumCircuit (compiled circuit), but designed as best-effort.
		try:
			n = getattr(qc, "num_qubits", None)
			if n is None:
				return None, None, None
			n = int(n)
			if n <= 0:
				return 0, 0, 0

			adj = [set() for _ in range(n)]

			# Prefer robust indexing if Qiskit circuit
			find_bit = getattr(qc, "find_bit", None)
			for ci in getattr(qc, "data", []) or []:
				try:
					qargs = getattr(ci, "qubits", None)
					if not qargs:
						continue

					qs = []
					for q in qargs:
						idx = None
						if callable(find_bit):
							try:
								idx = find_bit(q).index
							except Exception:
								idx = None
						if idx is None:
							idx = getattr(q, "index", None)
							if idx is None:
								idx = getattr(q, "_index", None)
						if idx is not None:
							qs.append(int(idx))

					if len(qs) < 2:
						continue

					for i in range(len(qs)):
						for j in range(i + 1, len(qs)):
							a = qs[i]
							b = qs[j]
							if 0 <= a < n and 0 <= b < n:
								adj[a].add(b)
								adj[b].add(a)
				except Exception:
					continue

			# connected components
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

			degrees = [len(adj[i]) for i in range(n)]
			max_deg = max(degrees) if degrees else 0
			avg_deg = (sum(degrees) / float(n)) if n > 0 else 0.0

			return cc, max_deg, avg_deg
		except Exception:
			return None, None, None

	def set_compiled_circuit_metrics(self, hw_circ):
		def safe_call(obj, attr):
			val = getattr(obj, attr, None)
			if callable(val):
				try:
					return val()
				except Exception:
					return None
			return val

		gate_counts = safe_call(hw_circ, "count_ops")
		if gate_counts is None:
			gate_counts = {}

		self.metrics["hw_circ_width"] = safe_call(hw_circ, "num_qubits")
		self.metrics["hw_circ_depth"] = safe_call(hw_circ, "depth")
		self.metrics["hw_circ_num_ops"] = safe_call(hw_circ, "size")
		self.metrics["hw_circ_gate_counts"] = dict(gate_counts) if isinstance(gate_counts, dict) else {}

		# Common post-transpile derived metrics
		self.metrics["hw_circ_swaps"] = self.metrics["hw_circ_gate_counts"].get("swap", 0)
		self.metrics["hw_circ_num_2q_gates"] = sum(self.metrics["hw_circ_gate_counts"].get(g, 0) for g in ["cx", "cz", "swap"])

		# README Layer-2 asks for connectivity + connected components
		cc, max_deg, avg_deg = self._connected_components_and_degree(hw_circ)
		self.metrics["hw_circ_connected_components"] = cc
		self.metrics["hw_circ_connectivity_degree_max"] = max_deg
		self.metrics["hw_circ_connectivity_degree_avg"] = avg_deg

	def auto_collect(self):
		return self.get_payload()
