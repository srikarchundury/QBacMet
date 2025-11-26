# This file is abstract base class for layers in QBacMetC

from time import perf_counter

class Layer():
	def __init__(self):
		self.start_time = None
		self.end_time = None
		self.tt = None

	def mark_start(self):
		self.tt = perf_counter()

	def mark_end(self):
		self.end_time = perf_counter()
		self.tt = self.end_time - self.start_time
	
	