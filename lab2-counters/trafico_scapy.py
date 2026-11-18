#!/usr/bin/env python3
"""
Generador de tráfico controlado (Scapy) para el Lab 2. Se corre DENTRO de un host de Mininet.

Envía una cantidad exacta de paquetes TCP, UDP, ICMP y "otros" (protocolo IP 253) hacia
un destino y guarda lo que mandó en /tmp/lab2_esperado.json, para que verificar.py lo
compare con los contadores del switch.

Los paquetes no generan respuestas del destino:
  - TCP y UDP van al puerto 7777, que topology.py bloquea con iptables (sin RST ni ICMP),
  - ICMP es tipo 0 (echo reply), que el destino no contesta,
  - el protocolo 253 también lo descarta iptables (sin "protocol unreachable").

Ejemplo:
    mininet> h1 python3 trafico_scapy.py 10.0.0.2 --tcp 100 --udp 50 --icmp 30 --otros 20 --tam 200
"""
import argparse
import json
import time

from scapy.all import Ether, IP, TCP, UDP, ICMP, Raw, sendp, get_if_list, get_if_hwaddr

PUERTO_PRUEBA = 7777
PROTO_OTROS = 253
ARCHIVO_ESPERADO = "/tmp/lab2_esperado.json"


def mac_de(ip):
    """Convención de topology.py: 10.0.0.N tiene MAC 08:00:00:00:00:0N."""
    return "08:00:00:00:00:%02x" % int(ip.split(".")[-1])


def interfaz_por_defecto():
    for nombre in get_if_list():
        if nombre.endswith("-eth0"):
            return nombre
    raise SystemExit("No encontré la interfaz hX-eth0; usar --iface.")


def main():
    ap = argparse.ArgumentParser(description="Envía tráfico mixto conocido hacia un host.")
    ap.add_argument("destino", help="IP destino, p. ej. 10.0.0.2")
    ap.add_argument("--tcp", type=int, default=0, help="cantidad de paquetes TCP")
    ap.add_argument("--udp", type=int, default=0, help="cantidad de paquetes UDP")
    ap.add_argument("--icmp", type=int, default=0, help="cantidad de paquetes ICMP")
    ap.add_argument("--otros", type=int, default=0, help="cantidad de paquetes IP protocolo 253")
    ap.add_argument("--tam", type=int, default=100, help="bytes de payload por paquete (100)")
    ap.add_argument("--iface", default=None, help="interfaz de salida (por defecto hX-eth0)")
    ap.add_argument("--anexar", action="store_true",
                    help="sumar a lo ya guardado en %s en vez de reemplazarlo" % ARCHIVO_ESPERADO)
    args = ap.parse_args()

    iface = args.iface or interfaz_por_defecto()
    mac_origen = get_if_hwaddr(iface)
    ip_origen = None

    payload = Raw(b"x" * args.tam)
    capa2 = Ether(src=mac_origen, dst=mac_de(args.destino))
    plantillas = {
        "TCP":   lambda: TCP(sport=40000, dport=PUERTO_PRUEBA, flags="A") / payload,
        "UDP":   lambda: UDP(sport=40000, dport=PUERTO_PRUEBA) / payload,
        "ICMP":  lambda: ICMP(type=0) / payload,
        "Otros": lambda: payload,
    }
    cantidades = {"TCP": args.tcp, "UDP": args.udp, "ICMP": args.icmp, "Otros": args.otros}

    enviado = {}
    for proto, n in cantidades.items():
        if n <= 0:
            enviado[proto] = {"paquetes": 0, "bytes": 0}
            continue
        capa3 = IP(dst=args.destino, proto=PROTO_OTROS) if proto == "Otros" else IP(dst=args.destino)
        pkt = capa2 / capa3 / plantillas[proto]()
        pkt = Ether(bytes(pkt))            # fija checksums y longitudes
        ip_origen = pkt[IP].src
        sendp([pkt] * n, iface=iface, verbose=False, inter=0.001)
        enviado[proto] = {"paquetes": n, "bytes": n * len(pkt)}
        print("  %-5s %5d paquetes x %4d B = %8d B" % (proto, n, len(pkt), n * len(pkt)))

    total_p = sum(v["paquetes"] for v in enviado.values())
    total_b = sum(v["bytes"] for v in enviado.values())
    print("  TOTAL %5d paquetes          = %8d B   (%s -> %s)" % (total_p, total_b, ip_origen, args.destino))

    # Guardar lo esperado para verificar.py (Mininet comparte /tmp entre hosts y la raíz)
    registros = []
    if args.anexar:
        try:
            with open(ARCHIVO_ESPERADO) as f:
                registros = json.load(f)
        except (OSError, ValueError):
            registros = []
    registros.append({"hora": time.time(), "origen": ip_origen, "destino": args.destino,
                      "por_protocolo": enviado})
    with open(ARCHIVO_ESPERADO, "w") as f:
        json.dump(registros, f, indent=2)
    print("Guardado en %s" % ARCHIVO_ESPERADO)


if __name__ == "__main__":
    main()
