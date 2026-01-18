# Layer-0 from README.md

from .layer import Layer


import os
import inspect

class SlurmLayer(Layer):
	def __init__(self):
		super().__init__()
		self.metrics = {}

	def auto_collect(self):
		# Collect SLURM/HPC metrics from environment and commands, filtered to current job's nodelist/partition
		def to_float(val):
			try:
				return float(val)
			except (TypeError, ValueError):
				return val
		self.metrics = {}  # Reset to avoid duplicates
		job_partition = os.environ.get('SLURM_JOB_PARTITION')
		job_nodelist = os.environ.get('SLURM_JOB_NODELIST')
		self.metrics['job_id'] = to_float(os.environ.get('SLURM_JOB_ID'))
		self.metrics['partition'] = job_partition
		self.metrics['nodelist'] = job_nodelist
		self.metrics['ntasks'] = to_float(os.environ.get('SLURM_NTASKS'))
		self.metrics['cpus_on_node'] = to_float(os.environ.get('SLURM_CPUS_ON_NODE'))
		self.metrics['scheduling_policy'] = os.environ.get('SLURM_SCHEDULING_POLICY')
		# Optionally, try to get more info using SLURM commands if available
		try:
			partitions = self.get_partitions()
			if isinstance(partitions, dict) and 'error' not in partitions and job_partition:
				# Filter to only current partition(s)
				filtered = [p for p in partitions.get('partitions', []) if p.get('partitionname') == job_partition]
				self.metrics['partitions'] = filtered
		except Exception:
			pass
		try:
			nodes = self.get_nodes()
			if isinstance(nodes, list) and job_nodelist:
				# job_nodelist can be a range, e.g. node[01-04], so expand if needed
				import re
				def expand_nodelist(nodelist):
					# Very basic: just split by comma and strip
					return [n.strip() for n in re.split(r'[\[\],]', nodelist) if n.strip() and not n.strip().isdigit() and '-' not in n.strip()]
				job_nodes = set(expand_nodelist(job_nodelist))
				filtered = [n for n in nodes if any(jn in n for jn in job_nodes)]
				self.metrics['nodes'] = filtered
		except Exception:
			pass
		return self.metrics
	

	import subprocess
	import json

	def get_partitions(self):
		"""Return partition info using scontrol."""
		try:
			result = self.subprocess.run(['scontrol', 'show', 'partition', '--json'], capture_output=True, text=True)
			return self.json.loads(result.stdout)
		except Exception as e:
			return {"error": str(e)}

	def get_nodes(self):
		"""Return node info using sinfo."""
		try:
			result = self.subprocess.run(['sinfo', '--format=%P,%D,%t,%N', '--noheader'], capture_output=True, text=True)
			lines = result.stdout.strip().splitlines()
			return [line.split(',') for line in lines]
		except Exception as e:
			return {"error": str(e)}

	def get_node_resources(self):
		"""Return CPUs, memory, disk, and GPU info for all nodes."""
		try:
			result = self.subprocess.run([
				'sinfo',
				'--format=%N,%c,%m,%G,%t',
				'--noheader'
			], capture_output=True, text=True)
			lines = result.stdout.strip().splitlines()
			return [dict(zip(['NodeName','CPUs','MemoryMB','Gres','State'], line.split(','))) for line in lines]
		except Exception as e:
			return {"error": str(e)}

	def get_partition_limits(self):
		"""Return partition limits: max time, max nodes, max CPUs per node."""
		try:
			result = self.subprocess.run([
				'sinfo',
				'--format=%P,%l,%s,%B',
				'--noheader'
			], capture_output=True, text=True)
			lines = result.stdout.strip().splitlines()
			return [dict(zip(['Partition','MaxTime','MaxNodes','MaxCPUsPerNode'], line.split(','))) for line in lines]
		except Exception as e:
			return {"error": str(e)}

	def get_node_states(self):
		"""Return number of nodes in each state (idle, allocated, down, etc)."""
		try:
			result = self.subprocess.run([
				'sinfo',
				'--format=%P,%D,%t',
				'--noheader'
			], capture_output=True, text=True)
			lines = result.stdout.strip().splitlines()
			return [dict(zip(['Partition','NumNodes','State'], line.split(','))) for line in lines]
		except Exception as e:
			return {"error": str(e)}

	def get_node_load(self):
		"""Return CPU load and free memory for all nodes."""
		try:
			result = self.subprocess.run([
				'sinfo',
				'--format=%N,%O,%e',
				'--noheader'
			], capture_output=True, text=True)
			lines = result.stdout.strip().splitlines()
			return [dict(zip(['NodeName','CPULoad','FreeMemMB'], line.split(','))) for line in lines]
		except Exception as e:
			return {"error": str(e)}

	def get_job_resource_usage(self, jobid):
		"""Return resource usage for a job using sacct."""
		try:
			result = self.subprocess.run([
				'sacct',
				f'--jobs={jobid}',
				'--format=JobID,Elapsed,NCPUS,AllocNodes,State,MaxRSS,MaxDiskRead,MaxDiskWrite',
				'--noheader'
			], capture_output=True, text=True)
			lines = result.stdout.strip().splitlines()
			return [dict(zip(['JobID','Elapsed','NCPUS','AllocNodes','State','MaxRSS','MaxDiskRead','MaxDiskWrite'], line.split())) for line in lines]
		except Exception as e:
			return {"error": str(e)}
	def get_job_info(self, jobid):
		"""Return job info using scontrol."""
		try:
			result = self.subprocess.run(['scontrol', 'show', 'job', str(jobid), '--json'], capture_output=True, text=True)
			return self.json.loads(result.stdout)
		except Exception as e:
			return {"error": str(e)}

	def get_slurm_version(self):
		"""Return Slurm version using sinfo."""
		try:
			result = self.subprocess.run(['sinfo', '--version'], capture_output=True, text=True)
			return result.stdout.strip()
		except Exception as e:
			return {"error": str(e)}

	def get_scheduling_policy(self):
		"""Return scheduling policy from partition info."""
		partitions = self.get_partitions()
		# Example: extract scheduling policy if present
		try:
			return [p.get('Scheduling', None) for p in partitions.get('partitions', [])]
		except Exception as e:
			return {"error": str(e)}

