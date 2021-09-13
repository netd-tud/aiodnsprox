# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

from .dns_server import DNSServer
from .dns_upstream import DNSUpstreamServerMixin
from .server_factory import BaseServerFactory


class DNSOverUDPServerFactory(BaseServerFactory):
    # pylint: disable=too-few-public-methods
    DNS_PORT = 53

    class DNSOverUDPServer(DNSServer, DNSUpstreamServerMixin):
        def __init__(self, factory):
            super().__init__(host=factory.upstream_host,
                             port=factory.upstream_port,
                             transport=factory.upstream_transport,
                             timeout=factory.upstream_timeout)
            self.transport = None

        def _send_response_to_requester(self, response, requester):
            self.transport.sendto(response, requester)

        def connection_made(self, transport):
            self.transport = transport

        def datagram_received(self, data, addr):
            self._dns_query_received(data, addr)

        def error_received(self, exc):  # pylint: disable=no-self-use
            raise exc   # pragma: no cover

        def close(self):
            if self.transport is not None:
                self.transport.close()
                self.transport = None

    def _create_server_protocol(self, *args, **kwargs):
        return self.DNSOverUDPServer(self, *args, **kwargs)

    async def create_server(self, loop, *args, local_addr=None,
                            **kwargs):
        if local_addr is None:
            local_addr = ('localhost', self.DNS_PORT)
        if local_addr[1] is None:
            local_addr = (local_addr[0], self.DNS_PORT)

        _, protocol = await loop.create_datagram_endpoint(
            self._create_server_protocol, *args,
            local_addr=local_addr,
            **kwargs,
        )
        return protocol
