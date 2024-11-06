# LiveNodes IO Python

The LiveNodes IO Python package provides nodes for data input and output using raw Python lists/NumPy arrays directly, as well as for generating data from NumPy functions. As such, these nodes are most useful for testing other nodes or extracting results from LiveNodes graphs for further external processing.

## Nodes in this package
| Node          | Purpose                                                               |
| ------------- | --------------------------------------------------------------------- |
| `Macro` | Node that internally runs another graph and exposes the graphs ports. |

## About LiveNodes
[LiveNodes](https://livenodes.pages.csl.uni-bremen.de/livenodes/index.html) are small units of computation for digital signal processing in python. They are connected multiple synced channels to create complex graphs for real-time applications. Each node may provide a GUI or Graph for live interaction and visualization.

Any contribution is welcome! These projects take more time, than I can muster, so feel free to create issues for everything that you think might work better and feel free to create a MR for them as well!

Have fun and good coding!

Yale

## Installation

`pip install ln_macro `

## Docs

You can find the docs [here](https://livenodes.pages.csl.uni-bremen.de/packages/ln_macro/readme.html).

## Restrictions

None, just pure python and numpy.
