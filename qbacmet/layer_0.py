# qbacmet/layer_0.py
from .layer import Layer
import os
import subprocess


class SlurmLayer(Layer):
	def __init__(self):
		super().__init__()

	def _run_cmd(self, cmd):
		try:
			res = subprocess.run(cmd, capture_output=True, text=True, check=False)
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

	def auto_collect(self):
		self.metrics = {}
		self.features = {}

		job_id = os.environ.get("SLURM_JOB_ID")
		self.features["in_slurm_job"] = True if job_id else False
		self.features["slurm_version"] = self._run_cmd(["sinfo", "--version"])

		self.metrics["job_id"] = self.to_int(job_id)
		self.metrics["partition"] = os.environ.get("SLURM_JOB_PARTITION")
		self.metrics["nodelist"] = os.environ.get("SLURM_JOB_NODELIST")
		self.metrics["ntasks"] = self.to_int(os.environ.get("SLURM_NTASKS"))
		self.metrics["cpus_on_node"] = self.to_int(os.environ.get("SLURM_CPUS_ON_NODE"))
		self.metrics["scheduling_policy"] = os.environ.get("SLURM_SCHEDULING_POLICY")

		self.features["cluster_name"] = os.environ.get("SLURM_CLUSTER_NAME")
		self.features["job_name"] = os.environ.get("SLURM_JOB_NAME")
		self.features["submit_dir"] = os.environ.get("SLURM_SUBMIT_DIR")
		self.features["user"] = os.environ.get("SLURM_JOB_USER", os.environ.get("USER"))
		self.features["step_id"] = os.environ.get("SLURM_STEP_ID")

		if job_id:
			info = self._scontrol_show_job(job_id)
			self.metrics["num_nodes"] = self.to_int(info.get("NumNodes"))
			self.metrics["num_cpus"] = self.to_int(info.get("NumCPUs"))
			self.metrics["num_tasks"] = self.to_int(info.get("NumTasks"))

			self.features["account"] = info.get("Account")
			self.features["qos"] = info.get("QOS")
			self.features["time_limit"] = info.get("TimeLimit")
			self.features["tres"] = info.get("TRES")

		return self.get_payload()
