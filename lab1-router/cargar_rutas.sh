#!/bin/bash
simple_switch_CLI --thrift-port 9090 < s1-rutas.txt
simple_switch_CLI --thrift-port 9091 < s2-rutas.txt
simple_switch_CLI --thrift-port 9092 < s3-rutas.txt
echo "Rutas cargadas en s1, s2 y s3."