#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

"""Base definitions for the serving side of the DNS proxy"""

import abc
import asyncio
import typing

from .dns_upstream import DNSTransport


class BaseDNSServer(abc.ABC):
    # pylint: disable=too-few-public-methods
    @abc.abstractmethod
    async def close(self):
        raise NotImplementedError


class BaseServerFactory(abc.ABC):
    # pylint: disable=too-few-public-methods
    def __init__(self, upstream_host: str,
                 upstream_port: typing.Optional[int] = None,
                 upstream_transport: typing.Optional[DNSTransport] =
                 DNSTransport.UDP,
                 upstream_timeout: typing.Optional[float] = None):
        self.upstream_host = upstream_host
        self.upstream_port = upstream_port
        self.upstream_transport = upstream_transport
        self.upstream_timeout = upstream_timeout

    @abc.abstractmethod
    async def create_server(
        self, loop: asyncio.AbstractEventLoop, *args,
        local_addr: typing.Tuple[str, int] = None, **kwargs
    ) -> BaseDNSServer:
        raise NotImplementedError
