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
		self.metrics['hw_circ_width'] = getattr(hw_circ, 'width', None)
		self.metrics['hw_circ_depth'] = getattr(hw_circ, 'depth', None)
		self.metrics['hw_circ_connectivity_degree'] = getattr(hw_circ, 'connectivity_degree', None)
		self.metrics['hw_circ_connected_components'] = getattr(hw_circ, 'connected_components', None)
		self.metrics['hw_circ_swaps'] = getattr(hw_circ, 'swaps', None)

	def auto_collect(self):
		# Try to find transpile/hw_circ objects in the caller's frame
		frame = inspect.currentframe().f_back
		for var in frame.f_locals.values():
			if hasattr(var, 'error_mitigation_level') or hasattr(var, 'optimization_level'):
				self.collect_transpilation_metrics(var)
			if hasattr(var, 'width') and hasattr(var, 'depth'):
				self.collect_post_transpilation_metrics(var)
		return self.get_metrics()
	
