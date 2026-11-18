#!/usr/bin/env python3
"""
Controlador del Lab 2: lee periódicamente los contadores y registers de s1 por thrift
(a través de simple_switch_CLI) y los imprime en consola.

Qué muestra en cada intervalo:
  - contador global por protocolo (TCP, UDP, ICMP, otros), con paquetes, bytes y tasa,
  - contador directo de cada flujo (IP origen -> IP destino), con tamaños mín/máx/último/promedio,
  - histograma global de tamaños de paquete,
  - flujos elefante: los que superan el umbral de bytes (marcados por el plano de datos y
    verificados por el controlador). Cada detección nueva se anota en elefantes.log.

Uso (en una terminal fuera de Mininet, con la topología corriendo y las tablas cargadas):
    sudo python3 controlador.py                      # cada 5 s, umbral 1 MB
    sudo python3 controlador.py --umbral 500000 --intervalo 2
    sudo python3 controlador.py --reset              # pone todo en cero antes de empezar
    sudo python3 controlador.py --una-vez            # imprime una sola vez y termina
"""
import argparse
import os
import re
import subprocess
import sys
import time
from datetime import datetime

# Nombres de los objetos en el JSON de BMv2 (control MiIngreso de counters.p4)
TABLA_FLUJOS = "MiIngreso.flujos"
CONT_PROTOCOLOS = "MiIngreso.contador_protocolos"
CONT_FLUJOS = "MiIngreso.contador_flujos"
REG_TAM_ULTIMO = "MiIngreso.tam_ultimo"
REG_TAM_MINIMO = "MiIngreso.tam_minimo"
REG_TAM_MAXIMO = "MiIngreso.tam_maximo"
REG_HISTOGRAMA = "MiIngreso.histograma_tam"
REG_BYTES = "MiIngreso.bytes_flujo"
REG_ELEFANTE = "MiIngreso.elefante"
REG_UMBRAL = "MiIngreso.umbral_elefante"

PROTOCOLOS = ["TCP", "UDP", "ICMP", "Otros"]          # mismo orden que IDX_* en el P4
RANGOS = ["<128 B", "128-511 B", "512-1023 B", ">=1024 B"]

DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_TABLAS = os.path.join(DIR, "s1-tablas.txt")
ARCHIVO_ELEFANTES = os.path.join(DIR, "elefantes.log")


# ---------------------------------------------------------------- acceso al switch

def ejecutar_cli(comandos, puerto):
    """Manda una lista de comandos a simple_switch_CLI (thrift) y devuelve la salida."""
    entrada = "\n".join(comandos) + "\n"
    try:
        r = subprocess.run(["simple_switch_CLI", "--thrift-port", str(puerto)],
                           input=entrada, capture_output=True, text=True, timeout=20)
    except FileNotFoundError:
        sys.exit("No se encontró simple_switch_CLI en el PATH.")
    if "Could not connect" in r.stdout + r.stderr:
        sys.exit("No se pudo conectar al switch en el puerto thrift %d. "
                 "¿Está corriendo topology.py?" % puerto)
    # Cada respuesta viene precedida del prompt "RuntimeCmd: "
    return r.stdout.replace("RuntimeCmd: ", "\n")


RE_CONTADOR = re.compile(r"([\w.]+)\[(\d+)\]=\s*BmCounterValue\(packets=(\d+),\s*bytes=(\d+)\)")
RE_REGISTER = re.compile(r"^([\w.]+)=\s*([\d,\s]*)$", re.MULTILINE)
RE_HANDLE = re.compile(r"Dumping entry (0x[0-9a-fA-F]+)")


def leer_contadores(salida):
    """{(nombre, indice): (paquetes, bytes)} a partir de la salida de counter_read."""
    return {(m.group(1), int(m.group(2))): (int(m.group(3)), int(m.group(4)))
            for m in RE_CONTADOR.finditer(salida)}


def leer_registers(salida):
    """{nombre: [valores]} a partir de la salida de register_read sin índice."""
    regs = {}
    for m in RE_REGISTER.finditer(salida):
        valores = [v.strip() for v in m.group(2).split(",") if v.strip()]
        regs[m.group(1)] = [int(v) for v in valores]
    return regs


# ---------------------------------------------------------------- flujos

def cargar_flujos(puerto):
    """
    Lee los flujos de s1-tablas.txt y busca el handle de cada entrada en el switch.
    Devuelve una lista de dicts: {id, origen, destino, handle}.
    """
    patron = re.compile(r"^table_add\s+\S*flujos\s+contar_flujo\s+(\S+)\s+(\S+)\s*=>\s*(\d+)")
    flujos = []
    with open(ARCHIVO_TABLAS) as f:
        for linea in f:
            m = patron.match(linea.strip())
            if m:
                flujos.append({"origen": m.group(1), "destino": m.group(2),
                               "id": int(m.group(3)), "handle": len(flujos)})

    # Handle real de cada entrada (más robusto que asumir el orden de carga)
    comandos = ["table_dump_entry_from_key %s %s %s" % (TABLA_FLUJOS, fl["origen"], fl["destino"])
                for fl in flujos]
    salida = ejecutar_cli(comandos, puerto)
    handles = RE_HANDLE.findall(salida)
    if len(handles) == len(flujos):
        for fl, h in zip(flujos, handles):
            fl["handle"] = int(h, 16)
    else:
        print("Aviso: no se pudieron leer todos los handles (%d de %d); se asume el orden "
              "de s1-tablas.txt. ¿Se cargaron las tablas?" % (len(handles), len(flujos)))
    return flujos


# ---------------------------------------------------------------- lectura completa

def tomar_muestra(flujos, puerto):
    """Lee todos los contadores y registers en una sola llamada al CLI."""
    comandos = ["counter_read %s %d" % (CONT_PROTOCOLOS, i) for i in range(len(PROTOCOLOS))]
    comandos += ["counter_read %s %d" % (CONT_FLUJOS, fl["handle"]) for fl in flujos]
    comandos += ["register_read %s" % r for r in
                 (REG_TAM_ULTIMO, REG_TAM_MINIMO, REG_TAM_MAXIMO, REG_HISTOGRAMA,
                  REG_BYTES, REG_ELEFANTE, REG_UMBRAL)]
    salida = ejecutar_cli(comandos, puerto)
    contadores = leer_contadores(salida)
    regs = leer_registers(salida)

    def reg(nombre, i):
        valores = regs.get(nombre, [])
        return valores[i] if i < len(valores) else 0

    muestra = {
        "hora": time.time(),
        "protocolos": [contadores.get((CONT_PROTOCOLOS, i), (0, 0)) for i in range(len(PROTOCOLOS))],
        "histograma": [reg(REG_HISTOGRAMA, i) for i in range(len(RANGOS))],
        "umbral_switch": reg(REG_UMBRAL, 0),
        "flujos": [],
    }
    for fl in flujos:
        paquetes, bytes_ = contadores.get((CONT_FLUJOS, fl["handle"]), (0, 0))
        i = fl["id"]
        muestra["flujos"].append({
            **fl,
            "paquetes": paquetes,
            "bytes": bytes_,
            "ultimo": reg(REG_TAM_ULTIMO, i),
            "minimo": reg(REG_TAM_MINIMO, i),
            "maximo": reg(REG_TAM_MAXIMO, i),
            "bytes_reg": reg(REG_BYTES, i),
            "marca_elefante": reg(REG_ELEFANTE, i) == 1,
        })
    return muestra


def resetear(flujos, puerto):
    """Pone en cero contadores y registers (el umbral se vuelve a escribir después)."""
    comandos = ["counter_reset %s" % CONT_PROTOCOLOS, "counter_reset %s" % CONT_FLUJOS]
    comandos += ["register_reset %s" % r for r in
                 (REG_TAM_ULTIMO, REG_TAM_MINIMO, REG_TAM_MAXIMO, REG_HISTOGRAMA,
                  REG_BYTES, REG_ELEFANTE)]
    ejecutar_cli(comandos, puerto)


def escribir_umbral(umbral, puerto):
    ejecutar_cli(["register_write %s 0 %d" % (REG_UMBRAL, umbral)], puerto)


# ---------------------------------------------------------------- formato

def fmt_bytes(n):
    for unidad in ("B", "KB", "MB", "GB"):
        if n < 1000 or unidad == "GB":
            return ("%d %s" % (n, unidad)) if unidad == "B" else ("%.2f %s" % (n, unidad))
        n /= 1000.0


def fmt_tasa(bytes_por_s):
    return "%.1f kb/s" % (bytes_por_s * 8 / 1000.0)


def imprimir(muestra, anterior, umbral, intervalo, limpiar):
    dt = (muestra["hora"] - anterior["hora"]) if anterior else 0

    def tasa(actual, previo):
        return (actual - previo) / dt if dt > 0 else 0.0

    lineas = []
    hora = datetime.fromtimestamp(muestra["hora"]).strftime("%H:%M:%S")
    lineas.append("=" * 100)
    lineas.append(" Estadísticas de s1   |   %s   |   cada %g s   |   umbral elefante: %s"
                  % (hora, intervalo, fmt_bytes(umbral)))
    lineas.append("=" * 100)

    # Protocolos
    lineas.append("\n Contadores globales por protocolo")
    lineas.append(" %-8s %12s %14s %14s %14s" % ("Proto", "Paquetes", "Bytes", "Paq/s", "Tasa"))
    tot_p = tot_b = 0
    for i, nombre in enumerate(PROTOCOLOS):
        p, b = muestra["protocolos"][i]
        pp, pb = anterior["protocolos"][i] if anterior else (p, b)
        tot_p += p
        tot_b += b
        lineas.append(" %-8s %12d %14s %14.1f %14s"
                      % (nombre, p, fmt_bytes(b), tasa(p, pp), fmt_tasa(tasa(b, pb))))
    lineas.append(" %-8s %12d %14s" % ("TOTAL", tot_p, fmt_bytes(tot_b)))

    # Flujos
    lineas.append("\n Flujos (contador directo por IP origen -> IP destino)")
    lineas.append(" %-24s %10s %12s %13s %7s %7s %7s %7s  %s"
                  % ("Flujo", "Paquetes", "Bytes", "Tasa", "Últ.", "Mín.", "Máx.", "Prom.", "Estado"))
    previos = {f["id"]: f for f in anterior["flujos"]} if anterior else {}
    elefantes = []
    for f in muestra["flujos"]:
        prev = previos.get(f["id"], f)
        promedio = f["bytes"] // f["paquetes"] if f["paquetes"] else 0
        es_elefante = f["marca_elefante"] or (umbral > 0 and f["bytes"] >= umbral)
        if es_elefante:
            elefantes.append(f)
        estado = "** ELEFANTE **" if es_elefante else ("activo" if f["bytes"] != prev["bytes"] else "")
        lineas.append(" %-24s %10d %12s %13s %7d %7d %7d %7d  %s"
                      % ("%s -> %s" % (f["origen"], f["destino"]), f["paquetes"], fmt_bytes(f["bytes"]),
                         fmt_tasa(tasa(f["bytes"], prev["bytes"])), f["ultimo"], f["minimo"],
                         f["maximo"], promedio, estado))

    # Histograma
    lineas.append("\n Histograma de tamaños (register)")
    total_h = sum(muestra["histograma"]) or 1
    for nombre, n in zip(RANGOS, muestra["histograma"]):
        barra = "#" * int(40 * n / total_h)
        lineas.append(" %-11s %10d  %s" % (nombre, n, barra))

    # Elefantes
    lineas.append("\n Flujos elefante: %s" % (
        ", ".join("%s -> %s (%s)" % (f["origen"], f["destino"], fmt_bytes(f["bytes"])) for f in elefantes)
        if elefantes else "ninguno"))

    if limpiar:
        print("\033[2J\033[H", end="")
    print("\n".join(lineas), flush=True)
    return elefantes


def anotar_elefantes(elefantes, ya_anotados, umbral):
    """Registra en elefantes.log cada flujo que pasa a ser elefante por primera vez."""
    nuevos = [f for f in elefantes if f["id"] not in ya_anotados]
    if not nuevos:
        return
    with open(ARCHIVO_ELEFANTES, "a") as log:
        for f in nuevos:
            log.write("%s  ELEFANTE  %s -> %s  bytes=%d  paquetes=%d  umbral=%d  marca_switch=%s\n"
                      % (datetime.now().isoformat(timespec="seconds"), f["origen"], f["destino"],
                         f["bytes"], f["paquetes"], umbral, f["marca_elefante"]))
            ya_anotados.add(f["id"])


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Lee y muestra los contadores de s1 (Lab 2).")
    ap.add_argument("--puerto", type=int, default=9090, help="puerto thrift del switch (9090)")
    ap.add_argument("--intervalo", type=float, default=5.0, help="segundos entre lecturas (5)")
    ap.add_argument("--umbral", type=int, default=1_000_000,
                    help="bytes para considerar un flujo elefante (1000000)")
    ap.add_argument("--reset", action="store_true", help="poner contadores y registers en cero al iniciar")
    ap.add_argument("--una-vez", action="store_true", help="imprimir una sola lectura y salir")
    ap.add_argument("--sin-limpiar", action="store_true", help="no limpiar la pantalla entre lecturas")
    args = ap.parse_args()

    if args.intervalo > 5:
        print("Aviso: el enunciado pide mostrar las estadísticas al menos cada 5 s.")

    flujos = cargar_flujos(args.puerto)
    if args.reset:
        resetear(flujos, args.puerto)
        print("Contadores y registers en cero.")
    escribir_umbral(args.umbral, args.puerto)   # el umbral se configura desde el control plane

    anterior = None
    anotados = set()
    try:
        while True:
            muestra = tomar_muestra(flujos, args.puerto)
            elefantes = imprimir(muestra, anterior, args.umbral, args.intervalo,
                                 limpiar=not (args.sin_limpiar or args.una_vez))
            anotar_elefantes(elefantes, anotados, args.umbral)
            if args.una_vez:
                break
            anterior = muestra
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        print("\nControlador detenido.")


if __name__ == "__main__":
    main()
