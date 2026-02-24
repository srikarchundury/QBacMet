# qbacmet/layer_5.py
from .layer import Layer
import inspect


class PostprocessLayer(Layer):
	def __init__(self):
		super().__init__()

	def collect_mitigation_overhead(self, d):
		if isinstance(d, dict):
			self.metrics["mitigation_overhead"] = d.get("mitigation_overhead", None)

	def collect_qec_syndrome_time(self, d):
		if isinstance(d, dict):
			self.metrics["qec_syndrome_time"] = d.get("qec_syndrome_time", None)

	def collect_result_marshalling_time(self, d):
		if isinstance(d, dict):
			self.metrics["result_marshalling_time"] = d.get("result_marshalling_time", None)

	def auto_collect(self):
		# Best-effort scan of caller frames; never overwrites explicitly set values.
		frame = inspect.currentframe().f_back
		while frame:
			for v in (frame.f_locals or {}).values():
				if not isinstance(v, dict):
					continue

				if "mitigation_overhead" in v and "mitigation_overhead" not in self.metrics:
					self.collect_mitigation_overhead(v)
				if "qec_syndrome_time" in v and "qec_syndrome_time" not in self.metrics:
					self.collect_qec_syndrome_time(v)
				if "result_marshalling_time" in v and "result_marshalling_time" not in self.metrics:
					self.collect_result_marshalling_time(v)

			frame = frame.f_back
		return self.get_payload()
