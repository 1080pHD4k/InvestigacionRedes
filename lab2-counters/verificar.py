#!/usr/bin/env python3
"""
Verifica que los contadores del switch reflejan exactamente el tráfico inyectado.

Compara lo que trafico_scapy.py dejó en /tmp/lab2_esperado.json con:
  - el contador directo de cada flujo enviado (paquetes y bytes),
  - el contador global de cada protocolo,
  - que los flujos que no se usaron sigan en cero.

Flujo de prueba (todo desde el prompt de Mininet):
    mininet> sh python3 controlador.py --reset --una-vez
    mininet> h1 python3 trafico_scapy.py 10.0.0.2 --tcp 100 --udp 50 --icmp 30 --otros 20 --tam 200
    mininet> h3 python3 trafico_scapy.py 10.0.0.4 --tcp 10 --udp 10 --tam 1200 --anexar
    mininet> sh python3 verificar.py
"""
import json
import sys

import controlador as c

ARCHIVO_ESPERADO = "/tmp/lab2_esperado.json"


def main():
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 9090
    try:
        with open(ARCHIVO_ESPERADO) as f:
            envios = json.load(f)
    except (OSError, ValueError):
        sys.exit("No hay %s; correr antes trafico_scapy.py." % ARCHIVO_ESPERADO)

    flujos = c.cargar_flujos(puerto)
    muestra = c.tomar_muestra(flujos, puerto)

    # Totales esperados por flujo y por protocolo
    esperado_flujo = {}
    esperado_proto = {p: [0, 0] for p in c.PROTOCOLOS}
    for e in envios:
        clave = (e["origen"], e["destino"])
        acum = esperado_flujo.setdefault(clave, [0, 0])
        for proto, v in e["por_protocolo"].items():
            acum[0] += v["paquetes"]
            acum[1] += v["bytes"]
            esperado_proto[proto][0] += v["paquetes"]
            esperado_proto[proto][1] += v["bytes"]

    fallos = 0

    def comparar(nombre, esperado, medido):
        nonlocal fallos
        ok = tuple(esperado) == tuple(medido)
        fallos += 0 if ok else 1
        print(" %-28s esperado %6d paq / %9d B   medido %6d paq / %9d B   %s"
              % (nombre, esperado[0], esperado[1], medido[0], medido[1], "OK" if ok else "DIFERENTE"))

    print("\nContadores directos por flujo")
    for f in muestra["flujos"]:
        clave = (f["origen"], f["destino"])
        comparar("%s -> %s" % clave, esperado_flujo.get(clave, [0, 0]), (f["paquetes"], f["bytes"]))

    print("\nContadores globales por protocolo")
    for i, proto in enumerate(c.PROTOCOLOS):
        comparar(proto, esperado_proto[proto], muestra["protocolos"][i])

    print("\nRegister de bytes por flujo vs. contador directo")
    distintos = [f for f in muestra["flujos"] if f["bytes_reg"] != f["bytes"]]
    for f in distintos:
        print(" %s -> %s: register %d B, contador %d B  DIFERENTE"
              % (f["origen"], f["destino"], f["bytes_reg"], f["bytes"]))
    if not distintos:
        print(" sin diferencias")
    fallos += len(distintos)

    print("\nRESULTADO: %s" % ("todos los contadores coinciden con el tráfico inyectado"
                               if fallos == 0 else "%d diferencias" % fallos))
    sys.exit(0 if fallos == 0 else 1)


if __name__ == "__main__":
    main()
