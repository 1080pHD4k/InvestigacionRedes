/*
 * Lab 2 — Contadores y estadísticas de tráfico en el plano de datos (v1model / BMv2)
 *
 * Qué mide el switch por cada paquete:
 *   1. Contador global por protocolo (counter indirecto): TCP, UDP, ICMP y otros.
 *   2. Contador directo (direct_counter) por flujo, donde un flujo = IP origen + IP destino.
 *   3. Tamaño de los paquetes en registers: último, mínimo y máximo por flujo, y un
 *      histograma global por rangos de tamaño.
 *   4. Detección de flujos elefante: se acumulan los bytes de cada flujo en un register y,
 *      si superan el umbral que escribe el control plane, el flujo queda marcado.
 *
 * Además reenvía los paquetes IPv4 por IP destino (tabla LPM) para que los hosts se comuniquen.
 *
 * Todas las tablas y el umbral se configuran desde el control plane (simple_switch_CLI / thrift).
 */
#include <core.p4>
#include <v1model.p4>

/* ---------------------------------------------------------------- constantes */

const bit<16> TIPO_IPV4 = 0x800;

const bit<8> PROTO_ICMP = 1;
const bit<8> PROTO_TCP  = 6;
const bit<8> PROTO_UDP  = 17;

/* Índices del contador global por protocolo */
const bit<32> IDX_TCP   = 0;
const bit<32> IDX_UDP   = 1;
const bit<32> IDX_ICMP  = 2;
const bit<32> IDX_OTROS = 3;   /* otros protocolos IPv4 y tramas que no son IPv4 */
const bit<32> N_PROTOCOLOS = 4;

/* Máximo de flujos monitoreados (cada uno tiene un id 0..N_FLUJOS-1) */
const bit<32> N_FLUJOS = 64;

/* Rangos del histograma de tamaños (en bytes de trama Ethernet) */
const bit<32> N_RANGOS = 4;    /* 0: <128, 1: 128-511, 2: 512-1023, 3: >=1024 */

typedef bit<9>  puerto_t;
typedef bit<48> mac_t;
typedef bit<32> ip4_t;

/* ---------------------------------------------------------------- cabeceras */

header ethernet_t {
    mac_t   dstAddr;
    mac_t   srcAddr;
    bit<16> etherType;
}

header ipv4_t {
    bit<4>  version;
    bit<4>  ihl;
    bit<8>  diffserv;
    bit<16> totalLen;
    bit<16> identification;
    bit<3>  flags;
    bit<13> fragOffset;
    bit<8>  ttl;
    bit<8>  protocol;
    bit<16> hdrChecksum;
    ip4_t   srcAddr;
    ip4_t   dstAddr;
}

/* Metadatos propios que viajan entre las etapas del pipeline */
struct metadata {
    bit<1>  flujo_conocido;   /* 1 si el paquete pegó en la tabla de flujos */
    bit<32> id_flujo;         /* índice del flujo en los registers */
}

struct headers {
    ethernet_t ethernet;
    ipv4_t     ipv4;
}

/* ---------------------------------------------------------------- parser */

parser MiParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {
    state start {
        transition parse_ethernet;
    }
    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TIPO_IPV4: parse_ipv4;
            default:   accept;
        }
    }
    state parse_ipv4 {
        /* Solo se necesita el campo protocol de IPv4 para clasificar, no hace
           falta parsear TCP/UDP/ICMP. */
        packet.extract(hdr.ipv4);
        transition accept;
    }
}

control MiVerificarChecksum(inout headers hdr, inout metadata meta) {
    apply { }
}

/* ---------------------------------------------------------------- ingreso */

control MiIngreso(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    /* --- Contadores ------------------------------------------------------ */

    /* Contador global indexado por protocolo (ver IDX_*). */
    counter(N_PROTOCOLOS, CounterType.packets_and_bytes) contador_protocolos;

    /* Contador directo: hay una celda por cada entrada de la tabla 'flujos'.
       En v1model se actualiza solo cuando una entrada hace match, aunque la
       acción no llame a count(). Los misses no se cuentan. */
    direct_counter(CounterType.packets_and_bytes) contador_flujos;

    /* --- Registers de tamaño y de flujos elefante ------------------------ */

    register<bit<32>>(N_FLUJOS) tam_ultimo;      /* tamaño del último paquete del flujo */
    register<bit<32>>(N_FLUJOS) tam_minimo;      /* 0 = todavía sin paquetes */
    register<bit<32>>(N_FLUJOS) tam_maximo;
    register<bit<32>>(N_RANGOS) histograma_tam;  /* paquetes por rango de tamaño (global) */

    register<bit<64>>(N_FLUJOS) bytes_flujo;     /* bytes acumulados por flujo */
    register<bit<8>>(N_FLUJOS)  elefante;        /* 1 = el flujo superó el umbral */
    register<bit<64>>(1)        umbral_elefante; /* lo escribe el controlador; 0 = desactivado */

    /* --- Acciones -------------------------------------------------------- */

    action descartar() {
        mark_to_drop(standard_metadata);
    }

    /* Reenvío: solo se elige el puerto de salida. Las MAC no se tocan porque los
       hosts están en la misma subred y tienen ARP estático. */
    action reenviar(puerto_t puerto) {
        standard_metadata.egress_spec = puerto;
    }

    /* El flujo está registrado: se guarda su id para indexar los registers. */
    action contar_flujo(bit<32> id) {
        meta.flujo_conocido = 1;
        meta.id_flujo = id;
    }

    action flujo_desconocido() {
        meta.flujo_conocido = 0;
    }

    /* --- Tablas ---------------------------------------------------------- */

    /* Tabla de flujos: (IP origen, IP destino) -> id del flujo, con contador directo. */
    table flujos {
        key = {
            hdr.ipv4.srcAddr: exact;
            hdr.ipv4.dstAddr: exact;
        }
        actions = {
            contar_flujo;
            flujo_desconocido;
        }
        counters = contador_flujos;
        size = 64;          /* = N_FLUJOS */
        default_action = flujo_desconocido();
    }

    /* Tabla de reenvío por IP destino. Si no hay ruta, el paquete se descarta. */
    table reenvio {
        key = { hdr.ipv4.dstAddr: lpm; }
        actions = {
            reenviar;
            descartar;
        }
        size = 256;
        default_action = descartar();
    }

    apply {
        /* Tamaño de la trama tal como entró al switch (incluye Ethernet). */
        bit<32> tam = standard_metadata.packet_length;

        /* 1. Contador global por protocolo ------------------------------- */
        if (!hdr.ipv4.isValid()) {
            /* Tramas que no son IPv4 (ARP, IPv6...): van a "otros". Los hosts
               usan ARP estático e IPv6 está desactivado, así que no debería haber. */
            contador_protocolos.count(IDX_OTROS);
        } else if (hdr.ipv4.protocol == PROTO_TCP) {
            contador_protocolos.count(IDX_TCP);
        } else if (hdr.ipv4.protocol == PROTO_UDP) {
            contador_protocolos.count(IDX_UDP);
        } else if (hdr.ipv4.protocol == PROTO_ICMP) {
            contador_protocolos.count(IDX_ICMP);
        } else {
            contador_protocolos.count(IDX_OTROS);
        }

        /* 2. Histograma global de tamaños --------------------------------- */
        bit<32> rango;
        if (tam < 128) {
            rango = 0;
        } else if (tam < 512) {
            rango = 1;
        } else if (tam < 1024) {
            rango = 2;
        } else {
            rango = 3;
        }
        bit<32> en_rango;
        histograma_tam.read(en_rango, rango);
        histograma_tam.write(rango, en_rango + 1);

        if (!hdr.ipv4.isValid()) {
            descartar();
            return;
        }

        /* 3. Contador directo por flujo (se actualiza solo al hacer match) - */
        flujos.apply();

        /* 4. Tamaños y detección de elefante para flujos registrados ------- */
        if (meta.flujo_conocido == 1) {
            bit<32> id = meta.id_flujo;

            tam_ultimo.write(id, tam);

            bit<32> minimo;
            tam_minimo.read(minimo, id);
            if (minimo == 0 || tam < minimo) {
                tam_minimo.write(id, tam);
            }

            bit<32> maximo;
            tam_maximo.read(maximo, id);
            if (tam > maximo) {
                tam_maximo.write(id, tam);
            }

            bit<64> acumulado;
            bytes_flujo.read(acumulado, id);
            acumulado = acumulado + (bit<64>) tam;
            bytes_flujo.write(id, acumulado);

            bit<64> umbral;
            umbral_elefante.read(umbral, 0);
            if (umbral != 0 && acumulado >= umbral) {
                elefante.write(id, 1);
            }
        }

        /* 5. Reenvío ------------------------------------------------------ */
        reenvio.apply();
    }
}

/* ---------------------------------------------------------------- egreso */

control MiEgreso(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply { }
}

/* No se modifica ningún campo de IPv4, pero se recalcula el checksum por consistencia. */
control MiComputarChecksum(inout headers hdr, inout metadata meta) {
    apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version, hdr.ipv4.ihl, hdr.ipv4.diffserv,
              hdr.ipv4.totalLen, hdr.ipv4.identification, hdr.ipv4.flags,
              hdr.ipv4.fragOffset, hdr.ipv4.ttl, hdr.ipv4.protocol,
              hdr.ipv4.srcAddr, hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);
    }
}

/* ---------------------------------------------------------------- deparser */

control MiDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
    }
}

V1Switch(
    MiParser(),
    MiVerificarChecksum(),
    MiIngreso(),
    MiEgreso(),
    MiComputarChecksum(),
    MiDeparser()
) main;
