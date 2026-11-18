#!/bin/bash
# Carga la tabla ipv4_lpm de los tres routers por thrift (simple_switch_CLI).
# Correr una sola vez después de levantar la topología:
#     mininet> sh bash cargar_rutas.sh
# Se quitan los comentarios y las líneas vacías antes de pasarle cada archivo al CLI.
cd "$(dirname "$0")"
grep -v '^#' s1-rutas.txt | grep -v '^$' | simple_switch_CLI --thrift-port 9090   # s1
grep -v '^#' s2-rutas.txt | grep -v '^$' | simple_switch_CLI --thrift-port 9091   # s2
grep -v '^#' s3-rutas.txt | grep -v '^$' | simple_switch_CLI --thrift-port 9092   # s3
echo "Rutas cargadas en s1, s2 y s3."
