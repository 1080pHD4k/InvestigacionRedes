## Lab 1 — Router IPv4 estático
Stephanie Monge Ortiz
Paula Sofía Grell Araya

### Requisitos
- p4c, BMv2, Mininet y Scapy


### Cómo ejecutar
1. Compilar el programa P4:
       p4c-bm2-ss --p4v 16 -o router.json router.p4
2. Levantar la red:
       sudo python3 topology.py
3. En el prompt mininet>:
       mininet> sh bash cargar_rutas.sh

### Pruebas
- Conectividad:
      mininet> pingall           # debe dar un 0% dropped
- Decremento de TTL (sale con 64, llega con 61 tras 3 routers):
      mininet> h4 python3 test_scripts/recibir.py h4-eth0 &
      mininet> h1 ping -c 1 10.0.4.4
- Descarte sin ruta:
      mininet> h1 ping -c 3 10.0.9.9   # debe dar un 100% packet loss

### Archivos
- router.p4         programa del router
- topology.py       topología Mininet
- s1/s2/s3-rutas.txt  tablas LPM de cada router
- cargar_rutas.sh   carga las tres tablas LPM
- test_scripts/     enviar.py y recibir.py 