# qbacmet/collector.py
"""QBacMet collector: one QBacMetCollector per collection, safe across threads.

Library hooks (qiskit.transpile, PassManager.run, backend.run, IBM Runtime primitives, PennyLane QNodes) are
installed once while any collection is active and send every call to the collector active in the calling
thread. If a call comes from a thread with no collection of its own (e.g. a library worker thread) and
exactly one collection is active in the process, that one gets it; otherwise the call is not recorded. This
replaces the old single shared collector, whose metrics could mix when a QFw QPM ran several circuits at once.

Explicit API for frameworks that run circuits out of process (QFw local simulators launch a separate program,
so no hook can see the run):
    c = QBacMetCollector()
    with c.collect(hooks=False):
        c.set_algorithm_from_qasm(qasm_text, shots=1024)
        c.set_backend_features(backend="nwqsim", sub_backend="MPI", np=4)
    ...                                    # later, when the run finishes
    c.set_timeline(created=..., started=..., completed=...)
    metrics = c.finalize()                 # JSON-safe snapshot of all six layers
"""
import contextlib
import copy
import threading
import time
from time import perf_counter

from .layer import Layer
from .layer_0 import SlurmLayer
from .layer_1 import AlgLayer
from .layer_2 import RoutingSwapCounter, TranspileLayer
from .layer_3 import BackendLayer
from .layer_4 import ExecutionLayer
from .layer_5 import PostprocessLayer

# ------------------------------------------------------------------ process-wide hook registry
_LOCK = threading.RLock()
_TLS = threading.local()
_ACTIVE = []                    # collectors with hooks wanted, any thread
_HOOKS = {"refs": 0, "patches": [], "wrapped": set()}


def _stack():
	st = getattr(_TLS, "stack", None)
	if st is None:
		st = _TLS.stack = []
	return st


def current():
	"""Collector that should receive a hooked call made from this thread, or None."""
	st = _stack()
	for c in reversed(st):
		if c.collecting and c._hooks_wanted:
			return c
	with _LOCK:
		live = [c for c in _ACTIVE if c.collecting]
		return live[0] if len(live) == 1 else None


def _patch(obj, attr, new):
	try:
		orig = getattr(obj, attr)
	except Exception:
		return None
	try:
		setattr(obj, attr, new)
	except Exception:
		return None
	_HOOKS["patches"].append((obj, attr, orig))
	return orig


def _acquire_hooks():
	with _LOCK:
		_HOOKS["refs"] += 1
		if _HOOKS["refs"] == 1:
			_install_qiskit_hooks()
			_install_pennylane_hooks()
			_install_ibm_runtime_hooks()


def _release_hooks():
	with _LOCK:
		_HOOKS["refs"] = max(_HOOKS["refs"] - 1, 0)
		if _HOOKS["refs"] == 0:
			for obj, attr, orig in reversed(_HOOKS["patches"]):
				try:
					setattr(obj, attr, orig)
				except Exception:
					pass
			_HOOKS["patches"] = []
			_HOOKS["wrapped"] = set()


def _wrap_backend_run(backend_obj):
	"""Time backend.run on this object while hooks are installed (instance-level patch)."""
	if backend_obj is None or not hasattr(backend_obj, "run"):
		return
	with _LOCK:
		if _HOOKS["refs"] == 0 or id(backend_obj) in _HOOKS["wrapped"]:
			return
		orig_run = backend_obj.run

		def wrapped_run(*args, **kwargs):
			cur = current()
			if cur is None:
				return orig_run(*args, **kwargs)
			cur._note_backend(backend_obj)
			shots = kwargs.get("shots")
			if shots is not None:
				cur.alg_layer.merge_metrics({"shots": shots})
			t0 = perf_counter()
			out = orig_run(*args, **kwargs)
			cur._add_time("execution_time", perf_counter() - t0)
			return out

		if _patch(backend_obj, "run", wrapped_run) is not None:
			_HOOKS["wrapped"].add(id(backend_obj))


def _first(out):
	return out[0] if isinstance(out, (list, tuple)) and out else out


def _with_callback(fn, args, kwargs, make_counter):
	"""Rebind (args, kwargs) of fn so its `callback` argument becomes our SWAP counter, chained to the
	caller's callback whether that was passed by keyword or by position. Returns (args, kwargs, counter)."""
	import inspect
	try:
		bound = inspect.signature(fn).bind_partial(*args, **kwargs)
	except (TypeError, ValueError):
		counter = make_counter(kwargs.get("callback"))
		return args, dict(kwargs, callback=counter), counter
	counter = make_counter(bound.arguments.get("callback"))
	bound.arguments["callback"] = counter
	return bound.args, bound.kwargs, counter


@contextlib.contextmanager
def _in_transpile():
	"""Marks this thread as inside a hooked transpile(), whose own PassManager.run must not count twice."""
	depth = getattr(_TLS, "transpile_depth", 0)
	_TLS.transpile_depth = depth + 1
	try:
		yield
	finally:
		_TLS.transpile_depth = depth


def _install_qiskit_hooks():
	try:
		import qiskit
		import qiskit.compiler

		orig_qiskit = getattr(qiskit, "transpile", None)
		orig_compiler = getattr(qiskit.compiler, "transpile", None)
		orig = orig_compiler or orig_qiskit

		def hooked_transpile(*args, **kwargs):
			cur = current()
			if cur is None or getattr(_TLS, "transpile_depth", 0):
				return orig(*args, **kwargs)
			circ = args[0] if args else kwargs.get("circuits")
			cur._before_transpile(circ, kwargs)
			args, kwargs, counter = _with_callback(
				orig, args, kwargs, lambda user_cb: RoutingSwapCounter(cur._input_swaps(circ), user_cb))
			t0 = perf_counter()
			with _in_transpile():
				out = orig(*args, **kwargs)
			cur._after_transpile(out, perf_counter() - t0, counter.routing_swaps)
			return out

		if orig_qiskit is not None:
			_patch(qiskit, "transpile", hooked_transpile)
		if orig_compiler is not None:
			_patch(qiskit.compiler, "transpile", hooked_transpile)
	except Exception:
		pass

	# generate_preset_pass_manager(...) + PassManager.run(qc) (what IBM's recommended flow uses)
	try:
		from qiskit.transpiler import passmanager as pm_mod
		from qiskit.transpiler import preset_passmanagers as ppm

		orig_gen = getattr(ppm, "generate_preset_pass_manager", None)
		if orig_gen is not None:
			def hooked_generate(*args, **kwargs):
				cur = current()
				if cur is not None:
					cur._note_pass_manager_args(args, kwargs)
				return orig_gen(*args, **kwargs)

			_patch(ppm, "generate_preset_pass_manager", hooked_generate)
			try:
				import qiskit.transpiler as _tr
				if getattr(_tr, "generate_preset_pass_manager", None) is orig_gen:
					_patch(_tr, "generate_preset_pass_manager", hooked_generate)
			except Exception:
				pass

		orig_pm_run = getattr(pm_mod.PassManager, "run", None)
		if orig_pm_run is not None:
			def hooked_pm_run(pm_self, *args, **kwargs):
				cur = current()
				if cur is None or getattr(_TLS, "transpile_depth", 0):
					return orig_pm_run(pm_self, *args, **kwargs)
				circ = args[0] if args else kwargs.get("circuits")
				cur._before_transpile(circ, {})
				full, kw, counter = _with_callback(
					orig_pm_run, (pm_self,) + tuple(args), kwargs,
					lambda user_cb: RoutingSwapCounter(cur._input_swaps(circ), user_cb))
				t0 = perf_counter()
				with _in_transpile():
					out = orig_pm_run(*full, **kw)
				cur._after_transpile(out, perf_counter() - t0, counter.routing_swaps)
				return out

			_patch(pm_mod.PassManager, "run", hooked_pm_run)
	except Exception:
		pass


def _install_pennylane_hooks():
	try:
		import pennylane as qml

		orig_call = getattr(qml.QNode, "__call__", None)
		if orig_call is None:
			return

		def hooked_qnode_call(qnode_self, *args, **kwargs):
			cur = current()
			if cur is None:
				return orig_call(qnode_self, *args, **kwargs)
			cur._last_pl_device_or_qnode = qnode_self
			t0 = perf_counter()
			out = orig_call(qnode_self, *args, **kwargs)
			cur._add_time("execution_time", perf_counter() - t0)
			cur._last_algo_obj = qnode_self
			try:
				cur.alg_layer.merge_metrics(cur.alg_layer.get_metrics(qnode_self, shots=None))
			except Exception:
				pass
			return out

		_patch(qml.QNode, "__call__", hooked_qnode_call)
	except Exception:
		pass


def _install_ibm_runtime_hooks():
	try:
		from qiskit_ibm_runtime import EstimatorV2 as _EstimatorV2
		from qiskit_ibm_runtime import SamplerV2 as _SamplerV2

		def wrap_prim_run(orig_run):
			if orig_run is None:
				return None

			def wrapped_run(prim_self, *args, **kwargs):
				cur = current()
				if cur is None:
					return orig_run(prim_self, *args, **kwargs)
				for attr in ["backend", "_backend", "mode", "_mode"]:
					b = getattr(prim_self, attr, None)
					if b is not None:
						cur._note_backend(b)
						break
				shots = kwargs.get("shots")
				if shots is not None:
					cur.alg_layer.merge_metrics({"shots": shots})
				t0 = perf_counter()
				out = orig_run(prim_self, *args, **kwargs)
				cur._add_time("execution_time", perf_counter() - t0)
				return out

			return wrapped_run

		for cls in (_SamplerV2, _EstimatorV2):
			w = wrap_prim_run(getattr(cls, "run", None))
			if w is not None:
				_patch(cls, "run", w)
	except Exception:
		pass


# ------------------------------------------------------------------ collector

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
		self._hooks_wanted = False
		self._lock = threading.RLock()

		self._last_algo_obj = None
		self._last_qiskit_backend = None
		self._last_pl_device_or_qnode = None

	# ---- lifecycle
	def start_collecting(self):
		self.collecting = True
		self.metrics = {}
		self._last_algo_obj = None
		self._last_qiskit_backend = None
		self._last_pl_device_or_qnode = None
		for layer in self._layers():
			layer.reset()

	def stop_collecting(self):
		self.collecting = False

	def _layers(self):
		return (self.alg_layer, self.transpile_layer, self.backend_layer, self.execution_layer,
		        self.postprocess_layer, self.slurm_layer)

	@contextlib.contextmanager
	def collect(self, hooks=True, realtime=True):
		"""Collect while the block runs. hooks=False: record only what is set explicitly (no library patching).
		realtime=True: fresh queue / calibration / partition-load readings are taken at the end of the block."""
		self.start_collecting()
		self._realtime = realtime
		self._hooks_wanted = hooks
		_stack().append(self)
		if hooks:
			with _LOCK:
				_ACTIVE.append(self)
			_acquire_hooks()
		try:
			yield self
		finally:
			try:
				self.auto_collect_all()
			finally:
				if hooks:
					with _LOCK:
						if self in _ACTIVE:
							_ACTIVE.remove(self)
					_release_hooks()
				st = _stack()
				if self in st:
					st.remove(self)
				_TLS.last = self
				self.stop_collecting()

	# ---- explicit API
	def set_algorithm_object(self, obj, shots=None):
		"""Mark the algorithm object (QuantumCircuit, QNode or tape) and take its Layer-1 metrics now."""
		self._last_algo_obj = obj
		try:
			self.alg_layer.merge_metrics(self.alg_layer.get_metrics(obj, shots=shots))
		except Exception:
			pass

	def set_algorithm_from_qasm(self, qasm_text, shots=None):
		"""Layer 1 from OpenQASM 2/3 text (for frameworks that only pass QASM to the executor)."""
		try:
			from qiskit import QuantumCircuit
			if "OPENQASM 3" in qasm_text[:200]:
				from qiskit import qasm3
				qc = qasm3.loads(qasm_text)
			else:
				qc = QuantumCircuit.from_qasm_str(qasm_text)
		except Exception as e:
			self.alg_layer.merge_metrics({"error": f"qasm parse: {e}", "shots": shots})
			return None
		self.set_algorithm_object(qc, shots=shots)
		return qc

	def set_backend_features(self, **features):
		"""Layer 3 features known to the caller (backend, sub-backend, method, device, precision, processes...)."""
		self.backend_layer.set_simulator_features(**features)

	def set_timeline(self, **epochs):
		"""Layer 4 from wall-clock epochs (time.time()) of one run's stages; see ExecutionLayer.set_timeline."""
		self.execution_layer.set_timeline(**epochs)

	def finalize(self):
		"""Rebuild the six-layer payload from the layers now and return a deep, JSON-safe copy (safe to attach
		to a result while this collector keeps being used)."""
		with self._lock:
			self.auto_collect_all()
			return Layer.json_safe(copy.deepcopy(self.metrics))

	# ---- called by hooks
	def _add_time(self, key, dt):
		with self._lock:
			prev = self.execution_layer.metrics.get(key, 0.0) or 0.0
			self.execution_layer.metrics[key] = float(prev) + dt

	def _note_backend(self, backend_obj):
		self._last_qiskit_backend = backend_obj
		try:
			self.backend_layer.set_backend_details(backend_obj)
		except Exception:
			pass
		_wrap_backend_run(backend_obj)

	def _input_swaps(self, circ):
		try:
			return int(_first(circ).count_ops().get("swap", 0))
		except Exception:
			return 0

	def _before_transpile(self, circ, kwargs):
		keep = ["optimization_level", "basis_gates", "coupling_map", "initial_layout", "layout_method",
		        "routing_method", "translation_method", "scheduling_method", "approximation_degree",
		        "seed_transpiler", "unitary_synthesis_method", "dt", "timing_constraints", "target", "shots"]
		try:
			self.transpile_layer.set_transpile_features(
				**{k: Layer.json_safe(kwargs[k]) for k in keep if k in kwargs})
		except Exception:
			pass
		if circ is not None:
			self._last_algo_obj = _first(circ)
			try:
				self.alg_layer.merge_metrics(self.alg_layer.get_metrics(_first(circ), shots=kwargs.get("shots")))
			except Exception:
				pass
		backend = kwargs.get("backend")
		if backend is not None:
			self._note_backend(backend)

	def _after_transpile(self, out, dt, routing_swaps):
		self._add_time("transpile_time", dt)
		try:
			self.transpile_layer.set_compiled_circuit_metrics(_first(out), routing_swaps=routing_swaps)
		except Exception:
			pass

	def _note_pass_manager_args(self, args, kwargs):
		feat = {}
		if args:
			feat["optimization_level"] = Layer.json_safe(args[0])
		if "optimization_level" in kwargs:
			feat["optimization_level"] = Layer.json_safe(kwargs["optimization_level"])
		if kwargs.get("target") is not None:
			feat["target"] = str(type(kwargs["target"]).__name__)
		if kwargs.get("backend") is not None:
			b = kwargs["backend"]
			self._note_backend(b)
			feat["backend"] = Layer.json_safe(getattr(b, "name", None) or type(b).__name__)
		if feat:
			self.transpile_layer.set_transpile_features(**feat)

	# ---- payload
	def auto_collect_all(self):
		realtime = getattr(self, "_realtime", True)
		self.metrics["slurm"] = self.slurm_layer.auto_collect(realtime=realtime)

		if self.alg_layer.metrics.get("framework") is None and self._last_algo_obj is not None:
			try:
				self.alg_layer.merge_metrics(self.alg_layer.get_metrics(self._last_algo_obj, shots=None))
			except Exception:
				pass
		self.metrics["algorithm"] = self.alg_layer.get_payload()
		self.metrics["transpile"] = self.transpile_layer.auto_collect()

		backend_obj = self._last_qiskit_backend if self._last_qiskit_backend is not None \
			else self._last_pl_device_or_qnode
		self.metrics["backend"] = self.backend_layer.auto_collect(backend_obj, realtime=realtime)

		self.metrics["execution"] = self.execution_layer.auto_collect()
		self.metrics["postprocess"] = self.postprocess_layer.auto_collect()
		self.metrics["collected_at"] = time.time()

	def print_metrics(self):
		import pprint
		pprint.pprint(self.metrics)


# ------------------------------------------------------------------ module-level `collector`

class CollectorProxy:
	"""What `from qbacmet import collector` gives. Each `collector.collect()` uses a new QBacMetCollector, so
	collections in different threads never share state. Everything else (collector.metrics,
	collector.alg_layer, collector.collecting, ...) goes to this thread's active collection, or after it
	ends, to the last one this thread finished; that keeps existing single-threaded code working unchanged."""

	def collect(self, hooks=True, realtime=True):
		return QBacMetCollector().collect(hooks=hooks, realtime=realtime)

	def new(self):
		return QBacMetCollector()

	@staticmethod
	def _target():
		st = _stack()
		if st:
			return st[-1]
		last = getattr(_TLS, "last", None)
		if last is None:
			last = _TLS.last = QBacMetCollector()
		return last

	def __getattr__(self, name):
		return getattr(self._target(), name)

	def __setattr__(self, name, value):
		setattr(self._target(), name, value)
