import pyreactor, time
from testclient import TestClient

s = pyreactor.Server("127.0.0.1", 4006, TestClient)
c = TestClient(host="127.0.0.1", port=4006)

c.send({"test": "just sending some test data...", "number": 41, "file": open("testdata.dat", "rb")})

reactor = pyreactor.Reactor()
reactor.add(s)
reactor.add(c)
reactor.loop()
