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
    sys.modules["pydantic"] = fake_pydantic

if "pydantic_settings" not in sys.modules:
    fake_ps = types.ModuleType("pydantic_settings")
    class FakeSettings:
        LOG_LEVEL = "INFO"
    fake_ps.BaseSettings = FakeSettings
    fake_ps.SettingsConfigDict = dict
    sys.modules["pydantic_settings"] = fake_ps

if "fastapi" not in sys.modules:
    class FakeStatus:
        HTTP_400_BAD_REQUEST = 400
        HTTP_401_UNAUTHORIZED = 401
        HTTP_403_FORBIDDEN = 403
        HTTP_404_NOT_FOUND = 404
        HTTP_409_CONFLICT = 409
        HTTP_500_INTERNAL_SERVER_ERROR = 500

    fake_fastapi = types.ModuleType("fastapi")
    fake_fastapi.status = FakeStatus
    fake_fastapi.Request = object
    fake_fastapi.APIRouter = lambda *args, **kwargs: None
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
    validate_client_max_body_size,
    validate_listen_port,
    validate_proxy_target,
    validate_server_names,
    validate_site_name,
    validate_ssl_paths,
    validate_web_root,
)


class TestNginxValidators(unittest.TestCase):
    def test_validate_site_name(self):
        self.assertEqual(validate_site_name("example.com"), "example.com")
        self.assertEqual(validate_site_name("my-blog_1.net"), "my-blog_1.net")
        self.assertEqual(validate_site_name("Sub.Domain.org"), "sub.domain.org")

        # Rejections
        with self.assertRaises(BadRequestError):
            validate_site_name("../traversal")
        with self.assertRaises(BadRequestError):
            validate_site_name("/var/www/html")
        with self.assertRaises(BadRequestError):
            validate_site_name("bad name with spaces")
        with self.assertRaises(BadRequestError):
            validate_site_name("; rm -rf /")
        with self.assertRaises(BadRequestError):
            validate_site_name("")

    def test_validate_server_names(self):
        valid = validate_server_names(["example.com", "www.example.com", "api.sub.org"])
        self.assertEqual(valid, ["example.com", "www.example.com", "api.sub.org"])

        # Prohibited injection
        with self.assertRaises(BadRequestError):
            validate_server_names(["example.com", "; return 200 'hacked';"])
        with self.assertRaises(BadRequestError):
            validate_server_names([])

    def test_validate_listen_port(self):
        self.assertEqual(validate_listen_port(80), 80)
        self.assertEqual(validate_listen_port(443), 443)
        self.assertEqual(validate_listen_port(8080), 8080)

        # Out of bounds
        with self.assertRaises(BadRequestError):
            validate_listen_port(0)
        with self.assertRaises(BadRequestError):
            validate_listen_port(70000)

    def test_validate_web_root(self):
        self.assertEqual(validate_web_root("/var/www/html"), "/var/www/html")
        self.assertEqual(validate_web_root("/srv/www/mysite/pub"), "/srv/www/mysite/pub")
        self.assertEqual(validate_web_root("/usr/share/nginx/html"), "/usr/share/nginx/html")

        # Test B: /home public directory acceptance
        self.assertEqual(validate_web_root("/home/user/public_html"), "/home/user/public_html")
        self.assertEqual(validate_web_root("/home/user/www"), "/home/user/www")
        self.assertEqual(validate_web_root("/home/user/htdocs"), "/home/user/htdocs")
        self.assertEqual(validate_web_root("/home/bob/htdocs/site1"), "/home/bob/htdocs/site1")
        self.assertEqual(validate_web_root("/home/alice_app/public_html/build"), "/home/alice_app/public_html/build")

        # Test B: /home strict rejections (raw home, sensitive dirs, hidden files, non-approved subfolders)
        with self.assertRaises(BadRequestError):
            validate_web_root("/home")
        with self.assertRaises(BadRequestError):
            validate_web_root("/home/user")
        with self.assertRaises(BadRequestError):
            validate_web_root("/home/user/.ssh")
        with self.assertRaises(BadRequestError):
            validate_web_root("/home/user/.gnupg")
        with self.assertRaises(BadRequestError):
            validate_web_root("/home/user/.config")
        with self.assertRaises(BadRequestError):
            validate_web_root("/home/user/../etc")
        with self.assertRaises(BadRequestError):
            validate_web_root("/home/alice/.ssh/public")
        with self.assertRaises(BadRequestError):
            validate_web_root("/home/alice/private_docs")
        with self.assertRaises(BadRequestError):
            validate_web_root("/home/alice/public_html/.hidden_dir")

        # Non-whitelisted system roots
        with self.assertRaises(BadRequestError):
            validate_web_root("/etc/nginx")
        with self.assertRaises(BadRequestError):
            validate_web_root("/root/.ssh")
        with self.assertRaises(BadRequestError):
            validate_web_root("/var/www/../../etc")
        with self.assertRaises(BadRequestError):
            validate_web_root("/tmp")
        with self.assertRaises(BadRequestError):
            validate_web_root("/var/log")

    def test_validate_proxy_target(self):
        self.assertEqual(validate_proxy_target("http://127.0.0.1:3000"), "http://127.0.0.1:3000")
        self.assertEqual(validate_proxy_target("https://api.internal:8443/v1"), "https://api.internal:8443/v1")
        self.assertEqual(validate_proxy_target("http://localhost:8080"), "http://localhost:8080")

        # Reject non-http / dangerous
        with self.assertRaises(BadRequestError):
            validate_proxy_target("ftp://127.0.0.1")
        with self.assertRaises(BadRequestError):
            validate_proxy_target("javascript:alert(1)")
        with self.assertRaises(BadRequestError):
            validate_proxy_target("http://127.0.0.1; rm -rf /")

    def test_validate_ssl_paths(self):
        cert, key = validate_ssl_paths("/etc/ssl/certs/test.crt", "/etc/ssl/private/test.key")
        self.assertEqual(cert, "/etc/ssl/certs/test.crt")
        self.assertEqual(key, "/etc/ssl/private/test.key")

        # Disallow paths outside approved SSL directories
        with self.assertRaises(BadRequestError):
            validate_ssl_paths("/tmp/test.crt", "/tmp/test.key")
        with self.assertRaises(BadRequestError):
            validate_ssl_paths("/etc/ssl/certs/../../etc/shadow", "/etc/ssl/private/test.key")

    def test_validate_client_max_body_size(self):
        self.assertEqual(validate_client_max_body_size("10m"), "10m")
        self.assertEqual(validate_client_max_body_size("100M"), "100m")
        self.assertEqual(validate_client_max_body_size("1g"), "1g")
        self.assertEqual(validate_client_max_body_size("512k"), "512k")

        with self.assertRaises(BadRequestError):
            validate_client_max_body_size("10gb")
        with self.assertRaises(BadRequestError):
            validate_client_max_body_size("10m; eval(x)")


if __name__ == "__main__":
    unittest.main()
