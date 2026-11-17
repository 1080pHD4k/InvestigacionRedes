#!/usr/bin/env python3
import sys
from scapy.all import IP, ICMP, send

dst = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
send(IP(dst=dst, ttl=64) / ICMP() / "prueba", count=n, verbose=False)
print("enviados %d paquete(s) a %s" % (n, dst))