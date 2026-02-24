# qbacmet/layer_3.py
from .layer import Layer
import os


class BackendLayer(Layer):
	def __init__(self):
		super().__init__()

	def auto_collect(self, backend_obj=None, **kwargs):
		if "env_backend" not in self.features:
			self.features["env_backend"] = os.environ.get("QBACMET_BACKEND")

		if backend_obj is not None:
			self.set_backend_details(backend_obj)
			self._auto_infer_backend_features(backend_obj)

		return self.get_payload()

	def set_backend_details(self, backend_obj):
		name = self.safe_call(backend_obj, "name")
		version = self.safe_call(backend_obj, "version")

		mod = None
		try:
			mod = backend_obj.__class__.__module__ or None
		except Exception:
			mod = None

		self.features["backend_name"] = name
		self.features["backend_version"] = version
		self.features["backend_module"] = mod

		is_sim = False
		try:
			mod_l = (mod or "").lower()
			name_l = (str(name).lower() if name is not None else "")
			if ("aer" in mod_l) or ("simulator" in name_l) or ("statevector" in name_l) or ("density" in name_l):
				is_sim = True
		except Exception:
			pass

		self.features["backend_is_simulator"] = is_sim
		self.features["backend_type"] = "simulator" if is_sim else "hardware"

	def _auto_infer_backend_features(self, backend_obj):
		if self._looks_like_qiskit_backend(backend_obj):
			self._infer_qiskit_backend_features(backend_obj)
			return
		if self._looks_like_pennylane_device_or_qnode(backend_obj):
			self._infer_pennylane_features(backend_obj)
			return

	def _looks_like_qiskit_backend(self, backend_obj):
		mod = ""
		try:
			mod = backend_obj.__class__.__module__ or ""
		except Exception:
			mod = ""
		mod_l = mod.lower()
		return ("qiskit" in mod_l) or (hasattr(backend_obj, "run") and hasattr(backend_obj, "options"))

	def _infer_qiskit_backend_features(self, backend_obj):
		try:
			opts = getattr(backend_obj, "options", None)
			if opts is not None:
				for key in ["method", "device", "precision", "max_parallel_threads", "max_parallel_experiments"]:
					val = getattr(opts, key, None)
					if val is not None:
						self.features[f"qiskit_option_{key}"] = val
		except Exception:
			pass

		try:
			cfg = getattr(backend_obj, "configuration", None)
			if callable(cfg):
				cfg = cfg()
			if cfg is not None:
				for key in ["backend_name", "backend_version", "simulator", "local", "n_qubits", "max_shots", "basis_gates"]:
					val = getattr(cfg, key, None)
					if val is not None:
						self.features[f"qiskit_cfg_{key}"] = val
		except Exception:
			pass

		try:
			props = getattr(backend_obj, "properties", None)
			if callable(props):
				props = props()
			if props is not None:
				self.features["qiskit_has_properties"] = True
				if hasattr(props, "last_update_date"):
					self.features["qiskit_calibration_last_update"] = str(getattr(props, "last_update_date"))
		except Exception:
			pass

	def _looks_like_pennylane_device_or_qnode(self, backend_obj):
		try:
			import pennylane as qml
			if isinstance(backend_obj, qml.QNode):
				return True
		except Exception:
			pass
		return hasattr(backend_obj, "short_name") or hasattr(backend_obj, "shots") or hasattr(backend_obj, "execute") or hasattr(backend_obj, "device")

	def _infer_pennylane_features(self, backend_obj):
		try:
			import pennylane as qml
			dev = getattr(backend_obj, "device", None) if isinstance(backend_obj, qml.QNode) else backend_obj
			if dev is None:
				return

			name = getattr(dev, "name", None)
			short_name = getattr(dev, "short_name", None)
			shots = getattr(dev, "shots", None)
			num_wires = getattr(dev, "num_wires", None)

			if name is not None:
				self.features["pennylane_device_name"] = name
			if short_name is not None:
				self.features["pennylane_device_short_name"] = short_name
			if shots is not None:
				self.features["pennylane_device_shots"] = shots
			if num_wires is not None:
				self.features["pennylane_device_num_wires"] = num_wires
		except Exception:
			return

	def set_run_dependent_features(self, run_config):
		if isinstance(run_config, dict):
			for k, v in run_config.items():
				self.features[k] = v
