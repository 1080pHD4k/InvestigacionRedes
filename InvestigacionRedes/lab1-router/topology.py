#!/usr/bin/env python3
import os
from mininet.net import Mininet
from mininet.node import Switch, Host
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel

JSON = "router.json"
SWITCH = "simple_switch"

class P4Host(Host):
    def config(self, **params):
        r = super().config(**params)
        intf = self.defaultIntf().name
        for opt in ["rx", "tx", "sg"]:
            self.cmd("ethtool --offload %s %s off" % (intf, opt))
        return r

class P4Switch(Switch):
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

def configurar_host(h, gw_ip, gw_mac):
    h.cmd("ip route add default via %s" % gw_ip)
    h.cmd("arp -s %s %s" % (gw_ip, gw_mac))

def main():
    net = Mininet(controller=None, link=TCLink, host=P4Host, switch=P4Switch)

    s1 = net.addSwitch("s1", thrift_port=9090, device_id=0)
    s2 = net.addSwitch("s2", thrift_port=9091, device_id=1)
    s3 = net.addSwitch("s3", thrift_port=9092, device_id=2)

    h1 = net.addHost("h1", ip="10.0.1.1/24", mac="08:00:00:00:01:11")
    h2 = net.addHost("h2", ip="10.0.2.2/24", mac="08:00:00:00:02:22")
    h3 = net.addHost("h3", ip="10.0.3.3/24", mac="08:00:00:00:03:33")
    h4 = net.addHost("h4", ip="10.0.4.4/24", mac="08:00:00:00:04:44")

    net.addLink(h1, s1, port2=1)
    net.addLink(s1, s2, port1=2, port2=1)
    net.addLink(h2, s2, port2=2)
    net.addLink(s2, s3, port1=3, port2=1)
    net.addLink(h3, s3, port2=2)
    net.addLink(h4, s3, port2=3)

    net.start()

    configurar_host(h1, "10.0.1.254", "00:00:00:01:01:00")
    configurar_host(h2, "10.0.2.254", "00:00:00:02:02:00")
    configurar_host(h3, "10.0.3.254", "00:00:00:03:02:00")
    configurar_host(h4, "10.0.4.254", "00:00:00:03:03:00")

    print("Red lista. Carga las rutas (rutas.txt) y luego proba con pingall.")
    CLI(net)
    net.stop()

if __name__ == "__main__":
    setLogLevel("info")
    main()
