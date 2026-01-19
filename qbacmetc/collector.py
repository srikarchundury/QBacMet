from .alg_layer import AlgLayer
from .transpile_layer import TranspileLayer
from .backend_layer import BackendLayer
from .execution_layer import ExecutionLayer
from .postprocess_layer import PostprocessLayer
from .slurm_layer import SlurmLayer

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

		# Hook state
		self._orig_qiskit_transpile = None
		self._orig_qiskit_compiler_transpile = None
		self._orig_qnode_call = None
		self._wrapped_backend_runs = set()

	def start_collecting(self):
		self.collecting = True
		self.metrics = {}

		# Reset layers
		self.alg_layer.reset()
		self.transpile_layer.reset()
		self.backend_layer.reset()
		self.execution_layer.reset()
		self.postprocess_layer.reset()
		self.slurm_layer.reset()

	def stop_collecting(self):
		self.collecting = False

	def _wrap_backend_run(self, backend_obj):
		# Wrap backend.run() once per backend instance (best-effort)
		if backend_obj is None:
			return
		key = id(backend_obj)
		if key in self._wrapped_backend_runs:
			return
		if not hasattr(backend_obj, "run"):
			return

		orig_run = backend_obj.run

		def wrapped_run(*args, **kwargs):
			self.backend_layer.set_backend_details(backend_obj)

			t0 = perf_counter()
			out = orig_run(*args, **kwargs)
			t1 = perf_counter()

			# backend.run() time is part of "execution_time" from the quantum side
			self.execution_layer.metrics["execution_time"] = self.execution_layer.metrics.get("execution_time", 0.0) or 0.0
			self.execution_layer.metrics["execution_time"] += (t1 - t0)

			return out

		try:
			backend_obj.run = wrapped_run
			self._wrapped_backend_runs.add(key)
		except Exception:
			# If backend.run is read-only, just skip wrapping
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
				# Capture transpile knobs as FEATURES
				self.transpile_layer.set_transpile_features(**kwargs)

				# Try to capture algorithm circuit metrics pre-transpile
				if args:
					cand = args[0]
					alg_m = self.alg_layer.get_metrics(cand, shots=kwargs.get("shots", None))
					if isinstance(alg_m, dict) and alg_m:
						self.alg_layer.metrics = alg_m

				backend = kwargs.get("backend", None)
				if backend is not None:
					try:
						self.backend_layer.set_backend_details(backend)
						self._wrap_backend_run(backend)
					except ImportError as e:
						# Record ImportError in backend metrics
						self.backend_layer.metrics["import_error"] = str(e)
						self.backend_layer.metrics["backend_details_error"] = True
						# Optionally, add to execution layer as well
						self.execution_layer.metrics["backend_import_error"] = str(e)

				try:
					t0 = perf_counter()
					out = self._orig_qiskit_compiler_transpile(*args, **kwargs) if self._orig_qiskit_compiler_transpile else self._orig_qiskit_transpile(*args, **kwargs)
					t1 = perf_counter()
				except ImportError as e:
					# Record ImportError in backend metrics
					self.backend_layer.metrics["import_error"] = str(e)
					self.backend_layer.metrics["transpile_error"] = True
					self.execution_layer.metrics["transpile_import_error"] = str(e)
					return None

				# Record transpile time
				self.execution_layer.metrics["transpile_time"] = self.execution_layer.metrics.get("transpile_time", 0.0) or 0.0
				self.execution_layer.metrics["transpile_time"] += (t1 - t0)

				# Capture compiled circuit metrics
				try:
					# out can be a circuit or list of circuits
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
			# If import fails, record in backend metrics
			self.backend_layer.metrics["import_error"] = str(e)
			self.backend_layer.metrics["qiskit_hook_error"] = True
			self.execution_layer.metrics["qiskit_hook_import_error"] = str(e)

		# PennyLane QNode hook
		try:
			import pennylane as qml

			if self._orig_qnode_call is None:
				self._orig_qnode_call = qml.QNode.__call__

			def hooked_qnode_call(qnode_self, *args, **kwargs):
				# Record algorithm metrics AFTER execution (tape exists)
				t0 = perf_counter()
				out = self._orig_qnode_call(qnode_self, *args, **kwargs)
				t1 = perf_counter()

				self.execution_layer.metrics["execution_time"] = self.execution_layer.metrics.get("execution_time", 0.0) or 0.0
				self.execution_layer.metrics["execution_time"] += (t1 - t0)

				try:
					tape = getattr(qnode_self, "tape", None) or getattr(qnode_self, "qtape", None)
					if tape is not None:
						alg_m = self.alg_layer.get_metrics(tape, shots=None)
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

		# Restore PennyLane hook
		try:
			import pennylane as qml
			if self._orig_qnode_call is not None:
				qml.QNode.__call__ = self._orig_qnode_call
		except Exception:
			pass

		# Don’t attempt to restore backend.run per-instance; it’s harmless and local anyway.

	def auto_collect_all(self):
		# Always include all layers (even if empty) for stable schema
		self.metrics["slurm"] = self.slurm_layer.auto_collect()
		self.metrics["algorithm"] = self.alg_layer.get_payload()
		self.metrics["transpile"] = self.transpile_layer.auto_collect()
		self.metrics["backend"] = self.backend_layer.auto_collect()
		self.metrics["execution"] = self.execution_layer.auto_collect()
		self.metrics["postprocess"] = self.postprocess_layer.auto_collect()

	@contextlib.contextmanager
	def collect(self):
		self.start_collecting()
		self._install_hooks()
		try:
			yield self
		finally:
			# Collect at end of user block
			try:
				self.auto_collect_all()
			finally:
				self._remove_hooks()
				self.stop_collecting()

	def print_metrics(self):
		import pprint
		pprint.pprint(self.metrics)


# Singleton instance
collector = QBacMetCollector()
