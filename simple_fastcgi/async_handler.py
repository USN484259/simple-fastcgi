#!/usr/bin/env python3

import sys
import socket
import asyncio

from .protocol import *


class AsyncFcgiHandler:
	def __init__(self, reader, writer):
		self.reader = reader
		self.writer = writer
		self.protocol = fastcgi_protocol()

	async def setup(self):
		while not self.protocol.ready:
			data = await self.reader.read(0x1000)
			self.protocol.feed(data)

		self.environ = self.protocol.environ
		self.rfile = self
		self.wfile = self

	async def handle(self):
		pass

	async def finish(self):
			self.protocol.complete()
			while True:
				resp = self.protocol.fetch(0x1000)
				if not resp:
					break
				self.writer.write(resp)
				await self.writer.drain()
			self.writer.write_eof()
			await self.writer.drain()
			self.writer.close()
			await self.writer.wait_closed()

	def readable(self):
		return True

	def writable(self):
		return True

	def aborted(self):
		return self.protocol.aborted

	async def readinto(self, buffer):
		while True:
			size = self.protocol.read(buffer)
			if size or self.protocol.eof:
				return size
			data = await self.reader.read(0x1000)
			self.protocol.feed(data)

	async def readall(self):
		while not self.protocol.eof:
			data = await self.reader.read(0x1000)
			self.protocol.feed(data)

		return self.protocol.readall()

	async def read(self, sz = -1):
		if sz < 0:
			return await self.readall()
		buffer = bytearray(sz)
		size = await self.readinto(buffer)
		return buffer[:size]

	async def write(self, data, *, flush = False):
		self.protocol.write(data)
		if flush:
			self.protocol.flush()

		while True:
			resp = self.protocol.fetch(0x1000)
			if resp:
				self.writer.write(resp)
				await self.writer.drain()
			else:
				break

	async def write_err(self, data):
		self.protocol.write_err(data)
		while True:
			resp = self.protocol.fetch(0x1000)
			if resp:
				self.writer.write(resp)
				await self.writer.drain()
			else:
				break


class AsyncFcgiServer:
	def __init__(self, handler, sockfd = sys.stdin.fileno()):
		self.handler_class = handler
		self.sockfd = sockfd
		self.server = None

	def fileno(self):
		return self.sockfd

	def get_loop(self):
		return self.server.get_loop()

	async def shutdown(self):
		if self.server is not None:
			self.server.close()
			self.server.close_clients()
			await self.server.wait_closed()
			self.server = None

	async def on_request(self, reader, writer):
		handler = self.handler_class(reader, writer)
		await handler.setup()
		try:
			await handler.handle()
		finally:
			await handler.finish()

	async def __aenter__(self):
		sock = socket.socket(fileno = self.sockfd)
		self.server = await asyncio.start_server(self.on_request, sock = sock, start_serving = True)
		return self

	async def __aexit__(self, exc_type, exc_value, traceback):
		await self.shutdown()

	async def serve_forever(self):
		await self.server.serve_forever()
