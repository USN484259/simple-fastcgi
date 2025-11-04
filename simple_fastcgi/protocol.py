#!/usr/bin/env python3

import struct
from collections import deque, namedtuple


# constants

FCGI_VERSION_1		= 1

FCGI_BEGIN_REQUEST	= 1
FCGI_ABORT_REQUEST	= 2
FCGI_END_REQUEST	= 3
FCGI_PARAMS		= 4
FCGI_STDIN		= 5
FCGI_STDOUT		= 6
FCGI_STDERR		= 7
FCGI_DATA		= 8
FCGI_GET_VALUES		= 9
FCGI_GET_VALUES_RESULT	= 10
FCGI_UNKNOWN_TYPE	= 11

FCGI_KEEP_CONN		= 1

FCGI_RESPONDER		= 1
FCGI_AUTHORIZER		= 2
FCGI_FILTER		= 3

FCGI_REQUEST_COMPLETE	= 0
FCGI_CANT_MPX_CONN	= 1
FCGI_OVERLOADED		= 2
FCGI_UNKNOWN_ROLE	= 3


# static objects

struct_record = struct.Struct(">BBHHBB")
struct_len_4b = struct.Struct(">I")
struct_begin_request = struct.Struct(">HBBI")
struct_end_request = struct.Struct(">iBBBB")

Record = namedtuple("Record", ("version", "type", "request_id", "length", "data"))

class ProtocolError(Exception):
	pass


# helper functions

def parse_var_len(data):
	length = int(data[0])
	if length & 0x80:
		return struct_len_4b.unpack_from(data)[0] & (0x7FFFFFFF), 4
	else:
		return length, 1


def parse_kv_pair(data, table):
	try:
		key_len, key_off = parse_var_len(data)
		val_len, val_off = parse_var_len(data[key_off:])
	except (IndexError, struct.error):
		return

	key_off = key_off + val_off
	val_off = key_off + key_len
	length = val_off + val_len
	if len(data) < length:
		return
	key = data[key_off : key_off + key_len]
	val = data[val_off : val_off + val_len]
	table[key.decode().upper()] = val.decode()
	return length


def pack_var_len(s):
	if len(s) < 0x80:
		return bytes(len(s))
	else:
		return struct_len_4b.pack(len(s) | 0x80000000)


def pack_kv_pair(k, v):
	return pack_var_len(k) + pack_var_len(v) + k + v


def pack_end_request(status, protocol_status = FCGI_REQUEST_COMPLETE):
	return struct_end_request.pack(status, protocol_status, 0, 0, 0)


def pack_data(data):
	return data


def pack_get_values(table):
	result = bytearray()
	for k, v in table:
		result += pack_kv_pair(k, v)
	return result


def pack_unknown(ty):
	result = bytearray(8)
	result[0] = ty
	return result


packer_table = {
	FCGI_END_REQUEST:	pack_end_request,
	FCGI_STDOUT:		pack_data,
	FCGI_STDERR:		pack_data,
	FCGI_GET_VALUES_RESULT:	pack_get_values,
	FCGI_UNKNOWN_TYPE:	pack_unknown,
}

def record_unpack(data):
	if len(data) < struct_record.size:
		return
	info = struct_record.unpack_from(data)
	length = struct_record.size + info[3] + info[4]
	if len(data) < length:
		return
	return Record(*info[0:3], length, data[struct_record.size : struct_record.size + info[3]])

def record_pack(ty, request_id, *args):
	packer = packer_table.get(ty)
	if not packer:
		raise ProtocolError("invalid type: %d" % ty)
	data = packer(*args)
	if len(data) > 0xFFFF:
		raise ProtocolError("payload exceeds limit: %d" % len(data))

	padding = (struct_record.size - (len(data) & (struct_record.size - 1))) % struct_record.size
	header = struct_record.pack(FCGI_VERSION_1, ty, request_id, len(data), padding, 0)
	return header + data + bytes(padding)


# classes

class fastcgi_protocol:
	# internal methods

	def parse_begin_request(self, record):
		if not self.request_id:
			self.request_id = record.request_id
		elif self.request_id == record.request_id:
			raise ProtocolError("repeating begin_request %d" % record.request_id)
		else:
			resp = record_pack(FCGI_END_REQUEST, record.request_id, 0, FCGI_CANT_MPX_CONN)
			self.output_queue.append(resp)
			return

		try:
			info = struct_begin_request.unpack(record.data)
		except struct.error as e:
			raise ProtocolError(str(e))

		if info[0] not in (FCGI_RESPONDER, FCGI_AUTHORIZER):
			resp = record_pack(FCGI_END_REQUEST, record.request_id, 0, FCGI_UNKNOWN_ROLE)
			self.output_queue.append(resp)
			return

		self.role = info[0]
		self.keep_conn = bool(info[1] & FCGI_KEEP_CONN)
		return

	def parse_abort_request(self, record):
		if self.request_id != record.request_id:
			return
		self.aborted = True

	def parse_params(self, record):
		if self.request_id != record.request_id:
			return
		self.params += record.data
		while self.params:
			length = parse_kv_pair(self.params, self.environ)
			if not length:
				break
			self.params[:] = self.params[length:]

	def parse_stdin(self, record):
		if self.request_id != record.request_id:
			return
		if record.data:
			self.stdin += record.data
		else:
			self.eof = True
		if self.params:
			raise ProtocolError("incomplete params")
		self.ready = True

	def parse_get_values(self, record):
		if record.request_id != 0:
			raise ProtocolError("get_values with request_id %d" % record.request_id)
		query_table = {}
		data = bytearray(record.data)
		while data:
			length = parse_kv_pair(data, query_table)
			if not length:
				raise ProtocolError("incomplete get_values")
			data[:] = data[length:]

		resp_table = {}
		for key in query_table.keys():
			if key == "FCGI_MPXS_CONNS":
				resp_table[key] = "0"

		resp = record_pack(FCGI_GET_VALUES_RESULT, 0, resp_table)
		self.output_queue.append(resp)

	def default_management_handler(self, record):
		if record.type == FCGI_GET_VALUES:
			return self.parse_get_values(record)

	# public methods

	def __init__(self, /, write_buffer_size = 0x1000, management_handler = None):
		self.request_id = None
		self.role = None
		self.keep_conn = None
		self.ready = False
		self.eof = False
		self.aborted = False
		self.write_buffer_size = write_buffer_size
		self.management_handler = management_handler or self.default_management_handler
		self.environ = {}
		self.params = bytearray()
		self.stdin = bytearray()
		self.stdout = bytearray()
		self.input_queue = bytearray()
		self.output_queue = deque()

		self.parser_table = {
			FCGI_BEGIN_REQUEST:	self.parse_begin_request,
			FCGI_ABORT_REQUEST:	self.parse_abort_request,
			FCGI_PARAMS:		self.parse_params,
			FCGI_STDIN:		self.parse_stdin,
			FCGI_DATA:		None,
			# FCGI_GET_VALUES:	self.parse_get_values,
		}

	def feed(self, data):
		self.input_queue += data
		try:
			while self.input_queue:
				record = record_unpack(self.input_queue)
				if record:
					self.input_queue[:] = self.input_queue[record.length:]
				else:
					break

				parser = self.parser_table.get(record.type)
				if not parser:
					if record.request_id == 0:
						resp = self.management_handler(record)
						if resp is None:
							resp = record_pack(FCGI_UNKNOWN_TYPE, 0, record.type)

						self.output_queue.append(resp)
						continue
					else:
						raise ProtocolError("invalid record type %d" % record.type)

				parser(record)

		except Exception:
			raise

	def fetch(self, expected_size):
		data = bytearray()
		while self.output_queue:
			if len(data) and len(data) + len(self.output_queue[0]) > expected_size:
				break
			data += self.output_queue.popleft()

		return data

	def read(self, buffer):
		size = min(len(buffer), len(self.stdin))
		buffer[:size] = self.stdin[:size]
		self.stdin[:] = self.stdin[size:]
		return size

	def readall(self):
		data = self.stdin
		self.stdin = bytearray()
		return data

	def flush(self):
		while self.stdout:
			size = min(len(self.stdout), 0x8000)
			resp = record_pack(FCGI_STDOUT, self.request_id, self.stdout[:size])
			self.stdout[:] = self.stdout[size:]
			self.output_queue.append(resp)

	def write(self, data):
		self.stdout += data
		if len(self.stdout) >= self.write_buffer_size:
			self.flush()

	def write_err(self, data):
		if not data:
			return
		resp = record_pack(FCGI_STDERR, self.request_id, data)
		self.output_queue.append(resp)

	def complete(self, status = 0):
		self.flush()
		resp = record_pack(FCGI_STDOUT, self.request_id, bytes())
		resp = record_pack(FCGI_STDERR, self.request_id, bytes())
		resp = record_pack(FCGI_END_REQUEST, self.request_id, status)
		self.output_queue.append(resp)
