#!/usr/bin/env python3
import sys
from scapy.all import sniff, IP

def manejar(pkt):
    if IP in pkt:
        print("de %s -> ttl %d" % (pkt[IP].src, pkt[IP].ttl))

iface = sys.argv[1] if len(sys.argv) > 1 else "h4-eth0"
print("escuchando en", iface)
sniff(iface=iface, filter="ip", prn=manejar)