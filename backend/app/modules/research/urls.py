"""Source URL safety (PRD E6). We never fetch these URLs ourselves (Tavily does: docs/decisions.md D10), but we
store them and render them as links, so only plain http(s) links to public hosts get through."""

import ipaddress
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

BLOCKED_HOSTS = {"localhost", "metadata", "metadata.google.internal", "instance-data"}
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".intranet", ".corp", ".home.arpa")
TRACKING_PARAM = re.compile(r"utm_\w+|fbclid|gclid|mc_eid|ref_src", re.IGNORECASE)


def safe_public_url(url: str) -> str | None:
    """The URL in canonical form if it's http(s) on a public host, else None."""
    try:
        parts = urlsplit(url.strip())
        port = parts.port  # raises ValueError on garbage ports
    except ValueError:
        return None
    host = (parts.hostname or "").rstrip(".").lower()
    if parts.scheme.lower() not in ("http", "https") or not host or parts.username or parts.password:
        return None
    if host in BLOCKED_HOSTS or host.endswith(BLOCKED_SUFFIXES):
        return None
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if not ip.is_global:  # loopback, private, link-local (169.254.169.254 metadata), reserved…
            return None
    elif "." not in host or all(re.fullmatch(r"\d+|0x[0-9a-f]*", label) for label in host.split(".")):
        return None  # single-label intranet names; numeric forms browsers still resolve (127.1, 0x7f.0.0.1)

    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not TRACKING_PARAM.fullmatch(k)])
    default_port = {"http": 80, "https": 443}[parts.scheme.lower()]
    netloc = host if port in (None, default_port) else f"{host}:{port}"
    if ip is not None and ip.version == 6:
        netloc = f"[{host}]" if port in (None, default_port) else f"[{host}]:{port}"
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))


def dedupe_key(canonical_url: str) -> str:
    """Same page over http/https, with or without www."""
    parts = urlsplit(canonical_url)
    return f"{parts.netloc.removeprefix('www.')}{parts.path}?{parts.query}"


def domain(canonical_url: str) -> str:
    return (urlsplit(canonical_url).hostname or "").removeprefix("www.")
