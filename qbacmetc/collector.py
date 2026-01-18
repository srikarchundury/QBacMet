from .alg_layer import AlgLayer
from .transpile_layer import TranspileLayer
from .backend_layer import BackendLayer
from .execution_layer import ExecutionLayer
from .postprocess_layer import PostprocessLayer
from .slurm_layer import SlurmLayer

import contextlib
class QBacMetCollector:
    def __init__(self):
        self.alg_layer = AlgLayer()
        self.transpile_layer = TranspileLayer()
        self.backend_layer = BackendLayer()
        self.execution_layer = ExecutionLayer()
        self.postprocess_layer = PostprocessLayer()
        self.slurm_layer = SlurmLayer()
        self.collecting = False
        self.metrics = {}

    def start_collecting(self):
        self.collecting = True
        self.metrics = {}

    def stop_collecting(self):
        self.collecting = False

    def auto_collect_all(self):
        if self.collecting:
            self.metrics['slurm'] = self.slurm_layer.auto_collect()
            self.metrics['algorithm'] = self.alg_layer.auto_collect()
            self.metrics['transpile'] = self.transpile_layer.auto_collect()
            self.metrics['backend'] = self.backend_layer.auto_collect()
            self.metrics['execution'] = self.execution_layer.auto_collect()
            self.metrics['postprocess'] = self.postprocess_layer.auto_collect()

    @contextlib.contextmanager
    def collect(self):
        self.start_collecting()
        try:
            yield self
            self.auto_collect_all()
        finally:
            self.stop_collecting()

    def print_metrics(self):
        import pprint
        pprint.pprint(self.metrics)

# Singleton instance
collector = QBacMetCollector()
