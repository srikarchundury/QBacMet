# Layer-0 from README.md

from .layer import Layer
import os
import subprocess
import json


class SlurmLayer(Layer):
	def __init__(self):
		super().__init__()

	def _to_float(self, val):
		try:
			return float(val)
		except Exception:
			return val

	def auto_collect(self):
		# Always collect env-level SLURM info (cheap, reliable)
		self.metrics = {}

		self.metrics["job_id"] = self._to_float(os.environ.get("SLURM_JOB_ID"))
		self.metrics["partition"] = os.environ.get("SLURM_JOB_PARTITION")
		self.metrics["nodelist"] = os.environ.get("SLURM_JOB_NODELIST")
		self.metrics["ntasks"] = self._to_float(os.environ.get("SLURM_NTASKS"))
		self.metrics["cpus_on_node"] = self._to_float(os.environ.get("SLURM_CPUS_ON_NODE"))
		self.metrics["scheduling_policy"] = os.environ.get("SLURM_SCHEDULING_POLICY")

		# Optional: best-effort command probes (don’t break collection if unavailable)
		self.features["slurm_version"] = self.get_slurm_version()

		return self.get_payload()

	def get_slurm_version(self):
		try:
			result = subprocess.run(["sinfo", "--version"], capture_output=True, text=True)
			out = (result.stdout or "").strip()
			return out if out else None
		except Exception:
			return None

	def get_partitions(self):
		try:
			result = subprocess.run(["scontrol", "show", "partition", "--json"], capture_output=True, text=True)
			if not result.stdout:
				return {"error": "empty_stdout"}
			return json.loads(result.stdout)
		except Exception as e:
			return {"error": str(e)}

	def get_nodes(self):
		try:
			result = subprocess.run(["sinfo", "--format=%P,%D,%t,%N", "--noheader"], capture_output=True, text=True)
			lines = (result.stdout or "").strip().splitlines()
			return [line.split(",") for line in lines if line.strip()]
		except Exception as e:
			return {"error": str(e)}
