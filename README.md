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

### Layer-0 (SLURM-HPC Metrics/Features)
This layer is the highest level of abstraction which revolves around how Q-HPC workflows look like abstractly, and where does the end user interface with.
User/Client writes a program in qiskit/pennylane/cuda-q etc that has the ability to interact with multi CPU/GPU/QPU alike.
How do they have the ability? via QFw, Qiskit's C API, Munich Quantum Stack?, NVQLink (the new Q-HPC interconnect, released in this Nvidia GTC).

&emsp; 1. scheduling policy used? (so unknown!)  
&emsp; 2. all of SLURM metrics. (what are these?)  
&emsp; 3. run-meta info i.e. backend name, version.  
&emsp; 4. cost?

---

### Layer-1 (Algorithm Metrics)
This layer answers "what are we executing?". This more about the algorithm and not hardware specific circuits.

Two kinds: Variational & non-Variational workloads.

#### 1.1 Circuit

&emsp; 4. width  
&emsp; 5. depth  
&emsp; 6. #2q gates (does this really matter at the algo level? because anyway they'd change post-transpilation?)  
&emsp; 7. #cliffords  
&emsp; 8. #non-cliffords  
&emsp; 9. critical path length (diameter)  
&emsp; 10. #shots required (minimum to establish the answer properly!)  
&emsp; 11. #connected components  

#### 1.2 Variational

&emsp; 12. Classical optimizer used  
&emsp; 13. #iterations  
&emsp; 14. #repetitions  
&emsp; 15. time taken by classical optimizer overall  

---

### Layer-2 (Backend specific Metrics/Features)
Everything between algorithm and actually running it on either an HPC simulator or actual QPU. So, we split this into sub types.

#### 2.1 Transpilation Features

&emsp; 16. Quantify Error Mitigation optimization levels in a way that's agnostic to hardware type. (IBM-Q's opt level vs. Ion-Q's levels vs. Quantinuum's levels etc.)

#### 2.2 Post-Transpilation Metrics

&emsp; 17. hw circ width
&emsp; 18. hw circ depth
&emsp; 19. hw circ connectivity degree (in the active area, for instance in IBM-Q)  
&emsp; 20. hw circ #connected components
&emsp; 21. hc circ "SWAPS"  

---

### Layer-3 (Backend Features)
Broadly, two kinds of backends:

#### 3.1 Simulator Features

&emsp; 22. SV?
&emsp; 23. TN?
&emsp; 24. if TN, max-bond-dim  
&emsp; 25. CPU based?  
&emsp; 26. GPU based?  
&emsp; 27. #nodes  
&emsp; 28. #cores_per_node  
&emsp; 29. Precision (#bits per complex/real or complex/imag)  

#### 3.2 H/W Features

&emsp; 30. Cycle Layer Ops Per Second (CLOPS)  
&emsp; 31. quantum volume  
&emsp; 32. T1 time (relaxation)  
&emsp; 33. T2 time (dephasing)  
&emsp; 34. 1q gate error  
&emsp; 35. 2q gate error  
&emsp; 36. readout error  
&emsp; 37. calibration frequency - every day, every hour? (crontab schedule)  
&emsp; 38. calibration age - time since calibrated  

---

### Layer-4 (Execution Metrics)
This layer is basically that runs the circuit, so runtime is the primary metric here!
But if backend is not local and not readily available and reserved for this particular job.
In that case, we'd have another queue apart from the HPC queue we accounted for in Layer-0.

&emsp; 39. queue time  
&emsp; 40. execution time  

---

### Layer-5 (Post-Processing Features/Metrics)
This layer deals with things after:

&emsp; 41. Mitigation overhead? time taken  
&emsp; 42. Quantum Error Correction syndrome extraction time?  
&emsp; 43. Result marshalling time based on what the frontend needs.
