#!/usr/bin/env python3

import sys
import socket
from io import BufferedIOBase
from socketserver import BaseServer, BaseRequestHandler, ThreadingMixIn

from .protocol import *


class FcgiHandler(BaseRequestHandler, BufferedIOBase):
	def setup(self):
		self.protocol = fastcgi_protocol()

		while not self.protocol.ready:
			data = self.request.recv(0x1000)
			self.protocol.feed(data)

		self.environ = self.protocol.environ
		self.rfile = self
		self.wfile = self

	def handle(self):
		pass

	def finish(self):
		self.protocol.complete()
		while True:
			resp = self.protocol.fetch(0x1000)
			if not resp:
				break

			self.request.send(resp)

	def readable(self):
		return True

	def writable(self):
		return True

	def aborted(self):
		return self.protocol.aborted

	def readinto(self, buffer):
		while True:
			size = self.protocol.read(buffer)
			if size or self.protocol.eof:
				return size
			data = self.request.recv(0x1000)
			self.protocol.feed(data)

	def readall(self):
		while not self.protocol.eof:
			data = self.request.recv(0x1000)
			self.protocol.feed(data)

		return self.protocol.readall()

	def read(self, sz = -1):
		if sz < 0:
			return self.readall()
		buffer = bytearray(sz)
		size = self.readinto(buffer)
		return buffer[:size]


	def write(self, data, *, flush = False):
		self.protocol.write(data)
		if flush:
			self.protocol.flush()

		while True:
			resp = self.protocol.fetch(0x1000)
			if resp:
				self.request.send(resp)
			else:
				break

	def write_err(self, data):
		self.protocol.write_err(data)
		while True:
			resp = self.protocol.fetch(0x1000)
			if resp:
				self.request.send(resp)
			else:
				break


# duplicated TCPServer code, with already listening fd
class FcgiServer(BaseServer):
	def __init__(self, handler, sockfd = sys.stdin.fileno()):
		super().__init__(None, handler)
		self.socket = socket.socket(fileno = sockfd)

	def server_close(self):
		self.socket.close()

	def fileno(self):
		return self.socket.fileno()

	def get_request(self):
		return self.socket.accept()

	def shutdown_request(self, request):
		try:
			request.shutdown(socket.SHUT_WR)
		except OSError:
			pass
		self.close_request(request)

	def close_request(self, request):
		request.close()


class FcgiThreadingServer(ThreadingMixIn, FcgiServer):
	pass
