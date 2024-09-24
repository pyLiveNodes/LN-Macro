from livenodes.node import Node
from ln_ports import Ports_any

class Noop(Node):
    ports_in = Ports_any()
    ports_out = Ports_any()

    category = "Data Source"
    description = ""

    example_init = {
        "name": "Noop",
    }

    def __init__(self, name="Noop", **kwargs):
        super().__init__(name, **kwargs)

    def process(self, any, **kwargs):
        return self.ret(any=any)
