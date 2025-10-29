### Quantum Backend Metric Collector (QBacMet)

QBacMet is a vendor-agnostic metrics/feature "tap" that can be attached
to any quantum job sim/hardware without having to rewrite experiments.

We define a "feature" as a configurable thing such as backend, sub backend details, max bond dim for TN simulation; things of that nature.
We define a "metric" as something the problem/algorithm tells me. Like circuit depth/width etc.

To understand this better, we'll first name them hierarchically and decide when they'd be assigned a value i.e. is it during a execution run, or are they things that are not linked an actual run.
Please note that some features are run dependent, for instance the optimization level could decide hw features? (some more thought is needed in this). 

Our tool makes it easy to collect both metrics and features of various components in a Q-HPC workflow.

#### Layers in a Q-HPC Workflow

---

<u>### Layer-0 (SLURM-HPC Metrics/Features)</u>
This layer is the highest level of abstraction which revolves around how Q-HPC workflows look like abstractly, and where does the end user interface with.
User/Client writes a program in qiskit/pennylane/cuda-q etc that has the ability to interact with multi CPU/GPU/QPU alike.
How do they have the ability? via QFw, Qiskit's C API, Munich Quantum Stack?, NVQLink (the new Q-HPC interconnect, released in this Nvidia GTC).

1. scheduling policy used? (so unknown!)  
2. all of SLURM metrics. (what are these?)  
3. run-meta info i.e. backend name, version.  
4. cost?  

---

<u>### Layer-1 (Algorithm Metrics)</u>
This layer answers "what are we executing?". This more about the algorithm and not hardware specific circuits.

Two kinds: Variational & non-Variational workloads.

**Circuit Metrics/Features:**
4. width  
5. depth  
6. #2q gates (does this really matter at the algo level? because anyway they'd change post-transpilation?)  
7. #cliffords  
8. #non-cliffords  
9. critical path length (diameter)  
10. #shots required (minimum to establish the answer properly!)  
11. #connected components  

**Variational workloads:**
12. Classical optimizer used  
13. #iterations  
14. #repetitions  
15. time taken by classical optimizer overall  

---

<u>### Layer-2 (Backend specific Metrics/Features)</u>
Everything between algorithm and actually running it on either an HPC simulator or actual QPU. So, we split this into sub types.

#### 2.1 Transpilation Features
16. Quantify Error Mitigation optimization levels in a way that's agnostic to hardware type. (IBM-Q's opt level vs. Ion-Q's levels vs. Quantinuum's levels etc.)

#### 2.2 Post-Transpilation Metrics
17. hw circ width  
18. hw circ depth  
19. hw circ connectivity degree (in the active area, for instance in IBM-Q)  
20. hw circ #connected components  
21. hc circ "SWAPS"  

---

<u>### Layer-3 (Backend Features)</u>
Broadly, two kinds of backends:

#### 3.1 Simulator Features

22. SV?  
23. TN?  
24. if TN, max-bond-dim  
25. CPU based?  
26. GPU based?  
27. #nodes  
28. #cores_per_node  
29. Precision (#bits per complex/real or complex/imag)  

#### 3.2 H/W Features

30. Cycle Layer Ops Per Second (CLOPS)  
31. quantum volume  
32. T1 time (relaxation)  
33. T2 time (dephasing)  
34. 1q gate error  
35. 2q gate error  
36. readout error  
37. calibration frequency - every day, every hour? (crontab schedule)  
38. calibration age - time since calibrated  

---

<u>### Layer-4 (Execution Metrics)</u>
This layer is basically that runs the circuit, so runtime is the primary metric here!
But if backend is not local and not readily available and reserved for this particular job. In that case, we'd have another queue apart from the HPC queue we accounted for in Layer-0.

39. queue time  
40. execution time  

---

<u>### Layer-5 (Post-Processing Features/Metrics)</u>
This layer deals with things after:

41. Mitigation overhead? time taken  
42. Quantum Error Correction syndrome extraction time?  
43. Result marshalling time based on what the frontend needs.
