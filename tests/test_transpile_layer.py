import unittest
from qbacmetc.transpile_layer import TranspileLayer

class DummyTranspileObj:
    def __init__(self):
        self.error_mitigation_level = 2
        self.optimization_level = 3

class DummyHwCirc:
    def __init__(self):
        self.width = 5
        self.depth = 10
        self.connectivity_degree = 2
        self.connected_components = 1
        self.swaps = 4

class TestTranspileLayer(unittest.TestCase):
    def test_transpilation_metrics(self):
        obj = DummyTranspileObj()
        layer = TranspileLayer()
        layer.collect_transpilation_metrics(obj)
        metrics = layer.get_metrics()
        self.assertEqual(metrics['error_mitigation_level'], 2)
        self.assertEqual(metrics['optimization_level'], 3)

    def test_post_transpilation_metrics(self):
        hw_circ = DummyHwCirc()
        layer = TranspileLayer()
        layer.collect_post_transpilation_metrics(hw_circ)
        metrics = layer.get_metrics()
        self.assertEqual(metrics['hw_circ_width'], 5)
        self.assertEqual(metrics['hw_circ_depth'], 10)
        self.assertEqual(metrics['hw_circ_connectivity_degree'], 2)
        self.assertEqual(metrics['hw_circ_connected_components'], 1)
        self.assertEqual(metrics['hw_circ_swaps'], 4)

if __name__ == "__main__":
    unittest.main()
