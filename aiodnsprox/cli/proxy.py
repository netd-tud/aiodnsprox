#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

"""A datagram-based DNS-over-X proxy"""

import argparse
import asyncio

from aiodnsprox.config import Config
from aiodnsprox import coap
from aiodnsprox import dns_upstream
from aiodnsprox import dtls
from aiodnsprox import udp


FACTORIES = {
    'coap': coap.DNSOverCoAPServerFactory,
    'dtls': dtls.DNSOverDTLSServerFactory,
    'udp': udp.DNSOverUDPServerFactory,
}
servers = []


class HostPortAction(argparse.Action):          # pylint: disable=R0903
    DEFAULT_HOST = 'localhost'
    DEFAULT_PORTS = {
        'coap': None,
        'dtls': dtls.DNSOverDTLSServerFactory.DODTLS_PORT,
        'udp': udp.DNSOverUDPServerFactory.DNS_PORT,
    }

    def __call__(self, parser, namespace, values, option_string,
                 *args, **kwargs):
        if len(values) > 2:
            raise ValueError(f"{option_string} requires 2 or less arguments")
        if len(values) == 0:
            host = self.DEFAULT_HOST
            port = self._default_port()
        else:
            host = values[0]
            if len(values) == 1:
                port = self._default_port()
            else:
                port = int(values[1])
        if not hasattr(namespace, 'transports'):
            setattr(namespace, 'transports', argparse.Namespace())
        setattr(namespace.transports, self.dest, {'host': host, 'port': port})

    def _default_port(self):
        return self.DEFAULT_PORTS[self.dest]


class DTLSCredentialsAction(argparse.Action):   # pylint: disable=R0903
    def __call__(self, parser, namespace, values, option_string,
                 *args, **kwargs):
        setattr(namespace, self.dest, {
            'client_identity': values[0],
            'psk': values[1],
        })


class UpstreamAction(HostPortAction):           # pylint: disable=R0903
    TRANSPORTS = {
        'tcp': dns_upstream.DNSTransport.TCP,
        'udp': dns_upstream.DNSTransport.UDP,
        'udp+tcp': dns_upstream.DNSTransport.UDP_TCP_FALLBACK,
    }

    def __call__(self, parser, namespace, values, option_string,
                 *args, **kwargs):
        if len(values) > 3:
            raise ValueError(f"{option_string} requires 3 or less arguments")
        if len(values) == 3:
            transport = self._get_transport(values[0])
            host = values[1]
            port = int(values[2])
        else:
            transport = dns_upstream.DNSTransport.UDP
            host = values[0]
            if len(values) == 2:
                port = int(values[1])
            else:
                port = None
        setattr(namespace, self.dest, {'host': host, 'port': port,
                                       'transport': transport})

    def _get_transport(self, val):
        return self.TRANSPORTS[val]


def build_argparser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-C", "--config-file",
                        type=argparse.FileType('r', encoding='utf-8'),
                        help="Config YAML file")
    group = parser.add_argument_group('Transports')
    group.add_argument("-u", "--udp", nargs='*', action=HostPortAction,
                       default=None, metavar='host [port]',
                       help="Start DNS-over-UDP proxy")
    group.add_argument("-d", "--dtls", nargs='*', action=HostPortAction,
                       default=None, metavar='host [port]',
                       help="Start DNS-over-DTLS proxy")
    group.add_argument("-c", "--coap", nargs='*', action=HostPortAction,
                       default=None, metavar='host [port]',
                       help="Start DNS-over-CoAP proxy")
    parser.add_argument("--dtls-credentials", nargs=2,
                        action=DTLSCredentialsAction, default=None,
                        metavar='client_id psk',
                        help="DTLS credentials")
    parser.add_argument("-U", "--upstream-dns",
                        action=UpstreamAction, default=None, nargs='+',
                        metavar='[{udp,tcp,udp+tcp}] host [port]',
                        help="Upstream server configuration. Required either "
                             "as CLI argument or via config file. udp+tcp "
                             "tries to use UDP first, then falls back to TCP.")
    return parser


def get_config(args):
    config = Config()
    if args.config_file:
        config.add_yaml_config(args.config_file)
        args.config_file.close()
    del args.config_file
    config.add_args_config(args)
    if 'upstream_dns' not in config:
        raise RuntimeError("No upstream DNS server provided")
    if 'transports' not in config:
        raise RuntimeError("No proxy config provided")
    return config


def get_factory(transport, config):
    upstream = config['upstream_dns']
    return FACTORIES[transport](
        **{f'upstream_{k}': v for k, v in upstream.items()}
    )


async def close_servers():
    for server in list(servers):
        await server.close()
        servers.remove(server)


async def main():
    parser = build_argparser()
    args = parser.parse_args()
    config = get_config(args)

    loop = asyncio.get_event_loop()
    try:
        for transport, args in config['transports'].items():
            factory = get_factory(transport, config)
            servers.append(await factory.create_server(
                loop=loop, local_addr=(args['host'], args['port'])
            ))
    finally:
        await close_servers()


def sync_main():                # pragma: no cover
    asyncio.Task(main())
    asyncio.get_event_loop().run_forever()
