/*
 * Lab 1 — Router IPv4 estático en el plano de datos (v1model / BMv2)
 *
 * Qué hace el switch con cada paquete:
 *   1. Parsea Ethernet y, si el etherType es 0x0800, la cabecera IPv4.
 *   2. Si el TTL ya no permite otro salto (TTL <= 1), descarta el paquete.
 *   3. Busca la IP destino en la tabla ipv4_lpm (Longest Prefix Match). Si hay ruta:
 *        - elige el puerto de salida,
 *        - reescribe la MAC origen (la del puerto del router) y la MAC destino
 *          (la del siguiente salto: otro router o el host final),
 *        - decrementa el TTL.
 *      Si no hay ruta, se aplica la acción por defecto: descartar (default drop).
 *   4. Recalcula el checksum IPv4, porque el TTL cambió.
 *
 * La tabla ipv4_lpm arranca vacía: las rutas se cargan desde el control plane
 * (simple_switch_CLI / thrift) con los archivos sN-rutas.txt.
 */
#include <core.p4>
#include <v1model.p4>

/* ---------------------------------------------------------------- constantes */

const bit<16> TIPO_IPV4 = 0x800;   /* etherType de IPv4 */

typedef bit<9>  puerto_t;          /* puerto de BMv2 (egress_spec es de 9 bits) */
typedef bit<48> mac_t;
typedef bit<32> ip4_t;

/* ---------------------------------------------------------------- cabeceras */

header ethernet_t {
    mac_t   dstAddr;
    mac_t   srcAddr;
    bit<16> etherType;
}

/* Cabecera IPv4 sin opciones (20 bytes). */
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

/* El router no necesita metadatos propios entre etapas. */
struct metadata { }

struct headers {
    ethernet_t ethernet;
    ipv4_t     ipv4;
}

/* ---------------------------------------------------------------- parser */

/* Máquina de estados: Ethernet -> (IPv4 si corresponde) -> accept.
   Las tramas que no son IPv4 quedan solo con Ethernet válido. */
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
        packet.extract(hdr.ipv4);
        transition accept;
    }
}

/* No se verifica el checksum de entrada; solo se recalcula a la salida. */
control MiVerificarChecksum(inout headers hdr, inout metadata meta) {
    apply { }
}

/* ---------------------------------------------------------------- ingreso */

control MiIngreso(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    /* --- Acciones -------------------------------------------------------- */

    /* Marca el paquete para que BMv2 lo descarte al final del ingreso. */
    action descartar() {
        mark_to_drop(standard_metadata);
    }

    /* Reenvío hacia el siguiente salto. Los tres parámetros los pone el control
       plane en cada entrada de la tabla:
         mac_origen  -> MAC del puerto de salida de este router
         mac_destino -> MAC del siguiente salto (router vecino o host final)
         puerto      -> puerto de salida */
    action reenviar_ipv4(mac_t mac_origen, mac_t mac_destino, puerto_t puerto) {
        standard_metadata.egress_spec = puerto;
        hdr.ethernet.srcAddr = mac_origen;
        hdr.ethernet.dstAddr = mac_destino;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    /* --- Tablas ---------------------------------------------------------- */

    /* Tabla de enrutamiento: IP destino (LPM) -> siguiente salto.
       Si ningún prefijo coincide, se descarta (default drop). */
    table ipv4_lpm {
        key = { hdr.ipv4.dstAddr: lpm; }
        actions = {
            reenviar_ipv4;
            descartar;
            NoAction;
        }
        size = 1024;
        default_action = descartar();
    }

    apply {
        if (hdr.ipv4.isValid()) {
            /* Con TTL <= 1 el paquete llegaría a 0 al decrementar: se descarta
               en lugar de reenviarlo. */
            if (hdr.ipv4.ttl <= 1) {
                descartar();
            } else {
                ipv4_lpm.apply();
            }
        }
    }
}

/* ---------------------------------------------------------------- egreso */

/* Todo el procesamiento se hace en el ingreso. */
control MiEgreso(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply { }
}

/* Como el TTL cambió, hay que recalcular el checksum de la cabecera IPv4. */
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

/* Reserializa las cabeceras válidas, en orden, delante del payload. */
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
