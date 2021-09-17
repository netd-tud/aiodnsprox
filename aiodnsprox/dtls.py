# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

import abc
import asyncio
import logging
import typing

from DTLSSocket import dtls

from .config import Config
from .dns_upstream import DNSUpstreamServerMixin
from .server_factory import BaseServerFactory


logger = logging.getLogger()


class BaseDTLSWrapper(abc.ABC):
    def __init__(self, transport: asyncio.DatagramTransport):
        self.transport = transport

    @abc.abstractmethod
    def is_connected(self, addr: typing.Tuple):
        raise NotImplementedError

    @abc.abstractmethod
    def sessions(self) -> typing.Sequence:
        raise NotImplementedError

    @abc.abstractmethod
    def connect(self, addr: typing.Tuple):
        raise NotImplementedError

    @abc.abstractmethod
    def close(self, session):
        raise NotImplementedError

    @abc.abstractmethod
    def handle_message(self, msg: bytes, session) -> \
            typing.Tuple[bytes, typing.Tuple, bool]:
        raise NotImplementedError

    @abc.abstractmethod
    def write(self, msg: bytes, session):
        raise NotImplementedError


class TinyDTLSWrapper(BaseDTLSWrapper):
    EVENT_CONNECTED = 0x1de

    def __init__(self, transport):
        super().__init__(transport)
        # pylint: disable=c-extension-no-member
        credentials = Config()['dtls_credentials']
        client_identity = credentials['client_identity'].encode()
        psk = credentials['psk'].encode()
        self._dtls = dtls.DTLS(
            read=self._read, write=self._write, event=self._event,
            pskId=client_identity, pskStore={client_identity: psk}
        )
        self._active_sessions = {}
        self._app_data = None
        self._last_event = None

    def __del__(self):
        self._active_sessions.clear()
        del self._dtls
        self._dtls = None

    def _read(self, addr, data):
        self._app_data = (data, addr + (0, 0))
        return len(data)

    def _write(self, addr, data):
        self.transport.sendto(data, addr + (0, 0))
        return len(data)

    def _event(self, level, code):
        # pylint: disable=unused-argument
        self._last_event = code

    def is_connected(self, addr):
        return addr in self._active_sessions

    def sessions(self):
        return list(self._active_sessions)

    def connect(self, addr):
        self._dtls.connect(*addr)

    def close(self, session):
        if self.is_connected(session):
            self._dtls.close(self._active_sessions[session])
            del self._active_sessions[session]

    def handle_message(self, msg, session):
        connected = False
        if isinstance(session, tuple):
            ret = self._dtls.handleMessageAddr(session[0], session[1], msg)
            addr = session
        elif isinstance(session, dtls.Session):     # pylint: disable=I1101
            ret = self._dtls.handleMessage(session, msg)
            addr = session.addr, session.port, session.flowinfo, \
                session.scope_id
        else:
            raise ValueError(f"Unexpected session type {type(session)}")
        if ret < 0:
            logger.warning('Unable to handle incoming DTLS message from '
                           '%s', addr)
            return None, None, connected
        if self._last_event == self.EVENT_CONNECTED and \
           not self.is_connected(addr):
            # pylint: disable=c-extension-no-member
            self._active_sessions[addr] = dtls.Session(*addr[:4])
            connected = True
        self._last_event = None
        if self._app_data is None:
            logger.debug("Unable to fetch application data from DTLS")
            return None, None, connected
        data, addr = self._app_data
        self._app_data = None
        return data, addr, connected

    def write(self, msg, session):
        if isinstance(session, tuple):
            if not self.is_connected(session):
                logger.warning('%s does not have an active session', session)
                return
            session = self._active_sessions[session]
        self._dtls.write(session, msg)


class DNSOverDTLSServerFactory(BaseServerFactory):
    # pylint: disable=too-few-public-methods
    DODTLS_PORT = 853
    dtls_class = TinyDTLSWrapper

    class DNSOverDTLSServer(DNSUpstreamServerMixin):
        def __init__(self, factory):
            super().__init__(host=factory.upstream_host,
                             port=factory.upstream_port,
                             transport=factory.upstream_transport,
                             timeout=factory.upstream_timeout)
            self.factory = factory
            self.transport = None
            self._dtls = None

        def __del__(self):
            del self._dtls
            self._dtls = None

        def connection_made(self, transport):
            self.transport = transport
            self._dtls = self.factory.dtls_class(self.transport)

        def datagram_received(self, data, addr):
            data, addr, _ = self._dtls.handle_message(data, addr)
            if data is None:
                return
            self._dns_query_received(data, addr)

        def error_received(self, exc):      # pylint: disable=no-self-use
            self._dtls = None               # pragma: no cover
            raise exc                       # pragma: no cover

        def _send_response_to_requester(self, response, requester):
            self._dtls.write(response, requester)

        def close(self):
            if self.transport is not None:
                if self._dtls is not None:  # pragma: no cover
                    for session in self._dtls.sessions():
                        self._dtls.close(session)
                self.transport.close()
                self.transport = None

        def connection_lost(self, exc):     # pylint: disable=unused-argument
            self._dtls = None

    def _create_server_protocol(self, *args, **kwargs):
        try:
            config = Config()
            _ = config['dtls_credentials']['client_identity']
            _ = config['dtls_credentials']['psk']
        except KeyError as exc:
            raise RuntimeError(f"DTLS credential option {exc} not found") \
                from exc
        return self.DNSOverDTLSServer(self, *args, **kwargs)

    async def create_server(self, loop, *args, local_addr=None, **kwargs):
        if local_addr is None:
            local_addr = ('localhost', self.DODTLS_PORT)
        if local_addr[1] is None:
            local_addr = (local_addr[0], self.DODTLS_PORT)

        _, protocol = await loop.create_datagram_endpoint(
            self._create_server_protocol,
            *args, local_addr=local_addr, **kwargs,
        )
        return protocol
