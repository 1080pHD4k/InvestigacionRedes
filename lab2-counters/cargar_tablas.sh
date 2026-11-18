#!/bin/bash
# Carga las tablas de reenvío y de flujos en s1 (thrift 9090).
# Correr una sola vez después de levantar la topología (mininet> sh bash cargar_tablas.sh).
cd "$(dirname "$0")"
grep -v '^#' s1-tablas.txt | grep -v '^$' | simple_switch_CLI --thrift-port 9090
echo "Tablas cargadas en s1."
