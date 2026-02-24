# qbacmet/layer.py
# Base layer + shared utilities

from time import perf_counter
import inspect


class Layer:
	def __init__(self):
		self.start_time = None
		self.end_time = None
		self.tt = None
		self.metrics = {}
		self.features = {}

	# -----------------------------
	# Timing helpers
	# -----------------------------
	def mark_start(self):
		self.start_time = perf_counter()
		self.end_time = None
		self.tt = None

	def mark_end(self):
		self.end_time = perf_counter()
		if self.start_time is not None:
			self.tt = self.end_time - self.start_time
		return self.tt

	def reset(self):
		self.metrics = {}
		self.features = {}
		self.start_time = None
		self.end_time = None
		self.tt = None

	def get_payload(self):
		return {
			"metrics": self.metrics if isinstance(self.metrics, dict) else {},
			"features": self.features if isinstance(self.features, dict) else {}
		}

	# -----------------------------
	# Shared safe helpers
	# -----------------------------
	@staticmethod
	def safe_call(obj, attr, default=None):
		try:
			val = getattr(obj, attr, None)
			if callable(val):
				return val()
			return val if val is not None else default
		except Exception:
			return default

	@staticmethod
	def to_int(v, default=None):
		if v is None:
			return default
		try:
			return int(str(v).strip())
		except Exception:
			return default

	@staticmethod
	def json_safe(v, max_list=2048):
		# Keep JSON-ish + stable. Avoid huge objects.
		if v is None:
			return None
		if isinstance(v, (bool, int, float, str)):
			return v
		if isinstance(v, (list, tuple)):
			out = []
			for i, x in enumerate(v):
				if i >= max_list:
					out.append("...truncated...")
					break
				out.append(Layer.json_safe(x, max_list=max_list))
			return out
		if isinstance(v, dict):
			out = {}
			for k, vv in v.items():
				kk = str(k)
				out[kk] = Layer.json_safe(vv, max_list=max_list)
			return out
		try:
			return str(v)
		except Exception:
			return None

	@staticmethod
	def find_first_in_frames(pred, max_depth=50):
		# Scan caller frames for first local value matching predicate
		f = inspect.currentframe()
		if f is None:
			return None
		f = f.f_back
		depth = 0
		while f and depth < max_depth:
			for v in (getattr(f, "f_locals", {}) or {}).values():
				try:
					if pred(v):
						return v
				except Exception:
					continue
			f = f.f_back
			depth += 1
		return None

	@staticmethod
	def qiskit_circuit_connected_components(qc):
		# Best-effort connected-components from qubit interaction graph
		try:
			n = getattr(qc, "num_qubits", None)
			if n is None:
				return None
			n = int(n)
			if n <= 0:
				return 0

			adj = [set() for _ in range(n)]
			find_bit = getattr(qc, "find_bit", None)

			for ci in getattr(qc, "data", []) or []:
				qargs = getattr(ci, "qubits", None)
				if not qargs:
					continue

				qs = []
				for q in qargs:
					idx = None
					if callable(find_bit):
						try:
							idx = find_bit(q).index
						except Exception:
							idx = None
					if idx is None:
						idx = getattr(q, "index", None)
						if idx is None:
							idx = getattr(q, "_index", None)
					if idx is None:
						try:
							idx = list(qc.qubits).index(q)
						except Exception:
							idx = None
					if idx is not None:
						qs.append(int(idx))

				if len(qs) < 2:
					continue

				for i in range(len(qs)):
					for j in range(i + 1, len(qs)):
						a, b = qs[i], qs[j]
						if 0 <= a < n and 0 <= b < n:
							adj[a].add(b)
							adj[b].add(a)

			seen = [False] * n
			cc = 0
			for i in range(n):
				if seen[i]:
					continue
				cc += 1
				stack = [i]
				seen[i] = True
				while stack:
					u = stack.pop()
					for v in adj[u]:
						if not seen[v]:
							seen[v] = True
							stack.append(v)
			return cc
		except Exception:
			return None

	@staticmethod
	def qiskit_connectivity_stats(qc):
		# returns (cc, max_deg, avg_deg)
		try:
			n = getattr(qc, "num_qubits", None)
			if n is None:
				return None, None, None
			n = int(n)
			if n <= 0:
				return 0, 0, 0.0

			adj = [set() for _ in range(n)]
			find_bit = getattr(qc, "find_bit", None)

			for ci in getattr(qc, "data", []) or []:
				qargs = getattr(ci, "qubits", None)
				if not qargs:
					continue

				qs = []
				for q in qargs:
					idx = None
					if callable(find_bit):
						try:
							idx = find_bit(q).index
						except Exception:
							idx = None
					if idx is None:
						idx = getattr(q, "index", None)
						if idx is None:
							idx = getattr(q, "_index", None)
					if idx is not None:
						qs.append(int(idx))

				if len(qs) < 2:
					continue

				for i in range(len(qs)):
					for j in range(i + 1, len(qs)):
						a, b = qs[i], qs[j]
						if 0 <= a < n and 0 <= b < n:
							adj[a].add(b)
							adj[b].add(a)

			# cc
			seen = [False] * n
			cc = 0
			for i in range(n):
				if seen[i]:
					continue
				cc += 1
				stack = [i]
				seen[i] = True
				while stack:
					u = stack.pop()
					for v in adj[u]:
						if not seen[v]:
							seen[v] = True
							stack.append(v)

			deg = [len(adj[i]) for i in range(n)]
			max_deg = max(deg) if deg else 0
			avg_deg = (sum(deg) / float(n)) if n > 0 else 0.0
			return cc, max_deg, avg_deg
		except Exception:
			return None, None, None
