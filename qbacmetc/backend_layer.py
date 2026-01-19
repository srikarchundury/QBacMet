# This is for Layer-3 in README.md

from .layer import Layer
import os


class BackendLayer(Layer):
	"""
	Collects backend features (sim vs HW), backend identity/version, and run-dependent settings if available.
	Primarily populated by collector hooks.
	"""
	def __init__(self):
		super().__init__()

	def set_backend_details(self, backend_obj):
		def safe_call(obj, attr):
			val = getattr(obj, attr, None)
			if callable(val):
				try:
					return val()
				except Exception:
					return None
			return val

		name = safe_call(backend_obj, "name")
		version = safe_call(backend_obj, "version")

		self.features["backend_name"] = name
		self.features["backend_version"] = version

		# Heuristics: simulator type / hw
		is_sim = False
		try:
			mod = backend_obj.__class__.__module__ or ""
			if "aer" in mod.lower() or "simulator" in (str(name).lower() if name else ""):
				is_sim = True
		except Exception:
			pass

		self.features["backend_is_simulator"] = is_sim

	def set_simulator_features(self, **kwargs):
		# Examples: sv/tn/max_bond_dim/cpu/gpu/nodes/cores/precision
		for k, v in kwargs.items():
			self.features[k] = v

	def set_run_dependent_features(self, run_config):
		if isinstance(run_config, dict):
			for k, v in run_config.items():
				self.features[k] = v

	def auto_collect(self):
		# Always at least include env hints
		self.features["env_backend"] = os.environ.get("QBACMET_BACKEND")
		return self.get_payload()
