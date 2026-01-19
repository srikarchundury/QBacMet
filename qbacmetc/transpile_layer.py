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

	def auto_collect(self):
		return self.get_payload()
