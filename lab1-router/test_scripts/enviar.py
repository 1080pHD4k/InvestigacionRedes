#!/usr/bin/env python3
"""
Envía paquetes ICMP con TTL inicial 64 hacia un destino (Lab 1). Se corre DENTRO de un host.

Junto con recibir.py sirve para comprobar el decremento del TTL: de h1 a h4 el paquete
atraviesa s1, s2 y s3, así que debe llegar con TTL 61.

Uso:
    mininet> h1 python3 test_scripts/enviar.py <IP destino> [cantidad]
    mininet> h1 python3 test_scripts/enviar.py 10.0.4.4 3
"""
import sys
from scapy.all import IP, ICMP, send

dst = sys.argv[1]                                  # IP destino
n = int(sys.argv[2]) if len(sys.argv) > 2 else 1   # cantidad de paquetes (1 por defecto)

# send() trabaja en capa 3: el kernel del host arma Ethernet usando su ruta por defecto
send(IP(dst=dst, ttl=64) / ICMP() / "prueba", count=n, verbose=False)
print("enviados %d paquete(s) a %s" % (n, dst))
