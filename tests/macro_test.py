import numpy as np
import logging

logging.basicConfig(level=logging.DEBUG)

from livenodes import Graph
from livenodes_io_python.in_python import In_python
from livenodes_io_python.out_python import Out_python
from ln_macro import Macro, Noop

def run_single_test(data):
    in_python = In_python(data=data)
    macro = Macro(path=Macro.example_init["path"])
    macro.add_input(in_python, emit_port=in_python.ports_out.any, recv_port=macro.ports_in.Noop_any)
    out_python = Out_python()
    out_python.add_input(macro, emit_port=macro.ports_out.Noop_any, recv_port=out_python.ports_in.any)

    g = Graph(start_node=in_python)
    g.start_all()
    g.join_all()
    g.stop_all()

    np.testing.assert_equal(np.array(data), np.array(out_python.get_state()))


class TestProcessing:

    def test_noop(self):
        d = [100]
        in_python = In_python(data=d)
        noop = Noop()
        noop.add_input(in_python, emit_port=in_python.ports_out.any, recv_port=noop.ports_in.any)
        out_python = Out_python()
        out_python.add_input(noop, emit_port=noop.ports_out.any, recv_port=out_python.ports_in.any)

        g = Graph(start_node=in_python)
        g.start_all()
        g.join_all()
        g.stop_all()

        np.testing.assert_equal(d, out_python.get_state())

    def test_loadable(self):
        Macro(path=Macro.example_init["path"])

    def test_connectable_input(self):
        in_python = In_python(data=[100])
        macro = Macro(path=Macro.example_init["path"])
        macro.add_input(in_python, emit_port=in_python.ports_out.any, recv_port=macro.ports_in.Noop_any)

    def test_connectable(self):
        in_python = In_python(data=[100])
        macro = Macro(path=Macro.example_init["path"])
        macro.add_input(in_python, emit_port=in_python.ports_out.any, recv_port=macro.ports_in.Noop_any)
        out_python = Out_python()
        out_python.add_input(macro, emit_port=macro.ports_out.Noop_any, recv_port=out_python.ports_in.any)

    def test_deconnectable(self):
        in_python = In_python(data=[100])
        macro = Macro(path=Macro.example_init["path"])
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
