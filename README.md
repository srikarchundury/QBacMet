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

&emsp; &emsp; 1. scheduling policy used? (so unknown!)  
&emsp; &emsp; 2. all of SLURM metrics. (what are these?)  
&emsp; &emsp; 3. run-meta info i.e. backend name, version.  
&emsp; &emsp; 4. cost?

---

### Layer-1 (Algorithm Metrics)
This layer answers "what are we executing?". This more about the algorithm and not hardware specific circuits.

Two kinds: Variational & non-Variational workloads.

#### 1.1 Circuit

&emsp; &emsp; 4. width  
&emsp; &emsp; 5. depth  
&emsp; &emsp; 6. #2q gates (does this really matter at the algo level? because anyway they'd change post-transpilation?)  
&emsp; &emsp; 7. #cliffords  
&emsp; &emsp; 8. #non-cliffords  
&emsp; &emsp; 9. critical path length (diameter)  
&emsp; &emsp; 10. #shots required (minimum to establish the answer properly!)  
&emsp; &emsp; 11. #connected components  

#### 1.2 Variational

&emsp; &emsp; 12. Classical optimizer used  
&emsp; &emsp; 13. #iterations  
&emsp; &emsp; 14. #repetitions  
&emsp; &emsp; 15. time taken by classical optimizer overall  

---

### Layer-2 (Backend specific Metrics/Features)
Everything between algorithm and actually running it on either an HPC simulator or actual QPU. So, we split this into sub types.

#### 2.1 Transpilation Features

&emsp; &emsp; 16. Quantify Error Mitigation optimization levels in a way that's agnostic to hardware type. (IBM-Q's opt level vs. Ion-Q's levels vs. Quantinuum's levels etc.)

#### 2.2 Post-Transpilation Metrics

&emsp; &emsp; 17. hw circ width
&emsp; &emsp; 18. hw circ depth
&emsp; &emsp; 19. hw circ connectivity degree (in the active area, for instance in IBM-Q)  
&emsp; &emsp; 20. hw circ #connected components
&emsp; &emsp; 21. hc circ "SWAPS"  

---

### Layer-3 (Backend Features)
Broadly, two kinds of backends:

#### 3.1 Simulator Features

&emsp; &emsp; 22. SV?
&emsp; &emsp; 23. TN?
&emsp; &emsp; 24. if TN, max-bond-dim  
&emsp; &emsp; 25. CPU based?  
&emsp; &emsp; 26. GPU based?  
&emsp; &emsp; 27. #nodes  
&emsp; &emsp; 28. #cores_per_node  
&emsp; &emsp; 29. Precision (#bits per complex/real or complex/imag)  

#### 3.2 H/W Features

&emsp; &emsp; 30. Cycle Layer Ops Per Second (CLOPS)  
&emsp; &emsp; 31. quantum volume  
&emsp; &emsp; 32. T1 time (relaxation)  
&emsp; &emsp; 33. T2 time (dephasing)  
&emsp; &emsp; 34. 1q gate error  
&emsp; &emsp; 35. 2q gate error  
&emsp; &emsp; 36. readout error  
&emsp; &emsp; 37. calibration frequency - every day, every hour? (crontab schedule)  
&emsp; &emsp; 38. calibration age - time since calibrated  

---

### Layer-4 (Execution Metrics)
This layer is basically that runs the circuit, so runtime is the primary metric here!
But if backend is not local and not readily available and reserved for this particular job.
In that case, we'd have another queue apart from the HPC queue we accounted for in Layer-0.

&emsp; &emsp; 39. queue time  
&emsp; &emsp; 40. execution time  

---

### Layer-5 (Post-Processing Features/Metrics)
This layer deals with things after:

&emsp; &emsp; 41. Mitigation overhead? time taken  
&emsp; &emsp; 42. Quantum Error Correction syndrome extraction time?  
&emsp; &emsp; 43. Result marshalling time based on what the frontend needs.
