import glob
from os.path import dirname, basename, isfile, join
from importlib.metadata import entry_points

import pytest


@pytest.fixture
def discovered_modules():
    exclude = ['__init__', 'utils', 'ports']
    modules = glob.glob(join(dirname(__file__), '../src/livenodes_io_python/', "*.py"))
    names = [basename(f)[:-3] for f in modules if isfile(f)]
    return [f for f in names if not f in exclude]


class TestProcessing:
    def test_modules_discoverable(self, discovered_modules):
        assert len(discovered_modules) > 0

    def test_all_declared(self, discovered_modules):
        livenodes_entrypoints = [x.name for x in entry_points()['livenodes.nodes']]

        print(set(discovered_modules).difference(set(livenodes_entrypoints)))
        assert set(discovered_modules) <= set(livenodes_entrypoints)

    def test_loads_class(self):
        in_python = [x.load() for x in entry_points()['livenodes.nodes'] if x.name == 'in_python'][0]
        from ln_macro.in_python import In_python

        assert in_python == In_python

    def test_all_loadable(self):
        for x in entry_points()['livenodes.nodes']:
            x.load()
