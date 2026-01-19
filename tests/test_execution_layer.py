import unittest
from qbacmetc.execution_layer import ExecutionLayer

class TestExecutionLayer(unittest.TestCase):
	def test_queue_time(self):
		layer = ExecutionLayer()
		layer.set_queue_time(12.5)
		self.assertEqual(layer.metrics["queue_time"], 12.5)

	def test_execution_time(self):
		layer = ExecutionLayer()
		layer.set_execution_time(8.2)
		self.assertEqual(layer.metrics["execution_time"], 8.2)

if __name__ == "__main__":
	unittest.main(verbosity=2)
