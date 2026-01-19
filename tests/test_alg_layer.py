from qbacmetc.alg_layer import AlgLayer

# Qiskit test
try:
	from qiskit import QuantumCircuit
	qc = QuantumCircuit(3)
	qc.h(0)
	qc.cx(0, 1)
	qc.cx(1, 2)
	qc.measure_all()

	print("Qiskit circuit metrics:")
	print(AlgLayer().get_metrics(qc, shots=1024))
except ImportError:
	print("Qiskit not installed.")

# PennyLane test
try:
	import pennylane as qml
	import numpy as np

	dev = qml.device("default.qubit", wires=2)

	@qml.qnode(dev)
	def circuit(x):
		qml.Hadamard(wires=0)
		qml.CNOT(wires=[0, 1])
		qml.RX(x, wires=1)
		return qml.expval(qml.PauliZ(0))

	# Execute once so tape exists
	try:
		circuit(0.5)
	except Exception:
		circuit(np.array([0.5]))

	print("PennyLane circuit metrics (from QNode tape):")
	print(AlgLayer().get_metrics(circuit))

	# Variational PennyLane test
	opt = qml.GradientDescentOptimizer(stepsize=0.1)
	max_iter = 20
	reps = 3
	print("PennyLane variational metrics:")
	print(AlgLayer().get_variational_metrics(optimizer=type(opt).__name__, iterations=max_iter, repetitions=reps))
except ImportError:
	print("PennyLane not installed.")

# Variational metrics test
print("Variational metrics:")
print(AlgLayer().get_variational_metrics(optimizer="Adam", iterations=100, repetitions=5))
