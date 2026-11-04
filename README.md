# QBacMet

QBacMet (Quantum Backend Metric Collector) is a vendor-agnostic metrics/feature "tap" that can be attached to any quantum job (simulator or hardware) without having to rewrite experiments. It is one half of **SeleQtor**, feeding the metrics and features that [MQBac](https://github.com/srikarchundury/MQBac) uses for backend selection and runtime estimation.

[![IEEE QCE 2026](https://img.shields.io/badge/IEEE%20QCE%20'26-SeleQtor-lightgrey.svg)]()
*(paper link will appear at IEEE Xplore once published)*

[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](LICENSE)

## Concepts

We define a **feature** as a configurable or descriptive property such as backend identity,
simulation method, max bond dimension for tensor networks, etc.
We define a **metric** as a quantitative value produced by the algorithm or execution,
such as circuit depth, runtime, or gate counts.

To structure this, we name metrics/features hierarchically and distinguish **when**
they are assigned a value (e.g., pre-run, during execution, or post-run).
Some features are run-dependent (for example, optimization level or backend options),
so strict separation is not always possible.

QBacMet makes it easy to collect both metrics and features across the layers of a Q-HPC workflow.

## Layers in a Q-HPC Workflow

---

### Layer-0 (SLURM / HPC Metrics & Features)
This layer captures information from the HPC scheduling and execution environment.
It reflects how Q-HPC workflows are launched and managed on systems such as Frontier.

User code may be written in qiskit / pennylane / cuda-q, etc., and executed via
frameworks such as QFw or native runtime layers.

&emsp; &emsp; 1. SLURM job metadata (job id, partition, nodelist, ntasks, CPUs per node)  
&emsp; &emsp; 2. Scheduling policy (if available)  
&emsp; &emsp; 3. SLURM version (best effort)  
&emsp; &emsp; 4. Run-level environment hints (e.g., job context)  

---

### Layer-1 (Algorithm Metrics)
This layer answers **"what are we executing?"** independent of hardware.
Metrics are extracted directly from the algorithm representation.

Two kinds of workloads are supported: **non-variational** and **variational**.

#### 1.1 Circuit (Qiskit / PennyLane)

&emsp; &emsp; 5. circuit width (# logical qubits / wires)  
&emsp; &emsp; 6. circuit depth  
&emsp; &emsp; 7. # two-qubit gates (logical, pre-transpilation)  
&emsp; &emsp; 8. # Clifford gates (heuristic)  
&emsp; &emsp; 9. # non-Clifford gates (heuristic)  
&emsp; &emsp; 10. critical path length  
&emsp; &emsp; 11. # shots (if specified)  
&emsp; &emsp; 12. # connected components (interaction graph)  

#### 1.2 Variational (optional)

&emsp; &emsp; 13. classical optimizer used  
&emsp; &emsp; 14. # optimizer iterations  
&emsp; &emsp; 15. # repetitions  
&emsp; &emsp; 16. classical optimizer time (if provided)  

---

### Layer-2 (Transpilation Metrics & Features)
This layer bridges the algorithm and the backend.
It captures both **transpilation knobs** and **post-transpilation circuit structure**.

#### 2.1 Transpilation Features

&emsp; &emsp; 17. optimization / error-mitigation knobs (vendor-agnostic capture)  

#### 2.2 Post-Transpilation Metrics

&emsp; &emsp; 18. hardware circuit width  
&emsp; &emsp; 19. hardware circuit depth  
&emsp; &emsp; 20. hardware circuit connectivity degree (max / avg, from interaction graph)  
&emsp; &emsp; 21. hardware circuit # connected components  
&emsp; &emsp; 22. hardware circuit SWAP count  
&emsp; &emsp; 23. hardware circuit # two-qubit gates  

---

### Layer-3 (Backend Features)
This layer describes the backend itself.
Features may be inferred automatically (best effort) or set explicitly.

#### 3.1 Simulator Features

&emsp; &emsp; 24. simulator vs hardware backend  
&emsp; &emsp; 25. simulation method (SV / density-matrix / TN, if available)  
&emsp; &emsp; 26. max bond dimension (for TN simulators, if applicable)  
&emsp; &emsp; 27. CPU / GPU execution (if detectable)  
&emsp; &emsp; 28. precision (if exposed by backend)  

#### 3.2 Hardware Features (best effort)

&emsp; &emsp; 29. CLOPS / throughput indicators (if available)  
&emsp; &emsp; 30. quantum volume  
&emsp; &emsp; 31. T1 time  
&emsp; &emsp; 32. T2 time  
&emsp; &emsp; 33. 1-qubit gate error  
&emsp; &emsp; 34. 2-qubit gate error  
&emsp; &emsp; 35. readout error  
&emsp; &emsp; 36. calibration age / last update (if accessible)  

---

### Layer-4 (Execution Metrics)
This layer captures **runtime behavior** of the job.

&emsp; &emsp; 37. queue time (if known)  
&emsp; &emsp; 38. execution time  
&emsp; &emsp; 39. MPI rank / world size  
&emsp; &emsp; 40. OpenMP thread count  
&emsp; &emsp; 41. job-level host / node context (best effort)  

---

### Layer-5 (Post-Processing Metrics)
This layer captures costs incurred **after execution**.

&emsp; &emsp; 42. mitigation overhead time  
&emsp; &emsp; 43. QEC syndrome extraction time (if applicable)  
&emsp; &emsp; 44. result marshalling / formatting time  

---

## Usage

```python
from qbacmet import collector

with collector.collect():          # every collect() starts a fresh collection; safe in threads
    tqc = transpile(qc, backend)   # hooked: Layers 1-3, SWAPs inserted by routing
    backend.run(tqc, shots=1024)   # hooked: execution time, shots
metrics = collector.metrics        # this thread's last collection
```

For runs the hooks cannot see (a separate executable, as for QFw's local simulators), set the layers
explicitly and finalize when the run ends:

```python
from qbacmet import QBacMetCollector
c = QBacMetCollector()
with c.collect(hooks=False):
    c.set_algorithm_from_qasm(qasm, shots=1024)
    c.set_backend_features(backend="nwqsim", sub_backend="MPI", np=4)
c.set_timeline(created=t0, resources_ready=t1, launched=t2, started=t3, completed=t4)
metrics = c.finalize()             # JSON-safe copy
```

Values that change between submissions (queue length, calibration, partition load) are read fresh at the end
of every collection, carry `rt_fetched_at`, and are recorded as `rt_error` when a read fails.

Tests: `python -m unittest discover -s tests` (run in the QFw environment, qfwVirtEnv).

## Installation

```bash
git clone https://github.com/srikarchundury/QBacMet.git
cd QBacMet
pip install -e .
```

## Related Tools

- [MQBac](https://github.com/srikarchundury/MQBac) — consumes the metrics/features collected by QBacMet to auto-select a QPM backend and estimate circuit runtime.

## Citation

If you use QBacMet in your research, please cite:

```bibtex
@inproceedings{chundury2026seleqtor,
    author = {Chundury, Srikar and Kim, Seongmin and Gopalakrishnan Meena, Muralikrishnan and Lu, Chao and Suh, In-Saeng and Mueller, Frank},
    title = {SeleQtor: Intelligent Quantum Backend Selection and Runtime Estimation},
    year = {2026},
    booktitle = {IEEE International Conference on Quantum Computing and Engineering (QCE '26)},
    note = {To appear}
}
```

## License

QBacMet is licensed under the [BSD 3-Clause License](LICENSE).
