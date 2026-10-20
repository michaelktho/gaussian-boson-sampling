"""Input validation and density evaluation for threshold GBS."""
from __future__ import annotations
import io
import numpy as np

EXAMPLE = """0,4,0,1,0,0
4,0,5,2,0,0
0,5,0,4,1,0
1,2,4,0,3,0
0,0,1,3,0,0.5
0,0,0,0,0.5,0"""


def parse_matrix(data: bytes | str) -> np.ndarray:
    """Read comma-, tab- or whitespace-delimited numeric matrix without headers."""
    if isinstance(data, bytes):
        text = data.decode('utf-8-sig')
    else:
        text = data.lstrip('\ufeff')
    if not text.strip():
        raise ValueError('Matrix is empty.')
    first = next((line for line in text.splitlines() if line.strip()), '')
    delimiter = ',' if ',' in first else None
    try:
        with io.StringIO(text) as stream:
            a = np.loadtxt(stream, delimiter=delimiter, dtype=np.float64, ndmin=2)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'Unable to parse numeric matrix: {exc}') from exc
    return validate_matrix(a)


def validate_matrix(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64)
    if a.ndim != 2 or a.shape[0] != a.shape[1] or a.shape[0] < 2:
        raise ValueError(f'Matrix must be square with at least two vertices; received {a.shape}.')
    if not np.isfinite(a).all():
        raise ValueError('All matrix entries must be finite numbers.')
    if (a < 0).any():
        raise ValueError('Negative weights are not supported. Transform signed similarities explicitly before uploading.')
    if not np.allclose(np.diag(a), 0, atol=1e-10, rtol=0):
        raise ValueError('Diagonal values must be zero (no self-loops).')
    if not np.allclose(a, a.T, rtol=1e-10, atol=1e-10):
        raise ValueError('Matrix must be symmetric (undirected graph).')
    return np.ascontiguousarray(a)


def internal_weight(a: np.ndarray, vertices: np.ndarray | list[int]) -> float:
    ix = np.asarray(vertices, dtype=int)
    if ix.size == 0:
        return 0.0
    block = a[np.ix_(ix, ix)]
    return float(np.triu(block, k=1).sum())


def density(a: np.ndarray, vertices: np.ndarray | list[int]) -> float:
    return internal_weight(a, vertices) / len(vertices) if len(vertices) else 0.0


def all_graph_density(a: np.ndarray) -> float:
    return float(np.triu(a, 1).sum()) / len(a)


def sample_vertices(row: np.ndarray) -> np.ndarray:
    """Each threshold detector click selects its corresponding graph vertex."""
    row = np.asarray(row)
    if row.ndim != 1 or not np.isin(row, (0, 1)).all():
        raise ValueError('The simulator returned a non-binary threshold click pattern.')
    return np.flatnonzero(row)
