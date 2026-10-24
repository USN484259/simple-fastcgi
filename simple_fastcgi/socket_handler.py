#!/usr/bin/env python3

import os
import sys
import socket
import selectors
from io import BufferedIOBase
from socketserver import BaseServer, BaseRequestHandler, ThreadingMixIn, _ServerSelector
from contextlib import suppress
from threading import Event

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

	def _send_out(self):
		while True:
			resp = self.protocol.fetch(0x1000)
			if not resp:
				break
			self.request.send(resp)

	def handle(self):
		pass

	def finish(self):
		self.protocol.complete()
		self._send_out()

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

	def write(self, data):
		self.protocol.write(data)
		self._send_out()

	def write_err(self, data):
		self.protocol.write_err(data)
		self._send_out()

	def flush(self):
		self.protocol.flush()
		self._send_out()


# duplicated TCPServer code, with already listening fd
class FcgiServer(BaseServer):
	def __init__(self, handler, sock = None):
		super().__init__(None, handler)
		# cannot access private members in parent, create our own
		self._is_shut_down = Event()
		self._shutdown_request = False

		self.socket = sock or socket.socket(fileno = sys.stdin.fileno())
		self._pipe_r = None
		self._pipe_w = None
		self.watches = {}

	def server_close(self):
		self.socket.close()
		if self._pipe_r is not None:
			os.close(self._pipe_r)
		if self._pipe_w is not None:
			os.close(self._pipe_w)

	def fileno(self):
		return self.socket.fileno()

	def get_request(self):
		return self.socket.accept()

	def shutdown_request(self, request):
		with suppress(OSError):
			request.shutdown(socket.SHUT_WR)
		self.close_request(request)

	def close_request(self, request):
		request.close()

	def wakeup(self):
		if self._pipe_w is not None:
			with suppress(BlockingIOError):
				os.write(self._pipe_w, b"x")

	def _on_wakeup(self, fd):
		with suppress(BlockingIOError):
			while os.read(self._pipe_r, 0x1000):
				pass

	def add_watch(self, fd, func):
		if not callable(func):
			raise ValueError("func not callable")
		self.watches[fd] = func

	def __enter__(self):
		self._pipe_r, self._pipe_w = os.pipe()
		os.set_blocking(self._pipe_r, False)
		os.set_blocking(self._pipe_w, False)
		self.add_watch(self._pipe_r, self._on_wakeup)
		return self

	def shutdown(self, /, wait = True):
		self._shutdown_request = True
		self.wakeup()
		if wait:
			self._is_shut_down.wait()

	def serve_forever(self, poll_interval = None):
		self._is_shut_down.clear()
		try:
			with _ServerSelector() as selector:
				selector.register(self, selectors.EVENT_READ)
				for fd, func in self.watches.items():
					selector.register(fd, selectors.EVENT_READ)

				while not self._shutdown_request:
					ready = selector.select(poll_interval)
					if self._shutdown_request:
						break
					for key, ev in ready:
						if key.fileobj is self:
							self._handle_request_noblock()
						else:
							func = self.watches.get(key.fileobj)
							if func is not None:
								func(key.fileobj)

					self.service_actions()

		finally:
			self._shutdown_request = False
			self._is_shut_down.set()


class FcgiThreadingServer(ThreadingMixIn, FcgiServer):
	pass
