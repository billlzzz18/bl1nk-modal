"""Test bootstrap: make the app package importable and stub the heavy ML
dependencies (torch/transformers/faiss) that search_service.py needs at
import time but that a unit-test environment doesn't need to actually run.
"""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class _NoGrad:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


if "torch" not in sys.modules:
    torch_stub = types.ModuleType("torch")
    torch_stub.cuda = types.SimpleNamespace(is_available=lambda: False, empty_cache=lambda: None)
    torch_stub.no_grad = _NoGrad
    sys.modules["torch"] = torch_stub

if "transformers" not in sys.modules:
    transformers_stub = types.ModuleType("transformers")
    transformers_stub.AutoTokenizer = MagicMock()
    transformers_stub.AutoModel = MagicMock()
    sys.modules["transformers"] = transformers_stub

if "faiss" not in sys.modules:
    faiss_stub = types.ModuleType("faiss")

    class _FakeIndexFlatIP:
        """Minimal stand-in for faiss.IndexFlatIP: brute-force inner product."""

        def __init__(self, dim):
            self.dim = dim
            self.ntotal = 0
            self._vectors = []

        def add(self, vec):
            self._vectors.append(np.asarray(vec).reshape(-1))
            self.ntotal += 1

        def search(self, vec, k):
            query = np.asarray(vec).reshape(-1)
            if not self._vectors:
                return np.zeros((1, 0), dtype="float32"), np.zeros((1, 0), dtype="int64")
            scores = [float(np.dot(v, query)) for v in self._vectors]
            order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
            return (
                np.array([[scores[i] for i in order]], dtype="float32"),
                np.array([order], dtype="int64"),
            )

    faiss_stub.IndexFlatIP = _FakeIndexFlatIP
    sys.modules["faiss"] = faiss_stub
