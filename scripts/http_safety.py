from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Collection
from typing import BinaryIO


class UnsafeUrlError(ValueError):
    pass


def _host_matches(hostname: str, allowed_hosts: Collection[str]) -> bool:
    hostname = hostname.casefold().rstrip(".")
    for allowed in allowed_hosts:
        allowed = allowed.casefold().rstrip(".")
        if allowed.startswith("."):
            if hostname.endswith(allowed) and hostname != allowed[1:]:
                return True
        elif hostname == allowed:
            return True
    return False


def validate_https_url(url: str, *, allowed_hosts: Collection[str]) -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise UnsafeUrlError(f"invalid URL: {url!r}") from exc
    hostname = parsed.hostname or ""
    if parsed.scheme.casefold() != "https":
        raise UnsafeUrlError(f"URL must use HTTPS: {url!r}")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeUrlError(f"URL credentials are not allowed: {url!r}")
    if port not in {None, 443}:
        raise UnsafeUrlError(f"URL port is not allowed: {url!r}")
    if not _host_matches(hostname, allowed_hosts):
        raise UnsafeUrlError(f"URL host is not allowed: {url!r}")
    return url


class _HttpsRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: Collection[str]) -> None:
        super().__init__()
        self.allowed_hosts = tuple(allowed_hosts)

    def redirect_request(  # type: ignore[override]
        self,
        req: urllib.request.Request,
        fp: BinaryIO,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> urllib.request.Request | None:
        validate_https_url(newurl, allowed_hosts=self.allowed_hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_https(
    request: str | urllib.request.Request,
    *,
    allowed_hosts: Collection[str],
    timeout: float,
) -> BinaryIO:
    url = request.full_url if isinstance(request, urllib.request.Request) else request
    validate_https_url(url, allowed_hosts=allowed_hosts)
    opener = urllib.request.build_opener(_HttpsRedirectHandler(allowed_hosts))
    return opener.open(request, timeout=timeout)


def read_limited(response: BinaryIO, *, maximum_bytes: int) -> bytes:
    if maximum_bytes <= 0:
        raise ValueError("maximum_bytes must be positive")
    content_length = response.headers.get("Content-Length")  # type: ignore[attr-defined]
    if content_length:
        try:
            declared = int(content_length)
        except ValueError as exc:
            raise urllib.error.URLError("invalid Content-Length") from exc
        if declared < 0 or declared > maximum_bytes:
            raise urllib.error.URLError(f"response exceeds {maximum_bytes} bytes")
    payload = response.read(maximum_bytes + 1)
    if len(payload) > maximum_bytes:
        raise urllib.error.URLError(f"response exceeds {maximum_bytes} bytes")
    return payload
