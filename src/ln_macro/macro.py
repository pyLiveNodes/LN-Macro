from livenodes import Node, Ports_collection, Connection
from ln_ports import Ports_empty

import pathlib
file_path = pathlib.Path(__file__).parent.resolve()

class MacroHelper(Node, abstract_class=True):
    category = "Meta"
    description = ""

    ports_in = Ports_empty()
    ports_out = Ports_empty()

    example_init = {
        "path": f"{file_path}/noop.yml",
        "name": "Macro",
    }

    def __init__(self, path, name=None, **kwargs):
        name = self.name(name, path)
        super().__init__(name, **kwargs)

        self.path = path

    @staticmethod
    def name(name, path):
        if name is not None:
            return name
        return f"Macro:{path.split('/')[-1].split('.')[-2]}"

    @staticmethod
    def all_ports_sub_nodes(nodes, ret_in = True):
        return [(n, port_name, port_value) for n in nodes for (port_name, port_value) in (n.ports_in if ret_in else n.ports_out)._asdict().items()]

    @staticmethod
    def _encode_node_port(node, port_name):
        return f"{node.name}_{port_name}"
    
    @property
    def node_macro_id_suffix(self):
        return f"[[m:{id(self)}]]"
    
    def _settings(self):
        return {"path": self.path, "name": self.name}
    
    ## TODO: this is an absolute hack, but follows the current livenodes implementation
    def _set_attr(self, **kwargs):
        # make sure the names are unique when being set
        if 'name' in kwargs:
            node_list = self.discover_graph_incl_macros(self)
            if not self.is_unique_name(kwargs['name'], node_list=node_list):
                kwargs['name'] = self.create_unique_name(kwargs['name'], node_list=node_list)

        # set values (again, we need a more specific idea of how node states and setting changes should look like!)
        for key, val in kwargs.items():
            setattr(self, key, val)

        # return the finally set values (TODO: should this be explizit? or would it be better to expect that params might not by finally set as passed?)
        return kwargs

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
    
    @staticmethod
    def discover_graph_incl_macros(node, direction='both', sort=True):
        if isinstance(node, MacroHelper):
            node = node.nodes[0]
        nodes = node.discover_graph(node, direction=direction, sort=sort)
        for n in nodes:
            if hasattr(n, '_macro_parent'):
                nodes.append(n._macro_parent)
        return node.remove_discovered_duplicates(nodes)
        
    def add_input(self, emit_node, emit_port, recv_port):
        # Retrieve the appropriate node from self.in_map using recv_port
        mapped_node, mapped_port = self.__get_correct_node(recv_port, io='in')
        # Call super().add_input() with the mapped node
        super(mapped_node.__class__, mapped_node).add_input(emit_node, emit_port, mapped_port)

        node_list = self.discover_graph_incl_macros(mapped_node)
        if not self.is_unique_name(self.name, node_list=node_list):
            new_name = self.create_unique_name(self.name, node_list=node_list)
            self.warn(f"{str(self)} not unique in new graph. Renaming Node to: {new_name}")
            self._set_attr(name=new_name)

    def _serialize_name(self):
        return str(self).replace(f'[{self.__class__.__name__}]', '[Macro]')

    def _add_output(self, connection):
        new_obj = self
        def map_fn(con):
            nonlocal new_obj
            if con._emit_node is new_obj:
                mapped_node, mapped_port = new_obj.__get_correct_node(con._emit_port, io='out')
                con._emit_node = mapped_node
                con._emit_port = mapped_port
            return con

        def serialize_compact(self):
            nonlocal new_obj
            # the str(self._emit_node) should not change, since neither the class nor the name of the node are accessible to the user
            # except, that the name might be changed by the system if str(node) is not unique in the graph
            #   -> we could prefix the node name with the macro name
            #   -> but the macro name is only truly set after the macro is created and connected to the subgraph
            #   -> is there a better unique prefix, that we know not yet exists in a graph?
            #   -> here the cat bites it's own tail... =
            #   => change the nodes name, rather than the macro's name
            emit_port = new_obj._encode_node_port(self._emit_node, self._emit_port.key).replace(new_obj.node_macro_id_suffix, '')
            return f"{new_obj._serialize_name()}.{emit_port} -> {str(self._recv_node)}.{str(self._recv_port.key)}"

        # it is important we keep the original function here, as we might patch this multiple times 
        # e.g. if multiple (different) macros input to the same node
        prev_rm_fn = connection._recv_node.remove_input_by_connection
        def remove_input_by_connection(self, connection):
            nonlocal map_fn
            prev_rm_fn(map_fn(connection))

        # patch connection
        connection = map_fn(connection)
        connection.serialize_compact = serialize_compact.__get__(connection, connection.__class__)
        # patch recv_node so that it removes the correct input if the connection is removed later
        connection._recv_node.remove_input_by_connection = remove_input_by_connection.__get__(connection._recv_node, connection._recv_node.__class__)
        # now add the connection to the mapped node
        super(connection._emit_node.__class__, connection._emit_node)._add_output(connection)

    def remove_all_inputs(self):
        # TODO: this is currently untested
        for n in self.nodes:
            for con in n.input_connections:
                # only remove connections that are from outside the sub-graph to inside it
                if self.node_macro_id_suffix not in str(con._emit_node):
                    super(n.__class__, n).remove_input_by_connection(con)
    
    def remove_input_by_connection(self, connection):
        # mapped_node = connection._emit_node
        mapped_node, mapped_port = self.__get_correct_node(connection._recv_port, io='in')
        connection._recv_node = mapped_node
        connection._recv_port = mapped_port
        super(mapped_node.__class__, mapped_node).remove_input_by_connection(connection)


class Macro(MacroHelper):
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
        own_in_port_reverse = {}

        # Populate the lists using classic for loops
        for n, port_name, port_value in cls.all_ports_sub_nodes(nodes, ret_in=True):
            macro_port = port_value.__class__(f"{n.name}: {port_value.label}", optional=port_value.optional, key=port_value.key)
            in_field_names.append(cls._encode_node_port(n, port_name))
            in_field_defaults.append(macro_port)
            own_in_port_to_ref[cls._encode_node_port(n, port_name)] = (n, port_name, port_value)
            own_in_port_reverse[f"{str(n)}.{port_name}"] = cls._encode_node_port(n, port_name)
            
        for n, port_name, port_value in cls.all_ports_sub_nodes(nodes, ret_in=False):
            macro_port = port_value.__class__(f"{n.name}: {port_value.label}", optional=port_value.optional, key=port_value.key)
            out_field_names.append(cls._encode_node_port(n, port_name))
            out_field_defaults.append(macro_port)
            own_out_port_to_ref[cls._encode_node_port(n, port_name)] = (n, port_name, port_value)


        # --- Create new (sub) class ----------------
        # new_cls = super(Macro, cls).__new__(cls)
        cls_name = f"Macro:{path.split('/')[-1].split('.')[-2]}"
        new_cls = type(cls_name, (MacroHelper, ), {})
        new_cls.ports_in = type('Macro_Ports_In', (Ports_collection,), dict(zip(in_field_names, in_field_defaults)))()
        new_cls.ports_out = type('Macro_Ports_Out', (Ports_collection,), dict(zip(out_field_names, out_field_defaults)))()
        new_cls.own_in_port_to_ref = own_in_port_to_ref
        new_cls.own_out_port_to_ref = own_out_port_to_ref

        # -- Create new instance from that new class ----------------
        new_obj = new_cls(path=path, name=name, compute_on=compute_on, **kwargs)
        new_obj.pl = pl
        new_obj.nodes = nodes

        # --- Patch Settings / Serialization ----------------
        # There are two main thoughts: (1) how to patch inputs into the macro and (2) how to patch nodes the macro inputs to (ie macros output)
        # (1) The idea for inputs is to replace the compact_settings method of each node with a method that just returns the macro nodes settings
        #   because the to_compact_dict method used for serialization overwrites nodes with the same str(node) (which should not occur, as each name must be unique in the graph) we can use that
        #   to just return the settings of the macro node over and over and not worrying about duplicates in the serialized output
        #   however, this is not the case for inputs, as they use inputs.extend() and thus we should only return those once
        # (2) The idea for outputs is to overwrite the serialize_compact method of their connection classes to return the macro instead of the sub-graph nodes
        #   This happens by overwriting the add_output method of the sub-graph nodes
        def compact_settings(self):
            nonlocal new_obj, own_in_port_reverse
            config = new_obj.get_settings().get('settings', {})
            inputs = []
            for inp in self.input_connections:
                # only keep those connections that are from outside the sub-graph to inside it
                if new_obj.node_macro_id_suffix not in str(inp._emit_node):
                    # copy connection, so that the original is not changed (not sure if necessary, but feels right)
                    inp = Connection(inp._emit_node, inp._recv_node, inp._emit_port, inp._recv_port)
                    # change the recv_node to the macro node
                    tmp_key = f"{str(inp._recv_node)}.{inp._recv_port.key}".replace(new_obj.node_macro_id_suffix, '')
                    inp._recv_port = getattr(new_obj.ports_in, own_in_port_reverse[tmp_key])
                    inp._recv_node = new_obj._serialize_name()
                    inputs.append(inp.serialize_compact())
            return config, inputs, new_obj._serialize_name()

        for n in nodes:
            # set a unique name for each node, so that it is not changed during connection into any existing graph
            # NOTE: we set this here as we don't want the suffix to bleed into the port names etc
            #    only for keeping the node name unique within the subgraph and the serialized graph
            #    TODO: double check if this results in any issues down the road -> so far test are looking good -yh
            n.name = f"{n.name}{new_obj.node_macro_id_suffix}"
            # following: https://stackoverflow.com/a/28127947
            n.compact_settings = compact_settings.__get__(n, n.__class__)
            n._macro_parent = new_obj

        return new_obj

if __name__ == '__main__':
    # m = Macro(path=Macro.example_init["path"]) 
    # print(m.ports_in)

    from livenodes import Graph
    from ln_io_python.in_python import In_python
    from ln_io_python.out_python import Out_python
    import numpy as np

    d = [100]
    in_python = In_python(data=d)
    macro = Macro(path=Macro.example_init["path"])
    # print(macro.ports_in.Noop_any.key, macro.ports_out.Noop_any.key)
    macro.add_input(in_python, emit_port=in_python.ports_out.any, recv_port=macro.ports_in.Noop_any)
    # print(macro.ports_in.Noop_any.key, macro.ports_out.Noop_any.key)
    # macro.remove_all_inputs()
    # dct = in_python.to_compact_dict(graph=True)
    out_python = Out_python() 
    # print(macro.ports_in.Noop_any.key, macro.ports_out.Noop_any.key)
    out_python.add_input(macro, emit_port=macro.ports_out.Noop_any, recv_port=out_python.ports_in.any)
    # g = Graph(start_node=in_python)
    out_python.remove_all_inputs()
    # g.start_all()
    # g.join_all()
    # g.stop_all()

    # np.testing.assert_equal(np.array(out_python.get_state()), np.array(d))

    dct = in_python.to_compact_dict(graph=True)
    print(dct)

    s = in_python.from_compact_dict(dct)
    print('Done')