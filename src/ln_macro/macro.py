from livenodes.node import Node
from livenodes import REGISTRY

from collections import namedtuple
# from typing import NamedTuple

# class Ports_BTS_data(NamedTuple):
#     data: Port_BTS_Number = Port_BTS_Number("Data")

# collections.namedtuple('Employee', ['name', 'id'])

from livenodes_common_ports.ports import Ports_empty

class Macro(Node, abstract_class=True):
    category = "Data Source"
    description = ""

    example_init = {
        "path": "path/to/macro.yml",
        "name": "Macro",
    }

    def __init__(self, path, name=None, **kwargs):
        print('call to __init__')
        if name is None:
            name = f'Macro: {path.split('/')[-1].split('.')[-2]}'
        super().__init__(name, **kwargs)

        self.path = path
        self.pl = Node.load(path)

    def _settings(self):
        # TODO: figure out if this is deserialized correctly or throws an error
        return {"path": self.path, "name": self.name}

    def process(self, *args, **kwargs):
        # big todo here
        # there should probably not be a process method here, but rather we should rewrite the on_connect (or similar, need to look that up) to connect to the subnodes instead
        return self.pl.process(data, **kwargs)

    def __new__(cls, path, name=None, **kwargs):
        print('call to macro new')

        pl = Node.load(path)
        nodes = [n for n in pl.sort_discovered_nodes(pl.discover_graph(pl))]
        
        # the name of a node is always unique, so we can use it as a key
        in_fields_names, in_field_defaults = zip(*[(f"{n.name}_{port_name}", port_value) for n in nodes for (port_name, port_value) in n.ports_in._asdict().items()])
        ports_in = namedtuple('Macro_Ports_In', in_fields_names, defaults=in_field_defaults)
        
        # the name of a node is always unique, so we can use it as a key
        out_fields_names, out_field_defaults = zip(*[(f"{n.name}_{port_name}", port_value) for n in nodes for (port_name, port_value) in n.ports_out._asdict().items()])
        ports_out = namedtuple('Macro_Ports_Out', out_fields_names, defaults=out_field_defaults)

        # new_cls = type("Macro", (cls,), dict(ports_in=Ports_empty(), ports_out=Ports_empty()))
        # # REGISTRY.node.register(name, new_cls)
        # return new_cls(name=name, path=path, **kwargs)
        new_cls = super(Macro, cls).__new__(cls)
        new_cls.ports_in = Ports_empty()
        new_cls.ports_out = Ports_empty()
        # new_cls.path = path

        return new_cls

    def process(self, data, **kwargs):
        return super().process(data, **kwargs)


if __name__ == '__main__':
    m = Macro('test.yml')
    print(m.ports_in)