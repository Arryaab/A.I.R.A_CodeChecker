def ip_to_int(ip: str) -> int:
    parts = [int(p) for p in ip.strip().split(".")]
    if len(parts) != 4 or any(p < 0 or p > 255 for p in parts):
        raise ValueError(f"Invalid IP address: {ip}")
    return (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]

def is_ip_in_cidr(ip: str, cidr: str) -> bool:
    """Checks whether an IPv4 address is in the specified CIDR block."""
    net_str, prefix_str = cidr.strip().split("/")
    prefix = int(prefix_str)
    if prefix < 0 or prefix > 32:
        raise ValueError(f"Invalid prefix: {prefix}")
    
    ip_int = ip_to_int(ip)
    net_int = ip_to_int(net_str)
    
    # BUG: Off by one shift fails on /32 and shifts incorrectly
    mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF if prefix > 0 else 0
    # BUG: Compares without masking net_int
    return (ip_int & mask) == net_int
