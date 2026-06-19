"""
Pure-Python reader for TensorFlow v2 checkpoints (tensor bundle).

Reads `variables.index` (a LevelDB SSTable) and
`variables.data-00000-of-00001` (raw tensor bytes) WITHOUT requiring
TensorFlow. This lets us convert the Deezer SavedModel weights to PyTorch
on any Python version (including 3.14, where TensorFlow has no wheels).

Supports the float32 tensors used by the Deezer specnn_amplitude model.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

_TABLE_MAGIC = 0xDB4775248B80FB57
_FOOTER_SIZE = 48

# TensorFlow DataType enum values we care about.
_DTYPE_TO_NUMPY = {
    1: np.float32,   # DT_FLOAT
    2: np.float64,   # DT_DOUBLE
    3: np.int32,     # DT_INT32
    9: np.int64,     # DT_INT64
}


def _read_varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break
        shift += 7
    return result, pos


def _iter_block_entries(content: bytes):
    """Yield (key, value) pairs from a LevelDB table block (no compression)."""
    num_restarts = struct.unpack("<I", content[-4:])[0]
    entries_end = len(content) - 4 * (num_restarts + 1)

    pos = 0
    key = b""
    while pos < entries_end:
        shared, pos = _read_varint(content, pos)
        unshared, pos = _read_varint(content, pos)
        value_len, pos = _read_varint(content, pos)
        key = key[:shared] + content[pos : pos + unshared]
        pos += unshared
        value = content[pos : pos + value_len]
        pos += value_len
        yield key, value


def _read_block(data: bytes, offset: int, size: int) -> bytes:
    return data[offset : offset + size]


def _parse_block_handle(buf: bytes, pos: int = 0) -> tuple[int, int, int]:
    offset, pos = _read_varint(buf, pos)
    size, pos = _read_varint(buf, pos)
    return offset, size, pos


def _parse_tensor_shape(buf: bytes) -> list[int]:
    """Parse TensorShapeProto, returning the list of dim sizes."""
    dims: list[int] = []
    pos = 0
    while pos < len(buf):
        tag, pos = _read_varint(buf, pos)
        field = tag >> 3
        wire = tag & 0x7
        if field == 2 and wire == 2:  # repeated Dim
            length, pos = _read_varint(buf, pos)
            dim_buf = buf[pos : pos + length]
            pos += length
            d_pos = 0
            size = 0
            while d_pos < len(dim_buf):
                d_tag, d_pos = _read_varint(dim_buf, d_pos)
                d_field = d_tag >> 3
                d_wire = d_tag & 0x7
                if d_field == 1 and d_wire == 0:  # size
                    size, d_pos = _read_varint(dim_buf, d_pos)
                elif d_wire == 2:
                    slen, d_pos = _read_varint(dim_buf, d_pos)
                    d_pos += slen
                else:
                    _, d_pos = _read_varint(dim_buf, d_pos)
            dims.append(size)
        elif wire == 2:
            length, pos = _read_varint(buf, pos)
            pos += length
        elif wire == 5:
            pos += 4
        elif wire == 1:
            pos += 8
        else:
            _, pos = _read_varint(buf, pos)
    return dims


def _parse_bundle_entry(buf: bytes) -> dict:
    """Parse BundleEntryProto -> {dtype, shape, offset, size}."""
    entry = {"dtype": 0, "shape": [], "offset": 0, "size": 0}
    pos = 0
    while pos < len(buf):
        tag, pos = _read_varint(buf, pos)
        field = tag >> 3
        wire = tag & 0x7
        if field == 1 and wire == 0:
            entry["dtype"], pos = _read_varint(buf, pos)
        elif field == 2 and wire == 2:
            length, pos = _read_varint(buf, pos)
            entry["shape"] = _parse_tensor_shape(buf[pos : pos + length])
            pos += length
        elif field == 4 and wire == 0:
            entry["offset"], pos = _read_varint(buf, pos)
        elif field == 5 and wire == 0:
            entry["size"], pos = _read_varint(buf, pos)
        elif wire == 2:
            length, pos = _read_varint(buf, pos)
            pos += length
        elif wire == 5:
            pos += 4
        elif wire == 1:
            pos += 8
        else:
            _, pos = _read_varint(buf, pos)
    return entry


def _read_index_entries(index_bytes: bytes) -> dict[str, dict]:
    if len(index_bytes) < _FOOTER_SIZE:
        raise ValueError("variables.index is too small to be a valid checkpoint.")

    footer = index_bytes[-_FOOTER_SIZE:]
    magic = struct.unpack("<Q", footer[-8:])[0]
    if magic != _TABLE_MAGIC:
        raise ValueError(
            "Unexpected checkpoint format (bad table magic). "
            "This reader supports uncompressed TensorFlow v2 checkpoints."
        )

    # Footer = metaindex handle, index handle (varints), padding, magic.
    pos = 0
    _, _, pos = _parse_block_handle(footer, pos)  # metaindex (unused)
    index_off, index_size, _ = _parse_block_handle(footer, pos)

    index_block = _read_block(index_bytes, index_off, index_size)

    entries: dict[str, dict] = {}
    for _key, value in _iter_block_entries(index_block):
        data_off, data_size, _ = _parse_block_handle(value, 0)
        data_block = _read_block(index_bytes, data_off, data_size)
        for tensor_key, entry_value in _iter_block_entries(data_block):
            if tensor_key == b"":  # bundle header, not a tensor
                continue
            entries[tensor_key.decode("utf-8")] = _parse_bundle_entry(entry_value)
    return entries


def read_checkpoint(variables_dir: str | Path) -> dict[str, np.ndarray]:
    """
    Read all tensors from a TensorFlow v2 checkpoint `variables` folder.

    Returns a mapping of tensor name -> numpy array.
    """
    variables_dir = Path(variables_dir)
    index_path = variables_dir / "variables.index"
    data_path = variables_dir / "variables.data-00000-of-00001"

    if not index_path.is_file() or not data_path.is_file():
        raise FileNotFoundError(
            f"Checkpoint files not found in {variables_dir}. "
            "Expected variables.index and variables.data-00000-of-00001."
        )

    index_bytes = index_path.read_bytes()
    shard_bytes = data_path.read_bytes()

    entries = _read_index_entries(index_bytes)

    tensors: dict[str, np.ndarray] = {}
    for name, entry in entries.items():
        dtype = _DTYPE_TO_NUMPY.get(entry["dtype"])
        if dtype is None:
            continue
        raw = shard_bytes[entry["offset"] : entry["offset"] + entry["size"]]
        array = np.frombuffer(raw, dtype=dtype)
        shape = entry["shape"]
        if shape:
            array = array.reshape(shape)
        tensors[name] = np.array(array, copy=True)
    return tensors
