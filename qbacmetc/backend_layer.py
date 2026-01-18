# This is for Layer-3 in README.md

from .layer import Layer


import os
import inspect
class BackendLayer(Layer):
	"""
	Collects backend-specific metrics and features, including transpilation, error mitigation, and hardware details.
	"""
	def __init__(self):
		super().__init__()
		self.metrics = {}
		self.features = {}

	def collect_transpilation_features(self, transpile_obj):
		self.features['optimization_level'] = getattr(transpile_obj, 'optimization_level', None)
		self.features['error_mitigation'] = getattr(transpile_obj, 'error_mitigation', None)

	def collect_backend_details(self, backend_obj):
		self.features['backend_name'] = getattr(backend_obj, 'name', None)
		self.features['backend_version'] = getattr(backend_obj, 'version', None)
		self.features['max_bond_dim'] = getattr(backend_obj, 'max_bond_dim', None)

	def collect_run_dependent_features(self, run_config):
		self.features['cost'] = run_config.get('cost', None)
		self.features['scheduling_policy'] = run_config.get('scheduling_policy', None)

	def auto_collect(self):
		# Try to find backend/transpile/run_config objects in the caller's frame
		frame = inspect.currentframe().f_back
		for var in frame.f_locals.values():
			if hasattr(var, 'name') and hasattr(var, 'version'):
				self.collect_backend_details(var)
			if hasattr(var, 'optimization_level'):
				self.collect_transpilation_features(var)
			if isinstance(var, dict) and ('cost' in var or 'scheduling_policy' in var):
				self.collect_run_dependent_features(var)
		# Also auto-collect some env info
		self.features['env_backend'] = os.environ.get('QBACMET_BACKEND')
		return {'metrics': self.metrics, 'features': self.features}
	
