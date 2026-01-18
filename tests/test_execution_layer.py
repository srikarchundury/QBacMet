import unittest
from qbacmetc.execution_layer import ExecutionLayer

class TestExecutionLayer(unittest.TestCase):
    def test_queue_time(self):
        layer = ExecutionLayer()
        queue_info = {'queue_time': 12.5}
        layer.collect_queue_time(queue_info)
        self.assertEqual(layer.metrics['queue_time'], 12.5)

    def test_execution_time(self):
        layer = ExecutionLayer()
        exec_info = {'execution_time': 8.2}
        layer.collect_execution_time(exec_info)
        self.assertEqual(layer.metrics['execution_time'], 8.2)

if __name__ == "__main__":
    unittest.main()
