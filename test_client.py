import pyreactor, time
from testclient import TestClient

c = TestClient(host="kerpia.cryto.net", port=4006)

c.send({"test": "just sending some test data...", "number": 41, "file": open("testdata.dat", "rb")})

reactor = pyreactor.Reactor()
reactor.add(c)
reactor.loop()
