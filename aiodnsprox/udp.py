# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

from .dns_server import BaseServerFactory, BaseDNSServer
from .dns_upstream import DNSUpstreamServerMixin


class DNSOverUDPServerFactory(BaseServerFactory):
    # pylint: disable=too-few-public-methods
    DNS_PORT = 53

    class DNSOverUDPServer(BaseDNSServer, DNSUpstreamServerMixin):
        def __init__(self, factory):
            super().__init__(host=factory.upstream_host,
                             port=factory.upstream_port,
                             transport=factory.upstream_transport,
                             timeout=factory.upstream_timeout)
            self.transport = None

        def send_response_to_requester(self, response, requester):
            self.transport.sendto(response, requester)

        def connection_made(self, transport):
            self.transport = transport

        def datagram_received(self, data, addr):
            self.dns_query_received(data, addr)

        def error_received(self, exc):      # pylint: disable=no-self-use
            raise exc                       # pragma: no cover

        def connection_lost(self, exc):     # pylint: disable=no-self-use
            pass                            # pragma: no cover

        async def close(self):
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
