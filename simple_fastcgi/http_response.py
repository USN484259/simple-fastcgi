#!/usr/bin/env python3

from json import dumps as json_dumps

status_table = {
	100:	"100 Continue",
	101:	"101 Switching Protocols",
	102:	"102 Processing",
	103:	"103 Early Hints",
	200:	"200 OK",
	201:	"201 Created",
	202:	"202 Accepted",
	203:	"203 Non-Authoritative Information",
	204:	"204 No Content",
	205:	"205 Reset Content",
	206:	"206 Partial Content",
	207:	"207 Multi-Status",
	208:	"208 Already Reported",
	226:	"226 IM Used",
	300:	"300 Multiple Choices",
	301:	"301 Moved Permanently",
	302:	"302 Found",
	303:	"303 See Other",
	304:	"304 Not Modified",
	305:	"305 Use Proxy",
	307:	"307 Temporary Redirect",
	308:	"308 Permanent Redirect",
	400:	"400 Bad Request",
	401:	"401 Unauthorized",
	402:	"402 Payment Required",
	403:	"403 Forbidden",
	404:	"404 Not Found",
	405:	"405 Method Not Allowed",
	406:	"406 Not Acceptable",
	407:	"407 Proxy Authentication Required",
	408:	"408 Request Timeout",
	409:	"409 Conflict",
	410:	"410 Gone",
	411:	"411 Length Required",
	412:	"412 Precondition Failed",
	413:	"413 Content Too Large",
	414:	"414 URI Too Long",
	415:	"415 Unsupported Media Type",
	416:	"416 Range Not Satisfiable",
	417:	"417 Expectation Failed",
	418:	"418 I'm a teapot",
	421:	"421 Misdirected Request",
	422:	"422 Unprocessable Content",
	423:	"423 Locked",
	424:	"424 Failed Dependency",
	425:	"425 Too Early",
	426:	"426 Upgrade Required",
	428:	"428 Precondition Required",
	429:	"429 Too Many Requests",
	431:	"431 Request Header Fields Too Large",
	451:	"451 Unavailable For Legal Reasons",
	500:	"500 Internal Server Error",
	501:	"501 Not Implemented",
	502:	"502 Bad Gateway",
	503:	"503 Service Unavailable",
	504:	"504 Gateway Timeout",
	505:	"505 HTTP Version Not Supported",
	506:	"506 Variant Also Negotiates",
	507:	"507 Insufficient Storage",
	508:	"508 Loop Detected",
	510:	"510 Not Extended",
	511:	"511 Network Authentication Required",
}


def make_header(code, mime_type, extra_headers, data, json):
	buffer = bytearray()
	resp_name = status_table.get(code)
	if not resp_name:
		resp_name = str(code)
	if not mime_type:
		mime_type = (json is None) and "text/plain" or "application/json"

	mime_ext = ""
	if mime_type.startswith("text/") and "charset=" not in mime_type:
		mime_ext = "; charset=utf-8"
	resp_str = "Status: %s\r\nContent-type: %s%s\r\n" % (resp_name, mime_type, mime_ext)
	buffer[:] = resp_str.encode()
	for header in extra_headers:
		buffer += header.encode()
		buffer += b"\r\n"
	buffer += b"\r\n"

	if data is None and json is None and mime_type == "text/plain":
		buffer += resp_name.encode()
		buffer += b"\r\n"

	return buffer


def process_data(data, json):
	if json is not None:
		return json_dumps(json, indent = '\t', ensure_ascii = False).encode()
	elif data is None:
		return b''
	elif isinstance(data, str):
		return data.encode()
	else:
		return data


class HttpResponseMixin:
	def send_response(self, code, /, mime_type = None, data = None, *, json = None, extra_headers = []):
		header = make_header(code, mime_type, extra_headers, data, json)
		self.write(header)

		if callable(data):
			for chunk in data():
				if isinstance(chunk, str):
					chunk = chunk.encode()
				self.write(chunk)
		else:
			self.write(process_data(data, json))

	def send_redirect(self, target):
		location_str = "Location: %s\r\n\r\n" % target
		self.write(location_str.encode())


class AsyncHttpResponseMixin:
	async def send_response(self, code, /, mime_type = "text/plain", data = None, *, json = None, extra_headers = []):
		header = make_header(code, mime_type, extra_headers, data, json)
		await self.write(header)

		if callable(data):
			async for chunk in data():
				if isinstance(chunk, str):
					chunk = chunk.encode()
				await self.write(chunk)
		else:
			await self.write(process_data(data, json))

	async def send_redirect(self, target):
		location_str = "Location: %s\r\n\r\n" % target
		await self.write(location_str.encode())

