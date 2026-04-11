# network_validation_simplified.py
import ipaddress
import re
from typing import Optional, Union
from urllib.parse import urlparse

MAX_UNSIGNED_INT32 = 0xFFFFFFFF


def is_private_ip(ip: str) -> bool:
    """Check if IP address is private/local using ipaddress module"""
    try:
        ip_obj = ipaddress.ip_address(ip)
        
        # Check if it's a private or loopback address
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_unspecified:
            return True
        
        # Check for link-local
        if ip_obj.is_link_local:
            return True
        
        # Check for IPv4-mapped IPv6 addresses
        if ip_obj.version == 6 and ip_obj.ipv4_mapped:
            return is_private_ip(str(ip_obj.ipv4_mapped))
        
        # Additional checks for specific ranges
        if ip_obj.version == 4:
            # CGNAT range (100.64.0.0/10)
            if ip_obj >= ipaddress.IPv4Address('100.64.0.0') and \
               ip_obj <= ipaddress.IPv4Address('100.127.255.255'):
                return True
            # Private-use networks (198.18.0.0/15)
            if ip_obj >= ipaddress.IPv4Address('198.18.0.0') and \
               ip_obj <= ipaddress.IPv4Address('198.19.255.255'):
                return True
        
        return False
    except ipaddress.AddressValueError:
        return False


def parse_integer_ipv4_literal(hostname: str) -> Optional[str]:
    """Parse integer IPv4 literal (e.g., 2130706433 -> 127.0.0.1)"""
    if not re.match(r'^\d+$', hostname):
        return None
    
    value = int(hostname)
    if value < 0 or value > MAX_UNSIGNED_INT32:
        return None
    
    # Convert integer to IPv4 address
    try:
        ip_obj = ipaddress.IPv4Address(value)
        return str(ip_obj)
    except ipaddress.AddressValueError:
        return None


def is_private_or_local_hostname(hostname: str) -> bool:
    """Check if hostname points to private/local network"""
    host = hostname.strip().lower()
    if not host:
        return True
    
    # Localhost variations
    if host == 'localhost' or host.endswith('.localhost'):
        return True
    
    # Cloud metadata endpoints
    if host in ['metadata.google.internal', 'metadata.azure.internal']:
        return True
    
    # Check integer IPv4 literal (e.g., 2130706433)
    integer_ip = parse_integer_ipv4_literal(host)
    if integer_ip and is_private_ip(integer_ip):
        return True
    
    # Check as regular IP address
    if is_private_ip(host):
        return True
    
    return False


def is_public_http_url(url: str) -> bool:
    """Check if URL is a public HTTP/HTTPS URL (not private/local)"""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ['http', 'https']:
            return False
        return not is_private_or_local_hostname(parsed.hostname or '')
    except Exception:
        return False


def assert_public_http_url(url: Union[str, object], label: str = 'URL') -> None:
    """Assert that URL is a public HTTP/HTTPS URL, raise error if not"""
    # Parse the URL
    if isinstance(url, str):
        parsed = urlparse(url)
    elif hasattr(url, 'scheme') and hasattr(url, 'hostname'):  # Duck typing for URL-like objects
        parsed = url
    else:
        raise TypeError(f"{label} must be a string or URL object")
    
    # Check protocol
    if parsed.scheme not in ['http', 'https']:
        raise ValueError(f"{label} must use HTTP or HTTPS")
    
    # Check hostname
    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"{label} has no hostname")
    
    if is_private_or_local_hostname(hostname):
        raise ValueError(f"{label} points to a private or local network target, which is not allowed")