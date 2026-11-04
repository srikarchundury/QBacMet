# qbacmet/layer_0.py
from .layer import Layer
import os
import subprocess
import threading
import time

# Job-level Slurm facts do not change during a job: look them up once per process, not once per circuit.
_STATIC_CACHE = {}
_STATIC_LOCK = threading.Lock()
_RT_CACHE = {}      # partition -> last partition-load reading (see realtime_partition_load)


class SlurmLayer(Layer):
	def __init__(self):
		super().__init__()

	def _run_cmd(self, cmd, timeout=10):
		try:
			res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout)
			out = (res.stdout or "").strip()
			return out if out else None
		except Exception:
			return None

	def _parse_scontrol_kv(self, text):
		out = {}
		if not text:
			return out
		for tok in text.replace("\n", " ").split():
			if "=" in tok:
				k, v = tok.split("=", 1)
				out[k.strip()] = v.strip()
		return out

	def _scontrol_show_job(self, job_id):
		if not job_id:
			return {}
		txt = self._run_cmd(["scontrol", "show", "job", str(job_id)])
		return self._parse_scontrol_kv(txt)

	def _static(self, job_id, nodelist):
		key = (job_id, nodelist)
		with _STATIC_LOCK:
			if key not in _STATIC_CACHE:
				hosts = self._run_cmd(["scontrol", "show", "hostnames", nodelist]) if nodelist else None
				_STATIC_CACHE[key] = {
					"slurm_version": self._run_cmd(["sinfo", "--version"]),
					"job": self._scontrol_show_job(job_id) if job_id else {},
					"hostlist": hosts.split() if hosts else None,
				}
			return _STATIC_CACHE[key]

	def get_partitions(self):
		"""{partition: {"avail", "nodes", "state"}} from sinfo, or {"error": ...}."""
		txt = self._run_cmd(["sinfo", "-h", "-o", "%P|%a|%D|%T"])
		if txt is None:
			return {"error": "sinfo unavailable"}
		out = {}
		for line in txt.splitlines():
			parts = line.split("|")
			if len(parts) == 4:
				name = parts[0].rstrip("*")
				out.setdefault(name, []).append({"avail": parts[1], "nodes": self.to_int(parts[2]), "state": parts[3]})
		return out

	def get_nodes(self):
		"""{node: state} from sinfo, or {"error": ...}."""
		txt = self._run_cmd(["sinfo", "-h", "-N", "-o", "%N|%T"])
		if txt is None:
			return {"error": "sinfo unavailable"}
		return dict(line.split("|", 1) for line in txt.splitlines() if "|" in line)

	def realtime_partition_load(self, partition):
		"""Node counts (allocated, idle, other, total) of a partition, read with sinfo.

		A reading is reused for at most QBACMET_RT_TTL seconds (default 10) so a burst of circuits does not
		start one sinfo each; rt_fetched_at is the time of the actual reading, so its age is always known.
		QBACMET_RT_TTL=0 reads every time."""
		if not partition:
			return {}
		ttl = float(os.environ.get("QBACMET_RT_TTL", "10"))
		with _STATIC_LOCK:
			hit = _RT_CACHE.get(partition)
			if hit is not None and time.time() - hit["rt_fetched_at"] < ttl:
				return dict(hit)
		txt = self._run_cmd(["sinfo", "-h", "-p", partition, "-o", "%F"])
		out = {"rt_fetched_at": time.time()}
		if txt and txt.count("/") == 3:
			a, i, o, t = (self.to_int(x) for x in txt.split()[0].split("/"))
			out.update(rt_partition_nodes_alloc=a, rt_partition_nodes_idle=i, rt_partition_nodes_other=o,
			           rt_partition_nodes_total=t)
			with _STATIC_LOCK:
				_RT_CACHE[partition] = dict(out)
		else:
			out["rt_error"] = "sinfo unavailable"
		return out

	def auto_collect(self, realtime=False, rt=None):
		self.metrics = {}
		self.features = {}

		job_id = os.environ.get("SLURM_JOB_ID")
		nodelist = os.environ.get("SLURM_JOB_NODELIST")
		static = self._static(job_id, nodelist)
		self.features["in_slurm_job"] = True if job_id else False
		self.features["slurm_version"] = static["slurm_version"]

		self.metrics["job_id"] = self.to_int(job_id)
		self.metrics["partition"] = os.environ.get("SLURM_JOB_PARTITION")
		self.metrics["nodelist"] = nodelist
		self.metrics["hostlist"] = static["hostlist"]
		self.metrics["ntasks"] = self.to_int(os.environ.get("SLURM_NTASKS"))
		self.metrics["cpus_on_node"] = self.to_int(os.environ.get("SLURM_CPUS_ON_NODE"))
		self.metrics["scheduling_policy"] = os.environ.get("SLURM_SCHEDULING_POLICY")

		self.features["cluster_name"] = os.environ.get("SLURM_CLUSTER_NAME")
		self.features["job_name"] = os.environ.get("SLURM_JOB_NAME")
		self.features["submit_dir"] = os.environ.get("SLURM_SUBMIT_DIR")
		self.features["user"] = os.environ.get("SLURM_JOB_USER", os.environ.get("USER"))
		self.features["step_id"] = os.environ.get("SLURM_STEP_ID")

		if job_id:
			info = static["job"]
			self.metrics["num_nodes"] = self.to_int(info.get("NumNodes"))
			self.metrics["num_cpus"] = self.to_int(info.get("NumCPUs"))
			self.metrics["num_tasks"] = self.to_int(info.get("NumTasks"))

			self.features["account"] = info.get("Account")
			self.features["qos"] = info.get("QOS")
			self.features["time_limit"] = info.get("TimeLimit")
			self.features["tres"] = info.get("TRES")

		if rt is not None:          # read when the collection started, i.e. before the run
			self.metrics.update(rt)
		elif realtime:
			self.metrics.update(self.realtime_partition_load(self.metrics["partition"]))

		return self.get_payload()
