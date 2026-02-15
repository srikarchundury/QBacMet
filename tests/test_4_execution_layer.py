import unittest
import time
import os
from qbacmet import ExecutionLayer


class TestExecutionLayer(unittest.TestCase):
	def setUp(self):
		self._env_backup = dict(os.environ)

	def tearDown(self):
		os.environ.clear()
		os.environ.update(self._env_backup)

	def test_payload_shape(self):
		layer = ExecutionLayer()
		payload = layer.auto_collect()

		self.assertIsInstance(payload, dict)
		self.assertIn("metrics", payload)
		self.assertIn("features", payload)
		self.assertIsInstance(payload["metrics"], dict)
		self.assertIsInstance(payload["features"], dict)

	def test_queue_time(self):
		layer = ExecutionLayer()
		layer.set_queue_time(12.5)
		self.assertEqual(layer.metrics["queue_time"], 12.5)

	def test_execution_time_manual(self):
		layer = ExecutionLayer()
		layer.set_execution_time(8.2)
		self.assertEqual(layer.metrics["execution_time"], 8.2)

	def test_parallel_env_defaults(self):
		# Clear relevant env vars
		for k in ["OMP_NUM_THREADS", "OMPI_COMM_WORLD_RANK", "OMPI_COMM_WORLD_SIZE", "MPI_RANK", "MPI_SIZE", "SLURM_JOB_ID", "SLURM_JOB_NODELIST"]:
			os.environ.pop(k, None)

		layer = ExecutionLayer()
		payload = layer.auto_collect()
		m = payload["metrics"]

		self.assertEqual(m.get("openmp_num_threads"), 1)
		self.assertEqual(m.get("mpi_rank"), 0)
		self.assertEqual(m.get("mpi_size"), 1)
		self.assertIsNone(m.get("hpc_job_id"))
		self.assertIsNone(m.get("hostlist"))

	def test_parallel_env_parsing(self):
		os.environ["OMP_NUM_THREADS"] = "16"
		os.environ["OMPI_COMM_WORLD_RANK"] = "2"
		os.environ["OMPI_COMM_WORLD_SIZE"] = "8"
		os.environ["SLURM_JOB_ID"] = "12345"
		os.environ["SLURM_JOB_NODELIST"] = "node[01-02]"

		layer = ExecutionLayer()
		payload = layer.auto_collect()
		m = payload["metrics"]

		self.assertEqual(m.get("openmp_num_threads"), 16)
		self.assertEqual(m.get("mpi_rank"), 2)
		self.assertEqual(m.get("mpi_size"), 8)
		self.assertEqual(m.get("hpc_job_id"), "12345")
		self.assertEqual(m.get("hostlist"), "node[01-02]")

	def test_timer_sets_execution_time(self):
		layer = ExecutionLayer()
		layer.mark_execution_start()
		time.sleep(0.01)
		tt = layer.mark_execution_end()

		self.assertIsNotNone(tt)
		self.assertIn("execution_time", layer.metrics)
		self.assertIsNotNone(layer.metrics["execution_time"])
		self.assertTrue(layer.metrics["execution_time"] >= 0.0)

	def test_auto_collect_does_not_overwrite_execution_time(self):
		layer = ExecutionLayer()
		layer.set_execution_time(8.2)

		# Even after auto_collect, explicit value should remain
		layer.auto_collect()
		self.assertEqual(layer.metrics["execution_time"], 8.2)


if __name__ == "__main__":
	unittest.main(verbosity=2)
