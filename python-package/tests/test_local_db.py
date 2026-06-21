"""Tests for geobr._local_db — local database support."""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

import geobr
from geobr._local_db import (
    _resolve_local,
    clear_local_db,
    get_local_db,
    list_local_datasets,
    set_local_db,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_local_db():
    """Ensure the local DB is cleared before and after every test."""
    clear_local_db()
    yield
    clear_local_db()


@pytest.fixture
def local_dir(tmp_path: Path):
    """A temporary directory with a few fake Parquet files."""
    # Create minimal valid parquet files (just needs to exist and be non-empty)
    files = [
        "municipalities_2022_simplified.parquet",
        "municipalities_2022_original.parquet",
        "states_2020_simplified.parquet",
        "biomes_2019_simplified.parquet",
        "not_a_geobr_file.txt",        # should be ignored
        "bad_name_2022.parquet",        # should be ignored (no type suffix)
    ]
    for fname in files:
        f = tmp_path / fname
        # Write dummy bytes so stat().st_size > 0
        f.write_bytes(b"PAR1" + b"\x00" * 100)
    return tmp_path


# ---------------------------------------------------------------------------
# set_local_db
# ---------------------------------------------------------------------------


class TestSetLocalDb:
    def test_set_valid_directory(self, local_dir):
        set_local_db(local_dir)
        assert get_local_db() == local_dir

    def test_set_string_path(self, local_dir):
        set_local_db(str(local_dir))
        assert get_local_db() == local_dir

    def test_set_nonexistent_path_raises(self, tmp_path):
        with pytest.raises(ValueError, match="does not exist"):
            set_local_db(tmp_path / "nonexistent_dir")

    def test_set_file_path_raises(self, tmp_path):
        f = tmp_path / "somefile.parquet"
        f.write_bytes(b"data")
        with pytest.raises(ValueError, match="not a directory"):
            set_local_db(f)

    def test_prints_confirmation(self, local_dir, capsys):
        set_local_db(local_dir)
        captured = capsys.readouterr()
        assert "Local geobr database set to" in captured.out


# ---------------------------------------------------------------------------
# get_local_db
# ---------------------------------------------------------------------------


class TestGetLocalDb:
    def test_returns_none_when_not_set(self):
        assert get_local_db() is None

    def test_returns_path_after_set(self, local_dir):
        set_local_db(local_dir)
        result = get_local_db()
        assert isinstance(result, Path)
        assert result == local_dir


# ---------------------------------------------------------------------------
# clear_local_db
# ---------------------------------------------------------------------------


class TestClearLocalDb:
    def test_clears_configured_path(self, local_dir):
        set_local_db(local_dir)
        clear_local_db()
        assert get_local_db() is None

    def test_clear_when_already_none_does_not_raise(self):
        clear_local_db()  # should not raise
        assert get_local_db() is None

    def test_prints_confirmation(self, local_dir, capsys):
        set_local_db(local_dir)
        clear_local_db()
        captured = capsys.readouterr()
        assert "cleared" in captured.out.lower()


# ---------------------------------------------------------------------------
# list_local_datasets
# ---------------------------------------------------------------------------


class TestListLocalDatasets:
    def test_returns_empty_df_when_not_set(self, capsys):
        result = list_local_datasets()
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["geography", "year", "simplified", "path"]
        assert len(result) == 0

    def test_lists_valid_parquet_files(self, local_dir):
        set_local_db(local_dir)
        result = list_local_datasets()
        assert isinstance(result, pd.DataFrame)
        # 4 valid geobr files: muni simplified, muni original, states, biomes
        assert len(result) == 4

    def test_ignores_non_parquet_files(self, local_dir):
        set_local_db(local_dir)
        result = list_local_datasets()
        paths = result["path"].tolist()
        assert not any("not_a_geobr_file.txt" in p for p in paths)

    def test_ignores_malformed_parquet_names(self, local_dir):
        set_local_db(local_dir)
        result = list_local_datasets()
        paths = result["path"].tolist()
        assert not any("bad_name_2022" in p for p in paths)

    def test_simplified_column_is_bool(self, local_dir):
        set_local_db(local_dir)
        result = list_local_datasets()
        assert result["simplified"].dtype == bool

    def test_year_column_is_int(self, local_dir):
        set_local_db(local_dir)
        result = list_local_datasets()
        assert pd.api.types.is_integer_dtype(result["year"])

    def test_correct_geography_parsed(self, local_dir):
        set_local_db(local_dir)
        result = list_local_datasets()
        assert set(result["geography"]) == {"municipalities", "states", "biomes"}

    def test_raises_if_dir_disappears(self, local_dir):
        set_local_db(local_dir)
        shutil.rmtree(local_dir)
        with pytest.raises(RuntimeError, match="no longer exists"):
            list_local_datasets()


# ---------------------------------------------------------------------------
# _resolve_local (internal)
# ---------------------------------------------------------------------------


class TestResolveLocal:
    def test_returns_none_when_no_local_db(self):
        result = _resolve_local("municipalities", 2022, simplified=True)
        assert result is None

    def test_resolves_existing_simplified_file(self, local_dir):
        set_local_db(local_dir)
        result = _resolve_local("municipalities", 2022, simplified=True)
        assert result is not None
        assert result.name == "municipalities_2022_simplified.parquet"

    def test_resolves_existing_original_file(self, local_dir):
        set_local_db(local_dir)
        result = _resolve_local("municipalities", 2022, simplified=False)
        assert result is not None
        assert result.name == "municipalities_2022_original.parquet"

    def test_returns_none_for_missing_year(self, local_dir):
        set_local_db(local_dir)
        result = _resolve_local("municipalities", 1990, simplified=True)
        assert result is None

    def test_returns_none_for_missing_geography(self, local_dir):
        set_local_db(local_dir)
        result = _resolve_local("census_tract", 2022, simplified=True)
        assert result is None

    def test_returns_latest_when_year_is_none(self, local_dir):
        """When year=None, return the latest year available locally."""
        # Add a second year for municipalities
        extra = local_dir / "municipalities_2023_simplified.parquet"
        extra.write_bytes(b"PAR1" + b"\x00" * 100)
        set_local_db(local_dir)
        result = _resolve_local("municipalities", None, simplified=True)
        assert result is not None
        assert "2023" in result.name


# ---------------------------------------------------------------------------
# Integration: read_*() functions use local DB when available
# ---------------------------------------------------------------------------


class TestReadUsesLocalDb:
    """
    These tests verify that read_*() routes to the local file.
    They use a real (minimal) Parquet file so DuckDB can open it.
    """

    @pytest.fixture
    def local_parquet_dir(self, tmp_path):
        """Create a real minimal Parquet file for municipalities."""
        import pyarrow as pa
        import pyarrow.parquet as pq
        from shapely.geometry import box
        import geopandas as gpd

        gdf = gpd.GeoDataFrame(
            {
                "code_muni": [3550308],
                "name_muni": ["São Paulo"],
                "code_state": [35],
                "abbrev_state": ["SP"],
                "code_region": [3],
                "name_region": ["Sudeste"],
                "year": [2022],
                "geometry": [box(-47.0, -24.0, -46.0, -23.0)],
            },
            crs="EPSG:4674",
        )

        path = tmp_path / "municipalities_2022_simplified.parquet"
        gdf.to_parquet(path)
        return tmp_path

    def test_read_municipality_uses_local_file(self, local_parquet_dir, monkeypatch):
        """read_municipality() should use the local file and not call download_parquet."""
        import geobr.utils as utils_mod

        download_called = []

        original_download = utils_mod.download_parquet

        def mock_download(*args, **kwargs):
            download_called.append(True)
            return original_download(*args, **kwargs)

        monkeypatch.setattr(utils_mod, "download_parquet", mock_download)

        set_local_db(local_parquet_dir)
        result = geobr.read_municipality(year=2022, output="gpd")

        assert len(download_called) == 0, (
            "download_parquet() should NOT have been called when local file exists"
        )
        assert result is not None
        assert len(result) > 0
