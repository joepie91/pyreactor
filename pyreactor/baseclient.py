import socket, ssl, msgpack, tempfile, os
from collections import deque
from bitstring import BitArray
from filelike import FileLike

class BaseClient:
	_tempbuff = b""
	_read_left = 0
	_read_buff = b""
	_tempfiles = {}
	_last_datastream_id = 10
	_active_datastreams = {}
	_filelike_counter = 0
	max_mem = 32 * 1024 * 1024
	reactor = None
	
	def __init__(self, host=None, port=None, use_ssl=False, allowed_certs=None, conn=None, source=None, **kwargs):
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
		
		return obj
	
	def _create_datastream(self, obj):
		datastream_id = self._get_datastream_id()
		self._active_datastreams[datastream_id] = obj
		#print "Datastream created on ID %d." % datastream_id
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
		self.event_datastream_progress(obj, obj._bytes_finished, obj._total_size)
	
	def _send_system_message(self, data):
		encoded = self._pack(data)
		header = self._encode_header(3, len(encoded), 1)
		self.sendq.append(header + encoded)
	
	def send(self, data):
		encoded = self._pack(data)
		header = self._encode_header(1, len(encoded), 1)
		self.sendq.append(header + encoded)
	
	def event_connected(self):
		pass
	
	def event_disconnected(self):
		pass
	
	def event_receive(self, data):
		pass
	
	def event_datastream_progress(self, stream, finished_bytes, total_bytes):
		pass
	
	def event_datastream_finished(self, stream):
		pass
