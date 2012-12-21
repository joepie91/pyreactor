import socket, ssl

class Server:
	reactor = None
	
	def __init__(self, interface, port, client_class, use_ssl=False, **kwargs):
		self.interface = interface
		self.port = port
		self.objtype = "server"
		self.ssl = use_ssl
		self.client_class = client_class
		
		if self.ssl == True and (kwargs.haskey('certfile') == False or kwargs.hasfile('keyfile') == False):
			raise Exception("SSL mode requires both a certificate and a keyfile.")
		
		try:
			self.certificate = kwargs['certfile']
			self.keyfile = kwargs['keyfile']
		except KeyError, e:
			pass
		
		self.stream = socket.socket()
		self.stream.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.stream.bind((self.interface, self.port))
		self.stream.listen(5)
		
	def spawn_client(self, connection, source):
		if self.ssl == True:
			new_socket = ssl.wrap_socket(connection, server_side=True, certfile=self.certificate, keyfile=self.keyfile, ssl_version=ssl.PROTOCOL_TLSv1)
		else:
			new_socket = connection
			
		return self.client_class(conn=connection, source=source)
		
		
