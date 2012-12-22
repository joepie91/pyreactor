import pyreactor, time
from testclient import TestClient

s = pyreactor.Server("0.0.0.0", 4006, TestClient)

reactor = pyreactor.Reactor()
reactor.add(s)
reactor.loop()
