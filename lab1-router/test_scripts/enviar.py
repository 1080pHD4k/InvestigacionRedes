#!/usr/bin/env python3
"""
Envía paquetes ICMP con un TTL inicial elegido hacia un destino (Lab 1). Se corre DENTRO de un host.

Junto con recibir.py sirve para comprobar:
  - el decremento del TTL: de h1 a h4 el paquete atraviesa s1, s2 y s3, así que con
    TTL 64 llega con 61;
  - el descarte por TTL agotado: un router que recibe un paquete con TTL <= 1 lo descarta.
    De h1 a h4, con TTL 4 llega con TTL 1; con TTL 3 lo descarta s3 y no llega.

Uso:
    mininet> h1 python3 test_scripts/enviar.py <IP destino> [cantidad] [ttl]
    mininet> h1 python3 test_scripts/enviar.py 10.0.4.4            # 1 paquete, TTL 64
    mininet> h1 python3 test_scripts/enviar.py 10.0.4.4 3 4        # 3 paquetes, TTL 4
"""
import sys
from scapy.all import Ether, IP, ICMP, sendp, conf, get_if_hwaddr

if len(sys.argv) < 2:
    sys.exit("uso: enviar.py <IP destino> [cantidad] [ttl]")

dst = sys.argv[1]                                     # IP destino
n = int(sys.argv[2]) if len(sys.argv) > 2 else 1      # cantidad de paquetes (1 por defecto)
ttl = int(sys.argv[3]) if len(sys.argv) > 3 else 64   # TTL inicial (64 por defecto)


def mac_en_tabla_arp(ip):
    """Busca la MAC de una IP en la tabla ARP del kernel (/proc/net/arp)."""
    with open("/proc/net/arp") as f:
        next(f)                                       # encabezado
        for linea in f:
            campos = linea.split()
            if campos[0] == ip:
                return campos[3]
    return None


# Interfaz de salida y siguiente salto según la tabla de rutas (el gateway del host).
# El router P4 no responde ARP: su MAC está en la tabla ARP estática que configura
# topology.py, así que se arma la trama Ethernet a mano en vez de dejar que Scapy pregunte.
iface, _, gw = conf.route.route(dst)
siguiente = gw if gw != "0.0.0.0" else dst
mac_gw = mac_en_tabla_arp(siguiente)
if mac_gw is None:
    sys.exit("no encontré la MAC de %s en la tabla ARP del host" % siguiente)

pkt = Ether(src=get_if_hwaddr(iface), dst=mac_gw) / IP(dst=dst, ttl=ttl) / ICMP() / "prueba"
sendp(pkt, iface=iface, count=n, verbose=False)
print("enviados %d paquete(s) a %s con TTL %d (vía %s)" % (n, dst, ttl, siguiente))
