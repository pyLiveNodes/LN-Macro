from livenodes.node import Node
from collections import namedtuple
from livenodes.components.port import Port

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

    def _settings(self):
        return {"path": self.path, "name": self.name}

    def add_input(self,
                  emit_node: 'Connectionist',
                  emit_port: Port,
                  recv_port: Port):
        # Retrieve the appropriate node from self.in_map using recv_port
        mapped_node, _, mapped_port = self.own_in_port_to_ref.get(recv_port)
        
        # Ensure that the mapped_node is not None
        if mapped_node is None:
            raise ValueError(f"No node found in in_map for recv_port: {recv_port}")
        
        # Call super().add_input() with the mapped node
        return super(mapped_node.__class__, mapped_node).add_input(emit_node, emit_port, mapped_port)

    @staticmethod
    def all_ports_sub_nodes(nodes, ret_in = True):
        return [(n, port_name, port_value) for n in nodes for (port_name, port_value) in (n.ports_in if ret_in else n.ports_out)._asdict().items()]

    def __new__(cls, path=f"{file_path}/noop.yml", name=None, compute_on="", **kwargs):
        pl = Node.load(path)
        nodes = pl.sort_discovered_nodes(pl.discover_graph(pl))

        for n in nodes:
            n.compute_on = compute_on

        in_ports = cls.all_ports_sub_nodes(nodes, ret_in=True)
        out_ports = cls.all_ports_sub_nodes(nodes, ret_in=True)
        
        # the name of a node is always unique in a graph, so we can use it as a key
        in_fields_names, in_field_defaults = zip(*[(f"{n.name}_{port_name}", port_value) for (n, port_name, port_value) in in_ports])
        out_fields_names, out_field_defaults = zip(*[(f"{n.name}_{port_name}", port_value) for (n, port_name, port_value) in out_ports])

        own_in_port_to_ref = {f"{n.name}_{port_name}": (n, port_name, port_value) for (n, port_name, port_value) in in_ports}
        own_out_port_to_ref = {f"{n.name}_{port_name}": (n, port_name, port_value) for (n, port_name, port_value) in out_ports}

        new_cls = super(Macro, cls).__new__(cls)
        new_cls.ports_in = namedtuple('Macro_Ports_In', in_fields_names)(**dict(zip(in_fields_names, in_field_defaults)))
        new_cls.ports_out = namedtuple('Macro_Ports_Out', out_fields_names)(** dict(zip(out_fields_names, out_field_defaults)))
        new_cls.pl = pl
        new_cls.nodes = nodes
        new_cls.own_in_port_to_ref = own_in_port_to_ref
        new_cls.own_out_port_to_ref = own_out_port_to_ref

        return new_cls

if __name__ == '__main__':
    m = Macro('../tests/test.yml')
    print(m.ports_in)