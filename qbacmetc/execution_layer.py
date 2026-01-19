# This is for Layer-4 in README.md

from .layer import Layer
import os


class ExecutionLayer(Layer):
	"""
	Collects execution metrics such as queue time, execution time, and parallel (OpenMP/MPI/HPC) details.
	Populated by env + collector hooks.
	"""
	def __init__(self):
		super().__init__()

	def set_queue_time(self, queue_time):
		self.metrics["queue_time"] = queue_time

	def set_execution_time(self, execution_time):
		self.metrics["execution_time"] = execution_time

	def set_parallel_env(self):
		# Best-effort environment capture (strings preserved)
		self.metrics["openmp_num_threads"] = os.environ.get("OMP_NUM_THREADS", "1")
		self.metrics["mpi_rank"] = os.environ.get("OMPI_COMM_WORLD_RANK", os.environ.get("MPI_RANK", "0"))
		self.metrics["mpi_size"] = os.environ.get("OMPI_COMM_WORLD_SIZE", os.environ.get("MPI_SIZE", "1"))
		self.metrics["hpc_job_id"] = os.environ.get("SLURM_JOB_ID")
		self.metrics["hostlist"] = os.environ.get("SLURM_JOB_NODELIST")

	def auto_collect(self):
		self.set_parallel_env()
		return self.get_payload()
