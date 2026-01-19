# This is for Layer-5 in README.md

from .layer import Layer
import inspect


class PostprocessLayer(Layer):
	"""
	Collects post-processing metrics/features such as mitigation overhead,
	QEC syndrome extraction time, and result marshalling time.
	"""
	def __init__(self):
		super().__init__()

	def collect_mitigation_overhead(self, mitigation_info):
		if isinstance(mitigation_info, dict):
			self.metrics["mitigation_overhead"] = mitigation_info.get("mitigation_overhead", None)

	def collect_qec_syndrome_time(self, qec_info):
		if isinstance(qec_info, dict):
			self.metrics["qec_syndrome_time"] = qec_info.get("qec_syndrome_time", None)

	def collect_result_marshalling_time(self, marshal_info):
		if isinstance(marshal_info, dict):
			self.metrics["result_marshalling_time"] = marshal_info.get("result_marshalling_time", None)

	def auto_collect(self):
		"""
		Optional fallback scan of the caller's frame for dicts containing
		mitigation_overhead / qec_syndrome_time / result_marshalling_time fields.
		Does not overwrite already-set values.
		"""
		frame = inspect.currentframe().f_back

		while frame:
			for var in frame.f_locals.values():
				if not isinstance(var, dict):
					continue

				if "mitigation_overhead" in var and "mitigation_overhead" not in self.metrics:
					self.collect_mitigation_overhead(var)

				if "qec_syndrome_time" in var and "qec_syndrome_time" not in self.metrics:
					self.collect_qec_syndrome_time(var)

				if "result_marshalling_time" in var and "result_marshalling_time" not in self.metrics:
					self.collect_result_marshalling_time(var)

			frame = frame.f_back

		return self.get_payload()
