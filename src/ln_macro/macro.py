import asyncio
import numpy as np

from livenodes.producer_async import Producer_async

from livenodes_common_ports.ports import Port_ListUnique_Str, Ports_empty, Port_Timeseries
from typing import NamedTuple


class Ports_out(NamedTuple):
    ts: Port_Timeseries = Port_Timeseries("TimeSeries")
    channels: Port_ListUnique_Str = Port_ListUnique_Str("Channel Names")


class In_function(Producer_async):
    """Inputs data generated from a NumPy function into the LiveNodes graph.

    Generates an infinite data stream [0, 1, 2, ...] and applies the
    given NumPy function to it.

    The output batch size is set via the `emit_at_once` attribute. The time
    interval between process invocations depends on both `emit_at_once` and the
    `sample rate` meta attribute.

    If multiple output channels are defined, all of them will contain identical
    data.

    Attributes
    ----------
    function : str
        Name of a NumPy function such as "sin". Defaults to a basic linear
        function if invalid.
    meta : dict
        Dict of meta parameters.

        * 'sample_rate' : int
            Sample rate to simulate.
        * 'channel_names' : list of unique str, optional
            List of channel names for `channels` port. Number of items also
            sets number of channels.
    emit_at_once : int
        Batch size, i.e. number of samples sent per process invocation.

    Ports Out
    ---------
    ts : Port_TimeSeries
        Batch of output samples.
    channels : Port_ListUnique_Str
        List of channel names. Can be overwritten using the `meta` attribute.
    """

    ports_in = Ports_empty()
    ports_out = Ports_out()

    category = "Data Source"
    description = ""

    example_init = {
        "function": "sin",
        "meta": {"sample_rate": 100, "channels": ["Function"]},
        "emit_at_once": 1,
        "name": "Function Input",
    }

    # TODO: consider using a file for meta data instead of dictionary...
    def __init__(self, meta, function="sin", emit_at_once=1, name="Function Input", **kwargs):
        super().__init__(name, **kwargs)

        self.meta = meta
        self.function = function
        self.emit_at_once = emit_at_once

        self.sample_rate = meta.get('sample_rate')
        self.channels = meta.get('channels')

    def _settings(self):
        return {"emit_at_once": self.emit_at_once, "function": self.function, "meta": self.meta}

    async def _async_run(self):
        self.ret_accu(self.channels, port=self.ports_out.channels)

        ctr = 0
        n_channels = len(self.channels)

        time_to_sleep = 1.0 / self.sample_rate * self.emit_at_once
        # last_emit_time = time.time()

        def linear(x):
            return x / 1000

        try:
            fn = getattr(np, self.function)
        except:
            self.error(f'Could not find {self.function}. Defaulting to linear.')
            fn = linear

        while True:
            samples = np.linspace(ctr, ctr + self.emit_at_once - 1, self.emit_at_once)
            res = fn(samples)
            res = np.array(np.array([res] * n_channels).T)
            self.ret_accu(res, port=self.ports_out.ts)

            ctr += self.emit_at_once

            # process_time = time.time() - last_emit_time
            # if time_to_sleep > process_time:
            #     await asyncio.sleep(time_to_sleep - process_time)
            await asyncio.sleep(time_to_sleep)

            yield (self.ret_accumulated())
            # last_emit_time = time.time()
