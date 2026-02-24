# qbacmet/collector.py
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
		self.alg_layer = AlgLayer()
		self.transpile_layer = TranspileLayer()
		self.backend_layer = BackendLayer()
		self.execution_layer = ExecutionLayer()
		self.postprocess_layer = PostprocessLayer()
		self.slurm_layer = SlurmLayer()

		self.collecting = False
		self.metrics = {}

		self._last_algo_obj = None
		self._last_qiskit_backend = None
		self._last_pl_device_or_qnode = None

		self._wrapped_backend_runs = set()
		self._patches = []  # [(obj, attr, orig)]

	def start_collecting(self):
		self.collecting = True
		self.metrics = {}
		self._last_algo_obj = None
		self._last_qiskit_backend = None
		self._last_pl_device_or_qnode = None

		self.alg_layer.reset()
		self.transpile_layer.reset()
		self.backend_layer.reset()
		self.execution_layer.reset()
		self.postprocess_layer.reset()
		self.slurm_layer.reset()

	def stop_collecting(self):
		self.collecting = False

	def set_algorithm_object(self, obj, shots=None):
		"""Allow caller to explicitly mark the algorithm object."""
		if not self.collecting:
			return
		self._last_algo_obj = obj
		try:
			alg_m = self.alg_layer.get_metrics(obj, shots=shots)
			if isinstance(alg_m, dict) and alg_m:
				self.alg_layer.metrics = alg_m
		except Exception:
			pass

	# -------------------------
	# Patch helpers
	# -------------------------
	def _patch_attr(self, obj, attr, new):
		try:
			orig = getattr(obj, attr)
		except Exception:
			return None
		self._patches.append((obj, attr, orig))
		try:
			setattr(obj, attr, new)
			return orig
		except Exception:
			# rollback record if we failed to set
			try:
				self._patches.pop()
			except Exception:
				pass
			return None

	def _unpatch_all(self):
		# restore in reverse order
		for obj, attr, orig in reversed(self._patches):
			try:
				setattr(obj, attr, orig)
			except Exception:
				pass
		self._patches = []

	def _filter_transpile_kwargs(self, kwargs):
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
				out[k] = self.alg_layer.json_safe(kwargs.get(k))
		return out

	def _wrap_backend_run(self, backend_obj):
		if backend_obj is None or not hasattr(backend_obj, "run"):
			return
		key = id(backend_obj)
		if key in self._wrapped_backend_runs:
			return

		orig_run = backend_obj.run

		def wrapped_run(*args, **kwargs):
			if not self.collecting:
				return orig_run(*args, **kwargs)

			self._last_qiskit_backend = backend_obj
			try:
				self.backend_layer.set_backend_details(backend_obj)
			except Exception:
				pass

			t0 = perf_counter()
			out = orig_run(*args, **kwargs)
			t1 = perf_counter()

			prev = self.execution_layer.metrics.get("execution_time", 0.0) or 0.0
			self.execution_layer.metrics["execution_time"] = float(prev) + (t1 - t0)
			return out

		try:
			backend_obj.run = wrapped_run
			self._wrapped_backend_runs.add(key)
		except Exception:
			return

	def _install_hooks(self):
		self._install_qiskit_hooks()
		self._install_pennylane_hooks()
		self._install_ibm_runtime_hooks()

	def _install_qiskit_hooks(self):
		# Hook qiskit.transpile + qiskit.compiler.transpile
		try:
			import qiskit
			import qiskit.compiler

			orig_qiskit_transpile = getattr(qiskit, "transpile", None)
			orig_compiler_transpile = getattr(qiskit.compiler, "transpile", None)

			def hooked_transpile(*args, **kwargs):
				if not self.collecting:
					# preserve original resolution order
					if orig_compiler_transpile is not None:
						return orig_compiler_transpile(*args, **kwargs)
					return orig_qiskit_transpile(*args, **kwargs)

				# features (knobs)
				try:
					self.transpile_layer.set_transpile_features(**self._filter_transpile_kwargs(kwargs))
				except Exception:
					pass

				# try infer algorithm object (usually qc)
				if args:
					self._last_algo_obj = args[0]
					try:
						alg_m = self.alg_layer.get_metrics(self._last_algo_obj, shots=kwargs.get("shots", None))
						if isinstance(alg_m, dict) and alg_m:
							self.alg_layer.metrics = alg_m
					except Exception:
						pass

				backend = kwargs.get("backend", None)
				if backend is not None:
					self._last_qiskit_backend = backend
					try:
						self.backend_layer.set_backend_details(backend)
					except Exception:
						pass
					self._wrap_backend_run(backend)

				t0 = perf_counter()
				out = (orig_compiler_transpile or orig_qiskit_transpile)(*args, **kwargs)
				t1 = perf_counter()

				prev = self.execution_layer.metrics.get("transpile_time", 0.0) or 0.0
				self.execution_layer.metrics["transpile_time"] = float(prev) + (t1 - t0)

				# compiled circuit metrics (first element if list)
				try:
					hw = out[0] if isinstance(out, (list, tuple)) and out else out
					self.transpile_layer.set_compiled_circuit_metrics(hw)
				except Exception:
					pass

				return out

			if orig_qiskit_transpile is not None:
				self._patch_attr(qiskit, "transpile", hooked_transpile)
			if orig_compiler_transpile is not None:
				self._patch_attr(qiskit.compiler, "transpile", hooked_transpile)

		except Exception as e:
			self.backend_layer.metrics["qiskit_hook_error"] = str(e)

		# Hook preset pass manager generator + PassManager.run (covers generate_preset_pass_manager(...).run(qc))
		try:
			from qiskit.transpiler import preset_passmanagers as ppm
			from qiskit.transpiler import passmanager as pm_mod

			orig_gen = getattr(ppm, "generate_preset_pass_manager", None)
			if orig_gen is not None:
				def hooked_generate_preset_pass_manager(*args, **kwargs):
					if not self.collecting:
						return orig_gen(*args, **kwargs)

					feat = {}
					if "optimization_level" in kwargs:
						feat["optimization_level"] = self.alg_layer.json_safe(kwargs.get("optimization_level"))
					if "target" in kwargs and kwargs["target"] is not None:
						try:
							feat["target"] = str(type(kwargs["target"]))
						except Exception:
							feat["target"] = self.alg_layer.json_safe(kwargs["target"])
					if "backend" in kwargs and kwargs["backend"] is not None:
						b = kwargs["backend"]
						self._last_qiskit_backend = b
						try:
							self.backend_layer.set_backend_details(b)
						except Exception:
							pass
						self._wrap_backend_run(b)
						feat["backend"] = self.alg_layer.json_safe(getattr(b, "name", None) or str(type(b)))

					if feat:
						try:
							self.transpile_layer.set_transpile_features(**feat)
						except Exception:
							pass

					return orig_gen(*args, **kwargs)

				self._patch_attr(ppm, "generate_preset_pass_manager", hooked_generate_preset_pass_manager)

			orig_pm_run = getattr(pm_mod.PassManager, "run", None)
			if orig_pm_run is not None:
				def hooked_pm_run(pm_self, *args, **kwargs):
					if not self.collecting:
						return orig_pm_run(pm_self, *args, **kwargs)

					t0 = perf_counter()
					out = orig_pm_run(pm_self, *args, **kwargs)
					t1 = perf_counter()

					prev = self.execution_layer.metrics.get("transpile_time", 0.0) or 0.0
					self.execution_layer.metrics["transpile_time"] = float(prev) + (t1 - t0)

					try:
						hw = out[0] if isinstance(out, (list, tuple)) and out else out
						self.transpile_layer.set_compiled_circuit_metrics(hw)
					except Exception:
						pass
					return out

				self._patch_attr(pm_mod.PassManager, "run", hooked_pm_run)

		except Exception as e:
			self.backend_layer.metrics["passmanager_hook_error"] = str(e)

	def _install_pennylane_hooks(self):
		try:
			import pennylane as qml

			orig_call = getattr(qml.QNode, "__call__", None)
			if orig_call is None:
				return

			def hooked_qnode_call(qnode_self, *args, **kwargs):
				if not self.collecting:
					return orig_call(qnode_self, *args, **kwargs)

				self._last_pl_device_or_qnode = qnode_self

				t0 = perf_counter()
				out = orig_call(qnode_self, *args, **kwargs)
				t1 = perf_counter()

				prev = self.execution_layer.metrics.get("execution_time", 0.0) or 0.0
				self.execution_layer.metrics["execution_time"] = float(prev) + (t1 - t0)

				# post execution alg metrics
				self._last_algo_obj = qnode_self
				try:
					alg_m = self.alg_layer.get_metrics(qnode_self, shots=None)
					if isinstance(alg_m, dict) and alg_m:
						self.alg_layer.metrics = alg_m
				except Exception:
					pass

				return out

			self._patch_attr(qml.QNode, "__call__", hooked_qnode_call)

		except Exception:
			pass

	def _install_ibm_runtime_hooks(self):
		# Hook SamplerV2/EstimatorV2 .run (timing + backend inference if possible)
		try:
			from qiskit_ibm_runtime import SamplerV2 as _SamplerV2
			from qiskit_ibm_runtime import EstimatorV2 as _EstimatorV2

			orig_sampler_run = getattr(_SamplerV2, "run", None)
			orig_estimator_run = getattr(_EstimatorV2, "run", None)

			def wrap_prim_run(orig_run):
				if orig_run is None:
					return None

				def wrapped_run(prim_self, *args, **kwargs):
					if not self.collecting:
						return orig_run(prim_self, *args, **kwargs)

					# best-effort: try infer a backend-like object off the primitive
					try:
						for attr in ["backend", "_backend", "mode", "_mode"]:
							b = getattr(prim_self, attr, None)
							if b is not None:
								self._last_qiskit_backend = b
								try:
									self.backend_layer.set_backend_details(b)
								except Exception:
									pass
								break
					except Exception:
						pass

					t0 = perf_counter()
					out = orig_run(prim_self, *args, **kwargs)
					t1 = perf_counter()

					prev = self.execution_layer.metrics.get("execution_time", 0.0) or 0.0
					self.execution_layer.metrics["execution_time"] = float(prev) + (t1 - t0)
					return out

				return wrapped_run

			w1 = wrap_prim_run(orig_sampler_run)
			if w1 is not None:
				self._patch_attr(_SamplerV2, "run", w1)

			w2 = wrap_prim_run(orig_estimator_run)
			if w2 is not None:
				self._patch_attr(_EstimatorV2, "run", w2)

		except Exception:
			pass

	def _remove_hooks(self):
		self._unpatch_all()

	def auto_collect_all(self):
		self.metrics["slurm"] = self.slurm_layer.auto_collect()

		# best-effort final algorithm capture
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
