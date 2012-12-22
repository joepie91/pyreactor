import os, shutil

class FileLike:
	_pos = 0
	_total_size = 0
	_bytes_finished = 0
	
	def __init__(self, original, file_id):
		self._file = original
		self.id = file_id
	
	def write(self, str):
		return self._file.write(str)
		
	def read(self, size=-1):
		self._file.seek(self._pos)
		data = self._file.read(size)
		self._pos = self._file.tell()
		self._file.seek(0, os.SEEK_END)
		return data

	def tell(self):
		return self._file.tell()
	
	def copy(self, destination):
		shutil.copyfileobj(self, open(destination, "wb"), 4096)
