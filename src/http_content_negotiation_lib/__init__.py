# http_content_negotiation_lib

"""HTTP content negotiation for Accept, Accept-Encoding, and Accept-Language."""

from .core import negotiate, parse_accept_header

__all__ = ["negotiate", "parse_accept_header"]
