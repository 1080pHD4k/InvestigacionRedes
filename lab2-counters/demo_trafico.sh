# Comandos de demostración del Lab 2 para pegar en el prompt de Mininet:
#     mininet> source demo_trafico.sh
# (el CLI de Mininet ejecuta cada línea como si se escribiera a mano)
#
# Antes: en otra terminal dejar corriendo   sudo python3 controlador.py --reset
#
# 1) Tráfico mixto controlado con Scapy (flujos "ratón", quedan bajo el umbral de 1 MB)
h1 python3 trafico_scapy.py 10.0.0.2 --tcp 100 --udp 50 --icmp 30 --otros 20 --tam 200
h2 python3 trafico_scapy.py 10.0.0.3 --tcp 40 --udp 40 --tam 600 --anexar
h4 python3 trafico_scapy.py 10.0.0.1 --icmp 25 --otros 15 --tam 1000 --anexar
# 2) Verificación exacta de los contadores contra lo enviado
sh python3 verificar.py
# 3) Flujo elefante TCP con iperf: h3 -> h4 (varios MB en 10 s)
h4 iperf -s &
h3 iperf -c 10.0.0.4 -t 10
# 4) Tráfico UDP con iperf: h1 -> h3 a 1 Mb/s (no llega a elefante en 5 s: ~650 KB)
h3 iperf -s -u &
h1 iperf -c 10.0.0.3 -u -b 1M -t 5
