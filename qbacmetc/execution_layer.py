# This is for Layer-4 in README.md

from .layer import Layer


import os
import inspect
class ExecutionLayer(Layer):
	"""
	Collects execution metrics such as queue time, execution time, and parallel (OpenMP/MPI/HPC) details.
	"""
	def __init__(self):
		super().__init__()
		self.metrics = {}

	def collect_queue_time(self, queue_info):
		self.metrics['queue_time'] = queue_info.get('queue_time', None)

	def collect_execution_time(self, exec_info):
		self.metrics['execution_time'] = exec_info.get('execution_time', None)

	def collect_parallel_metrics(self, parallel_info):
		self.metrics['openmp_num_threads'] = parallel_info.get('openmp_num_threads', None)
		self.metrics['mpi_rank'] = parallel_info.get('mpi_rank', None)
		self.metrics['mpi_size'] = parallel_info.get('mpi_size', None)
		self.metrics['node_id'] = parallel_info.get('node_id', None)
		self.metrics['hostlist'] = parallel_info.get('hostlist', None)
		self.metrics['hpc_job_id'] = parallel_info.get('hpc_job_id', None)

	def auto_collect(self):
		# Auto-collect from environment variables (no forced float conversion)
		self.metrics['openmp_num_threads'] = os.environ.get('OMP_NUM_THREADS', '1')
		self.metrics['mpi_rank'] = os.environ.get('OMPI_COMM_WORLD_RANK', os.environ.get('MPI_RANK', '0'))
		self.metrics['mpi_size'] = os.environ.get('OMPI_COMM_WORLD_SIZE', os.environ.get('MPI_SIZE', '1'))
		self.metrics['hpc_job_id'] = os.environ.get('SLURM_JOB_ID')
		self.metrics['hostlist'] = os.environ.get('SLURM_JOB_NODELIST')
		# Scan all frames for queue/execution info
		frame = inspect.currentframe().f_back
		found = False
		while frame:
			for var in frame.f_locals.values():
				if isinstance(var, dict) and 'queue_time' in var:
					self.collect_queue_time(var)
					found = True
				if isinstance(var, dict) and 'execution_time' in var:
					self.collect_execution_time(var)
					found = True
			frame = frame.f_back
		return self.get_metrics()
	