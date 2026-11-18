## Lab 1 — Router IPv4 estático
Stephanie Monge Ortiz y
Paula Sofía Grell Araya

### Requisitos
- p4c, BMv2, Mininet y Scapy


### Cómo ejecutar
1. Compilar el programa P4:
       cd lab1-router
       p4c-bm2-ss --p4v 16 -o router.json router.p4
2. Levantar la red:
       sudo python3 topology.py
3. En el prompt mininet>:
       mininet> sh bash cargar_rutas.sh

### Pruebas
- Conectividad:
      mininet> pingall           # debe dar un 0% dropped
- Decremento de TTL (sale con 64, llega con 61 tras 3 routers). Se deja capturando a h4 y
  su salida va a un archivo, porque Mininet no muestra la salida de procesos en segundo plano:
      mininet> h4 python3 -u test_scripts/recibir.py h4-eth0 > /tmp/h4.txt 2>&1 &
      mininet> h1 python3 test_scripts/enviar.py 10.0.4.4
      mininet> sh cat /tmp/h4.txt      # "de 10.0.1.1 -> ttl 61"
  (también se ve en `h1 ping -c 1 10.0.4.4`: la respuesta llega con ttl=61)
- Descarte por TTL agotado (un router descarta lo que recibe con TTL <= 1; de h1 a h4 hay 3 routers):
      mininet> h1 python3 test_scripts/enviar.py 10.0.4.4 1 4    # llega con ttl 1
      mininet> h1 python3 test_scripts/enviar.py 10.0.4.4 1 3    # lo descarta s3, no llega
      mininet> sh cat /tmp/h4.txt      # solo aparece el paquete con TTL 4
- Descarte sin ruta:
      mininet> h1 ping -c 3 10.0.9.9   # debe dar un 100% packet loss
- Al terminar:  mininet> h4 kill %python3

### Archivos
- router.p4         programa del router
- topology.py       topología Mininet
- s1/s2/s3-rutas.txt  tablas LPM de cada router
- cargar_rutas.sh   carga las tres tablas LPM
- test_scripts/     enviar.py (ICMP con TTL configurable) y recibir.py (muestra el TTL que llega)


## Lab 2 — Contadores y estadísticas de tráfico
Carpeta `lab2-counters/`. Topología: 1 switch P4 (s1) y 4 hosts (h1–h4, 10.0.0.1–10.0.0.4).

### Qué implementa
- Contador directo (`direct_counter`) por flujo IP origen + IP destino (tabla `flujos`).
- Contador global por protocolo: TCP, UDP, ICMP y otros.
- Registers con el tamaño de los paquetes: último, mínimo y máximo por flujo, más un histograma global.
- Detección de flujos elefante: el switch acumula bytes por flujo y marca los que superan el umbral
  (configurable, lo escribe el controlador en un register). El controlador además los anota en `elefantes.log`.
- Controlador en Python (thrift vía `simple_switch_CLI`) que imprime todo cada 5 s.

### Requisitos
- p4c, BMv2, Mininet, Scapy, iperf e iptables

### Cómo ejecutar
1. Compilar:
       cd lab2-counters
       p4c-bm2-ss --p4v 16 -o counters.json counters.p4
2. Levantar la red:
       sudo python3 topology.py
3. Cargar las tablas (reenvío + flujos):
       mininet> sh bash cargar_tablas.sh
4. En otra terminal, en `lab2-counters/`, iniciar el controlador:
       sudo python3 controlador.py --reset              # cada 5 s, umbral 1 MB
       sudo python3 controlador.py --umbral 500000      # otro umbral

### Pruebas
- Exactitud de los contadores (tráfico conocido con Scapy y comparación automática):
      mininet> sh python3 controlador.py --reset --una-vez
      mininet> h1 python3 trafico_scapy.py 10.0.0.2 --tcp 100 --udp 50 --icmp 30 --otros 20 --tam 200
      mininet> h2 python3 trafico_scapy.py 10.0.0.3 --tcp 40 --udp 40 --tam 600 --anexar
      mininet> sh python3 verificar.py      # debe decir que todos los contadores coinciden
- Flujo elefante con iperf (h3 -> h4 aparece como ** ELEFANTE ** en el controlador):
      mininet> h4 iperf -s &
      mininet> h3 iperf -c 10.0.0.4 -t 10
- Todo junto: `mininet> source demo_trafico.sh`

Notas: para que la medición sea exacta, `topology.py` usa ARP estático, desactiva IPv6 en los hosts y
bloquea con iptables el puerto 7777 y el protocolo 253, así el destino no responde al tráfico de prueba.

### Archivos
- counters.p4        programa P4 (contadores, registers, elefantes y reenvío)
- topology.py        topología Mininet (1 switch, 4 hosts)
- s1-tablas.txt      entradas de las tablas `reenvio` y `flujos`
- cargar_tablas.sh   carga las tablas en s1
- controlador.py     lectura periódica y presentación de estadísticas
- trafico_scapy.py   generador de tráfico mixto con cantidades exactas
- verificar.py       compara los contadores con el tráfico enviado
- demo_trafico.sh    secuencia de comandos para la demo
