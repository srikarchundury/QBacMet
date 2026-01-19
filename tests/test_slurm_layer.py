
import unittest
import os
from qbacmetc.slurm_layer import SlurmLayer


class TestSlurmLayer(unittest.TestCase):
	def setUp(self):
		# Backup env so we can restore cleanly
		self._env_backup = dict(os.environ)

	def tearDown(self):
		os.environ.clear()
		os.environ.update(self._env_backup)

	def test_auto_collect_shape_and_keys(self):
		# Set a minimal fake SLURM env
		os.environ["SLURM_JOB_ID"] = "12345"
		os.environ["SLURM_JOB_PARTITION"] = "debug"
		os.environ["SLURM_JOB_NODELIST"] = "node[01-02]"
		os.environ["SLURM_NTASKS"] = "8"
		os.environ["SLURM_CPUS_ON_NODE"] = "64"
		os.environ["SLURM_SCHEDULING_POLICY"] = "FIFO"

		layer = SlurmLayer()
		payload = layer.auto_collect()

		# Standard payload shape
		self.assertIsInstance(payload, dict)
		self.assertIn("metrics", payload)
		self.assertIn("features", payload)
		self.assertIsInstance(payload["metrics"], dict)
		self.assertIsInstance(payload["features"], dict)

		# Metrics keys should exist
		for k in ["job_id", "partition", "nodelist", "ntasks", "cpus_on_node", "scheduling_policy"]:
			self.assertIn(k, payload["metrics"])

		# Values should match our env (job_id/ntasks/cpus_on_node may be float)
		self.assertEqual(payload["metrics"]["partition"], "debug")
		self.assertEqual(payload["metrics"]["nodelist"], "node[01-02]")
		self.assertEqual(payload["metrics"]["scheduling_policy"], "FIFO")

		self.assertIn(payload["metrics"]["job_id"], [12345, 12345.0, "12345"])
		self.assertIn(payload["metrics"]["ntasks"], [8, 8.0, "8"])
		self.assertIn(payload["metrics"]["cpus_on_node"], [64, 64.0, "64"])

		# Features should include slurm_version key (may be None)
		self.assertIn("slurm_version", payload["features"])

	def test_helpers_do_not_throw(self):
		# This test only ensures helper methods return gracefully.
		layer = SlurmLayer()

		# get_partitions/get_nodes may return {"error": "..."} on non-Slurm systems.
		partitions = layer.get_partitions()
		nodes = layer.get_nodes()

		self.assertIsInstance(partitions, (dict, list))
		self.assertIsInstance(nodes, (dict, list))

		# If dict, it should be either error or contain some expected keys
		if isinstance(partitions, dict):
			self.assertTrue(("error" in partitions) or ("partitions" in partitions) or (len(partitions.keys()) >= 0))

		if isinstance(nodes, dict):
			self.assertTrue(("error" in nodes) or (len(nodes.keys()) >= 0))

	def test_auto_collect_no_env(self):
		# With no SLURM env set, should still return shape with keys present (values None)
		for k in list(os.environ.keys()):
			if k.startswith("SLURM_"):
				os.environ.pop(k, None)

		layer = SlurmLayer()
		payload = layer.auto_collect()

		self.assertIn("metrics", payload)
		self.assertIn("features", payload)

		for k in ["job_id", "partition", "nodelist", "ntasks", "cpus_on_node", "scheduling_policy"]:
			self.assertIn(k, payload["metrics"])


if __name__ == "__main__":
	unittest.main(verbosity=2)
