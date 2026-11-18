#!/usr/bin/env python3
"""
Topología del Lab 1: 3 routers P4 en línea y 4 hosts, cada uno en su propia subred /24.

    h1 --p1-[ s1 ]-p2------p1-[ s2 ]-p3------p1-[ s3 ]-p2-- h3
                                  |p2                 |p3
                                  h2                  h4

  Host  IP            MAC                 Gateway (IP / MAC)
  h1    10.0.1.1/24   08:00:00:00:01:11   10.0.1.254 / 00:00:00:01:01:00  (s1, puerto 1)
  h2    10.0.2.2/24   08:00:00:00:02:22   10.0.2.254 / 00:00:00:02:02:00  (s2, puerto 2)
  h3    10.0.3.3/24   08:00:00:00:03:33   10.0.3.254 / 00:00:00:03:02:00  (s3, puerto 2)
  h4    10.0.4.4/24   08:00:00:00:04:44   10.0.4.254 / 00:00:00:03:03:00  (s3, puerto 3)

Convención de MAC de los routers: 00:00:00:0S:0P:00 = switch S, puerto P. Son MAC lógicas:
las usa el P4 al reescribir Ethernet y las conocen los hosts por ARP estático.

Uso:  sudo python3 topology.py      (antes compilar: p4c-bm2-ss --p4v 16 -o router.json router.p4)
"""
import os
from mininet.net import Mininet
from mininet.node import Switch, Host
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel

JSON = "router.json"        # programa compilado que carga cada switch
SWITCH = "simple_switch"    # binario de BMv2


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
        self.thrift_port = thrift_port   # puerto donde escucha simple_switch_CLI
        self.device_id = device_id

    def start(self, controllers):
        # Cada interfaz de Mininet se mapea al puerto BMv2 del mismo número: -i <puerto>@<interfaz>.
        # Se omite la interfaz de loopback (la única que tiene IP).
        args = [SWITCH, "--device-id", str(self.device_id)]
        for port, intf in self.intfs.items():
            if not intf.IP():
                args += ["-i", "%d@%s" % (port, intf.name)]
        args += ["--thrift-port", str(self.thrift_port), self.json_path]
        # El log de cada switch queda en /tmp/sN.log
        self.cmd(" ".join(args) + " >/tmp/%s.log 2>&1 &" % self.name)

    def stop(self):
        self.cmd("kill %" + SWITCH)
        self.deleteIntfs()


def configurar_host(h, gw_ip, gw_mac):
    """Ruta por defecto hacia el router y ARP estático para su MAC
    (el router P4 no responde ARP)."""
    h.cmd("ip route add default via %s" % gw_ip)
    h.cmd("arp -s %s %s" % (gw_ip, gw_mac))


def main():
    net = Mininet(controller=None, link=TCLink, host=P4Host, switch=P4Switch)

    # Routers: cada uno con su propio puerto thrift para cargarle las rutas
    s1 = net.addSwitch("s1", thrift_port=9090, device_id=0)
    s2 = net.addSwitch("s2", thrift_port=9091, device_id=1)
    s3 = net.addSwitch("s3", thrift_port=9092, device_id=2)

    # Hosts, uno por subred
    h1 = net.addHost("h1", ip="10.0.1.1/24", mac="08:00:00:00:01:11")
    h2 = net.addHost("h2", ip="10.0.2.2/24", mac="08:00:00:00:02:22")
    h3 = net.addHost("h3", ip="10.0.3.3/24", mac="08:00:00:00:03:33")
    h4 = net.addHost("h4", ip="10.0.4.4/24", mac="08:00:00:00:04:44")

    # Enlaces con números de puerto fijos (deben coincidir con sN-rutas.txt)
    net.addLink(h1, s1, port2=1)                 # h1  <-> s1:1
    net.addLink(s1, s2, port1=2, port2=1)        # s1:2 <-> s2:1
    net.addLink(h2, s2, port2=2)                 # h2  <-> s2:2
    net.addLink(s2, s3, port1=3, port2=1)        # s2:3 <-> s3:1
    net.addLink(h3, s3, port2=2)                 # h3  <-> s3:2
    net.addLink(h4, s3, port2=3)                 # h4  <-> s3:3

    net.start()

    # Gateway de cada host = puerto del router al que está conectado
    configurar_host(h1, "10.0.1.254", "00:00:00:01:01:00")
    configurar_host(h2, "10.0.2.254", "00:00:00:02:02:00")
    configurar_host(h3, "10.0.3.254", "00:00:00:03:02:00")
    configurar_host(h4, "10.0.4.254", "00:00:00:03:03:00")

    print("\nRed lista. Siguiente paso, desde este prompt:")
    print("  mininet> sh bash cargar_rutas.sh")
    print("y luego probar con:  mininet> pingall\n")
    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    main()
