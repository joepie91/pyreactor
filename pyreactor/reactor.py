from bitstring import BitArray
import select, msgpack

class ReactorException(Exception):
	pass

class Reactor:
	queue = []
	objmap = {}
	_abort_flag = False
	
	def __init__(self):
		pass
	
	def _cycle(self):
		readable, writable, error = select.select(self.queue, self.queue, self.queue)
		
		for stream in readable:
			fileno = stream.fileno()
			obj = self.objmap[fileno]
			
			#print "Data is available to read on %s with id %d" % (repr(stream), stream.fileno())
			
			if obj.objtype == "server":
				sock, addr = obj.stream.accept()
				new_client = obj.spawn_client(sock, addr)
				self.add(new_client)
				print "Found new client from %s:%d" % addr
			elif obj.objtype == "client":
				obj._read_cycle()
		
		for stream in writable:
			fileno = stream.fileno()
			obj = self.objmap[fileno]
			
			if obj.objtype == "client":
				obj._write_cycle()
	
	def add(self, obj):
		try:
			self.queue.append(obj.stream)
			self.objmap[obj.stream.fileno()] = obj
		except AttributeError, e:
			raise ReactorException("The provided object has no valid stream attached to it.")
			
		obj.reactor = self
					
	def loop(self):
		while self._abort_flag == False:
			self._cycle()
	
	def stop(self):
		self._abort_flag = True
