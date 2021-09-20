# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

import asyncio
import abc
import copy
import enum
import typing
import time

import dns.asyncquery
import dns.entropy
import dns.exception
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
    DEFAULT_LIFETIME = 5.0
    DEFAULT_TIMEOUT = 2.0

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
        self._transport = transport
        self._query_func = self._QUERY_FUNC[transport]

    @property
    def port(self):
        return self._port

    def _compute_timeout(self, start, lifetime=None):
        # https://dnspython.readthedocs.io/en/stable/_modules/dns/resolver.html
        # Resolver._compute_timeout()
        if lifetime is None:
            lifetime = self.DEFAULT_LIFETIME
        now = time.time()
        duration = now - start
        if duration < 0:    # pragma: no cover
            if duration < -1:
                # Time going backwards is bad. Just give up.
                raise dns.exception.Timeout(timeout=duration)
            # Time went backwards, but only a little.  This can
            # happen, e.g. under vmware with older linux kernels.
            # Pretend it didn't happen.
            now = start
        if duration >= lifetime:
            raise dns.exception.Timeout(timeout=duration)   # pragma: no cover
        return min(lifetime - duration, self.DEFAULT_TIMEOUT)

    @staticmethod
    def _resp_servfail(query):
        resp = copy.deepcopy(query)
        resp.flags = dns.flags.QR | dns.flags.RD | dns.flags.RA
        resp.set_rcode(dns.rcode.SERVFAIL)
        return resp

    async def query(self, query: bytes,
                    timeout: typing.Optional[float] = None) -> bytes:
        qry = dns.message.from_wire(query)
        start = time.time()
        id_ = qry.id
        tuple_resp = self._transport in [DNSTransport.UDP_TCP_FALLBACK]
        if qry.id == 0:
            id_ = dns.entropy.random_16()
            qry.id = id_
        if self._transport in [DNSTransport.UDP]:
            resp = None
            lifetime = timeout
            while resp is None:
                timeout = self._compute_timeout(start, lifetime)
                try:
                    resp = await self._query_func(qry, where=self._host,
                                                  port=self._port,
                                                  timeout=timeout)
                except dns.exception.DNSException:
                    resp = self._resp_servfail(qry)
                    break
        else:
            try:
                resp = await self._query_func(qry, where=self._host,
                                              port=self._port, timeout=timeout)
            except (dns.exception.DNSException, ConnectionRefusedError):
                resp = self._resp_servfail(qry)
                tuple_resp = False
        if tuple_resp:
            resp = resp[0]
        resp.id = id_
        return resp.to_wire()


class DNSUpstreamServerMixin(abc.ABC):
    # pylint: disable=too-few-public-methods
    def __init__(self, host, port: typing.Optional[int] = None,
                 transport: typing.Optional[DNSTransport] = DNSTransport.UDP,
                 timeout: typing.Optional[float] = None):
        self._dns_upstream = DNSUpstream(
            host=host,
            port=port,
            transport=transport
        )
        self._timeout = timeout

    async def _get_query_response(self, query, requester):
        resp = await self._dns_upstream.query(query, timeout=self._timeout)
        self._send_response_to_requester(resp, requester)

    def _dns_query_received(self, query, requester) -> None:
        loop = asyncio.get_event_loop()
        coroutine = self._get_query_response(query, requester)
        loop.create_task(coroutine)

    @abc.abstractmethod
    def _send_response_to_requester(self, response: bytes,
                                    requester: typing.Tuple) -> None:
        raise NotImplementedError
