#include <core.p4>
#include <v1model.p4>

const bit<16> TIPO_IPV4 = 0x800;

typedef bit<9>  puerto_t;
typedef bit<48> mac_t;
typedef bit<32> ip4_t;

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

struct metadata { }

struct headers {
    ethernet_t ethernet;
    ipv4_t     ipv4;
}

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

control MiVerificarChecksum(inout headers hdr, inout metadata meta) {
    apply { }
}

control MiIngreso(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    action descartar() {
        mark_to_drop(standard_metadata);
    }

    action reenviar_ipv4(mac_t mac_origen, mac_t mac_destino, puerto_t puerto) {
        standard_metadata.egress_spec = puerto;
        hdr.ethernet.srcAddr = mac_origen;
        hdr.ethernet.dstAddr = mac_destino;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

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
            if (hdr.ipv4.ttl <= 1) {
                descartar();
            } else {
                ipv4_lpm.apply();
            }
        }
    }
}

control MiEgreso(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply { }
}

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