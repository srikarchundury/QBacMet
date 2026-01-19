# This file is abstract base class for layers in QBacMetC

from time import perf_counter


class Layer:
	def __init__(self):
		self.start_time = None
		self.end_time = None
		self.tt = None
		self.metrics = {}
		self.features = {}

	def mark_start(self):
		self.start_time = perf_counter()
		self.end_time = None
		self.tt = None

	def mark_end(self):
		self.end_time = perf_counter()
		if self.start_time is not None:
			self.tt = self.end_time - self.start_time
		return self.tt

	def reset(self):
		self.metrics = {}
		self.features = {}
		self.start_time = None
		self.end_time = None
		self.tt = None

	def get_payload(self):
		# Standardized shape across all layers
		return {
			"metrics": self.metrics if isinstance(self.metrics, dict) else {},
			"features": self.features if isinstance(self.features, dict) else {}
		}
