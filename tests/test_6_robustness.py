import threading
import time
import unittest

try:
	import qiskit
	from qiskit import QuantumCircuit
	from qiskit.transpiler import CouplingMap
	HAVE_QISKIT = True
except Exception:
	HAVE_QISKIT = False

from qbacmet import QBacMetCollector, collector


def all_to_all(n):
	qc = QuantumCircuit(n)
	qc.h(0)
	for i in range(n):
		for j in range(i + 1, n):
			qc.cx(i, j)
	qc.measure_all()
	return qc


@unittest.skipUnless(HAVE_QISKIT, "qiskit not installed")
class TestRobustness(unittest.TestCase):
	BASIS = ["cz", "rz", "sx", "x"]

	def test_routing_swaps_are_counted(self):
		with collector.collect():
			qiskit.transpile(all_to_all(6), coupling_map=CouplingMap.from_line(6), basis_gates=self.BASIS,
			                 optimization_level=1, seed_transpiler=1)
		m = collector.metrics["transpile"]["metrics"]
		self.assertGreater(m["hw_circ_swaps"], 0)                      # was always 0 before
		self.assertEqual(m["hw_circ_gate_counts"].get("swap", 0), 0)   # decomposed in the output
		self.assertEqual(m["hw_circ_num_2q_gates"], m["hw_circ_gate_counts"]["cz"])

	def test_pass_manager_path_counts_swaps(self):
		from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
		with collector.collect():
			pm = generate_preset_pass_manager(optimization_level=1, coupling_map=CouplingMap.from_line(6),
			                                  basis_gates=self.BASIS, seed_transpiler=1)
			pm.run(all_to_all(6))
		self.assertGreater(collector.metrics["transpile"]["metrics"]["hw_circ_swaps"], 0)

	def test_user_callback_still_called(self):
		calls = []
		with collector.collect():
			qiskit.transpile(all_to_all(4), coupling_map=CouplingMap.from_line(4), basis_gates=self.BASIS,
			                 callback=lambda **kw: calls.append(1))
		self.assertTrue(calls)

	def test_shots_survive_transpile(self):
		with collector.collect():
			collector.alg_layer.metrics["shots"] = 1024
			qiskit.transpile(all_to_all(3), basis_gates=self.BASIS)
		self.assertEqual(collector.metrics["algorithm"]["metrics"]["shots"], 1024)

	def test_threads_do_not_mix(self):
		barrier = threading.Barrier(4)
		results, errors = {}, []

		def worker(n):
			try:
				c = QBacMetCollector()
				with c.collect():
					barrier.wait()
					for _ in range(5):
						qiskit.transpile(all_to_all(n), basis_gates=self.BASIS, optimization_level=0)
				results[n] = (c.metrics["algorithm"]["metrics"]["width"], c.metrics["transpile"]["metrics"]["hw_circ_width"])
			except Exception as e:
				errors.append(e)

		threads = [threading.Thread(target=worker, args=(n,)) for n in (3, 4, 5, 6)]
		for t in threads:
			t.start()
		for t in threads:
			t.join()
		self.assertFalse(errors)
		for n, (w, hw) in results.items():
			self.assertEqual((w, hw), (n, n))

	def test_hooks_removed_after_last_collection(self):
		orig = qiskit.transpile
		with collector.collect():
			self.assertIsNot(qiskit.transpile, orig)
			with collector.collect():
				pass
			self.assertIsNot(qiskit.transpile, orig)     # outer collection still active
		self.assertIs(qiskit.transpile, orig)

	def test_explicit_api_without_hooks(self):
		orig = qiskit.transpile
		qasm = "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[3];\ncreg c[3];\nh q[0];\ncx q[0],q[1];\ncx q[1],q[2];\nmeasure q -> c;\n"
		c = QBacMetCollector()
		with c.collect(hooks=False):
			self.assertIs(qiskit.transpile, orig)
			c.set_algorithm_from_qasm(qasm, shots=2048)
			c.set_backend_features(backend="nwqsim", sub_backend="MPI", np=4)
		t = time.time()
		c.set_timeline(created=t, resources_ready=t + 1, launched=t + 1.5, started=t + 2, completed=t + 7)
		m = c.finalize()
		self.assertEqual(m["algorithm"]["metrics"]["width"], 3)
		self.assertEqual(m["algorithm"]["metrics"]["shots"], 2048)
		self.assertEqual(m["algorithm"]["metrics"]["num_2q_gates"], 2)
		self.assertEqual(m["backend"]["features"]["np"], 4)
		ex = m["execution"]["metrics"]
		self.assertAlmostEqual(ex["execution_time"], 5.0, places=3)
		self.assertAlmostEqual(ex["time_waiting_for_resources"], 1.0, places=3)
		self.assertAlmostEqual(ex["time_total"], 7.0, places=3)

	def test_finalize_returns_independent_copy(self):
		c = QBacMetCollector()
		with c.collect(hooks=False):
			c.set_backend_features(backend="a")
		snap = c.finalize()
		c.set_backend_features(backend="b")
		self.assertEqual(snap["backend"]["features"]["backend"], "a")

	def test_dynamic_values_read_before_the_run(self):
		import os
		from unittest import mock
		from qbacmet import SlurmLayer
		calls = []
		with mock.patch.dict(os.environ, {"SLURM_JOB_PARTITION": "batch", "QBACMET_RT_TTL": "0"}), \
				mock.patch.object(SlurmLayer, "_run_cmd",
				                  lambda self, cmd, timeout=10: calls.append((cmd, time.time())) or "1/2/3/6"):
			c = QBacMetCollector()
			with c.collect(hooks=False):
				t_run = time.time()
			reads = [t for cmd, t in calls if "-p" in cmd]
		self.assertEqual(len(reads), 1)                    # one reading, taken at the start
		self.assertLessEqual(reads[0], t_run)
		self.assertEqual(c.metrics["slurm"]["metrics"]["rt_partition_nodes_idle"], 2)

	def test_realtime_snapshot_from_target(self):
		try:
			from qiskit.providers.fake_provider import GenericBackendV2
		except Exception as e:
			raise unittest.SkipTest(f"no fake backend: {e}")
		from qbacmet import BackendLayer
		rt = BackendLayer().realtime_snapshot(GenericBackendV2(num_qubits=5, seed=1))
		self.assertIn("rt_fetched_at", rt)
		self.assertEqual(rt["rt_num_qubits"], 5)
		self.assertIsNotNone(rt["rt_median_2q_error"])


if __name__ == "__main__":
	unittest.main(verbosity=2)
