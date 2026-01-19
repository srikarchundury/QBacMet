# Layer-0 from README.md

from .layer import Layer
import os
import subprocess
import json


class SlurmLayer(Layer):
	def __init__(self):
		super().__init__()

	def _to_int(self, val):
		if val is None:
			return None
		try:
			# Some SLURM vars can look like "16(x2)" or "16,16" depending on site config
			# Keep it conservative: parse leading int if possible.
			s = str(val).strip()
			num = ""
			for ch in s:
				if ch.isdigit():
					num += ch
				else:
					break
			return int(num) if num else None
		except Exception:
			return None

	def _run(self, cmd):
		# Best-effort command runner that never raises
		try:
			res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
			if res.returncode != 0:
				return None
			out = (res.stdout or "").strip()
			return out if out else None
		except Exception:
			return None

	def auto_collect(self):
		# Always collect env-level SLURM info (cheap, reliable)
		# IMPORTANT: do not wipe features each time unless you intend to.
		# We'll rebuild both dicts to keep payload stable.
		self.metrics = {}
		self.features = {}

		job_id = os.environ.get("SLURM_JOB_ID")
		nodelist = os.environ.get("SLURM_JOB_NODELIST")
		partition = os.environ.get("SLURM_JOB_PARTITION")

		self.metrics["job_id"] = self._to_int(job_id)
		self.metrics["partition"] = partition
		self.metrics["nodelist"] = nodelist

		# Tasks / CPUs: SLURM has multiple ways to represent these; try common envs.
		self.metrics["ntasks"] = self._to_int(os.environ.get("SLURM_NTASKS")) or self._to_int(os.environ.get("SLURM_NPROCS"))
		self.metrics["cpus_on_node"] = (
			self._to_int(os.environ.get("SLURM_CPUS_ON_NODE"))
			or self._to_int(os.environ.get("SLURM_CPUS_PER_TASK"))
			or self._to_int(os.environ.get("SLURM_JOB_CPUS_PER_NODE"))
		)

		# Scheduling policy is often not directly available; keep env first.
		self.metrics["scheduling_policy"] = os.environ.get("SLURM_SCHEDULING_POLICY")

		# hostlist: try derive from nodelist (works in-job and when env is stubbed)
		self.metrics["hostlist"] = self.get_hostlist(nodelist)

		# Features
		self.features["slurm_version"] = self.get_slurm_version()

		# Optional fallback: if we're in a real SLURM job, enrich from scontrol.
		# This is helpful when some env vars aren't present.
		if self.metrics["job_id"] is not None:
			job_info = self.get_job_info(self.metrics["job_id"])
			# Only fill missing items (never overwrite env values)
			if job_info and isinstance(job_info, dict):
				if self.metrics["partition"] is None:
					self.metrics["partition"] = job_info.get("Partition")
				if self.metrics["nodelist"] is None:
					self.metrics["nodelist"] = job_info.get("NodeList")
				if self.metrics["ntasks"] is None:
					self.metrics["ntasks"] = self._to_int(job_info.get("NumTasks"))
				# cpus_on_node is tricky from job info; keep env-derived value unless empty.

		return self.get_payload()

	def get_slurm_version(self):
		# Prefer the command that is most likely to exist everywhere
		out = self._run(["scontrol", "--version"])
		if out:
			return out
		out = self._run(["sinfo", "--version"])
		return out

	def get_hostlist(self, nodelist):
		if not nodelist:
			return None
		out = self._run(["scontrol", "show", "hostnames", nodelist])
		if not out:
			return None
		hosts = [line.strip() for line in out.splitlines() if line.strip()]
		return hosts if hosts else None

	def get_job_info(self, job_id):
		# Parse `scontrol show job` into a dict (best-effort).
		out = self._run(["scontrol", "show", "job", str(job_id)])
		if not out:
			return None

		# scontrol output is space-separated key=value pairs, sometimes wrapped across lines.
		info = {}
		parts = out.replace("\n", " ").split()
		for tok in parts:
			if "=" in tok:
				k, v = tok.split("=", 1)
				info[k] = v
		return info

	def get_partitions(self):
		try:
			result = subprocess.run(["scontrol", "show", "partition", "--json"], capture_output=True, text=True, timeout=2)
			if not result.stdout:
				return {"error": "empty_stdout"}
			return json.loads(result.stdout)
		except Exception as e:
			return {"error": str(e)}

	def get_nodes(self):
		try:
			result = subprocess.run(["sinfo", "--format=%P,%D,%t,%N", "--noheader"], capture_output=True, text=True, timeout=2)
			lines = (result.stdout or "").strip().splitlines()
			return [line.split(",") for line in lines if line.strip()]
		except Exception as e:
			return {"error": str(e)}
