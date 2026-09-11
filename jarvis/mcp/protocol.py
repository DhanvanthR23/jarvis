import json
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MCPRequest:
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class MCPResponse:
    id: str
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

def serialize_request(request: MCPRequest) -> bytes:
    data = {"method": request.method, "params": request.params, "id": request.id}
    return (json.dumps(data) + "\n").encode("utf-8")

def deserialize_request(data: bytes) -> MCPRequest:
    parsed = json.loads(data.decode("utf-8").strip())
    return MCPRequest(method=parsed["method"], params=parsed.get("params", {}), id=parsed.get("id", str(uuid.uuid4())))

def serialize_response(response: MCPResponse) -> bytes:
    data = {"id": response.id, "result": response.result, "error": response.error}
    return (json.dumps(data) + "\n").encode("utf-8")

def deserialize_response(data: bytes) -> MCPResponse:
    parsed = json.loads(data.decode("utf-8").strip())
    return MCPResponse(id=parsed["id"], result=parsed.get("result"), error=parsed.get("error"))
