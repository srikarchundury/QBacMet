from .layer_0 import SlurmLayer
from .layer_1 import AlgLayer
from .layer_2 import TranspileLayer
from .layer_3 import BackendLayer
from .layer_4 import ExecutionLayer
from .layer_5 import PostprocessLayer

import contextlib
from time import perf_counter


class QBacMetCollector:
	def __init__(self):
		self._last_algo_obj = None
		self.alg_layer = AlgLayer()
		self.transpile_layer = TranspileLayer()
		self.backend_layer = BackendLayer()
		self.execution_layer = ExecutionLayer()
		self.postprocess_layer = PostprocessLayer()
		self.slurm_layer = SlurmLayer()

		self.collecting = False
		self.metrics = {}

		# Hook state
		self._orig_qiskit_transpile = None
		self._orig_qiskit_compiler_transpile = None
		self._orig_qnode_call = None
		self._wrapped_backend_runs = set()

		# PassManager / preset hooks (for generate_preset_pass_manager(...).run(qc))
		self._orig_generate_preset_pass_manager = None
		self._orig_passmanager_run = None

		# Track last seen backend objects for final auto_collect()
		self._last_qiskit_backend = None
		self._last_pl_device_or_qnode = None

	def start_collecting(self):
		self._last_algo_obj = None
		self.collecting = True
		self.metrics = {}
		self._last_qiskit_backend = None
		self._last_pl_device_or_qnode = None

		# Reset layers
		self.alg_layer.reset()
		self.transpile_layer.reset()
		self.backend_layer.reset()
		self.execution_layer.reset()
		self.postprocess_layer.reset()
		self.slurm_layer.reset()

	def stop_collecting(self):
		self.collecting = False

	# -------------------------
	# Small helpers
	# -------------------------
	def _safe_value(self, v):
		# Keep features JSON-ish and stable.
		if v is None:
			return None
		if isinstance(v, (bool, int, float, str)):
			return v
		if isinstance(v, (list, tuple)):
			return [self._safe_value(x) for x in v]
		if isinstance(v, dict):
			out = {}
			for k, vv in v.items():
				try:
					out[str(k)] = self._safe_value(vv)
				except Exception:
					out[str(k)] = str(vv)
			return out
		# fallback
		try:
			return str(v)
		except Exception:
			return None

	def _filter_transpile_kwargs(self, kwargs):
		# Avoid storing large / non-serializable objects. Keep only useful knobs.
		keep = [
			"optimization_level",
			"basis_gates",
			"coupling_map",
			"initial_layout",
			"layout_method",
			"routing_method",
			"translation_method",
			"scheduling_method",
			"approximation_degree",
			"seed_transpiler",
			"unitary_synthesis_method",
			"dt",
			"timing_constraints",
			"target",
			"shots",
		]

		out = {}
		for k in keep:
			if k in kwargs:
				out[k] = self._safe_value(kwargs.get(k))
		return out

	def _wrap_backend_run(self, backend_obj):
		# Wrap backend.run() once per backend instance (best-effort)
		if backend_obj is None:
			return
		key = id(backend_obj)
		if key in self._wrapped_backend_runs:
			return
		if not hasattr(backend_obj, "run"):
			return

		orig_run = backend_obj.run  # bound method

		def wrapped_run(*args, **kwargs):
			# Do nothing if not actively collecting
			if not self.collecting:
				return orig_run(*args, **kwargs)

			self._last_qiskit_backend = backend_obj
			self.backend_layer.set_backend_details(backend_obj)

			t0 = perf_counter()
			out = orig_run(*args, **kwargs)
			t1 = perf_counter()

			# backend.run() is part of execution time
			prev = self.execution_layer.metrics.get("execution_time", None)
			if prev is None:
				prev = 0.0
			self.execution_layer.metrics["execution_time"] = float(prev) + (t1 - t0)

			return out

		try:
			backend_obj.run = wrapped_run
			self._wrapped_backend_runs.add(key)
		except Exception:
			return

	def _install_hooks(self):
		# Qiskit transpile hook
		try:
			import qiskit
			import qiskit.compiler

			if self._orig_qiskit_transpile is None:
				self._orig_qiskit_transpile = getattr(qiskit, "transpile", None)
			if self._orig_qiskit_compiler_transpile is None:
				self._orig_qiskit_compiler_transpile = getattr(qiskit.compiler, "transpile", None)

			def hooked_transpile(*args, **kwargs):
				# If not collecting, behave like normal
				if not self.collecting:
					if self._orig_qiskit_compiler_transpile is not None:
						return self._orig_qiskit_compiler_transpile(*args, **kwargs)
					return self._orig_qiskit_transpile(*args, **kwargs)

				# Capture transpile knobs as FEATURES (sanitized)
				self.transpile_layer.set_transpile_features(**self._filter_transpile_kwargs(kwargs))

				# Capture algorithm metrics pre-transpile (best effort)
				if args:
					cand = args[0]
					self._last_algo_obj = cand

					alg_m = self.alg_layer.get_metrics(cand, shots=kwargs.get("shots", None))
					if isinstance(alg_m, dict) and alg_m:
						self.alg_layer.metrics = alg_m

				backend = kwargs.get("backend", None)
				if backend is not None:
					self._last_qiskit_backend = backend
					try:
						self.backend_layer.set_backend_details(backend)
						self._wrap_backend_run(backend)
					except Exception as e:
						self.backend_layer.metrics["backend_details_error"] = str(e)

				# Actually transpile (time it)
				t0 = perf_counter()
				if self._orig_qiskit_compiler_transpile is not None:
					out = self._orig_qiskit_compiler_transpile(*args, **kwargs)
				else:
					out = self._orig_qiskit_transpile(*args, **kwargs)
				t1 = perf_counter()

				prev = self.execution_layer.metrics.get("transpile_time", None)
				if prev is None:
					prev = 0.0
				self.execution_layer.metrics["transpile_time"] = float(prev) + (t1 - t0)

				# Capture compiled circuit metrics
				try:
					hw_circ = out[0] if isinstance(out, (list, tuple)) and out else out
					self.transpile_layer.set_compiled_circuit_metrics(hw_circ)
				except Exception:
					pass

				return out

			# Patch both common entry points
			if self._orig_qiskit_transpile is not None:
				qiskit.transpile = hooked_transpile
			if self._orig_qiskit_compiler_transpile is not None:
				qiskit.compiler.transpile = hooked_transpile

		except Exception as e:
			self.backend_layer.metrics["qiskit_hook_error"] = str(e)

		# -------------------------
		# Qiskit preset pass manager + PassManager.run hooks
		# -------------------------
		try:
			from qiskit.transpiler import preset_passmanagers as ppm
			from qiskit.transpiler import passmanager as pm_mod

			# Hook generate_preset_pass_manager so we see optimization_level/target
			if self._orig_generate_preset_pass_manager is None:
				self._orig_generate_preset_pass_manager = getattr(ppm, "generate_preset_pass_manager", None)

			def hooked_generate_preset_pass_manager(*args, **kwargs):
				if (not self.collecting) or (self._orig_generate_preset_pass_manager is None):
					return self._orig_generate_preset_pass_manager(*args, **kwargs)

				# Capture knobs as features (best-effort, JSON-safe)
				try:
					feat = {}

					if "optimization_level" in kwargs:
						try:
							feat["optimization_level"] = int(kwargs["optimization_level"])
						except Exception:
							feat["optimization_level"] = self._safe_value(kwargs["optimization_level"])

					# Target is important for preset PM
					if "target" in kwargs and kwargs["target"] is not None:
						# Avoid serializing the whole target object
						try:
							feat["target"] = str(type(kwargs["target"]))
						except Exception:
							feat["target"] = self._safe_value(kwargs["target"])

					# Some callers pass backend=...
					if "backend" in kwargs and kwargs["backend"] is not None:
						b = kwargs["backend"]
						self._last_qiskit_backend = b
						try:
							self.backend_layer.set_backend_details(b)
							self._wrap_backend_run(b)
						except Exception as e:
							self.backend_layer.metrics["backend_details_error"] = str(e)
						feat["backend"] = self._safe_value(getattr(b, "name", None) or str(type(b)))

					if feat:
						self.transpile_layer.set_transpile_features(**feat)
				except Exception:
					pass

				return self._orig_generate_preset_pass_manager(*args, **kwargs)

			if self._orig_generate_preset_pass_manager is not None:
				ppm.generate_preset_pass_manager = hooked_generate_preset_pass_manager

			# Hook PassManager.run to time + collect compiled circuit metrics
			if self._orig_passmanager_run is None:
				self._orig_passmanager_run = getattr(pm_mod.PassManager, "run", None)

			def hooked_passmanager_run(pm_self, *args, **kwargs):
				if (not self.collecting) or (self._orig_passmanager_run is None):
					return self._orig_passmanager_run(pm_self, *args, **kwargs)

				t0 = perf_counter()
				out = self._orig_passmanager_run(pm_self, *args, **kwargs)
				t1 = perf_counter()

				# Treat PassManager.run as transpile_time
				prev = self.execution_layer.metrics.get("transpile_time", 0.0) or 0.0
				self.execution_layer.metrics["transpile_time"] = float(prev) + (t1 - t0)

				# Compiled circuit metrics
				try:
					hw_circ = out[0] if isinstance(out, (list, tuple)) and out else out
					self.transpile_layer.set_compiled_circuit_metrics(hw_circ)
				except Exception:
					pass

				return out

			if self._orig_passmanager_run is not None:
				pm_mod.PassManager.run = hooked_passmanager_run

		except Exception as e:
			self.backend_layer.metrics["passmanager_hook_error"] = str(e)

		# PennyLane QNode hook
		try:
			import pennylane as qml

			if self._orig_qnode_call is None:
				self._orig_qnode_call = qml.QNode.__call__

			def hooked_qnode_call(qnode_self, *args, **kwargs):
				if not self.collecting:
					return self._orig_qnode_call(qnode_self, *args, **kwargs)

				# Track backend-ish object for Layer-3 inference
				self._last_pl_device_or_qnode = qnode_self

				t0 = perf_counter()
				out = self._orig_qnode_call(qnode_self, *args, **kwargs)
				t1 = perf_counter()

				prev = self.execution_layer.metrics.get("execution_time", None)
				if prev is None:
					prev = 0.0
				self.execution_layer.metrics["execution_time"] = float(prev) + (t1 - t0)

				# Record algorithm metrics AFTER execution
				try:
					self._last_algo_obj = qnode_self

					alg_m = self.alg_layer.get_metrics(qnode_self, shots=None)
					if isinstance(alg_m, dict) and alg_m:
						self.alg_layer.metrics = alg_m
				except Exception:
					pass

				return out

			qml.QNode.__call__ = hooked_qnode_call

		except Exception:
			pass

	def _remove_hooks(self):
		# Restore Qiskit hooks
		try:
			import qiskit
			import qiskit.compiler
			if self._orig_qiskit_transpile is not None:
				qiskit.transpile = self._orig_qiskit_transpile
			if self._orig_qiskit_compiler_transpile is not None:
				qiskit.compiler.transpile = self._orig_qiskit_compiler_transpile
		except Exception:
			pass

		# Restore preset pass manager / PassManager hooks
		try:
			from qiskit.transpiler import preset_passmanagers as ppm
			from qiskit.transpiler import passmanager as pm_mod

			if self._orig_generate_preset_pass_manager is not None:
				ppm.generate_preset_pass_manager = self._orig_generate_preset_pass_manager
			if self._orig_passmanager_run is not None:
				pm_mod.PassManager.run = self._orig_passmanager_run
		except Exception:
			pass

		# Restore PennyLane hook
		try:
			import pennylane as qml
			if self._orig_qnode_call is not None:
				qml.QNode.__call__ = self._orig_qnode_call
		except Exception:
			pass

	def auto_collect_all(self):
		# Always include all layers (even if empty) for stable schema
		self.metrics["slurm"] = self.slurm_layer.auto_collect()
		# Final best-effort alg collection (hooks can miss if user imported transpile early)
		if (not isinstance(self.alg_layer.metrics, dict)) or (self.alg_layer.metrics.get("framework") is None):
			if self._last_algo_obj is not None:
				try:
					alg_m = self.alg_layer.get_metrics(self._last_algo_obj, shots=None)
					if isinstance(alg_m, dict) and alg_m:
						self.alg_layer.metrics = alg_m
				except Exception:
					pass
		self.metrics["algorithm"] = self.alg_layer.get_payload()

		self.metrics["transpile"] = self.transpile_layer.auto_collect()

		# Important: call backend auto_collect with the last seen backend object
		backend_obj = self._last_qiskit_backend if self._last_qiskit_backend is not None else self._last_pl_device_or_qnode
		self.metrics["backend"] = self.backend_layer.auto_collect(backend_obj) if backend_obj is not None else self.backend_layer.auto_collect()

		self.metrics["execution"] = self.execution_layer.auto_collect()
		self.metrics["postprocess"] = self.postprocess_layer.auto_collect()

	@contextlib.contextmanager
	def collect(self):
		self.start_collecting()
		self._install_hooks()
		try:
			yield self
		finally:
			try:
				self.auto_collect_all()
			finally:
				self._remove_hooks()
				self.stop_collecting()

	def print_metrics(self):
		import pprint
		pprint.pprint(self.metrics)
