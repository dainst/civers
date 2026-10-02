"""Configuration consumers do not need optional network transports installed."""

import subprocess
import sys


def test_configuration_import_without_optional_transports():
    code = '''
import importlib.abc
import sys
class BlockOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] in {'fastapi', 'uvicorn', 'aiokafka'}:
            raise ImportError(f'Optional dependency unavailable: {fullname}')
sys.meta_path.insert(0, BlockOptional())
import civers_common
from civers_common import *
from civers_common.transport.cli import CliTransport
assert all(hasattr(civers_common, name) for name in civers_common.__all__)
'''
    subprocess.run([sys.executable, '-c', code], check=True, capture_output=True, text=True)
