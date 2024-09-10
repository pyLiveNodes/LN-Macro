import numpy as np
import logging

logging.basicConfig(level=logging.DEBUG)

from livenodes import Graph

from ln_macro.macro import Macro

def run_single_test(data):
    in_python = In_python(data=data)

    out_python = Out_python()
    out_python.add_input(in_python, emit_port=in_python.ports_out.any, recv_port=out_python.ports_in.any)

    g = Graph(start_node=in_python)
    g.start_all()
    g.join_all()
    g.stop_all()

    actual = np.array(out_python.get_state())

    np.testing.assert_equal(data, actual)


class TestProcessing:

    def test_list(self):
        run_single_test(list(range(100)))

    def test_numpy_1D(self):
        run_single_test(np.arange(100))

    def test_numpy_2D(self):
        run_single_test(np.arange(100).reshape((20, 5)))

    def test_numpy_2D_nested_axis_0(self):
        run_single_test(np.arange(100).reshape((1, 20, 5)))

    def test_numpy_2D_nested_axis_1(self):
        run_single_test(np.arange(100).reshape((20, 1, 5)))

    def test_numpy_2D_nested_axis_2(self):
        run_single_test(np.arange(100).reshape((20, 5, 1)))

    def test_numpy_3D(self):
        run_single_test(np.arange(100).reshape((2, 10, 5)))

    def test_large(self):
        run_single_test(np.arange(1000000).reshape((1000, -1)))
