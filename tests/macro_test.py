import numpy as np
import logging

logging.basicConfig(level=logging.DEBUG)

from livenodes import Graph, Node
from ln_io_python.in_python import In_python
from ln_io_python.out_python import Out_python
from ln_macro import Macro, Noop, MacroHelper
import yaml

def build_pipeline(data=[100]):
    in_python = In_python(data=data)
    macro = Macro(path=Macro.example_init["path"])
    macro.add_input(in_python, emit_port=in_python.ports_out.any, recv_port=macro.ports_in.Noop_any)
    out_python = Out_python()
    out_python.add_input(macro, emit_port=macro.ports_out.Noop2_any, recv_port=out_python.ports_in.any)

    return in_python, macro, out_python

def run_single_test(data):
    in_python, macro, out_python = build_pipeline(data)

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
        a = Macro(path=Macro.example_init["path"])
        assert isinstance(a, MacroHelper)
        assert str(a) == 'Macro:noop [Macro:noop]'

    def test_port_context(self):
        a = Macro(path=Macro.example_init["path"])
        assert len(a.ports_in) == 2
        assert len(a.ports_out) == 2
        assert a.ports_in.Noop_any.key == "Noop_any"
        assert a.ports_in.Noop_any.label == "Noop: Any"
        assert a.nodes[0].ports_in.any.key == "any"

    def test_connectable_input(self):
        in_python = In_python(data=[100])
        macro = Macro(path=Macro.example_init["path"])
        macro.add_input(in_python, emit_port=in_python.ports_out.any, recv_port=macro.ports_in.Noop_any)
        
        assert not in_python.provides_input_to(macro), 'Macro itself should never be connected, as it\'s not processing anything'
        assert in_python.provides_input_to(macro.nodes[0]), 'Input should be connected to the only node in macro'

    def test_deconnectable_all(self):
        in_python, macro, out_python = build_pipeline()
        assert not in_python.provides_input_to(macro), 'Macro itself should never be connected, as it\'s not processing anything'
        assert in_python.provides_input_to(macro.nodes[0]), 'Input should be connected to the only node in macro'
        assert macro.nodes[1].provides_input_to(out_python), 'Input should be connected to the only node in macro'

        macro.remove_all_inputs()
        out_python.remove_all_inputs()
        assert not in_python.provides_input_to(macro), 'Macro itself should never be connected, as it\'s not processing anything'
        assert not in_python.provides_input_to(macro.nodes[0]), 'Input should not be connected to the only node in macro anymore since we removed that connection'
        assert not macro.provides_input_to(out_python), 'Macro should not be connected to output anymore'
        assert not macro.nodes[1].provides_input_to(out_python), 'Node in macro should not be connected to output anymore'

    def test_deconnectable_specific(self):
        in_python, macro, out_python = build_pipeline()
        assert not in_python.provides_input_to(macro), 'Macro itself should never be connected, as it\'s not processing anything'
        assert in_python.provides_input_to(macro.nodes[0]), 'Input should be connected to the only node in macro'
        assert macro.nodes[1].provides_input_to(out_python), 'Input should be connected to the only node in macro'

        macro.remove_input(emit_node=in_python, emit_port=in_python.ports_out.any, recv_port=macro.ports_in.Noop_any)
        out_python.remove_input(emit_node=macro, emit_port=macro.ports_out.Noop2_any, recv_port=out_python.ports_in.any)
        assert not in_python.provides_input_to(macro), 'Macro itself should never be connected, as it\'s not processing anything'
        assert not in_python.provides_input_to(macro.nodes[0]), 'Input should not be connected to the only node in macro anymore since we removed that connection'
        assert not macro.provides_input_to(out_python), 'Macro should not be connected to output anymore'
        assert not macro.nodes[1].provides_input_to(out_python), 'Node in macro should not be connected to output anymore'



    def test_using_constructor_of_created(self):
        a = Macro(path=Macro.example_init["path"])
        assert len(a.ports_out) == 2
        assert a.ports_in.Noop_any.key == "Noop_any"

        b = a.__class__(path=Macro.example_init["path"])
        assert len(b.ports_out) == 2
        assert b.ports_in.Noop_any.key == "Noop_any"

    def test_unique_name_on_connect(self):
        in_python, macro, out_python = build_pipeline([100])
        macro2 = Macro(path=Macro.example_init["path"])
        macro2.add_input(in_python, emit_port=in_python.ports_out.any, recv_port=macro2.ports_in.Noop_any)
        assert macro2.name != macro.name

    def test_unique_name_on_set(self):
        in_python, macro, out_python = build_pipeline([100])
        macro2 = Macro(path=Macro.example_init["path"])
        macro2.add_input(in_python, emit_port=in_python.ports_out.any, recv_port=macro2.ports_in.Noop_any)
        assert macro2.name != macro.name
        macro2._set_attr(name=macro.name)
        assert macro2.name != macro.name
        assert in_python.provides_input_to(macro.nodes[0])
        assert in_python.provides_input_to(macro2.nodes[0])

    def test_chain(self):
        in_python, macro, out_python = build_pipeline([100])
        macro2 = macro.__class__(path=Macro.example_init["path"])
        macro2.add_input(macro, emit_port=macro.ports_out.Noop2_any, recv_port=macro2.ports_in.Noop_any)
        assert macro2.name != macro.name
        assert str(macro.nodes[1]) != str(macro2.nodes[0])
        assert in_python.provides_input_to(macro.nodes[0])
        assert in_python.provides_input_to(macro2.nodes[0])
        
        macro2._set_attr(name=macro.name)
        assert macro2.name != macro.name

        dct = in_python.to_compact_dict(graph=True)
        assert set(dct['Inputs']) == set(['Python Input [In_python].any -> Macro:noop [Macro].Noop_any', 
            'Macro:noop [Macro].Noop2_any -> Python Output [Out_python].any',
            'Macro:noop [Macro].Noop2_any -> Macro:noop_1 [Macro].Noop_any'])
        
        macro2.remove_input(emit_node=macro, emit_port=macro.ports_out.Noop2_any, recv_port=macro2.ports_in.Noop_any)
        assert not in_python.provides_input_to(macro2.nodes[0])

    def test_list(self):
        run_single_test(list(range(100)))

    def test_numpy_1D(self):
        run_single_test(np.arange(100))

    def test_numpy_2D(self):
        run_single_test(np.arange(100).reshape((20, 5)))

    def test_serialize(self):
        in_python, macro, out_python = build_pipeline()
        dct = in_python.to_compact_dict(graph=True)
        print(dct)
        assert list(sorted(dct['Nodes'].keys())) == ['Macro:noop [Macro]', 'Python Input [In_python]', 'Python Output [Out_python]']
        assert dct['Inputs'][1] == 'Python Input [In_python].any -> Macro:noop [Macro].Noop_any'
        assert dct['Inputs'][0] == 'Macro:noop [Macro].Noop2_any -> Python Output [Out_python].any'

        serialized_output = yaml.dump(dct, allow_unicode=True)
        assert '[Macro]' in serialized_output
        assert '[Noop]' not in serialized_output

    def test_serialize_directly(self):
        macro = Macro(path=Macro.example_init["path"])
        dct = macro.to_compact_dict(graph=True)
        print(dct)

        serialized_output = yaml.dump(dct, allow_unicode=True)
        assert '[Macro]' in serialized_output
        

    def test_deserialize(self):
        data = [100]
        # double check the graph is working in the first place
        in_python, macro, out_python = build_pipeline(data)
        g = Graph(start_node=in_python)
        g.start_all()
        g.join_all()
        g.stop_all()
        np.testing.assert_equal(np.array(data), np.array(out_python.get_state()))

        # now serialize and deserialize and check if still working
        s = Node.from_compact_dict(in_python.to_compact_dict(graph=True))
        s.data = data
        g = Graph(start_node=s)
        g.start_all()
        g.join_all()
        g.stop_all()
        # TODO: update this once https://gitlab.csl.uni-bremen.de/livenodes/livenodes/-/issues/57 is merged
        assert isinstance(s, In_python)
        n1 = s.output_connections[0]._recv_node
        assert isinstance(n1, Noop)
        n2 = n1.output_connections[0]._recv_node
        assert isinstance(n2, Noop)
        o = n2.output_connections[0]._recv_node
        assert isinstance(o, Out_python)
        np.testing.assert_equal(np.array(data), np.array(o.get_state()))



    def test_compute_on(self):
        macro = Macro(path=Macro.example_init["path"], compute_on="1:2")
        assert macro.compute_on == "1:2"
        assert len(macro.nodes) > 0
        for n in macro.nodes:
            assert n.compute_on == "1:2"
    
