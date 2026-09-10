"""Small shared persistence/concurrency helpers, independent of either workflow."""

from __future__ import annotations

import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def atomic_write_json(path: Path, value: object) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def run_parallel(function: Callable[[T], R], items: Iterable[T], max_concurrency: int) -> list[R]:
    work = list(items)
    if max_concurrency < 1:
        raise ValueError("max_concurrency must be positive")
    if len(work) <= 1 or max_concurrency == 1:
        return [function(item) for item in work]
    with ThreadPoolExecutor(max_workers=min(max_concurrency, len(work))) as executor:
        return list(executor.map(function, work))
