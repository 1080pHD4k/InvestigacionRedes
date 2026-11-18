#!/usr/bin/env python3
"""
Captura los paquetes IPv4 que llegan a una interfaz e imprime la IP origen y el TTL (Lab 1).
Se corre DENTRO del host destino, normalmente en segundo plano. Solo muestra lo que entra:
ignora los paquetes que el propio host envía (por ejemplo, sus respuestas a un ping).

Uso (Mininet no muestra la salida de procesos en segundo plano, por eso va a un archivo):
    mininet> h4 python3 -u test_scripts/recibir.py h4-eth0 > /tmp/h4.txt 2>&1 &
    mininet> h1 python3 test_scripts/enviar.py 10.0.4.4
    mininet> sh cat /tmp/h4.txt
    -> "de 10.0.1.1 -> ttl 61"              (64 - 3 routers)
"""
import sys
from scapy.all import sniff, IP, get_if_hwaddr

iface = sys.argv[1] if len(sys.argv) > 1 else "h4-eth0"
mi_mac = get_if_hwaddr(iface)   # para reconocer los paquetes que salen de este host


def manejar(pkt):
    """Se llama por cada paquete capturado."""
    if IP in pkt and pkt.src != mi_mac:
        print("de %s -> ttl %d" % (pkt[IP].src, pkt[IP].ttl))


print("escuchando en", iface)
sniff(iface=iface, filter="ip", prn=manejar)   # captura indefinidamente (Ctrl+C o kill para parar)
