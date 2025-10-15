# Simple FastCGI

simple FastCGI protocol parser and sync/async handler in pure python


## Example (sync)

```python
import json
from simple_fastcgi import *

class example_handler(HttpResponseMixin, FcgiHandler):
	def handle(self):
		self.send_response(200, "application/json", self.environ)

if __name__ == "__main__":
	with FcgiServer(example_handler) as server:
		server.serve_forever()
```


## Example (async)


```python
import json
import asyncio
from simple_fastcgi import *

class example_handler(AsyncHttpResponseMixin, AsyncFcgiHandler):
	async def handle(self):
		await self.send_response(200, "application/json", self.environ)

async def main():
	async with AsyncFcgiServer(example_handler) as server:
		await server.serve_forever()

if __name__ == "__main__":
	asyncio.run(main())
```


## API reference

The import module name is **simple_fastcgi**

### Exceptions

**ProtocolError**

Raised when encountered FastCGI protocol violations.


### Handlers

**class FcgiHandler**

FastCGI Handler, subclass of BaseRequestHandler.
To implement your own handler, subclass FcgiHandler and override the **handle()** method.

**environ**

Member *environ* is a *dictionary* containing key-value pairs from the webserver.
The keys are converted to upper-case.

**handle()**

Override this method and do all the work here to serve a request.

**aborted()**

Check if the FastCGI request has been aborted by the webserver.

**read(sz = -1)**

Read and return up to *sz* bytes from input stream. If *sz* < 0, read until EOF.
Returns empty bytes object on EOF.

**readinto(buffer)**

Read from input stream into *buffer*, return the actual read byte count.
Returns 0 on EOF.

**readall()**

Read input stream until EOF and return all the data.

**write(data)**

Write *data* to the output stream.

**write_err(data)**

Write *data* to the error stream.



**class AsyncFcgiHandler**

Async variant of **FcgiHandler**. methods are the same, except being async.

async **handle()**

**aborted()**

async **read(sz = -1)**

async **readinto(buffer)**

async **readall()**

async **write(data)**

async **write_err(data)**


### Servers

**class FcgiServer**

Subclass of **BaseServer**, but instead listening on FCGI_LISTENSOCK_FILENO ( fd 0 ).
Can be used with context manager.

**__init__(handler, sockfd = sys.stdin.fileno())**

Initialize a server object. Subclass may override and do extra initialization.

*handler* is the handler-class which is instantiated on each request.

*sockfd* is a listening socket on which the server is running, defaults to fd 0 in conforming to FastCGI Specification.

**fileno()**

Get the underlying fd of the server object. Returns *sockfd*.

**shutdown()**

Stop the server.

**serve_forever()**

Start the server and block until shutdown.

**service_actions()**

Called in serve_forever loop. Subclass may override and do their own actions.


**class AsyncFcgiServer**

Async variant of **FcgiServer**. methods are the same, except being async.
Can be used with async context manager.

Note there is no **service_actions()** in **AsyncFcgiServer**, since it runs on event loop instead of its own loop, and one can easily schedule tasks to event loop.

**__init__(handler, sockfd = sys.stdin.fileno())**

**fileno()**

**get_loop()**

Get the event loop on which the server is running.

async **shutdown()**

async **serve_forever()**


### Mixins

**class HttpResponseMixin**

Helper mixin class for **FcgiServer**, to construct CGI/HTTP responses.

**send_response(code, /, mime_type = "text/plain", data = None, \*, extra_headers = [])**

Construct a CGI document response and write to output stream.

*code* is the HTTP status code of the response.

*mime_type* is the content-type of the response.

*extra_headers* is the extra HTTP header fields that should be included in the response header.

*data* is the payload of the response.
- if *data* is a function, it is assumed to be a generator and called to get chunks of data.
- if *data* is a string, it is encoded in UTF-8.
- if "json" appears in *mime_type* and *data* is not bytes-like, try to encode *data* as json.
- else, append *data* to payload as-is.

Note that you **can** mix this method with *write()* calls. For example, you can call this method,
passing first data chunk as *data* parameter, followed by multiple *write()* calls to append more data.

Also note that this method does **not** calculate or append a *content-length* header for you.
You need to handle *content-length* header yourself, either omit this header, or calculate in advance.

**send_redirect(target)**

Construct a CGI redirect response and write to output stream.

*target* is the redirect target, it can be either *local-Location* or *client-Location* as defined in CGI Specification.


**AsyncHttpResponseMixin**

Async variant of **HttpResponseMixin**. methods are the same, except being async

async **send_response(code, /, mime_type = "text/plain", data = None, \*, extra_headers = [])**

Note that if *data* is a function, it is assumed to be an **async generator** instead.

async **send_redirect(target)**


## Reference

+ [FastCGI Specification](https://fast-cgi.github.io/spec.html) (Unofficial)
+ [RFC 3875](https://www.rfc-editor.org/rfc/rfc3875): The Common Gateway Interface (CGI) Version 1.1

