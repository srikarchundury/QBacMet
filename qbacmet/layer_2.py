# qbacmet/layer_2.py
from .layer import Layer


class TranspileLayer(Layer):
	def __init__(self):
		super().__init__()

	def set_transpile_features(self, **kwargs):
		for k, v in kwargs.items():
			self.features[k] = v

	def set_compiled_circuit_metrics(self, hw_circ):
		gc = self.safe_call(hw_circ, "count_ops", default={}) or {}

		self.metrics["hw_circ_width"] = self.safe_call(hw_circ, "num_qubits")
		self.metrics["hw_circ_depth"] = self.safe_call(hw_circ, "depth")
		self.metrics["hw_circ_num_ops"] = self.safe_call(hw_circ, "size")
		self.metrics["hw_circ_gate_counts"] = dict(gc) if isinstance(gc, dict) else {}

		self.metrics["hw_circ_swaps"] = self.metrics["hw_circ_gate_counts"].get("swap", 0)
		self.metrics["hw_circ_num_2q_gates"] = sum(self.metrics["hw_circ_gate_counts"].get(g, 0) for g in ["cx", "cz", "swap"])

		cc, max_deg, avg_deg = self.qiskit_connectivity_stats(hw_circ)
		self.metrics["hw_circ_connected_components"] = cc
		self.metrics["hw_circ_connectivity_degree_max"] = max_deg
		self.metrics["hw_circ_connectivity_degree_avg"] = avg_deg

	def auto_collect(self):
		return self.get_payload()
