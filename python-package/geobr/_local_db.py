"""Local database support for geobr.

Allows users to point geobr to a local directory of Parquet files so that
``read_*()`` functions work offline or use pre-downloaded data.

The local files must follow the same naming convention used by the geobr
data server::

    {geography}_{year}_simplified.parquet   # simplified=True
    {geography}_{year}_original.parquet     # simplified=False

Examples
--------
>>> import geobr
>>> geobr.set_local_db("/path/to/parquets/")
>>> geobr.list_local_datasets()
>>> mun = geobr.read_municipality(year=2022)   # reads locally, no download
>>> geobr.clear_local_db()
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pandas as pd

# Module-level state: the configured local directory (None = not set)
_LOCAL_DB_PATH: Optional[Path] = None

# Regex to parse filenames: e.g. "municipalities_2022_simplified.parquet"
_FILENAME_RE = re.compile(
    r"^(?P<geo>.+?)_(?P<year>\d{4})_(?P<type>simplified|original)\.parquet$",
    re.IGNORECASE,
)


def set_local_db(path: str | Path) -> None:
    """Configure a local directory as the geobr data source.

    After calling this function, all ``read_*()`` functions will first look
    for the requested dataset in *path* before attempting a network download.

    Parameters
    ----------
    path : str or Path
        Path to a directory containing Parquet files named according to the
        geobr convention: ``{geography}_{year}_simplified.parquet`` or
        ``{geography}_{year}_original.parquet``.

    Raises
    ------
    ValueError
        If *path* does not exist or is not a directory.

    Examples
    --------
    >>> geobr.set_local_db("/data/geobr/")
    Local geobr database set to: /data/geobr
    """
    global _LOCAL_DB_PATH
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise ValueError(
            f"Path does not exist: {p}\n"
            "Please provide a valid directory path containing geobr Parquet files."
        )
    if not p.is_dir():
        raise ValueError(
            f"Path is not a directory: {p}\n"
            "Please provide a directory (not a file). Files inside should follow the "
            "naming convention: {{geography}}_{{year}}_simplified.parquet"
        )
    _LOCAL_DB_PATH = p
    print(f"Local geobr database set to: {_LOCAL_DB_PATH}")


def get_local_db() -> Optional[Path]:
    """Return the currently configured local database path.

    Returns
    -------
    Path or None
        The configured local directory, or ``None`` if no local database
        has been set.

    Examples
    --------
    >>> geobr.get_local_db()
    PosixPath('/data/geobr')
    """
    return _LOCAL_DB_PATH


def clear_local_db() -> None:
    """Remove the local database configuration.

    After calling this function, ``read_*()`` functions will resume
    downloading data from the geobr servers.

    Examples
    --------
    >>> geobr.clear_local_db()
    Local geobr database cleared. Downloads will resume from the network.
    """
    global _LOCAL_DB_PATH
    _LOCAL_DB_PATH = None
    print("Local geobr database cleared. Downloads will resume from the network.")


def list_local_datasets() -> pd.DataFrame:
    """List all geobr datasets available in the configured local directory.

    Returns
    -------
    pd.DataFrame
        A DataFrame with columns ``geography``, ``year``, ``simplified``,
        and ``path`` for each recognised Parquet file in the local directory.
        Returns an empty DataFrame if no local database has been configured.

    Raises
    ------
    RuntimeError
        If a local database is configured but the directory no longer exists.

    Examples
    --------
    >>> geobr.set_local_db("/data/geobr/")
    >>> geobr.list_local_datasets()
       geography  year  simplified                                          path
    0  municipalities  2022    True  /data/geobr/municipalities_2022_simplified.parquet
    """
    if _LOCAL_DB_PATH is None:
        print(
            "No local database configured. Use geobr.set_local_db('/path/') first."
        )
        return pd.DataFrame(
            columns=["geography", "year", "simplified", "path"]
        )

    if not _LOCAL_DB_PATH.exists():
        raise RuntimeError(
            f"Configured local database path no longer exists: {_LOCAL_DB_PATH}\n"
            "Please update it with geobr.set_local_db() or call geobr.clear_local_db()."
        )

    rows = []
    for parquet_file in sorted(_LOCAL_DB_PATH.glob("*.parquet")):
        match = _FILENAME_RE.match(parquet_file.name)
        if match:
            rows.append(
                {
                    "geography": match.group("geo"),
                    "year": int(match.group("year")),
                    "simplified": match.group("type").lower() == "simplified",
                    "path": str(parquet_file),
                }
            )

    if not rows:
        print(
            f"No geobr Parquet files found in: {_LOCAL_DB_PATH}\n"
            "Files must follow the naming pattern: "
            "{{geography}}_{{year}}_simplified.parquet"
        )

    return pd.DataFrame(rows, columns=["geography", "year", "simplified", "path"])


def _resolve_local(
    geography: str,
    year: Optional[int],
    simplified: bool,
) -> Optional[Path]:
    """Internal: resolve the local Parquet path for the requested dataset.

    Parameters
    ----------
    geography : str
        The geobr geography identifier (e.g. ``"municipalities"``).
    year : int or None
        The requested year. If ``None``, the latest available local year
        is returned.
    simplified : bool
        Whether the simplified geometry is requested.

    Returns
    -------
    Path or None
        Full path to the local Parquet file, or ``None`` if not found.
    """
    if _LOCAL_DB_PATH is None or not _LOCAL_DB_PATH.exists():
        return None

    suffix = "simplified" if simplified else "original"

    # If year is specified, try direct match first
    if year is not None:
        candidate = _LOCAL_DB_PATH / f"{geography}_{year}_{suffix}.parquet"
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate

    # If year is None (or direct match failed for None), find latest available
    if year is None:
        available = []
        for parquet_file in _LOCAL_DB_PATH.glob(f"{geography}_*_{suffix}.parquet"):
            match = _FILENAME_RE.match(parquet_file.name)
            if match and match.group("geo") == geography:
                available.append((int(match.group("year")), parquet_file))
        if available:
            return max(available, key=lambda x: x[0])[1]

    return None
