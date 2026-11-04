# qbacmet/layer_4.py
from .layer import Layer
import os


class ExecutionLayer(Layer):
	def __init__(self):
		super().__init__()

	def mark_execution_start(self):
		self.mark_start()
		self.set_parallel_env(preserve_existing=True)

	def mark_execution_end(self):
		tt = self.mark_end()
		if "execution_time" not in self.metrics or self.metrics["execution_time"] is None:
			self.metrics["execution_time"] = tt
		return tt

	def set_queue_time(self, queue_time):
		self.metrics["queue_time"] = queue_time

	def set_execution_time(self, execution_time):
		self.metrics["execution_time"] = execution_time

	# stage boundaries (wall-clock epochs) -> (metric, start, end)
	TIMELINE = [
		("time_waiting_for_resources", "created", "resources_ready"),
		("time_to_launch", "resources_ready", "launched"),
		("launch_overhead", "launched", "started"),
		("execution_time", "started", "completed"),
		("time_in_result_queue", "result_queued", "result_taken"),
		("time_total", "created", "completed"),
	]

	def set_timeline(self, **epochs):
		"""Record the stage epochs of one run and the durations between them (seconds). Unknown or unset
		epochs (None, <= 0) are skipped, so a framework passes whatever stages it tracks. A measured
		execution_time wins over a hook's in-process timing of the same run."""
		ep = {k: float(v) for k, v in epochs.items() if v is not None and float(v) > 0}
		self.metrics["timeline"] = ep
		for name, a, b in self.TIMELINE:
			if a in ep and b in ep and ep[b] >= ep[a]:
				self.metrics[name] = ep[b] - ep[a]

	def set_parallel_env(self, preserve_existing=True):
		def put(key, val):
			if preserve_existing and key in self.metrics and self.metrics[key] is not None:
				return
			self.metrics[key] = val

		put("openmp_num_threads", self.to_int(os.environ.get("OMP_NUM_THREADS"), default=1) or 1)

		put("mpi_rank", self.to_int(os.environ.get("OMPI_COMM_WORLD_RANK")) or self.to_int(os.environ.get("MPI_RANK")) or 0)
		put("mpi_size", self.to_int(os.environ.get("OMPI_COMM_WORLD_SIZE")) or self.to_int(os.environ.get("MPI_SIZE")) or 1)

		put("hpc_job_id", os.environ.get("SLURM_JOB_ID"))
		put("hostlist", os.environ.get("SLURM_JOB_NODELIST"))

	def auto_collect(self):
		self.set_parallel_env(preserve_existing=True)
		return self.get_payload()
