import socket, ssl, msgpack, tempfile, os
from collections import deque
from bitstring import BitArray
from filelike import FileLike

class BaseClient:
	# Overridable settings
	max_mem = 32 * 1024 * 1024  # Maximum amount of memory per RAM-based temp file
	chunk_size = 1024  # Size per chunk of raw datastream
	recv_size = 1024  # Amount of data to receive at once
	
	def __init__(self, host=None, port=None, use_ssl=False, allowed_certs=None, conn=None, source=None, **kwargs):
		# Internal variables
		self._tempbuff = b""
		self._read_left = 0
		self._read_buff = b""
		self._tempfiles = {}
		self._last_datastream_id = 10
		self._active_datastreams = {}
		self._filelike_counter = 0
		self._datastream_started = []
		
		# Parent reactor
		self.reactor = None
		
		self.objtype = "client"
		self.sendq = deque([])
		
		if (host is None or port is None) and (conn is None or source is None):
			raise Exception("You must specify either a connection and source address, or a hostname and port.")
		
		if host is not None:
			# Treat this as a new client
			self.host = host
			self.port = port
			self.ssl = use_ssl
			self.spawned = False
			
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			
			if self.ssl == True:
				self.stream = ssl.wrap_socket(sock, cert_reqs=ssl.CERT_REQUIRED, ca_certs=allowed_certs)
			else:
				self.stream = sock
			
			self.stream.connect((self.host, self.port))
			
			self.event_connected()
				
		elif conn is not None:
			# Treat this as a client spawned by a server
			self.host = source[0]
			self.port = source[1]
			self.stream = conn
			self.spawned = True
			self.event_connected()
	
	def _send_chunk(self, chunk):
		self.stream.send(chunk)
	
	def _encode_header(self, chunktype, size, channel):
		header_type = BitArray(uint=chunktype, length=7)
		header_size = BitArray(uint=size, length=25)
		header_channel = BitArray(uint=channel, length=24)
		header = header_type + header_size + header_channel
		return header.bytes
	
	def _decode_header(self, header):
		bits = BitArray(bytes=header)   # 7 byte chunk header
		chunktype = bits[:7].uint   # Bits 0-6 inc
		chunksize = bits[7:32].uint # Bits 7-31 inc
		channel = bits[32:56].uint  # Bits 32-55 inc
		
		return (chunktype, chunksize, channel)
	
	def _pack(self, data):
		return msgpack.packb(data, default=self._encode_pack)
	
	def _encode_pack(self, obj):
		if hasattr(obj, "read"):
			datastream_id = self._create_datastream(obj)
			
			# Determine the total size of the file
			current_pos = obj.tell()
			obj.seek(0, os.SEEK_END)
			total_size = obj.tell()
			obj.seek(current_pos)
			
			obj = {"__type__": "file", "__id__": datastream_id, "__size__": total_size}
			
		return obj
	
	def _unpack(self, data):
		return msgpack.unpackb(data, object_hook=self._decode_unpack)
		
	def _decode_unpack(self, obj):
		if "__type__" in obj:
			if obj['__type__'] == "file":
				# TODO: Validate item
				datastream_id = obj['__id__']
				size = obj['__size__']
				self._create_tempfile(datastream_id)
				obj = self._tempfiles[datastream_id]
				obj._total_size = size
				
				self._datastream_started.append(datastream_id)
				self.event_datastream_start(obj, size)
		
		return obj
	
	def _create_datastream(self, obj):
		datastream_id = self._get_datastream_id()
		self._active_datastreams[datastream_id] = obj
		return datastream_id
	
	def _get_datastream_id(self):
		self._last_datastream_id += 1
		
		if self._last_datastream_id > 10000:
			self._last_datastream_id = 10
		
		if self._last_datastream_id in self._active_datastreams:
			return self._get_datastream_id()
		
		return self._last_datastream_id
	
	def _create_tempfile(self, datastream_id):
		# This creates a temporary file for the specified datastream if it does not already exist.
		if datastream_id not in self._tempfiles:
			self._filelike_counter += 1
			self._tempfiles[datastream_id] = FileLike(tempfile.SpooledTemporaryFile(max_size=self.max_mem), self._filelike_counter)
	
	def _receive_datastream(self, datastream_id, data):
		self._create_tempfile(datastream_id)
		obj = self._tempfiles[datastream_id]
		obj.write(data)
		obj._bytes_finished += len(data)
		
		if datastream_id in self._datastream_started:
			self.event_datastream_progress(obj, obj._bytes_finished, obj._total_size)
	
	def _send_system_message(self, data):
		encoded = self._pack(data)
		header = self._encode_header(3, len(encoded), 1)
		self.sendq.append(header + encoded)
	
	def _read_cycle(self):
		fileno = self.stream.fileno()
		
		while True:
			try:
				buff = self.stream.recv(self.recv_size)
				break
			except ssl.SSLError, err:
				if err.args[0] == ssl.SSL_ERROR_WANT_READ:
					select.select([self.stream], [], [])
				elif err.args[0] == ssl.SSL_ERROR_WANT_WRITE:
					select.select([], [self.stream], [])
				else:
					raise
		
		if not buff:
			# The client has ceased to exist - most likely it has closed the connection.
			del self.reactor.objmap[fileno]
			self.reactor.queue.remove(self.stream)
			self.event_disconnected()
		
		buff = self._tempbuff + buff
		self._tempbuff = b""
		
		while buff != b"":
			if self._read_left > 0:
				# Continue reading a chunk in progress
				if self._read_left <= len(buff):
					# All the data we need is in the buffer.
					self._read_buff += buff[:self._read_left]
					buff = buff[self._read_left:]
					
					self._read_left = 0 
					
					self._process_chunk(self._chunktype, self._channel, self._read_buff)
					
					self._read_buff = b""
				else:
					# We need to read more data than is in the buffer.
					self._read_buff += buff
					self._read_left -= len(buff)
					buff = b""
			elif len(buff) >= 7:
				# Start reading a new chunk
				header = buff[:7]
				
				chunktype, chunksize, channel = self._decode_header(header)
				
				buff = buff[7:]
				self._read_left = chunksize
				self._chunksize = chunksize
				self._chunktype = chunktype
				self._channel = channel
				
			else:
				# We need more data to do anything meaningful
				self._tempbuff = buff
				buff = b""
	
	def _process_chunk(self, chunktype, channel, data):
		if chunktype == 1:
			# Client message
			self.event_receive(self._unpack(data))
		elif chunktype == 2:
			# Datastream chunk
			self._receive_datastream(channel, data)
		elif chunktype == 3:
			# System message
			self._process_system_message(msgpack.unpackb(data))
	
	def _process_system_message(self, data):
		if data['type'] == "datastream_finished":
			datastream_id = data['id']
			self.event_datastream_finished(self._tempfiles[datastream_id])
			self._datastream_started.remove(datastream_id)
			del self._tempfiles[datastream_id]
	
	def _write_cycle(self):
		if len(self.sendq) > 0:
			item = self.sendq.popleft()
			self._send_chunk(item)
		
		if len(self._active_datastreams) > 0:
			to_delete = []
			
			for datastream_id, datastream in self._active_datastreams.iteritems():
				data = datastream.read(self.chunk_size)
				
				if data:
					header = self._encode_header(2, len(data), datastream_id)
					
					self._send_chunk(header + data)
				else:
					# Done with this datastream.
					self._send_system_message({"type": "datastream_finished", "id": datastream_id})
					to_delete.append(datastream_id)
			
			for datastream_id in to_delete:
				del self._active_datastreams[datastream_id]
	
	def send(self, data):
		encoded = self._pack(data)
		header = self._encode_header(1, len(encoded), 0)
		self.sendq.append(header + encoded)
	
	def event_connected(self):
		pass
	
	def event_disconnected(self):
		pass
	
	def event_receive(self, data):
		pass
	
	def event_datastream_start(self, stream, total_bytes):
		pass
	
	def event_datastream_progress(self, stream, finished_bytes, total_bytes):
		pass
	
	def event_datastream_finished(self, stream):
		pass
