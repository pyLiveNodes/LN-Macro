from livenodes.node import Node
from collections import namedtuple
from livenodes.components.port import Port, Ports_collection

import pathlib
file_path = pathlib.Path(__file__).parent.resolve()

class Macro(Node, abstract_class=True):
    category = "Data Source"
    description = ""

    example_init = {
        "path": f"{file_path}/noop.yml",
        "name": "Macro",
    }

    def __init__(self, path, name=None, **kwargs):
        if name is None:
            name = f'Macro: {path.split('/')[-1].split('.')[-2]}'
        super().__init__(name, **kwargs)

        self.path = path

    @staticmethod
    def all_ports_sub_nodes(nodes, ret_in = True):
        return [(n, port_name, port_value) for n in nodes for (port_name, port_value) in (n.ports_in if ret_in else n.ports_out)._asdict().items()]

    def __new__(cls, path=f"{file_path}/noop.yml", name=None, compute_on="", **kwargs):
        pl = Node.load(path)
        nodes = pl.sort_discovered_nodes(pl.discover_graph(pl))

        for n in nodes:
            n.compute_on = compute_on

        # Initialize lists for field names and defaults
        in_field_names, in_field_defaults = [], []
        out_field_names, out_field_defaults = [], []
        own_in_port_to_ref, own_out_port_to_ref = {}, {}

        # Populate the lists using classic for loops
        for n, port_name, port_value in cls.all_ports_sub_nodes(nodes, ret_in=True):
            # port_value.label = f"{n.name}: {port_value.label}"
            in_field_names.append(f"{n.name}_{port_name}")
            in_field_defaults.append(port_value)
            own_in_port_to_ref[f"{n.name}_{port_name}"] = (n, port_name, port_value)
            
        for n, port_name, port_value in cls.all_ports_sub_nodes(nodes, ret_in=True):
            # port_value.label = f"{n.name}: {port_value.label}"
            out_field_names.append(f"{n.name}_{port_name}")
            out_field_defaults.append(port_value)
            own_out_port_to_ref[f"{n.name}_{port_name}"] = (n, port_name, port_value)

        new_cls = super(Macro, cls).__new__(cls)
        new_cls.ports_in = type('Macro_Ports_In', (Ports_collection,), dict(zip(in_field_names, in_field_defaults)))()
        new_cls.ports_out = type('Macro_Ports_Out', (Ports_collection,), dict(zip(out_field_names, out_field_defaults)))()
        new_cls.pl = pl
        new_cls.nodes = nodes
        new_cls.own_in_port_to_ref = own_in_port_to_ref
        new_cls.own_out_port_to_ref = own_out_port_to_ref

        return new_cls
    
    def _settings(self):
        return {"path": self.path, "name": self.name}

    def __get_correct_node(self, port, io='in'):
        # Retrieve the appropriate node from self.in_map using recv_port
        if io == 'in':
            mapped_node, _, mapped_port = self.own_in_port_to_ref.get(port.key)
        elif io == 'out':
            mapped_node, _, mapped_port = self.own_out_port_to_ref.get(port.key)
        else:
            raise ValueError(f"Invalid io: {io}")
        
         # Ensure that the mapped_node is not None
        if mapped_node is None:
            raise ValueError(f"No node found in in_map for recv_port: {port}")
        
        return mapped_node, mapped_port

    def add_input(self, emit_node, emit_port, recv_port):
        # Retrieve the appropriate node from self.in_map using recv_port
        mapped_node, mapped_port = self.__get_correct_node(recv_port, io='in')
        # Call super().add_input() with the mapped node
        super(mapped_node.__class__, mapped_node).add_input(emit_node, emit_port, mapped_port)

    def _add_output(self, connection):
        # mapped_node = connection._emit_node
        mapped_node, mapped_port = self.__get_correct_node(connection._emit_port, io='out')
        connection._emit_node = mapped_node
        connection._emit_port = mapped_port
        super(mapped_node.__class__, mapped_node)._add_output(connection)


if __name__ == '__main__':
    m = Macro(path=Macro.example_init["path"]) 
    print(m.ports_in)

    from livenodes import Graph
    from livenodes_io_python.in_python import In_python
    from livenodes_io_python.out_python import Out_python
    import numpy as np

    d = [100]
    in_python = In_python(data=d)
    # e.g. if this is here the following will run, but all ports are named "Noop_any" and the test will fail
    # if the lines is moved after macro.add_input() there is an error, as then all ports are named "any"
    # ...
    macro = Macro(path=Macro.example_init["path"])
    print(macro.ports_in.Noop_any.key, macro.ports_out.Noop_any.key)
    macro.add_input(in_python, emit_port=in_python.ports_out.any, recv_port=macro.ports_in.Noop_any)
    print(macro.ports_in.Noop_any.key, macro.ports_out.Noop_any.key)
    out_python = Out_python() # <- this line in combination with the usage of super() seems to be the issue
    print(macro.ports_in.Noop_any.key, macro.ports_out.Noop_any.key)
    out_python.add_input(macro, emit_port=macro.ports_out.Noop_any, recv_port=out_python.ports_in.any)

    g = Graph(start_node=in_python)
    g.start_all()
    g.join_all()
    g.stop_all()

    np.testing.assert_equal(np.array(out_python.get_state()), np.array(d))
