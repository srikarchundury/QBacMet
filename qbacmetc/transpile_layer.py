# This is Layer-2 in README.md

from .layer import Layer


import inspect
class TranspileLayer(Layer):
	"""
	Collects transpilation and post-transpilation metrics/features.
	"""
	def __init__(self):
		super().__init__()
		self.metrics = {}

	def collect_transpilation_metrics(self, transpile_obj):
		self.metrics['error_mitigation_level'] = getattr(transpile_obj, 'error_mitigation_level', None)
		self.metrics['optimization_level'] = getattr(transpile_obj, 'optimization_level', None)

	def collect_post_transpilation_metrics(self, hw_circ):
		def get_val(obj, attr):
			val = getattr(obj, attr, None)
			if callable(val):
				try:
					return val()
				except Exception:
					return None
			return val
		self.metrics['hw_circ_width'] = get_val(hw_circ, 'width')
		self.metrics['hw_circ_depth'] = get_val(hw_circ, 'depth')
		self.metrics['hw_circ_connectivity_degree'] = get_val(hw_circ, 'connectivity_degree')
		self.metrics['hw_circ_connected_components'] = get_val(hw_circ, 'connected_components')
		self.metrics['hw_circ_swaps'] = get_val(hw_circ, 'swaps')

	def auto_collect(self):
		# Scan all frames for transpile/hw_circ objects
		frame = inspect.currentframe().f_back
		found = False
		while frame:
			for var in frame.f_locals.values():
				if hasattr(var, 'error_mitigation_level') or hasattr(var, 'optimization_level'):
					self.collect_transpilation_metrics(var)
					found = True
				if hasattr(var, 'width') and hasattr(var, 'depth'):
					self.collect_post_transpilation_metrics(var)
					found = True
			frame = frame.f_back
		return self.get_metrics() if found else {}
	
