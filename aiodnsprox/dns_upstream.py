# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

import enum
import typing

import dns.asyncquery
import dns.entropy
import dns.message


class DNSTransport(enum.Enum):
    UDP = 0
    UDP_TCP_FALLBACK = 1
    TCP = 2


class DNSUpstream:
    _QUERY_FUNC = {
        DNSTransport.UDP: dns.asyncquery.udp,
        DNSTransport.UDP_TCP_FALLBACK: dns.asyncquery.udp_with_fallback,
        DNSTransport.TCP: dns.asyncquery.tcp,
    }

    def __init__(self, host: str, port: typing.Optional[int] = None,
                 transport: typing.Optional[DNSTransport] = DNSTransport.UDP):
        self._host = host
        if port is None:
            if transport in [DNSTransport.UDP, DNSTransport.UDP_TCP_FALLBACK,
                             DNSTransport.TCP]:
                self._port = 53
            else:
                raise ValueError(f"Unsupported transport {transport}")
        else:
            self._port = port
        self._query_func = self._QUERY_FUNC[transport]

    @property
    def port(self):
        return self._port

    async def query(self, query: bytes,
                    timeout: typing.Optional[float] = None) -> bytes:
        qry = dns.message.from_wire(query)
        id_ = qry.id
        if qry.id == 0:
            id_ = dns.entropy.random_16()
            qry.id = id_
        resp = await self._query_func(qry, where=self._host, port=self._port,
                                      timeout=timeout)
        if self._query_func in [
            self._QUERY_FUNC[DNSTransport.UDP_TCP_FALLBACK]
        ]:
            resp = resp[0]
        resp.id = id_
        return resp.to_wire()
