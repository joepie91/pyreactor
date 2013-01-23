import pyreactor, time

class TestClient(pyreactor.BaseClient):
	chunk_size = 8192
	
	def event_receive(self, data):
		print "Received message: %s" % repr(data)
	
	def event_datastream_start(self, stream, size):
		print "Starting transfer of file with size %d..." % size
		stream.start_time = time.time()
		stream.last_measure_time = stream.start_time
		stream.last_measure_bytes = 0
		stream.last_measure_speed = 0
	
	def event_datastream_progress(self, stream, finished_bytes, total_bytes):
		cur_time = time.time()
		
		if int(cur_time) > int(stream.last_measure_time):
			speed = (finished_bytes - stream.last_measure_bytes) / (cur_time - stream.last_measure_time)
			stream.last_measure_time = cur_time
			stream.last_measure_bytes = finished_bytes
			stream.last_measure_speed = speed
			
			print "Completed %d of %d bytes for stream %d. (%.2fMB/sec)" % (finished_bytes, total_bytes, stream.id, speed / 1024 / 1024)
	
	def event_datastream_finished(self, stream):
		print "Completed stream %d in %.2f seconds! Saved to file test.dat." % (stream.id, time.time() - stream.start_time)
		stream.copy("test.dat")
		print "Exiting..."
		self.reactor.stop()
	
	def event_disconnected(self):
		print "Client disconnected."
