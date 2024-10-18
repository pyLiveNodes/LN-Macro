from livenodes import Node, Ports_collection, Connection
from ln_ports import Ports_empty

import pathlib
file_path = pathlib.Path(__file__).parent.resolve()

from enum import Enum
# NOTE: this is only needed/used atm because for some reason isinstance(node, MacroHelper) is not always true for nodes from macros...
class MAttr(Enum):
    macro = 10
    macro_child = 11

class MacroHelper(Node, abstract_class=True):
    attrs = [MAttr.macro]
    category = "Meta"
    description = ""

    ports_in = Ports_empty()
    ports_out = Ports_empty()

    example_init = {
        "path": f"{file_path}/noop.yml",
        "name": "Macro",
    }

    def __init__(self, path, name=None, compute_on="", **kwargs):
        name = self.name(name, path)
        super().__init__(name, compute_on=compute_on, **kwargs)

        self.path = path

        # --- Load the pipeline ----------------
        pl = Node.load(path)
        nodes = self._discover_graph_excl_macros(pl)
        
        # Set the compute_on attribute for all nodes 
        for n in nodes:
            n.compute_on = compute_on
            n.attrs.append(MAttr.macro_child)

        # --- Match Ports ----------------
        # Initialize lists for field names and defaults
        own_in_port_to_ref, own_out_port_to_ref = {}, {}
        own_in_port_reverse, own_out_port_reverse = {}, {}

        # Populate the lists using classic for loops
        for n, port_name, port_value in self.all_ports_sub_nodes(nodes, ret_in=True):
            own_in_port_to_ref[self._encode_node_port(n, port_name)] = (n, port_name, port_value)
            own_in_port_reverse[f"{str(n)}.{port_name}"] = self._encode_node_port(n, port_name)
            
        for n, port_name, port_value in self.all_ports_sub_nodes(nodes, ret_in=False):
            own_out_port_to_ref[self._encode_node_port(n, port_name)] = (n, port_name, port_value)
            own_out_port_reverse[f"{str(n)}.{port_name}"] = self._encode_node_port(n, port_name)



        # --- Set object specifics ----------------
        self.pl = pl
        self.nodes = nodes
        self.own_in_port_to_ref = own_in_port_to_ref
        self.own_out_port_to_ref = own_out_port_to_ref
        self.own_in_port_reverse = own_in_port_reverse
        self.own_out_port_reverse = own_out_port_reverse

        # --- Patch Settings / Serialization ----------------
        # There are two main thoughts: (1) how to patch inputs into the macro and (2) how to patch nodes the macro inputs to (ie macros output)
        # (1) The idea for inputs is to replace the compact_settings method of each node with a method that just returns the macro nodes settings
        #   because the to_compact_dict method used for serialization overwrites nodes with the same str(node) (which should not occur, as each name must be unique in the graph) we can use that
        #   to just return the settings of the macro node over and over and not worrying about duplicates in the serialized output
        #   however, this is not the case for inputs, as they use inputs.extend() and thus we should only return those once
        # (2) The idea for outputs is to overwrite the serialize_compact method of their connection classes to return the macro instead of the sub-graph nodes
        #   This happens by overwriting the add_output method of the sub-graph nodes
        closure_self = self
        def compact_settings(self):
            nonlocal closure_self
            config = closure_self.get_settings().get('settings', {})
            inputs = []
            for inp in self.input_connections:
                # only keep those connections that are from outside the sub-graph to inside it
                if closure_self.node_macro_id_suffix not in str(inp._emit_node):
                    # copy connection, so that the original is not changed (not sure if necessary, but feels right)
                    inp = Connection(inp._emit_node, inp._recv_node, inp._emit_port, inp._recv_port)
                    # change the recv_node to the macro node
                    inp._emit_node, inp._emit_port = closure_self.adjust(inp._emit_node, inp._emit_port, in_ports=False) # emiting node -> their output port is relevant
                    inp._recv_node, inp._recv_port = closure_self.adjust(inp._recv_node, inp._recv_port, in_ports=True) # recv node -> their input port is relevant
                    inputs.append(inp.serialize_compact())
            return config, inputs, closure_self._serialize_name()
        
        def get_name_resolve_macro(self):
            name = self.name
            for m in self._macro_parent:
                name = name.replace(m.node_macro_id_suffix, f"({str(m)})")
            return name

        for n in nodes:
            # set a unique name for each node, so that it is not changed during connection into any existing graph
            # NOTE: we set this here as we don't want the suffix to bleed into the port names etc
            #    only for keeping the node name unique within the subgraph and the serialized graph
            #    TODO: double check if this results in any issues down the road -> so far test are looking good -yh
            #       -> only issue is that the node name changes between multiple graph loads -> and thus the gui cannot save the running layout properly
            n.name = f"{n.name}{self.node_macro_id_suffix}"
            # following: https://stackoverflow.com/a/28127947
            n.compact_settings = compact_settings.__get__(n, n.__class__)
            n.get_name_resolve_macro = get_name_resolve_macro.__get__(n, n.__class__)
            if not hasattr(n, '_macro_parent'):
                n._macro_parent = []
            n._macro_parent.append(self)

    @staticmethod
    def name(name, path):
        if name is not None:
            return name
        return f"Macro:{path.split('/')[-1].split('.')[-2]}"

    @staticmethod
    def all_ports_sub_nodes(nodes, ret_in = True):
        return [(n, port_name, port_value) for n in nodes for (port_name, port_value) in (n.ports_in if ret_in else n.ports_out)._asdict().items()]

    @classmethod
    def _encode_node_port(cls, node, port_name):
        return f"{cls._get_node_name(node)}_{port_name}"
    
    @property
    def node_macro_id_suffix(self):
        return f"[[m:{id(self)}]]"
    
    def _settings(self):
        return {"path": self.path, "name": self.name}
    
    # def compact_settings(self):
    #     config = self.get_settings().get('settings', {})
    #     inputs = [
    #         inp.serialize_compact() for inp in self.input_connections
    #     ]
    #     return config, inputs, str(self)
    
    ## TODO: this is an absolute hack, but follows the current livenodes implementation
    def _set_attr(self, **kwargs):
        # make sure the names are unique when being set
        if 'name' in kwargs:
            kwargs['name'] = self.make_sure_name_is_unique(kwargs['name'])

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
    def adjust(node, port, in_ports):
        if not hasattr(node, '_macro_parent'):
            return node, port
        m_parent = node._macro_parent[-1]
        tmp_key = f"{str(node)}.{port.key}".replace(m_parent.node_macro_id_suffix, '')
        if in_ports:
            _port = getattr(m_parent.ports_in, m_parent.own_in_port_reverse[tmp_key])
        else:
            _port = getattr(m_parent.ports_out, m_parent.own_out_port_reverse[tmp_key])
        _node = m_parent._serialize_name()
        return _node, _port
    
    def get_non_macro_node(self):
        if hasattr(self.nodes[0], 'get_non_macro_node'):
            return self.nodes[0].get_non_macro_node()
         # as all nodes are connected it doesn't matter from where we start to discover
        return self.nodes[0]

    @staticmethod
    def _discover_graph_excl_macros(node, direction='both', sort=True):
        if isinstance(node, MacroHelper) or MAttr.macro in node.attrs:
            node = node.nodes[0]
        nodes = node.discover_graph(node, direction=direction, sort=sort)
        return node.remove_discovered_duplicates(nodes)
    
    @staticmethod
    def discover_graph_macros_only(node, direction='both', sort=True):
        if isinstance(node, MacroHelper):
            # start with a node that is not a macro (bc macros are never part of the processing graph)
            node = node.nodes[0]
        nodes = []
        for n in node.discover_graph(node, direction=direction, sort=sort):
            if hasattr(n, '_macro_parent'):
                nodes.extend(n._macro_parent)
        return node.remove_discovered_duplicates(nodes)
        
    def is_unique_macro_name(self, name, macro_list):
        # since macros all have the same class suffix, we only need to check for the name itself
        for m in macro_list:
            if m.name == name and m is not self:
                return False
        return True
        # return not name in [x.name for x in  set(macro_list) - set([self])]
    
    def create_unique_name(self, base, macro_list):
        if self.is_unique_macro_name(base, macro_list):
            return base
        return self.create_unique_name(f"{base}_1", macro_list)
    
    def make_sure_name_is_unique(self, name):
        macro_list = self.discover_graph_macros_only(self.get_non_macro_node())
        if not self.is_unique_macro_name(name, macro_list):
            new_name = self.create_unique_name(name, macro_list)
            self.warn(f"{str(self)} not unique in new graph. Renaming Node to: {new_name}")
            return new_name
        return name

    def add_input(self, emit_node, emit_port, recv_port):
        # Retrieve the appropriate node from self.in_map using recv_port
        # TODO: the correct_node is wrong here, since its mapping is determined in __new__ however the object created in __init__ is different and unfortunately the created ports contain the subgraph's macro suffix
        mapped_node, mapped_port = self.__get_correct_node(recv_port, io='in')
        # Call super().add_input() with the mapped node
        super(mapped_node.__class__, mapped_node).add_input(emit_node, emit_port, mapped_port)
        # after the processing graph is connected, make sure the macro name is unique as well
        self._set_attr(name=self.make_sure_name_is_unique(self.name))
        

    def _serialize_name(self):
        return str(self).replace(f'[{self.__class__.__name__}]', '[Macro]')
    
    @staticmethod
    def _get_node_name(node):
        name = node.name
        if hasattr(node, '_macro_parent'):
            for n in node._macro_parent:
                name = name.replace(n.node_macro_id_suffix, '')
        return name

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
            #   -> here the dragon bites it's own tail... =
            #   => change the nodes name, rather than the macro's name
            emit_port = new_obj._encode_node_port(self._emit_node, self._emit_port.key).replace(new_obj.node_macro_id_suffix, '')
            print('seralizing con', emit_port)
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
        if isinstance(connection._emit_node, MacroHelper):
            connection._emit_node, connection._emit_port = connection._emit_node.__get_correct_node(connection._emit_port, io='out')
        mapped_node, mapped_port = self.__get_correct_node(connection._recv_port, io='in')
        connection._recv_node = mapped_node
        connection._recv_port = mapped_port
        super(mapped_node.__class__, mapped_node).remove_input_by_connection(connection)


    # --- mapping functions ---
    def to_compact_dict(self, graph=False):
        return self.get_non_macro_node().to_compact_dict(graph=graph)
    
    def dot_graph_full(self, filename=None, file_type='png', **kwargs):
        return self.get_non_macro_node().dot_graph_full(filename=filename, file_type=file_type, **kwargs)


class Macro(MacroHelper):
    def __new__(cls, path=f"{file_path}/noop.yml", name=None, compute_on="", **kwargs):
        # The only function of all this hassle is to create a new class with the correct ports
        
        # --- Load the pipeline ----------------
        # this is not kept (ie the one kept is the one from __init__), but we need to load the pipeline to get the ports
        pl = Node.load(path)
        nodes = cls._discover_graph_excl_macros(pl)
        
        # --- Match Ports ----------------
        # Initialize lists for field names and defaults
        in_field_names, in_field_defaults = [], []
        out_field_names, out_field_defaults = [], []

        # Populate the lists using classic for loops
        for n, port_name, port_value in cls.all_ports_sub_nodes(nodes, ret_in=True):
            # only keep those inputs that aren't already taken
            # TODO: check if we could add this functionality to the port class itself, this feels kinda hacky -yh
            # could also consider adding it to the node class itself
            if id(port_value) not in [id(x._recv_port) for x in n.input_connections]:
                macro_port = port_value.__class__(f"{cls._get_node_name(n)}: {port_value.label}", optional=port_value.optional, key=port_value.key)
                in_field_names.append(cls._encode_node_port(n, port_name))
                in_field_defaults.append(macro_port)
            
        for n, port_name, port_value in cls.all_ports_sub_nodes(nodes, ret_in=False):
            macro_port = port_value.__class__(f"{cls._get_node_name(n)}: {port_value.label}", optional=port_value.optional, key=port_value.key)
            out_field_names.append(cls._encode_node_port(n, port_name))
            out_field_defaults.append(macro_port)


        # --- Create new (sub) class ----------------
        # new_cls = super(Macro, cls).__new__(cls)
        cls_name = f"Macro:{path.split('/')[-1].split('.')[-2]}"
        new_cls = type(cls_name, (MacroHelper, ), {})
        new_cls.example_init["path"] = path
        new_cls.example_init["name"] = new_cls.name(name, path)
        new_cls.ports_in = type('Macro_Ports_In', (Ports_collection,), dict(zip(in_field_names, in_field_defaults)))()
        new_cls.ports_out = type('Macro_Ports_Out', (Ports_collection,), dict(zip(out_field_names, out_field_defaults)))()
        
        # -- Create new instance from that new class ----------------
        new_obj = new_cls(path=path, name=name, compute_on=compute_on, **kwargs)
        assert issubclass(new_cls, MacroHelper)
        assert isinstance(new_obj, MacroHelper)
        return new_obj

if __name__ == '__main__':
    m = Macro(path=Macro.example_init["path"]) 
    # m = Macro(path="/Users/yale/Repositories/livenodes/packages/ln_macro/src/ln_macro/noop_nested_2.yml")
    # print(m.ports_in)

    # from livenodes import Graph
    # from ln_io_python.in_python import In_python
    # from ln_io_python.out_python import Out_python
    # import numpy as np

    # d = [100]
    # in_python = In_python(data=d)
    # macro = Macro(path=Macro.example_init["path"])
    # # print(macro.ports_in.Noop_any.key, macro.ports_out.Noop_any.key)
    # macro.add_input(in_python, emit_port=in_python.ports_out.any, recv_port=macro.ports_in.Noop_any)
    # # print(macro.ports_in.Noop_any.key, macro.ports_out.Noop_any.key)
    # # macro.remove_all_inputs()
    # # dct = in_python.to_compact_dict(graph=True)
    # out_python = Out_python() 
    # # print(macro.ports_in.Noop_any.key, macro.ports_out.Noop_any.key)
    # out_python.add_input(macro, emit_port=macro.ports_out.Noop_any, recv_port=out_python.ports_in.any)
    # # g = Graph(start_node=in_python)
    # out_python.remove_all_inputs()
    # g.start_all()
    # g.join_all()
    # g.stop_all()

    # np.testing.assert_equal(np.array(out_python.get_state()), np.array(d))

    # dct = in_python.to_compact_dict(graph=True)
    # print(dct)

    # s = in_python.from_compact_dict(dct)
    # print('Done')

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

    in_python, macro, out_python = build_pipeline([100])
    macro2 = Macro(path=Macro.example_init["path"])
    macro2.add_input(in_python, emit_port=in_python.ports_out.any, recv_port=macro2.ports_in.Noop_any)
    assert macro2.name != macro.name
    macro2._set_attr(name=macro.name)
    assert macro2.name != macro.name
