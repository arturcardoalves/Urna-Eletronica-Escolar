"""Small, shared LAN protocol. No internet discovery, no DNS dependencies."""
import ipaddress
import json
import socket
import time

import psutil

DISCOVERY_PORT = 38443
PROTOCOL = "urna-escolar/2.3"


def interfaces():
    result = []
    stats = psutil.net_if_stats()
    for name, addresses in psutil.net_if_addrs().items():
        if name not in stats or not stats[name].isup:
            continue
        for address in addresses:
            if address.family != socket.AF_INET or not address.netmask:
                continue
            ip = ipaddress.ip_address(address.address)
            if ip.is_loopback or ip.is_link_local or not ip.is_private:
                continue
            network = ipaddress.ip_network(f"{address.address}/{address.netmask}", strict=False)
            result.append({"name": name, "ip": address.address, "broadcast": str(network.broadcast_address)})
    return result


def discover(timeout=1.5):
    sockets = []
    found = {}
    try:
        for interface in interfaces():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.bind((interface["ip"], 0))
                sock.settimeout(0.1)
                sock.sendto(PROTOCOL.encode(), (interface["broadcast"], DISCOVERY_PORT))
                sockets.append(sock)
            except OSError:
                sock.close()
        deadline = time.monotonic() + timeout
        while sockets and time.monotonic() < deadline:
            for sock in sockets:
                try:
                    packet, address = sock.recvfrom(4096)
                    data = json.loads(packet)
                    if (isinstance(data, dict) and data.get("protocol") == PROTOCOL
                            and isinstance(data.get("id"), str) and len(data["id"]) == 64):
                        found[address[0]] = {"id": data["id"], "name": str(data.get("name", ""))[:80],
                                             "version": data.get("version"), "url": f"https://{address[0]}:8443"}
                except (OSError, ValueError):
                    continue
    finally:
        for sock in sockets:
            sock.close()
    return list(found.values())


def serve_discovery(stop, identity):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("0.0.0.0", DISCOVERY_PORT))
        sock.settimeout(1)
        while not stop.is_set():
            try:
                packet, address = sock.recvfrom(256)
                ip = ipaddress.ip_address(address[0])
                if packet != PROTOCOL.encode() or not (ip.is_private or ip.is_loopback):
                    continue
                data = identity()
                sock.sendto(json.dumps({"protocol": PROTOCOL, "id": data["id"], "name": data["name"], "version": data["version"]}).encode(), address)
            except socket.timeout:
                continue
            except OSError:
                if stop.is_set():
                    return
                raise
