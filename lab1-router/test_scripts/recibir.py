#!/usr/bin/env python3
"""
Captura los paquetes IPv4 que llegan a una interfaz e imprime la IP origen y el TTL (Lab 1).
Se corre DENTRO del host destino, normalmente en segundo plano.

Uso:
    mininet> h4 python3 test_scripts/recibir.py h4-eth0 &
    mininet> h1 ping -c 1 10.0.4.4         # o test_scripts/enviar.py
    -> "de 10.0.1.1 -> ttl 61"              (64 - 3 routers)
"""
import sys
from scapy.all import sniff, IP


def manejar(pkt):
    """Se llama por cada paquete capturado."""
    if IP in pkt:
        print("de %s -> ttl %d" % (pkt[IP].src, pkt[IP].ttl))


iface = sys.argv[1] if len(sys.argv) > 1 else "h4-eth0"
print("escuchando en", iface)
sniff(iface=iface, filter="ip", prn=manejar)   # captura indefinidamente (Ctrl+C o kill para parar)
