from livenodes.node import Node
from collections import namedtuple
from livenodes.components.port import Port

class Macro(Node, abstract_class=True):
    category = "Data Source"
    description = ""

    example_init = {
        "path": "path/to/macro.yml",
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
        mapped_node = self.in_map.get(recv_port)
        
        # Ensure that the mapped_node is not None
        if mapped_node is None:
            raise ValueError(f"No node found in in_map for recv_port: {recv_port}")
        
        # Call super().add_input() with the mapped node
        return super(mapped_node.__class__, mapped_node).add_input(emit_node, emit_port, recv_port)

    def __new__(cls, path, name=None, **kwargs):
        pl = Node.load(path)
        nodes = [n for n in pl.sort_discovered_nodes(pl.discover_graph(pl))]
        
        # the name of a node is always unique in a graph, so we can use it as a key
        in_fields_names, in_field_defaults = zip(*[(f"{n.name}_{port_name}", port_value) for n in nodes for (port_name, port_value) in n.ports_in._asdict().items()])
        out_fields_names, out_field_defaults = zip(*[(f"{n.name}_{port_name}", port_value) for n in nodes for (port_name, port_value) in n.ports_out._asdict().items()])

        in_map = dict(zip(in_fields_names, in_field_defaults))
        out_map = dict(zip(out_fields_names, out_field_defaults))

        new_cls = super(Macro, cls).__new__(cls)
        new_cls.ports_in = namedtuple('Macro_Ports_In', in_fields_names)(**in_map)
        new_cls.ports_out = namedtuple('Macro_Ports_Out', out_fields_names)(**out_map)
        new_cls.pl = pl
        new_cls.nodes = nodes
        new_cls.in_map = in_map
        new_cls.out_map = out_map

        return new_cls

    def process(self, data, **kwargs):
        return super().process(data, **kwargs)


if __name__ == '__main__':
    m = Macro('test.yml')
    print(m.ports_in)