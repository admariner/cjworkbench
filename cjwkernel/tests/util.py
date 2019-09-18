from contextlib import contextmanager
import io
import pathlib
import os
import tempfile
from typing import Any, ContextManager, Dict, Iterable, List, Optional, Union
import unittest
from numpy.testing import assert_equal  # [None, "x"] == [None, "x"]
import pyarrow
import pyarrow.parquet
from cjwkernel import settings
from cjwkernel.types import ArrowTable, Column, ColumnType, RenderResult, TableMetadata


@contextmanager
def arrow_file(
    table: Union[Dict[str, List[Any]], pyarrow.Table],
    dir: Optional[pathlib.Path] = None,
) -> ContextManager[pathlib.Path]:
    """
    Yield a path with `table` written to an Arrow file.
    """
    if isinstance(table, dict):
        table = pyarrow.Table.from_pydict(table)

    fd, filename = tempfile.mkstemp(dir=dir)
    try:
        os.close(fd)
        writer = pyarrow.RecordBatchFileWriter(filename, table.schema)
        writer.write_table(table)
        writer.close()
        yield pathlib.Path(filename)
    finally:
        try:
            os.unlink(filename)
        except FileNotFoundError:
            pass


def _arrow_column_to_column(column: pyarrow.Column) -> Column:
    if pyarrow.types.is_floating(column.type) or pyarrow.types.is_integer(column.type):
        column_type = ColumnType.Number("{:,}")
    elif pyarrow.types.is_timestamp(column.type):
        column_type = ColumnType.Datetime()
    elif pyarrow.types.is_string(column.type) or pyarrow.types.is_dictionary(
        column.type
    ):
        column_type = ColumnType.Text()
    else:
        raise RuntimeError("Unknown column type %r" % column.type)
    return Column(column.name, column_type)


@contextmanager
def arrow_table_context(
    table: Union[Dict[str, List[Any]], pyarrow.Table],
    columns: Optional[List[Column]] = None,
    dir: Optional[pathlib.Path] = None,
) -> ContextManager[ArrowTable]:
    """
    Yield an ArrowTable (whose `.path` is a file).

    Metadata is inferred. Number columns have format `{:,}`.
    """
    if isinstance(table, dict):
        table = pyarrow.Table.from_pydict(table)

    if columns is None:
        columns = [_arrow_column_to_column(c) for c in table.columns]
    metadata = TableMetadata(table.num_rows, columns)

    with arrow_file(table, dir=dir) as filename:
        yield ArrowTable(pathlib.Path(filename), metadata)


def arrow_table(
    table: Union[Dict[str, List[Any]], pyarrow.Table],
    columns: Optional[List[Column]] = None,
) -> ArrowTable:
    """
    Yield an ArrowTable (whose `.path` is a _deleted_ file).

    Metadata is inferred. Number columns have format `{:,}`.

    The path may be deleted, but the file on disk is still mmapped.
    """
    with arrow_table_context(table, columns) as table:
        return table


def assert_arrow_table_equals(
    result1: Union[pyarrow.Table, ArrowTable],
    result2: Union[Dict[str, Any], pyarrow.Table, ArrowTable],
) -> None:
    if isinstance(result1, pyarrow.Table):
        result1 = arrow_table(result1)
    if isinstance(result2, pyarrow.Table) or isinstance(result2, dict):
        result2 = arrow_table(result2)
    assertEqual = unittest.TestCase().assertEqual
    assertEqual(result1.metadata.columns, result2.metadata.columns)
    assertEqual(result1.metadata.n_rows, result2.metadata.n_rows)
    if not result1.metadata.columns:
        # No columns? Then any two tables with same number of rows are equal
        return
    if result1.table is not None and result2.table is not None:
        for actual_col, expected_col in zip(
            result1.table.columns, result2.table.columns
        ):
            assertEqual(
                actual_col.type,
                expected_col.type,
                msg=f"Column {actual_col.name} has wrong type",
            )
            assert_equal(
                actual_col.to_pylist(),
                expected_col.to_pylist(),
                err_msg=f"Column {actual_col.name} has wrong values",
            )
    else:
        assertEqual(result1.table is None, result2.table is None)


def assert_render_result_equals(result1: RenderResult, result2: RenderResult) -> None:
    assert_arrow_table_equals(result1.table, result2.table)
    assertEqual = unittest.TestCase().assertEqual
    assertEqual(
        [e.to_dict() for e in result1.errors], [e.to_dict() for e in result2.errors]
    )
    assertEqual(result1.json, result2.json)


@contextmanager
def parquet_file(
    table: Union[Dict[str, List[Any]], pyarrow.Table],
    dir: Optional[pathlib.Path] = None,
) -> ContextManager[pathlib.Path]:
    """
    Yield a filename with `table` written to a Parquet file.
    """
    atable = arrow_table(table)
    fd, filename = tempfile.mkstemp(dir=dir)
    try:
        os.close(fd)
        pyarrow.parquet.write_table(atable.table, filename, compression="SNAPPY")
        yield pathlib.Path(filename)
    finally:
        os.unlink(filename)


def override_settings(**kwargs):
    return unittest.mock.patch.multiple(settings, **kwargs)


class MockPath(pathlib.PurePosixPath):
    """
    Simulate pathlib.Path

    Features:

        * read_bytes()
        * read_text(), including encoding and errors
        * open()
        * when `data` is None, raise `FileNotFoundError` when expecting a file
    """

    def __new__(
        cls,
        parts: List[str],
        data: Optional[bytes],
        parent: Optional[pathlib.PurePosixPath] = None,
    ):
        ret = super().__new__(cls, *parts)
        ret.data = data
        ret._parent = parent
        return ret

    # override
    @property
    def parent(self):
        return self._parent

    # Path interface
    def read_bytes(self):
        if self.data is None:
            raise FileNotFoundError(self.name)

        return self.data

    # Path interface
    def read_text(self, encoding="utf-8", errors="strict"):
        if self.data is None:
            raise FileNotFoundError(self.name)

        return self.data.decode(encoding, errors)

    def open(self, mode):
        assert mode == "rb"
        return io.BytesIO(self.data)


class MockDir(pathlib.PurePosixPath):
    """
    Mock filesystem directory using pathlib.Path interface.

    Usage:

        dirpath: PurePath = MockDir({
            'xxx.yaml': b'id_name: xxx...'
            'xxx.py': b'def render(
        })

        yaml_text = (dirpath / 'xxx.yaml').read_text()
    """

    def __new__(cls, filedata: Dict[str, bytes]):  # filename => bytes
        ret = super().__new__(cls, pathlib.PurePath("root"))
        ret.filedata = filedata
        return ret

    # override
    def __truediv__(self, filename: str) -> MockPath:
        data = self.filedata.get(filename)  # None if file does not exist
        return MockPath(["root", filename], data, parent=self)
        try:
            return self.files[filename]
        except KeyError:
            return MockPath(["root", filename], None)

    def glob(self, pattern: str) -> Iterable[MockPath]:
        for key in self.filedata.keys():
            path = self / key
            if path.match(pattern):
                yield path
