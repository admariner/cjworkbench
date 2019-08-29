import io
from pathlib import Path
import tempfile
from typing import List, Optional
import fastparquet
from typing import Any, Callable
import pyarrow as pa
import pyarrow.parquet
from fastparquet import ParquetFile
import pandas
import snappy
import warnings
from server import minio


# Workaround for https://github.com/dask/fastparquet/issues/394
# When we upgrade to fastparquet >= 0.2.2, nix this!
warnings.filterwarnings(
    "ignore", category=FutureWarning, module="fastparquet.util", lineno=221
)


def _minio_open_random(bucket, key):
    if key.endswith("/_metadata"):
        # fastparquet insists upon trying for the 'hive' storage schema before
        # settling on the 'simple' storage schema. At no time have we ever
        # saved a file in 'hive' format; therefore there are no '_metadata'
        # files; therefore we can skip hitting minio here.
        raise FileNotFoundError

    # TODO store column metadata in the database, so we don't need to read it
    # from S3. Then consider minio.FullReadMinioFile, which could be faster.
    # (We'll want to benchmark.) Another option is to use the 'hive' format and
    # FullReadMinioFile; but that choice would be hard to un-choose, so let's
    # not rush into it.
    raw = minio.RandomReadMinioFile(bucket, key)

    # fastparquet actually expects a _buffered_ reader -- it expects `read()`
    # to always return a buffer of the same length it requests.
    buffered = io.BufferedReader(raw)

    return buffered


def _minio_open_full(bucket, key):
    """
    Optimized open call, for when we know we'll read the entire file.
    """
    if key.endswith("/_metadata"):
        # fastparquet insists upon trying for the 'hive' storage schema before
        # settling on the 'simple' storage schema. At no time have we ever
        # saved a file in 'hive' format; therefore there are no '_metadata'
        # files; therefore we can skip hitting minio here.
        raise FileNotFoundError

    # Don't worry about needing a _buffered_ reader here (like we worry in
    # _minio_open_random). FullReadMinioFile actually does a regular open() on
    # a regular file -- so it will behave exactly as fastparquet expects.
    return minio.FullReadMinioFile(bucket, key)


# Suppress this arning:
# .../python3.6/site-packages/fastparquet/writer.py:407: FutureWarning: Method
# .valid will be removed in a future version. Use .dropna instead.
#   out = data.valid()  # better, data[data.notnull()], from above ?
#
# warnings.catch_warnings() is not thread-safe so we can't use it.
warnings.filterwarnings(
    action="ignore",
    message="Method .valid will be removed in a future version.",
    category=FutureWarning,
    module="fastparquet.writer",
)


class FastparquetCouldNotHandleFile(Exception):
    pass


class FastparquetIssue375(FastparquetCouldNotHandleFile):
    """
    The file was written by pyarrow, has a really long string and
    Fastparquet has a bug.

    Track the issue at https://github.com/dask/fastparquet/issues/375
    """

    pass


def read_header(
    bucket: str, key: str, open_with: Callable[[str, str], Any] = _minio_open_random
) -> ParquetFile:
    """
    Ensure a ParquetFile exists, and return it with headers read.

    May raise FileNotFoundError or FastparquetCouldNotHandleFile.

    `retval.fn` gives the filename; `retval.columns` gives column names;
    `retval.dtypes` gives pandas dtypes, and `retval.to_pandas()` reads
    the entire file.
    """
    filelike = open_with(bucket, key)  # raises FileNotFoundError
    return fastparquet.ParquetFile(filelike)


def read(
    bucket: str, key: str, to_pandas_args=[], to_pandas_kwargs={}
) -> pandas.DataFrame:
    """
    Load a Pandas DataFrame from disk or raise FileNotFoundError or
    FastparquetCouldNotHandleFile.

    May raise OSError (e.g., FileNotFoundError) or
    FastparquetCouldNotHandleFile. The latter comes from
    https://github.com/dask/fastparquet/issues/375 -- we used to write with
    pyarrow, and fastparquet fails on some files with large strings. Those
    files are so old we won't attempt to support them.
    """
    if to_pandas_args or to_pandas_kwargs:
        open_with = _minio_open_random
    else:
        open_with = _minio_open_full

    try:
        pf = read_header(bucket, key, open_with=open_with)
        dataframe = pf.to_pandas(*to_pandas_args, **to_pandas_kwargs)
    except snappy.UncompressError as err:
        if str(err) == "Error while decompressing: invalid input":
            # Assume Fastparquet is reporting the wrong bug.
            #
            # XXX this means we can't actually report corrupt files. Let's fix
            # Fastparquet and delete this possibility altogether.
            raise FastparquetIssue375
        raise
    except AssertionError:
        raise FastparquetIssue375

    # Empty categorical gets read as int64. Convert to str.
    if dataframe.empty:
        cat_colnames = dataframe.columns[dataframe.dtypes == "category"]
        for cat_colname in cat_colnames:
            dataframe[cat_colname] = (
                dataframe[cat_colname].astype(str).astype("category")
            )
    return dataframe


def read_arrow_table(
    bucket: str, key: str, *, only_columns: Optional[List[str]] = None
) -> pa.Table:
    """
    Return data from minio, as an Apache Arrow Table.

    The table is stored entirely in RAM. TODO stream it to an mmapped file.
    """
    with minio.temporarily_download(bucket, key) as path:
        table = pyarrow.parquet.read_table(
            path, use_threads=False, columns=only_columns
        )

        # Avoid a problem calling .to_pandas() with fastparquet-dumped files.
        #
        #   File "pyarrow/array.pxi", line 441, in pyarrow.lib._PandasConvertible.to_pandas
        #   File "pyarrow/table.pxi", line 1367, in pyarrow.lib.Table._to_pandas
        #   File "/root/.local/share/virtualenvs/app-4PlAip0Q/lib/python3.7/site-packages/pyarrow/pandas_compat.py", line 644, in table_to_blockmanager
        #     table = _add_any_metadata(table, pandas_metadata)
        #   File "/root/.local/share/virtualenvs/app-4PlAip0Q/lib/python3.7/site-packages/pyarrow/pandas_compat.py", line 967, in _add_any_metadata
        #     idx = schema.get_field_index(raw_name)
        #   File "pyarrow/types.pxi", line 902, in pyarrow.lib.Schema.get_field_index
        #   File "stringsource", line 15, in string.from_py.__pyx_convert_string_from_py_std__in_string
        # TypeError: expected bytes, dict found
        #
        # [2019-08-22] fastparquet-dumped files will be around for a long time.
        #
        # We don't care about schema metadata, anyway. Workbench has its own
        # restrictive schema; we don't need extra Pandas-specific data because
        # we don't support everything Pandas supports.
        table = table.replace_schema_metadata(None)  # FIXME unit-test this!

        return table


def write(bucket: str, key: str, table: pandas.DataFrame) -> int:
    """
    Write a Pandas DataFrame to a minio file, overwriting if needed.

    Return number of bytes written.

    We aim to keep the file format "stable": all future versions of
    parquet.read() should support all files written by today's version of this
    function.
    """
    with tempfile.NamedTemporaryFile() as tf:
        fastparquet.write(tf.name, table, compression="SNAPPY", object_encoding="utf8")
        minio.fput_file(bucket, key, Path(tf.name))
        tf.seek(0, io.SEEK_END)
        return tf.tell()