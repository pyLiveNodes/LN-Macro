from livenodes import Node, Ports_collection
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

    @staticmethod
    def _encode_node_port(node, port_name):
        return f"{node.name}_{port_name}"
    
    @property
    def node_macro_id_suffix(self):
        return f"[[m:{id(self)}]]"

    def __new__(cls, path=f"{file_path}/noop.yml", name=None, compute_on="", **kwargs):
        pl = Node.load(path)
        nodes = pl.sort_discovered_nodes(pl.discover_graph(pl))
        
        # Set the compute_on attribute for all nodes 
        for n in nodes:
            n.compute_on = compute_on

        # --- Match Ports ----------------
        # Initialize lists for field names and defaults
        in_field_names, in_field_defaults = [], []
        out_field_names, out_field_defaults = [], []
        own_in_port_to_ref, own_out_port_to_ref = {}, {}

        # Populate the lists using classic for loops
        for n, port_name, port_value in cls.all_ports_sub_nodes(nodes, ret_in=True):
            # port_value.label = f"{n.name}: {port_value.label}"
            in_field_names.append(cls._encode_node_port(n, port_name))
            in_field_defaults.append(port_value)
            own_in_port_to_ref[cls._encode_node_port(n, port_name)] = (n, port_name, port_value)
            
        for n, port_name, port_value in cls.all_ports_sub_nodes(nodes, ret_in=True):
            # port_value.label = f"{n.name}: {port_value.label}"
            out_field_names.append(cls._encode_node_port(n, port_name))
            out_field_defaults.append(port_value)
            own_out_port_to_ref[cls._encode_node_port(n, port_name)] = (n, port_name, port_value)


        # --- Create new (sub) class ----------------
        new_cls = super(Macro, cls).__new__(cls)
        new_cls.ports_in = type('Macro_Ports_In', (Ports_collection,), dict(zip(in_field_names, in_field_defaults)))()
        new_cls.ports_out = type('Macro_Ports_Out', (Ports_collection,), dict(zip(out_field_names, out_field_defaults)))()
        new_cls.pl = pl
        new_cls.nodes = nodes
        new_cls.own_in_port_to_ref = own_in_port_to_ref
        new_cls.own_out_port_to_ref = own_out_port_to_ref


        # --- Patch Settings / Serialization ----------------
        # There are two main thoughts: (1) how to patch inputs into the macro and (2) how to patch nodes the macro inputs to (ie macros output)
        # (1) The idea for inputs is to replace the compact_settings method of each node with a method that just returns the macro nodes settings
        #   because the to_compact_dict method used for serialization overwrites nodes with the same str(node) (which should not occur, as each name must be unique in the graph) we can use that
        #   to just return the settings of the macro node over and over and not worrying about duplicates in the serialized output
        #   however, this is not the case for inputs, as they use inputs.extend() and thus we should only return those once
        # (2) The idea for outputs is to overwrite the serialize_compact method of their connection classes to return the macro instead of the sub-graph nodes
        #   This happens by overwriting the add_output method of the sub-graph nodes
        def compact_settings_no_inputs(self):
            config = macro.get_settings().get('settings', {})
            return config, []

        def compact_settings(self):
            config = macro.get_settings().get('settings', {})
            inputs = [
                inp.serialize_compact() for inp in macro.input_connections
            ]
            return config, inputs

        for n in nodes:
            # set a unique name for each node, so that it is not changed during connection into any existing graph
            # NOTE: we set this here as we don't want the suffix to bleed into the port names etc
            #    only for keeping the node name unique within the subgraph and the serialized graph
            #    TODO: double check if this results in any issues down the road
            n.name = f"{n.name}{new_cls.node_macro_id_suffix}"
            n.compact_settings = compact_settings_no_inputs.__get__(n, n.__class__)
        # As no connections within the subgraph are changed, all subgraph nodes that are loaded will also be present in the serialized graph
        # Thus we can just select the first one to also return the inputs of our macro node
        nodes[0].compact_settings = compact_settings.__get__(n, n.__class__)

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
        new_cls = self
        def serialize_compact(self):
            nonlocal new_cls
            # the str(self._emit_node) should not change, since neither the class nor the name of the node are accessible to the user
            # except, that the name might be changed by the system if str(node) is not unique in the graph
            #   -> we could prefix the node name with the macro name
            #   -> but the macro name is only truly set after the macro is created and connected to the subgraph
            #   -> is there a better unique prefix, that we know not yet exists in a graph?
            #   -> here the cat bites it's own tail... =
            #   => change the nodes name, rather than the macro's name
            return f"{str(new_cls)}.{new_cls._encode_node_port(self._emit_node, self._emit_port.key).replace(new_cls.node_macro_id_suffix, '')} -> {str(self._recv_node)}.{str(self._recv_port.key)}"

        # mapped_node = connection._emit_node
        mapped_node, mapped_port = self.__get_correct_node(connection._emit_port, io='out')
        connection._emit_node = mapped_node
        connection._emit_port = mapped_port
        connection.serialize_compact = serialize_compact.__get__(connection, connection.__class__)
        super(mapped_node.__class__, mapped_node)._add_output(connection)

    def remove_all_inputs(self):
        for n in self.nodes:
            # TODO: this is actually wrong, as all subgraphs would unform...
            n.remove_all_inputs()
    
    def remove_input_by_connection(self, connection):
        # mapped_node = connection._emit_node
        mapped_node, mapped_port = self.__get_correct_node(connection._recv_port, io='in')
        connection._recv_node = mapped_node
        connection._recv_port = mapped_port
        super(mapped_node.__class__, mapped_node).remove_input_by_connection(connection)

if __name__ == '__main__':
    # m = Macro(path=Macro.example_init["path"]) 
    # print(m.ports_in)

    from livenodes import Graph
    from livenodes_io_python.in_python import In_python
    from livenodes_io_python.out_python import Out_python
    import numpy as np

    d = [100]
    in_python = In_python(data=d)
    macro = Macro(path=Macro.example_init["path"])
    # print(macro.ports_in.Noop_any.key, macro.ports_out.Noop_any.key)
    macro.add_input(in_python, emit_port=in_python.ports_out.any, recv_port=macro.ports_in.Noop_any)
    # print(macro.ports_in.Noop_any.key, macro.ports_out.Noop_any.key)
    # macro.remove_all_inputs()
    out_python = Out_python() 
    # print(macro.ports_in.Noop_any.key, macro.ports_out.Noop_any.key)
    out_python.add_input(macro, emit_port=macro.ports_out.Noop_any, recv_port=out_python.ports_in.any)

    # g = Graph(start_node=in_python)
    # g.start_all()
    # g.join_all()
    # g.stop_all()

    # np.testing.assert_equal(np.array(out_python.get_state()), np.array(d))

    print(in_python.to_compact_dict(graph=True))
    print('Done')