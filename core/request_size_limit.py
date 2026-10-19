class RequestSizeLimitMiddleware:
    def __init__(self, app, max_body_size: int = 10 * 1024):
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or not scope.get("path", "").startswith("/api/")
            or scope.get("method") not in {"POST", "PUT", "PATCH"}
        ):
            await self.app(scope, receive, send)
            return

        body_size = 0
        request_messages = []
        while True:
            message = await receive()
            request_messages.append(message)
            if message["type"] == "http.request":
                body_size += len(message.get("body", b""))
                if body_size > self.max_body_size:
                    response_body = b'{"error":"El cuerpo de la solicitud es demasiado grande."}'
                    await send(
                        {
                            "type": "http.response.start",
                            "status": 413,
                            "headers": [
                                (b"content-type", b"application/json"),
                                (b"content-length", str(len(response_body)).encode()),
                            ],
                        }
                    )
                    await send(
                        {"type": "http.response.body", "body": response_body}
                    )
                    return
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                return

        async def replay_request():
            if request_messages:
                return request_messages.pop(0)
            return await receive()

        await self.app(scope, replay_request, send)
