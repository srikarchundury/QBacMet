from .layer import Layer
import os
import subprocess


class SlurmLayer(Layer):
	def __init__(self):
		super().__init__()

	def _to_int(self, val):
		try:
			if val is None:
				return None
			return int(val)
		except Exception:
			return None

	def _run_cmd(self, cmd):
		try:
			res = subprocess.run(cmd, capture_output=True, text=True)
			out = (res.stdout or "").strip()
			return out if out else None
		except Exception:
			return None

	def get_slurm_version(self):
		return self._run_cmd(["sinfo", "--version"])

	def _parse_scontrol_kv(self, text):
		# Parses "Key=Value" tokens from scontrol output into a dict
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

	def auto_collect(self):
		self.metrics = {}
		self.features = {}

		job_id = os.environ.get("SLURM_JOB_ID")
		self.features["slurm_version"] = self.get_slurm_version()

		# Helpful "mode" signal
		self.features["in_slurm_job"] = True if job_id else False

		# Basic env metrics (works only inside allocation)
		self.metrics["job_id"] = self._to_int(job_id)
		self.metrics["partition"] = os.environ.get("SLURM_JOB_PARTITION")
		self.metrics["nodelist"] = os.environ.get("SLURM_JOB_NODELIST")
		self.metrics["ntasks"] = self._to_int(os.environ.get("SLURM_NTASKS"))
		self.metrics["cpus_on_node"] = self._to_int(os.environ.get("SLURM_CPUS_ON_NODE"))

		# Sometimes present (cluster-dependent)
		self.metrics["scheduling_policy"] = os.environ.get("SLURM_SCHEDULING_POLICY")

		# Extra useful env features
		self.features["cluster_name"] = os.environ.get("SLURM_CLUSTER_NAME")
		self.features["job_name"] = os.environ.get("SLURM_JOB_NAME")
		self.features["submit_dir"] = os.environ.get("SLURM_SUBMIT_DIR")
		self.features["user"] = os.environ.get("SLURM_JOB_USER", os.environ.get("USER"))
		self.features["step_id"] = os.environ.get("SLURM_STEP_ID")

		# If actually in a job, enrich via scontrol
		if job_id:
			info = self._scontrol_show_job(job_id)

			# Only add common ones (stable, useful)
			self.metrics["num_nodes"] = self._to_int(info.get("NumNodes"))
			self.metrics["num_cpus"] = self._to_int(info.get("NumCPUs"))
			self.metrics["num_tasks"] = self._to_int(info.get("NumTasks"))

			self.features["account"] = info.get("Account")
			self.features["qos"] = info.get("QOS")
			self.features["time_limit"] = info.get("TimeLimit")
			self.features["tres"] = info.get("TRES")

		return self.get_payload()
