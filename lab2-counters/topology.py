#!/usr/bin/env python3
"""
Topología del Lab 2: 1 switch P4 (s1) y 4 hosts en la misma subred 10.0.0.0/24.

        h1 (10.0.0.1) --p1--+
        h2 (10.0.0.2) --p2--+-- s1 (BMv2, thrift 9090)
        h3 (10.0.0.3) --p3--+
        h4 (10.0.0.4) --p4--+

Convención: el host hN tiene IP 10.0.0.N, MAC 08:00:00:00:00:0N y está en el puerto N de s1.

Para que los contadores reflejen exactamente el tráfico inyectado, en cada host:
  - se usa ARP estático (no salen tramas ARP por la red),
  - se desactiva IPv6 (no salen anuncios ND/MLD),
  - se descartan con iptables los paquetes de prueba entrantes (TCP/UDP al puerto 7777 y
    protocolo 253), así el host destino no responde con RST ni ICMP unreachable.

Uso:  sudo python3 topology.py      (antes compilar: p4c-bm2-ss --p4v 16 -o counters.json counters.p4)
"""
from mininet.net import Mininet
from mininet.node import Switch, Host
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel, info

JSON = "counters.json"
SWITCH = "simple_switch"
PUERTO_PRUEBA = 7777   # puerto que usan los scripts de Scapy (ver trafico_scapy.py)


class P4Host(Host):
    """Host con el offload de checksums desactivado (si no, BMv2 ve checksums inválidos)."""
    def config(self, **params):
        r = super().config(**params)
        intf = self.defaultIntf().name
        for opt in ["rx", "tx", "sg"]:
            self.cmd("ethtool --offload %s %s off" % (intf, opt))
        return r


class P4Switch(Switch):
    """Lanza un proceso simple_switch (BMv2) con las interfaces del switch."""
    def __init__(self, name, json_path=JSON, thrift_port=None, device_id=0, **kw):
        Switch.__init__(self, name, **kw)
        self.json_path = json_path
        self.thrift_port = thrift_port
        self.device_id = device_id

    def start(self, controllers):
        args = [SWITCH, "--device-id", str(self.device_id)]
        for port, intf in self.intfs.items():
            if not intf.IP():
                args += ["-i", "%d@%s" % (port, intf.name)]
        args += ["--thrift-port", str(self.thrift_port), self.json_path]
        self.cmd(" ".join(args) + " >/tmp/%s.log 2>&1 &" % self.name)

    def stop(self):
        self.cmd("kill %" + SWITCH)
        self.deleteIntfs()


def preparar_host(h):
    """Deja el host 'silencioso' para que solo pase por el switch el tráfico de prueba."""
    h.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
    h.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
    h.cmd("sysctl -w net.ipv6.conf.lo.disable_ipv6=1")
    reglas = [
        "iptables -A INPUT -p tcp --dport %d -j DROP" % PUERTO_PRUEBA,
        "iptables -A INPUT -p udp --dport %d -j DROP" % PUERTO_PRUEBA,
        "iptables -A INPUT -p 253 -j DROP",
    ]
    for regla in reglas:
        salida = h.cmd(regla + " 2>&1")
        if salida.strip():
            info("*** Aviso en %s: '%s' -> %s\n" % (h.name, regla, salida.strip()))


def main():
    net = Mininet(controller=None, link=TCLink, host=P4Host, switch=P4Switch)

    s1 = net.addSwitch("s1", thrift_port=9090, device_id=0)

    hosts = []
    for n in range(1, 5):
        h = net.addHost("h%d" % n, ip="10.0.0.%d/24" % n, mac="08:00:00:00:00:0%d" % n)
        net.addLink(h, s1, port2=n)   # hN -> puerto N del switch
        hosts.append(h)

    net.start()
    net.staticArp()                    # ARP estático entre todos los hosts
    for h in hosts:
        preparar_host(h)

    print("\nRed lista. Siguiente paso, desde este prompt:")
    print("  mininet> sh bash cargar_tablas.sh")
    print("y en otra terminal:  sudo python3 controlador.py\n")
    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    main()
