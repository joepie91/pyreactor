import pyreactor, time
from testclient import TestClient

s = pyreactor.Server("127.0.0.1", 4006, TestClient)

reactor = pyreactor.Reactor()
reactor.add(s)
reactor.loop()
