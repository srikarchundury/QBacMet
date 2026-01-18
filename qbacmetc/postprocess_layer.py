# This is for Layer-4 in README.md

from .layer import Layer


import inspect
class PostprocessLayer(Layer):
	"""
	Collects post-processing metrics/features such as mitigation overhead, QEC syndrome extraction time, and result marshalling time.
	"""
	def __init__(self):
		super().__init__()
		self.metrics = {}

	def collect_mitigation_overhead(self, mitigation_info):
		self.metrics['mitigation_overhead'] = mitigation_info.get('mitigation_overhead', None)

	def collect_qec_syndrome_time(self, qec_info):
		self.metrics['qec_syndrome_time'] = qec_info.get('qec_syndrome_time', None)

	def collect_result_marshalling_time(self, marshal_info):
		self.metrics['result_marshalling_time'] = marshal_info.get('result_marshalling_time', None)

	def auto_collect(self):
		# Try to find mitigation/qec/marshal info in the caller's frame
		frame = inspect.currentframe().f_back
		for var in frame.f_locals.values():
			if isinstance(var, dict) and 'mitigation_overhead' in var:
				self.collect_mitigation_overhead(var)
			if isinstance(var, dict) and 'qec_syndrome_time' in var:
				self.collect_qec_syndrome_time(var)
			if isinstance(var, dict) and 'result_marshalling_time' in var:
				self.collect_result_marshalling_time(var)
		return self.get_metrics()

	