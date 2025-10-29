#!/usr/bin/env python3

"""
bench_meta_gen.py — Generate and save metadata of quantum circuit benchmarks to CSV.

Usage:
	python bench_meta_gen.py <start_qubit> <end_qubit> [--out-csv OUTPUT_CSV]

Description:
	- Generates metadata for standard quantum circuit benchmarks (ghz, ham, mermin_bell, tfim, hhl).
	- For each benchmark and qubit count in the specified range, extracts circuit properties.
	- Saves the metadata to a CSV file (default: benchmarks_metadata.csv).

Arguments:
	start_qubit   Start of qubit range (inclusive)
	end_qubit     End of qubit range (inclusive)

Options:
	--out-csv     Output CSV filename (default: benchmarks_metadata.csv)
"""

import os
import sys
import csv
import argparse
from statistics import pstdev
from typing import Dict, Tuple

from qiskit import QuantumCircuit
from qiskit.converters import circuit_to_dag

# === Circuit Metadata Extraction Utilities ===

def extract_circuit_metadata(qc: QuantumCircuit):
	"""Extract various metadata from a Qiskit circuit, including gate arity counts."""

	depth = qc.depth()
	width = qc.num_qubits
	n_clbits = qc.num_clbits
	n_ops = qc.size()
	dag = circuit_to_dag(qc)

	n_gates = sum(1 for ci in qc.data if ci.operation.name != "barrier")
	gate_counts = qc.count_ops()
	n_parameters = qc.num_parameters
	measure_ops = gate_counts.get("measure", 0)

	# Count single/2/3/4-qubit gates
	single_qubit_gates = 0
	two_qubit_gates = 0
	three_qubit_gates = 0
	four_qubit_gates = 0
	for ci in qc.data:
		inst = ci.operation
		qargs = ci.qubits
		if inst.name == "barrier":
			continue
		n_q = len(qargs)
		if n_q == 1:
			single_qubit_gates += 1
		elif n_q == 2:
			two_qubit_gates += 1
		elif n_q == 3:
			three_qubit_gates += 1
		elif n_q == 4:
			four_qubit_gates += 1

	def _twoq_pairs(d):
		p = set()
		for n in d.two_qubit_ops():
			qs = [q._index for q in n.qargs]
			if len(qs) == 2:
				a, b = sorted(qs)
				p.add((a, b))
		return p

	def _touch_counts(d):
		nq = d.num_qubits()
		tc = [0] * nq
		for n in d.op_nodes():
			for q in n.qargs:
				tc[q._index] += 1
		return tc

	def _clifford_noncliff(gcounts: Dict[str, int]) -> Tuple[int, int]:
		cliff = 0
		cliff_set = {"id","x","y","z","h","s","sdg","cx","cz","swap","sx","sxdg","ecr","dcx"}
		for g, c in gcounts.items():
			if g in cliff_set:
				cliff += c
		total = sum(gcounts.values())
		return cliff, total - cliff

	def _params_per_gate_stats(qc_: QuantumCircuit) -> Tuple[int, float, float, int, int]:
		per_gate = [len(ci.operation.params) for ci in qc_.data if ci.operation.name != "barrier"]
		if not per_gate:
			return 0, 0.0, 0.0, 0, 0
		total = sum(per_gate)
		return total, total/len(per_gate), pstdev(per_gate) if len(per_gate) > 1 else 0.0, min(per_gate), max(per_gate)

	num_controlled_gates = sum(
		1
		for ci in qc.data
		if ci.operation.name != "barrier"
		and (getattr(ci.operation, "num_ctrl_qubits", 0) > 0 or ci.operation.name.startswith("c"))
	)

	dag_size_ops = dag.size()
	dag_edge_count = len(list(dag.edges()))
	longest_path_len = len(dag.longest_path()) if hasattr(dag, "longest_path") else None
	idle_wires = len(list(dag.idle_wires()))
	if dag.control_flow_op_nodes() is not None:
		num_control_flow_ops = len(list(dag.control_flow_op_nodes()))
	else:
		num_control_flow_ops = None
	num_barriers = sum(1 for ci in qc.data if ci.operation.name == "barrier")
	twoq_pairs = _twoq_pairs(dag)
	num_distinct_twoq_pairs = len(twoq_pairs)
	touch_counts = _touch_counts(dag)
	touch_min = min(touch_counts) if touch_counts else 0
	touch_max = max(touch_counts) if touch_counts else 0
	touch_avg = (sum(touch_counts)/len(touch_counts)) if touch_counts else 0.0
	global_phase = float(qc.global_phase) if getattr(qc, "global_phase", None) is not None else 0.0
	num_registers = len(qc.qregs)
	num_cregs = len(qc.cregs)
	num_ancillas = qc.num_ancillas
	qc_width_total = qc.width()  # n_qubits + n_clbits

	total_gate_params, avg_gate_params, std_gate_params, min_gate_params, max_gate_params = _params_per_gate_stats(qc)
	num_unitary_factors = qc.num_unitary_factors()
	dag_duration = getattr(dag, "duration", None)
	dag_duration = dag_duration() if callable(dag_duration) else dag_duration
	qc_duration = getattr(qc, "duration", None)

	n_connected_components = getattr(qc, "num_connected_components", None)
	if callable(n_connected_components):
		n_connected_components = n_connected_components()
	elif n_connected_components is None:
		n_connected_components = dag.num_tensor_factors()

	clifford_count, nonclifford_count = _clifford_noncliff(gate_counts)
	measure_fraction = (measure_ops / qc.num_qubits) if qc.num_qubits else 0.0

	return {
		"depth": depth,
		"width": width,
		"n_qubits": qc.num_qubits,
		"n_clbits": n_clbits,
		"n_ops": n_ops,
		"n_gates": n_gates,
		"gate_counts": dict(gate_counts),
		"n_parameters": n_parameters,
		"n_measure_ops": measure_ops,
		"single_qubit_gates": single_qubit_gates,
		"two_qubit_gates": two_qubit_gates,
		"three_qubit_gates": three_qubit_gates,
		"four_qubit_gates": four_qubit_gates,
		# from dag
		"num_separable_circuits": len(dag.separable_circuits()) if dag else None,
		"num_tensor_factors": dag.num_tensor_factors() if dag else None,
		"num_serial_layers": len(list(dag.serial_layers())) if dag else None,
		# from qc
		"n_connected_components": n_connected_components,
		"qc_width_total": qc_width_total,
		"num_registers": num_registers,
		"num_cregs": num_cregs,
		"num_ancillas": num_ancillas,
		"idle_wires": idle_wires,
		"global_phase": global_phase,
		"dag_size_ops": dag_size_ops,
		"dag_edge_count": dag_edge_count,
		"longest_path_len": longest_path_len,
		"num_control_flow_ops": num_control_flow_ops,
		"num_barriers": num_barriers,
		"num_distinct_twoq_pairs": num_distinct_twoq_pairs,
		"touch_min": touch_min,
		"touch_max": touch_max,
		"touch_avg": touch_avg,
		"clifford_count": clifford_count,
		"nonclifford_count": nonclifford_count,
		"measure_fraction": measure_fraction,
		"total_gate_params": total_gate_params,
		"avg_gate_params": avg_gate_params,
		"std_gate_params": std_gate_params,
		"min_gate_params": min_gate_params,
		"max_gate_params": max_gate_params,
		"num_controlled_gates": num_controlled_gates,
		"num_unitary_factors": num_unitary_factors,
		"dag_duration": dag_duration,
		"qc_duration": qc_duration,
	}

# --- Supermarq (ghz, ham, mermin_bell) ---
def supermarq_metadata(benchmark: str, n_qubits: int):
	import supermarq as sm
	def get_qc(benchmark, n_qubits):
		if benchmark == "ghz":
			ghz = sm.benchmarks.ghz.GHZ(num_qubits=n_qubits)
			return ghz.qiskit_circuit()
		elif benchmark == "ham":
			ham = sm.benchmarks.hamiltonian_simulation.HamiltonianSimulation(num_qubits=n_qubits)
			return ham.qiskit_circuit()
		elif benchmark == "mermin_bell":
			mermin_bell = sm.benchmarks.mermin_bell.MerminBell(num_qubits=n_qubits)
			return mermin_bell.qiskit_circuit()
		elif benchmark == "bit_code":
			bit_code = sm.benchmarks.bit_code.BitCode(num_data_qubits=n_qubits, num_rounds=1, bit_state=[0]*n_qubits)
			return bit_code.qiskit_circuit()
		elif benchmark == "phase_code":
			phase_code = sm.benchmarks.phase_code.PhaseCode(num_data_qubits=n_qubits, num_rounds=1, phase_state=[0]*n_qubits)
			return phase_code.qiskit_circuit()
		elif benchmark == "qaoa_fermionic_swap_proxy":
			qaoa_fermionic_swap_proxy = sm.benchmarks.qaoa_fermionic_swap_proxy.QAOAFermionicSwapProxy(num_qubits=n_qubits)
			return qaoa_fermionic_swap_proxy.qiskit_circuit()
		elif benchmark == "qaoa_vanilla_proxy":
			qaoa_vanilla_proxy = sm.benchmarks.qaoa_vanilla_proxy.QAOAVanillaProxy(num_qubits=n_qubits)
			return qaoa_vanilla_proxy.qiskit_circuit()
		elif benchmark == "vqe_proxy":
			vqe_proxy = sm.benchmarks.vqe_proxy.VQEProxy(num_qubits=n_qubits)
			return vqe_proxy.qiskit_circuit()
		else:
			raise Exception("Invalid benchmark name")
	qc = get_qc(benchmark, n_qubits)
	meta = extract_circuit_metadata(qc)
	meta.update({"benchmark": benchmark, "n_qubits": n_qubits})
	return meta

# --- TFIM ---
def tfim_metadata(n_qubits: int, J=1.0, B=0.5, dt=0.01):
	# Inline TFIM circuit construction to avoid import issues
	qc = QuantumCircuit(n_qubits, n_qubits)
	for qubit in range(n_qubits):
		qc.rx(-2 * dt * B, qubit)
	for qubit in range(n_qubits - 1):
		qc.cx(qubit, qubit + 1)
		qc.rz(-2 * dt * J, qubit + 1)
		qc.cx(qubit, qubit + 1)
	if n_qubits > 2:
		qc.cx(n_qubits - 1, 0)
		qc.rz(-2 * dt * J, 0)
		qc.cx(n_qubits - 1, 0)
	qc.measure(range(n_qubits), range(n_qubits))
	meta = extract_circuit_metadata(qc)
	meta.update({"benchmark": "tfim", "n_qubits": n_qubits, "J": J, "B": B, "dt": dt})
	return meta

# --- HHL ---
def hhl_metadata(qasm_file_path: str):
	qc = QuantumCircuit.from_qasm_file(qasm_file_path)
	meta = extract_circuit_metadata(qc)
	meta.update({
		"benchmark": "hhl",
		"qasm_file": qasm_file_path,
		"n_qubits": qc.num_qubits,
	})
	return meta

# --- Batch metadata generation and CSV saving ---
def save_benchmarks_metadata(meta_rows, out_csv):
	if not meta_rows:
		print("[warn] No metadata rows to save.")
		return
	# Flatten gate_counts for CSV
	all_gate_types = set()
	for row in meta_rows:
		all_gate_types.update(row.get("gate_counts", {}).keys())
	gate_cols = sorted(all_gate_types)
	base_cols = [
		"benchmark", "n_qubits", "depth", "width", "n_clbits", "n_ops", "n_gates", "n_parameters", "n_connected_components", "n_measure_ops",
		"single_qubit_gates", "two_qubit_gates", "three_qubit_gates", "four_qubit_gates",
		"num_separable_circuits", "num_tensor_factors", "num_serial_layers",
		# additions
		"qc_width_total","num_registers","num_cregs","num_ancillas","idle_wires","global_phase",
		"dag_size_ops","dag_edge_count",
		"longest_path_len",
		"num_control_flow_ops","num_barriers","num_distinct_twoq_pairs","touch_min","touch_max","touch_avg",
		"clifford_count","nonclifford_count","measure_fraction",
		"total_gate_params","avg_gate_params","std_gate_params","min_gate_params","max_gate_params",
		"num_controlled_gates","num_unitary_factors","dag_duration","qc_duration",
	]
	cols = base_cols + [f"gate_{g}" for g in gate_cols]
	with open(out_csv, "w", newline="") as f:
		w = csv.DictWriter(f, fieldnames=cols)
		w.writeheader()
		for row in meta_rows:
			flat = {k: row.get(k, None) for k in base_cols}
			for g in gate_cols:
				flat[f"gate_{g}"] = row.get("gate_counts", {}).get(g, 0)
			w.writerow(flat)
	print(f"[ok] saved benchmark metadata CSV: {out_csv} (rows={len(meta_rows)})")

def parse_args():
	parser = argparse.ArgumentParser(
		description="Generate and save quantum circuit benchmark metadata to CSV.\n"
					"Usage: python bench_meta_gen.py <start_qubit> <end_qubit>"
	)
	parser.add_argument("start_qubit", type=int, help="Start of qubit range (inclusive)")
	parser.add_argument("end_qubit", type=int, help="End of qubit range (inclusive)")
	parser.add_argument("--out-csv", default="benchmarks_metadata.csv", help="Output CSV filename (default: benchmarks_metadata.csv)")
	return parser.parse_args()

def main():
	args = parse_args()
	if args.start_qubit < 1 or args.end_qubit < args.start_qubit:
		print("[error] Invalid qubit range. start_qubit must be >= 1 and end_qubit >= start_qubit.")
		sys.exit(1)
	qubit_range = range(args.start_qubit, args.end_qubit + 1)

	meta_rows = []
	# GHZ, HAM, Mermin Bell
	for bench in ["ghz", "ham", "mermin_bell"]:
		for nq in qubit_range:
			try:
				meta = supermarq_metadata(bench, nq)
				meta_rows.append(meta)
			except Exception as e:
				print(f"[err] {bench} n={nq}: {e}")
				raise e
	# TFIM
	for nq in qubit_range:
		try:
			meta = tfim_metadata(nq)
			meta_rows.append(meta)
		except Exception as e:
			print(f"[err] tfim n={nq}: {e}")
			raise e
	# HHL
	hhl_qasm_map = {
		5: "./hhl/HHL_QASM/sample_HHL_circ_nqmatrix1.qasm",
		7: "./hhl/HHL_QASM/sample_HHL_circ_nqmatrix2.qasm",
		9: "./hhl/HHL_QASM/sample_HHL_circ_nqmatrix3.qasm",
		11: "./hhl/HHL_QASM/sample_HHL_circ_nqmatrix4.qasm",
		13: "./hhl/HHL_QASM/sample_HHL_circ_nqmatrix5.qasm",
		15: "./hhl/HHL_QASM/sample_HHL_circ_nqmatrix6.qasm",
		17: "./hhl/HHL_QASM/sample_HHL_circ_nqmatrix7.qasm",
		19: "./hhl/HHL_QASM/sample_HHL_circ_nqmatrix8.qasm",
		21: "./hhl/HHL_QASM/sample_HHL_circ_nqmatrix9.qasm",
		23: "./hhl/HHL_QASM/sample_HHL_circ_nqmatrix10.qasm",
		25: "./hhl/HHL_QASM/sample_HHL_circ_nqmatrix11.qasm",
	}
	for nq in qubit_range:
		qasm_path = hhl_qasm_map.get(nq)
		if qasm_path and os.path.exists(qasm_path):
			try:
				meta = hhl_metadata(qasm_path)
				meta_rows.append(meta)
			except Exception as e:
				print(f"[err] hhl n={nq}: {e}")
				raise e
		elif qasm_path:
			print(f"[warn] hhl n={nq}: qasm file not found: {qasm_path}")

	save_benchmarks_metadata(meta_rows, args.out_csv)

if __name__ == "__main__":
	main()
