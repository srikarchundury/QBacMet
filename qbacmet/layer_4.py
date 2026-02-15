# This is for Layer-4 in README.md

from .layer import Layer
import os
import time


class ExecutionLayer(Layer):
	"""
	Collects execution metrics such as queue time, execution time, and parallel (OpenMP/MPI/HPC) details.
	Populated by env + collector hooks.
	"""
	def __init__(self):
		super().__init__()

	def _to_int(self, val):
		if val is None:
			return None
		try:
			return int(str(val).strip())
		except Exception:
			return None

	def mark_execution_start(self):
		# Wrapper around Layer timer for semantic clarity
		self.mark_start()
		# capture parallel env at start (best effort)
		self.set_parallel_env(preserve_existing=True)

	def mark_execution_end(self):
		tt = self.mark_end()
		# Only set execution_time if not explicitly set already
		if "execution_time" not in self.metrics or self.metrics["execution_time"] is None:
			self.metrics["execution_time"] = tt
		return tt

	def set_queue_time(self, queue_time):
		self.metrics["queue_time"] = queue_time

	def set_execution_time(self, execution_time):
		self.metrics["execution_time"] = execution_time

	def set_parallel_env(self, preserve_existing=True):
		# Best-effort environment capture; do not overwrite explicit values if preserve_existing=True
		def put(key, val):
			if preserve_existing and key in self.metrics and self.metrics[key] is not None:
				return
			self.metrics[key] = val

		put("openmp_num_threads", self._to_int(os.environ.get("OMP_NUM_THREADS")) or 1)

		put("mpi_rank", self._to_int(os.environ.get("OMPI_COMM_WORLD_RANK")) or self._to_int(os.environ.get("MPI_RANK")) or 0)
		put("mpi_size", self._to_int(os.environ.get("OMPI_COMM_WORLD_SIZE")) or self._to_int(os.environ.get("MPI_SIZE")) or 1)

		# These are SLURM env hints; real SLURM collection should happen in SlurmLayer.
		put("hpc_job_id", os.environ.get("SLURM_JOB_ID"))
		put("hostlist", os.environ.get("SLURM_JOB_NODELIST"))

	def auto_collect(self):
		# Only enrich; do not wipe metrics
		self.set_parallel_env(preserve_existing=True)
		return self.get_payload()
