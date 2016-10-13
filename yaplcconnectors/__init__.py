#!/usr/bin/env python
# package initializations

from os import listdir, path


_base_path = path.split(__file__)[0]


def _GetLocalConnectorClassFactory(name):
    return lambda: getattr(__import__(name, globals(), locals()), name + "_connector_factory")

connectors = {name: _GetLocalConnectorClassFactory(name)
                  for name in listdir(_base_path)
                      if path.isdir(path.join(_base_path, name))
                          and not name.startswith("__")}


def ConnectorFactory(uri, confnodesroot):
    """
    Return a connector corresponding to the URI
    or None if cannot connect to URI
    """
    servicetype = uri.split("://")[0].upper()
    if servicetype == "LOCAL":
        # Local is special case
        # pyro connection to local runtime
        # started on demand, listening on random port
        servicetype = "PYRO"
        runtime_port = confnodesroot.AppFrame.StartLocalRuntime(
            taskbaricon=True)
        uri = "PYROLOC://127.0.0.1:" + str(runtime_port)
    elif servicetype in connectors:
        pass
    elif servicetype[-1] == 'S' and servicetype[:-1] in connectors:
        servicetype = servicetype[:-1]
    else:
        return None

    # import module according to uri type
    connectorclass = connectors[servicetype]()
    return connectorclass(uri, confnodesroot)