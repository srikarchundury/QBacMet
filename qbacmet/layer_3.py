# qbacmet/layer_3.py
from .layer import Layer
import os
import time


class BackendLayer(Layer):
	def __init__(self):
		super().__init__()

	def auto_collect(self, backend_obj=None, realtime=True, **kwargs):
		if "env_backend" not in self.features:
			self.features["env_backend"] = os.environ.get("QBACMET_BACKEND")

		if backend_obj is not None:
			self.set_backend_details(backend_obj)
			self._auto_infer_backend_features(backend_obj)
			if realtime:
				self.metrics.update(self.realtime_snapshot(backend_obj))

		return self.get_payload()

	def set_simulator_features(self, **features):
		"""Features the caller knows (simulation method, device, precision, bond dimension, processes, ...)."""
		for k, v in features.items():
			self.features[k] = self.json_safe(v)

	def realtime_snapshot(self, backend_obj):
		"""Values that change between submissions, read from the backend now and never cached: status and
		queue, and for devices with a Qiskit Target the current calibration (medians over qubits and gates).
		Every value carries rt_fetched_at; a failed read is recorded as rt_error, not filled from older data."""
		out = {"rt_fetched_at": time.time()}
		errors = []

		try:
			st = backend_obj.status() if callable(getattr(backend_obj, "status", None)) else None
			if st is not None:
				out["rt_operational"] = getattr(st, "operational", None)
				out["rt_pending_jobs"] = getattr(st, "pending_jobs", None)
				out["rt_status_msg"] = getattr(st, "status_msg", None)
		except Exception as e:
			errors.append(f"status: {e}")

		try:
			target = getattr(backend_obj, "target", None)
			if target is not None and getattr(target, "num_qubits", None):
				out.update(self._calibration_medians(target))
		except Exception as e:
			errors.append(f"target: {e}")

		try:
			props = backend_obj.properties() if callable(getattr(backend_obj, "properties", None)) else None
			when = getattr(props, "last_update_date", None) if props is not None else None
			if when is not None:
				out["rt_calibration_time"] = str(when)
				try:
					out["rt_calibration_age_s"] = time.time() - when.timestamp()
				except Exception:
					pass
		except Exception as e:
			errors.append(f"properties: {e}")

		if errors:
			out["rt_error"] = "; ".join(errors)[:500]
		return out

	@staticmethod
	def _median(vals):
		vals = sorted(v for v in vals if v is not None)
		if not vals:
			return None
		m = len(vals) // 2
		return vals[m] if len(vals) % 2 else 0.5 * (vals[m - 1] + vals[m])

	def _calibration_medians(self, target):
		e1, e2, ro, t1, t2, d2 = [], [], [], [], [], []
		for name in target.operation_names:
			try:
				props = target[name]
			except Exception:
				continue
			if not hasattr(props, "items"):
				continue
			for qargs, p in props.items():
				if qargs is None or p is None:
					continue
				err = getattr(p, "error", None)
				if err is None or err >= 0.5:      # unusable elements are listed with error >= 0.5
					continue
				if name == "measure":
					ro.append(err)
				elif len(qargs) == 1 and name not in ("delay", "reset", "id"):
					e1.append(err)
				elif len(qargs) == 2:
					e2.append(err)
					d2.append(getattr(p, "duration", None))
		for q in range(target.num_qubits):
			try:
				qp = target.qubit_properties[q] if target.qubit_properties else None
			except Exception:
				qp = None
			if qp is not None:
				t1.append(getattr(qp, "t1", None))
				t2.append(getattr(qp, "t2", None))
		return {"rt_num_qubits": target.num_qubits,
		        "rt_median_1q_error": self._median(e1), "rt_median_2q_error": self._median(e2),
		        "rt_median_readout_error": self._median(ro), "rt_median_t1_s": self._median(t1),
		        "rt_median_t2_s": self._median(t2), "rt_median_2q_duration_s": self._median(d2),
		        "rt_usable_2q_gates": len(e2)}

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
