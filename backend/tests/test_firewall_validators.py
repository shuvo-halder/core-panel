import os
import sys
import types
import unittest

# Provide minimal mocks for fastapi/pydantic/starlette if running in container without them
if "pydantic" not in sys.modules:
    fake_pydantic = types.ModuleType("pydantic")
    class FakeBaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump_json(self):
            import json
            return json.dumps(self.__dict__)
        @classmethod
        def model_validate_json(cls, s):
            import json
            inst = cls()
            inst.__dict__.update(json.loads(s))
            return inst
    fake_pydantic.BaseModel = FakeBaseModel
    fake_pydantic.Field = lambda *args, **kwargs: None
    fake_pydantic.ConfigDict = dict
    fake_pydantic.EmailStr = str
    sys.modules["pydantic"] = fake_pydantic

if "pydantic_settings" not in sys.modules:
    fake_ps = types.ModuleType("pydantic_settings")
    class FakeSettings:
        LOG_LEVEL = "INFO"
        PORT = 8000
        APP_VERSION = "0.1.0"
        ENVIRONMENT = "test"
    fake_ps.BaseSettings = FakeSettings
    fake_ps.SettingsConfigDict = dict
    sys.modules["pydantic_settings"] = fake_ps

if "fastapi" not in sys.modules:
    class FakeStatus:
        HTTP_200_OK = 200
        HTTP_201_CREATED = 201
        HTTP_400_BAD_REQUEST = 400
        HTTP_401_UNAUTHORIZED = 401
        HTTP_403_FORBIDDEN = 403
        HTTP_404_NOT_FOUND = 404
        HTTP_409_CONFLICT = 409
        HTTP_500_INTERNAL_SERVER_ERROR = 500
        HTTP_503_SERVICE_UNAVAILABLE = 503

    def fake_route_decorator(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

    class FakeRouter:
        def __init__(self, *args, **kwargs):
            pass
        def get(self, *args, **kwargs):
            return fake_route_decorator(*args, **kwargs)
        def post(self, *args, **kwargs):
            return fake_route_decorator(*args, **kwargs)
        def delete(self, *args, **kwargs):
            return fake_route_decorator(*args, **kwargs)
        def put(self, *args, **kwargs):
            return fake_route_decorator(*args, **kwargs)

    fake_fastapi = types.ModuleType("fastapi")
    fake_fastapi.status = FakeStatus
    fake_fastapi.Request = object
    fake_fastapi.APIRouter = FakeRouter
    fake_fastapi.Depends = lambda *args, **kwargs: None
    fake_fastapi.Query = lambda *args, **kwargs: None
    sys.modules["fastapi"] = fake_fastapi

    fake_fastapi_exc = types.ModuleType("fastapi.exceptions")
    fake_fastapi_exc.RequestValidationError = Exception
    sys.modules["fastapi.exceptions"] = fake_fastapi_exc

    fake_fastapi_resp = types.ModuleType("fastapi.responses")
    fake_fastapi_resp.JSONResponse = object
    sys.modules["fastapi.responses"] = fake_fastapi_resp

if "starlette.exceptions" not in sys.modules:
    fake_starlette = types.ModuleType("starlette")
    fake_starlette_exc = types.ModuleType("starlette.exceptions")
    fake_starlette_exc.HTTPException = Exception
    sys.modules["starlette"] = fake_starlette
    sys.modules["starlette.exceptions"] = fake_starlette_exc

from backend.app.core.errors import BadRequestError
from backend.app.core.validators import (
    validate_firewall_action,
    validate_firewall_comment,
    validate_firewall_direction,
    validate_firewall_port,
    validate_firewall_protocol,
    validate_firewall_source,
)


class TestFirewallValidators(unittest.TestCase):

    def test_validate_firewall_port_valid(self):
        self.assertEqual(validate_firewall_port("80"), "80")
        self.assertEqual(validate_firewall_port(22), "22")
        self.assertEqual(validate_firewall_port("3000:3010"), "3000:3010")
        self.assertEqual(validate_firewall_port(65535), "65535")
        self.assertEqual(validate_firewall_port("1:65535"), "1:65535")

    def test_validate_firewall_port_invalid(self):
        # Negative / 0
        with self.assertRaises(BadRequestError):
            validate_firewall_port(0)
        with self.assertRaises(BadRequestError):
            validate_firewall_port(-1)

        # > 65535
        with self.assertRaises(BadRequestError):
            validate_firewall_port(65536)
        with self.assertRaises(BadRequestError):
            validate_firewall_port("8000:70000")

        # Inverted range
        with self.assertRaises(BadRequestError):
            validate_firewall_port("3010:3000")

        # Non-digits / command injection attempts
        with self.assertRaises(BadRequestError):
            validate_firewall_port("80; rm -rf /")
        with self.assertRaises(BadRequestError):
            validate_firewall_port("80`whoami`")
        with self.assertRaises(BadRequestError):
            validate_firewall_port("http")

    def test_validate_firewall_protocol(self):
        self.assertEqual(validate_firewall_protocol("tcp"), "tcp")
        self.assertEqual(validate_firewall_protocol("TCP"), "tcp")
        self.assertEqual(validate_firewall_protocol("udp"), "udp")
        self.assertEqual(validate_firewall_protocol("any"), "any")
        self.assertEqual(validate_firewall_protocol(None), "any")

        with self.assertRaises(BadRequestError):
            validate_firewall_protocol("icmp")
        with self.assertRaises(BadRequestError):
            validate_firewall_protocol("tcp; ls")

    def test_validate_firewall_action(self):
        self.assertEqual(validate_firewall_action("allow"), "allow")
        self.assertEqual(validate_firewall_action("ALLOW"), "allow")
        self.assertEqual(validate_firewall_action("deny"), "deny")

        with self.assertRaises(BadRequestError):
            validate_firewall_action(None)
        with self.assertRaises(BadRequestError):
            validate_firewall_action("drop")
        with self.assertRaises(BadRequestError):
            validate_firewall_action("reject; rm")

    def test_validate_firewall_direction(self):
        self.assertEqual(validate_firewall_direction("in"), "in")
        self.assertEqual(validate_firewall_direction("out"), "out")
        self.assertEqual(validate_firewall_direction(None), "in")

        with self.assertRaises(BadRequestError):
            validate_firewall_direction("forward")

    def test_validate_firewall_source(self):
        self.assertEqual(validate_firewall_source("any"), "any")
        self.assertEqual(validate_firewall_source("Anywhere"), "any")
        self.assertEqual(validate_firewall_source(None), "any")
        self.assertEqual(validate_firewall_source("0.0.0.0/0"), "any")
        self.assertEqual(validate_firewall_source("192.168.1.100"), "192.168.1.100/32")
        self.assertEqual(validate_firewall_source("10.0.0.0/8"), "10.0.0.0/8")
        self.assertEqual(validate_firewall_source("2001:db8::/32"), "2001:db8::/32")

        # Invalid IP / metacharacters
        with self.assertRaises(BadRequestError):
            validate_firewall_source("999.999.999.999")
        with self.assertRaises(BadRequestError):
            validate_firewall_source("192.168.1.1; cat /etc/passwd")

    def test_validate_firewall_comment(self):
        self.assertIsNone(validate_firewall_comment(None))
        self.assertIsNone(validate_firewall_comment(""))
        self.assertEqual(validate_firewall_comment("SSH access rule"), "SSH access rule")
        self.assertEqual(validate_firewall_comment("api-v1_port-80.test"), "api-v1_port-80.test")

        # Metacharacters / control chars / newlines
        with self.assertRaises(BadRequestError):
            validate_firewall_comment("bad\ncomment")
        with self.assertRaises(BadRequestError):
            validate_firewall_comment("comment; rm -rf")
        with self.assertRaises(BadRequestError):
            validate_firewall_comment("a" * 65)  # Exceeds max length of 64


if __name__ == "__main__":
    unittest.main()
