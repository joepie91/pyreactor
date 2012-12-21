from bitstring import BitArray
import select, msgpack

class ReactorException(Exception):
	pass

class Reactor:
	queue = []
	objmap = {}
	abort_flag = False
	
	recv_size = 1024
	#chunk_size = 512 * 1024
	chunk_size = 512
	
	def __init__(self):
		pass
	
	def _process_chunk(self, obj, chunktype, channel, data):
		if chunktype == 1:
			# Client message
			obj.event_receive(obj._unpack(data))
		elif chunktype == 2:
			# Datastream chunk
			obj._receive_datastream(channel, data)
		elif chunktype == 3:
			# System message
			self._process_message(obj, msgpack.unpackb(data))
	
	def _process_message(self, client, data):
		if data['type'] == "datastream_finished":
			datastream_id = data['id']
			#print "Successfully finished receiving datastream %d." % datastream_id
			#print client._tempfiles[datastream_id].read()
			client.event_datastream_finished(client._tempfiles[datastream_id])
			del client._tempfiles[datastream_id]
	
	def add(self, obj):
		try:
			self.queue.append(obj.stream)
			self.objmap[obj.stream.fileno()] = obj
		except AttributeError, e:
			raise ReactorException("The provided object has no valid stream attached to it.")
			
		obj.reactor = self
	
	def cycle(self):
		readable, writable, error = select.select(self.queue, self.queue, self.queue)
		
		for stream in readable:
			fileno = stream.fileno()
			obj = self.objmap[fileno]
			
			if obj.objtype == "server":
				sock, addr = obj.stream.accept()
				new_client = obj.spawn_client(sock, addr)
				self.add(new_client)
				print "Found new client from %s:%d" % addr
			elif obj.objtype == "client":
				while True:
					try:
						buff = stream.recv(self.recv_size)
						break
					except ssl.SSLError, err:
						if err.args[0] == ssl.SSL_ERROR_WANT_READ:
							select.select([sock], [], [])
						elif err.args[0] == ssl.SSL_ERROR_WANT_WRITE:
							select.select([], [sock], [])
						else:
							raise
				
				if not buff:
					# The client has ceased to exist - most likely it has closed the connection.
					del self.objmap[fileno]
					self.queue.remove(stream)
					print "Client disconnected: %s:%d" % (obj.host, obj.port)
				
				buff = obj._tempbuff + buff
				
				while buff != b"":
					if obj._read_left > 0:
						# Continue reading a chunk in progress
						if obj._read_left < self.recv_size:
							# All the data we need is in the buffer.
							obj._read_buff += buff[:obj._read_left]
							buff = buff[obj._read_left:]
							obj._read_left = 0 
							
							self._process_chunk(obj, obj._chunktype, obj._channel, obj._read_buff)
							
							obj._read_buff = b""
						else:
							# We need to read more data than is in the buffer.
							obj._read_buff += buff
							obj._read_left -= len(buff)
							buff = b""
					elif len(buff) >= 7:
						# Start reading a new chunk
						header = BitArray(bytes=buff[:7])   # 7 byte chunk header
						chunktype = header[:7].uint   # Bits 0-6 inc
						chunksize = header[7:32].uint # Bits 7-31 inc
						channel = header[32:56].uint  # Bits 32-55 inc
						
						buff = buff[7:]
						obj._read_left = chunksize
						obj._chunksize = chunksize
						obj._chunktype = chunktype
						obj._channel = channel
					else:
						# We need more data to do anything meaningful
						obj._tempbuff = buff
						break
		
		for stream in writable:
			fileno = stream.fileno()
			obj = self.objmap[fileno]
			
			if obj.objtype == "client":
				if len(obj.sendq) > 0:
					item = obj.sendq.popleft()
					obj._send_chunk(item)
				
				if len(obj._active_datastreams) > 0:
					to_delete = []
					
					for datastream_id, datastream in obj._active_datastreams.iteritems():
						data = datastream.read(self.chunk_size)
						
						if data:
							header = obj._encode_header(2, len(data), datastream_id)
							stream.send(header + data)
						else:
							# Done with this datastream.
							obj._send_system_message({"type": "datastream_finished", "id": datastream_id})
							to_delete.append(datastream_id)
					
					for datastream_id in to_delete:
						del obj._active_datastreams[datastream_id]
					
	def loop(self):
		while self.abort_flag == False:
			self.cycle()
	
	def stop(self):
		self.abort_flag = True
