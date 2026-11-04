# qbacmet/layer_2.py
from .layer import Layer

TWO_QUBIT_NAMES = ("cx", "cz", "swap", "ecr", "iswap", "cy", "ch", "cp", "crx", "cry", "crz", "cu", "cu1", "cu3",
                   "rxx", "ryy", "rzz", "rzx", "xx_plus_yy", "xx_minus_yy", "dcx", "ms", "zz", "csx")


class RoutingSwapCounter:
	"""Transpiler callback that records the SWAPs routing inserted.

	SWAPs are decomposed into native two-qubit gates before transpilation ends, so counting them on the output
	always gives 0. The routed circuit is seen by the callback after every pass; the largest SWAP count seen,
	minus the SWAPs already in the input circuit, is what routing added. Chains to a user callback.
	"""

	def __init__(self, input_swaps=0, user_callback=None):
		self.input_swaps = int(input_swaps or 0)
		self.max_swaps = 0
		self.user_callback = user_callback

	def __call__(self, **kwargs):
		try:
			dag = kwargs.get("dag")
			if dag is not None:
				self.max_swaps = max(self.max_swaps, int(dag.count_ops().get("swap", 0)))
		except Exception:
			pass
		if self.user_callback is not None:
			return self.user_callback(**kwargs)

	@property
	def routing_swaps(self):
		return max(self.max_swaps - self.input_swaps, 0)


class TranspileLayer(Layer):
	def __init__(self):
		super().__init__()

	def set_transpile_features(self, **kwargs):
		for k, v in kwargs.items():
			self.features[k] = v

	def set_compiled_circuit_metrics(self, hw_circ, routing_swaps=None):
		gc = self.safe_call(hw_circ, "count_ops", default={}) or {}
		gc = dict(gc) if isinstance(gc, dict) else {}

		self.metrics["hw_circ_width"] = self.safe_call(hw_circ, "num_qubits")
		self.metrics["hw_circ_depth"] = self.safe_call(hw_circ, "depth")
		self.metrics["hw_circ_num_ops"] = self.safe_call(hw_circ, "size")
		self.metrics["hw_circ_gate_counts"] = gc

		# SWAPs inserted by routing (measured during transpilation); explicit swaps left in the output count too
		if routing_swaps is not None:
			self.metrics["hw_circ_swaps"] = int(routing_swaps) + int(gc.get("swap", 0))
		else:
			self.metrics["hw_circ_swaps"] = int(gc.get("swap", 0))
		n2q = self.count_2q_by_arity(hw_circ)
		if n2q is None:      # circuit-like object without instructions: fall back to known 2q gate names
			n2q = sum(int(gc.get(g, 0) or 0) for g in TWO_QUBIT_NAMES)
		self.metrics["hw_circ_num_2q_gates"] = n2q
		self.metrics["hw_circ_depth_2q"] = self.depth_2q(hw_circ)

		cc, max_deg, avg_deg = self.qiskit_connectivity_stats(hw_circ)
		self.metrics["hw_circ_connected_components"] = cc
		self.metrics["hw_circ_connectivity_degree_max"] = max_deg
		self.metrics["hw_circ_connectivity_degree_avg"] = avg_deg

	def auto_collect(self):
		return self.get_payload()
