#!/usr/bin/env python3

import json

status_table = {
	200:	"200 OK",
	206:	"206 Partial Content",
	400:	"400 Bad Request",
	403:	"403 Forbidden",
	404:	"404 Not Found",
	405:	"405 Method Not Allowed",
	416:	"416 Range Not Satisfiable",
	429:	"429 Too Many Requests",
	500:	"500 Internal Server Error",
	502:	"502 Bad Gateway",
	504:	"504 Gateway Timeout",
}


def make_header(code, mime_type, extra_headers, has_data):
	buffer = bytearray()
	resp_name = status_table.get(code)
	if not resp_name:
		resp_name = str(code)

	mime_ext = ""
	if mime_type.startswith("text/") and "charset" not in mime_type:
		mime_ext = "; charset=utf-8"
	resp_str = "Status: %s\r\nContent-type: %s%s\r\n" % (resp_name, mime_type, mime_ext)
	buffer[:] = resp_str.encode()
	for header in extra_headers:
		buffer += header.encode()
		buffer += b"\r\n"
	buffer += b"\r\n"

	if not has_data and code >= 400 and mime_type == "text/plain":
		buffer += resp_name.encode()
		buffer += b"\r\n"

	return buffer


class HttpResponseMixin:
	def send_response(self, code, /, mime_type = "text/plain", data = None, *, extra_headers = [], flush = True):
		header = make_header(code, mime_type, extra_headers, (data is None))
		self.write(header)

		if data is not None:
			if callable(data):
				for chunk in data():
					if isinstance(chunk, str):
						chunk = chunk.encode()
					self.write(chunk, flush = flush)
				return

			if isinstance(data, str):
				data = data.encode()
			elif (not isinstance(data, (bytes, bytearray))) and ("json" in mime_type):
				data = json.dumps(data, indent = '\t', ensure_ascii = False).encode()

			self.write(data)


	def send_redirect(self, target):
		location_str = "Location: %s\r\n\r\n" % target
		self.write(location_str.encode())


class AsyncHttpResponseMixin:
	async def send_response(self, code, /, mime_type = "text/plain", data = None, *, extra_headers = [], flush = True):
		header = make_header(code, mime_type, extra_headers, (data is None))
		await self.write(header)

		if data is not None:
			if callable(data):
				async for chunk in data():
					if isinstance(chunk, str):
						chunk = chunk.encode()
					await self.write(chunk, flush = flush)
				return

			if isinstance(data, str):
				data = data.encode()
			elif (not isinstance(data, bytes)) and ("json" in mime_type):
				data = json.dumps(data, indent = '\t', ensure_ascii = False).encode()

			await self.write(data)


	async def send_redirect(self, target):
		location_str = "Location: %s\r\n\r\n" % target
		await self.write(location_str.encode())

