import numpy as np
import logging

logging.basicConfig(level=logging.DEBUG)

from livenodes import Graph
from livenodes_io_python.in_python import In_python
from livenodes_io_python.out_python import Out_python
from ln_macro.macro import Macro

def run_single_test(data):
    in_python = In_python(data=data)
    macro = Macro()
    macro.add_input(in_python, emit_port=in_python.ports_out.any, recv_port=macro.ports_in.Noop_any)
    out_python = Out_python()
    out_python.add_input(macro, emit_port=macro.ports_out.Noop_any, recv_port=out_python.ports_in.any)

    g = Graph(start_node=in_python)
    g.start_all()
    g.join_all()
    g.stop_all()

    actual = np.array(out_python.get_state())

    np.testing.assert_equal(data, actual)


class TestProcessing:

    def test_loadable(self):
        Macro()

    def test_connectable_input(self):
        in_python = In_python(data=[100])
        macro = Macro()
        macro.add_input(in_python, emit_port=in_python.ports_out.any, recv_port=macro.ports_in.Noop_any)

    def test_connectable(self):
        in_python = In_python(data=[100])
        macro = Macro()
        macro.add_input(in_python, emit_port=in_python.ports_out.any, recv_port=macro.ports_in.Noop_any)
        out_python = Out_python()
        out_python.add_input(macro, emit_port=macro.ports_out.Noop_any, recv_port=out_python.ports_in.any)

    def test_deconnectable(self):
        in_python = In_python(data=[100])
        macro = Macro()
        macro.add_input(in_python, emit_port=in_python.ports_out.any, recv_port=macro.ports_in.Noop_any)
        out_python = Out_python()
        out_python.add_input(macro, emit_port=macro.ports_out.Noop_any, recv_port=out_python.ports_in.any)

        macro.remove_all_inputs()
        out_python.remove_all_inputs()

    def test_list(self):
        run_single_test(list(range(100)))

    def test_numpy_1D(self):
        run_single_test(np.arange(100))

    def test_numpy_2D(self):
        run_single_test(np.arange(100).reshape((20, 5)))
