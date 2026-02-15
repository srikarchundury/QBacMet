import unittest
from qbacmet import PostprocessLayer


class TestPostprocessLayer(unittest.TestCase):
	def test_mitigation_overhead(self):
		layer = PostprocessLayer()
		mitigation_info = {"mitigation_overhead": 3.5}
		layer.collect_mitigation_overhead(mitigation_info)
		self.assertEqual(layer.metrics["mitigation_overhead"], 3.5)

	def test_qec_syndrome_time(self):
		layer = PostprocessLayer()
		qec_info = {"qec_syndrome_time": 1.2}
		layer.collect_qec_syndrome_time(qec_info)
		self.assertEqual(layer.metrics["qec_syndrome_time"], 1.2)

	def test_result_marshalling_time(self):
		layer = PostprocessLayer()
		marshal_info = {"result_marshalling_time": 0.8}
		layer.collect_result_marshalling_time(marshal_info)
		self.assertEqual(layer.metrics["result_marshalling_time"], 0.8)

	def test_auto_collect_fallback(self):
		# Define local dicts that frame scan can find
		mit = {"mitigation_overhead": 7.1}
		qec = {"qec_syndrome_time": 2.4}
		res = {"result_marshalling_time": 0.55}

		layer = PostprocessLayer()
		payload = layer.auto_collect()

		m = payload["metrics"]

		self.assertEqual(m["mitigation_overhead"], 7.1)
		self.assertEqual(m["qec_syndrome_time"], 2.4)
		self.assertEqual(m["result_marshalling_time"], 0.55)


if __name__ == "__main__":
	unittest.main(verbosity=2)
