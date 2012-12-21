import pyreactor

class TestClient(pyreactor.BaseClient):
	def event_receive(self, data):
		print "Received message: %s" % repr(data)
	
	def event_datastream_progress(self, stream, finished_bytes, total_bytes):
		print "Completed %d of %d bytes for stream %d." % (finished_bytes, total_bytes, stream.id)
	
	def event_datastream_finished(self, stream):
		print "Completed stream %d! Data follows..." % stream.id
		print "============================================"
		print stream.read()
		
		print "============================================"
		print "Exiting..."
		self.reactor.stop()

s = pyreactor.Server("127.0.0.1", 4006, TestClient)
c = TestClient(host="127.0.0.1", port=4006)

c.send({"test": "just sending some test data...", "number": 41, "file": open("test.py", "r")})

reactor = pyreactor.Reactor()
reactor.add(s)
reactor.add(c)
reactor.loop()
