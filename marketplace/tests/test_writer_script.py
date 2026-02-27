"""Tests for marketplace/services/_writer.py.

This is a standalone CLI script that reads a base64-encoded file path from
argv[1], decodes it, and writes the bytes to argv[2].

We test it by running it as a subprocess with valid and invalid inputs.
"""

from __future__ import annotations

import base64
import subprocess
import sys
from pathlib import Path

import pytest


_WRITER = (
    Path(__file__).resolve().parent.parent / "services" / "_writer.py"
)


class TestWriterScript:
    def test_writes_decoded_bytes_to_output(self, tmp_path):
        """Lines 1-6: encode content, write to input file, run script, verify output."""
        content = b"hello from writer script test"
        encoded = base64.b64encode(content).decode()

        input_file = tmp_path / "input.b64"
        input_file.write_text(encoded, encoding="utf-8")

        output_file = tmp_path / "output.bin"

        result = subprocess.run(
            [sys.executable, str(_WRITER), str(input_file), str(output_file)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert output_file.exists()
        assert output_file.read_bytes() == content
        assert str(output_file.stat().st_size) in result.stdout

    def test_writes_binary_content(self, tmp_path):
        """Binary data (non-text) is written correctly."""
        content = bytes(range(256))
        encoded = base64.b64encode(content).decode()

        input_file = tmp_path / "bin_input.b64"
        input_file.write_text(encoded, encoding="utf-8")
        output_file = tmp_path / "bin_output.bin"

        result = subprocess.run(
            [sys.executable, str(_WRITER), str(input_file), str(output_file)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert output_file.read_bytes() == content

    def test_output_size_reported(self, tmp_path):
        """The script prints 'Written N bytes to <path>'."""
        content = b"size check"
        encoded = base64.b64encode(content).decode()

        input_file = tmp_path / "size.b64"
        input_file.write_text(encoded, encoding="utf-8")
        output_file = tmp_path / "size.out"

        result = subprocess.run(
            [sys.executable, str(_WRITER), str(input_file), str(output_file)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Written" in result.stdout
        assert "bytes" in result.stdout
        assert str(len(content)) in result.stdout

    def test_missing_argv_raises(self):
        """Running without arguments fails with a non-zero exit code."""
        result = subprocess.run(
            [sys.executable, str(_WRITER)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
