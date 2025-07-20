# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021-23 Freie Universität Berlin
# Copyright (C) 2023-25 TU Dresden
#
# Distributed under terms of the MIT license.

"""DNS over DTLS serving side of the proxy."""

import abc
import asyncio
import logging
import time
import typing

from DTLSSocket import dtls  # type: ignore

from .config import Config
from .dns_server import BaseServerFactory, BaseDNSServer
from .dns_upstream import DNSUpstreamServerMixin


logger = logging.getLogger()


class BaseDTLSWrapper(abc.ABC):
    """An abstract wrapper for a DTLS implementation

    :param transport: The datagram transport the datagrams should be encrypted
                      and decrypted for.
    :type transport: :py:class:`asyncio.DatagramTransport`
    """

    def __init__(self, transport: asyncio.DatagramTransport):
        self.transport = transport

    @abc.abstractmethod
    def is_connected(self, addr: typing.Any) -> bool:
        """Check if a session with ``addr`` was established.

        :param addr: A remote endpoint (implementation-specific)
        :returns: ``True``, when a session with ``addr`` is established,
                  ``False`` if not.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def sessions(self) -> typing.Sequence:
        """Returns all currently established sessions.

        :returns: A sequence of (implementation-specific) remote endpoints with
                  which a session is established.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def connect(self, addr: typing.Any) -> typing.NoReturn:
        """Establish a session with ``addr``.

        :param addr: An (implementation-specific) remote endpoint
        """
        raise NotImplementedError

    @abc.abstractmethod
    def close(self, addr: typing.Any) -> typing.NoReturn:
        """Closes a session with ``addr``.

        :param addr: An (implementation-specific) remote endpoint
        """
        raise NotImplementedError

    @abc.abstractmethod
    def handle_message(
        self, msg: bytes, addr: typing.Any
    ) -> typing.Tuple[bytes, typing.Any, bool]:
        """Handles a DTLS message that came over the datagram transport.

        :param msg: An incoming DTLS message.
        :type msg: bytes
        :param addr: The remote endpoint as served by the datagram transport.
        :returns: A 3-tuple, containing

                  1. The unencrypted message,
                  2. The (implementation-specific) remote endpoint the
                     message was received from, an
                  3. A boolean, indicating if the last message established a
                     session with the remote endpoint.

                  If ``msg`` was a control message, the first and second
                  elements will be ``None``.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def write(self, msg: bytes, addr: typing.Any) -> typing.NoReturn:
        """Send a ``msg`` encrypted to ``addr``

        :param msg: The message to encrypt via DTLS.
        :type msg: bytes
        :param addr: An (implementation-specific) remote endpoint to send the
                     encrypted message to.
        """
        raise NotImplementedError


class TinyDTLSWrapper(BaseDTLSWrapper):
    """A wrapper for
    `tinydtls <https://projects.eclipse.org/projects/iot.tinydtls>`_.
    """

    EVENT_CONNECTED = 0x1DE
    _CT_HANDSHAKE = 22
    _HT_SERVER_HELLO_DONE = 14
    LOG_LEVEL = {
        # pylint: disable=c-extension-no-member
        logging.DEBUG: dtls.DTLS_LOG_DEBUG,
        logging.INFO: dtls.DTLS_LOG_INFO,
        logging.WARNING: dtls.DTLS_LOG_WARN,
        logging.ERROR: dtls.DTLS_LOG_CRIT,
        logging.CRITICAL: dtls.DTLS_LOG_EMERG,
    }

    def __init__(self, transport):
        super().__init__(transport)
        # pylint: disable=c-extension-no-member
        credentials = Config()["dtls_credentials"]
        client_identity = credentials["client_identity"].encode()
        psk = credentials["psk"].encode()
        self._dtls = dtls.DTLS(
            read=self._read,
            write=self._write,
            event=self._event,
            pskId=client_identity,
            pskStore={client_identity: psk},
        )
        dtls.setLogLevel(self.LOG_LEVEL[logger.level])
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
        if (
            len(data) > 13
            and data[0] == self._CT_HANDSHAKE
            and data[13] == self._HT_SERVER_HELLO_DONE
        ):
            delay = Config().get("dtls", {}).get("server_hello_done_delay")

            if delay:
                # Delay Server Hello Done for a bit
                time.sleep(delay)
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
        connection = self._dtls.connect(*addr)
        if connection:
            self._active_sessions[addr] = connection

    def close(self, addr):
        if self.is_connected(addr):
            self._dtls.close(self._active_sessions[addr])
            del self._active_sessions[addr]

    def handle_message(self, msg, addr):
        connected = False
        if isinstance(addr, tuple):
            ret = self._dtls.handleMessageAddr(addr[0], addr[1], msg)
        elif isinstance(addr, dtls.Session):  # pylint: disable=I1101
            ret = self._dtls.handleMessage(addr, msg)
            addr = addr.addr, addr.port, addr.flowinfo, addr.scope_id
        else:
            raise ValueError(f"Unexpected session type {type(addr)}")
        if ret < 0:
            logger.warning("Unable to handle incoming DTLS message from %s", addr)
            return None, None, connected
        if self._last_event == self.EVENT_CONNECTED and not self.is_connected(addr):
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

    def write(self, msg, addr):
        if isinstance(addr, tuple):
            if not self.is_connected(addr):
                logger.warning("%s does not have an active session", addr)
                return
            addr = self._active_sessions[addr]
        self._dtls.write(addr, msg)


class DNSOverDTLSServerFactory(BaseServerFactory):
    """Factory to create DNS over DLTS servers"""

    # pylint: disable=too-few-public-methods
    DODTLS_PORT = 853
    dtls_class = TinyDTLSWrapper

    class DNSOverDTLSServer(BaseDNSServer, DNSUpstreamServerMixin):
        """DNS over DTLS server implementation.

        :param factory: The factory that created the DNS over DTLS server.
        :type factory: :py:class:`DNSOverDTLSServerFactory`
        """

        def __init__(self, factory):
            super().__init__(dns_upstream=factory.dns_upstream)
            self.factory = factory
            self.transport = None
            self._dtls = None

        def __del__(self):
            del self._dtls
            self._dtls = None

        def connection_made(self, transport):
            # pylint: disable=line-too-long
            """See `connection_made()`_

            .. _`connection_made()`: https://docs.python.org/3/library/asyncio-protocol.html#asyncio.BaseProtocol.connection_made
            """  # noqa: E501
            self.transport = transport
            self._dtls = self.factory.dtls_class(self.transport)

        def datagram_received(self, data, addr):
            # pylint: disable=line-too-long
            """See `datagram_received()`_

            .. _`datagram_received()`: https://docs.python.org/3/library/asyncio-protocol.html#asyncio.DatagramProtocol.datagram_received
            """  # noqa: E501
            data, addr, _ = self._dtls.handle_message(data, addr)
            if data is None:
                return
            self.dns_query_received(data, addr)

        def error_received(self, exc):
            # pylint: disable=line-too-long
            """See `error_received()`_

            .. _`error_received()`: https://docs.python.org/3/library/asyncio-protocol.html#asyncio.DatagramProtocol.error_received
            """  # noqa: E501
            self._dtls = None  # pragma: no cover
            raise exc  # pragma: no cover

        def send_response_to_requester(self, response, requester):
            self._dtls.write(response, requester)

        async def close(self):
            if self.transport is not None:
                if self._dtls is not None:  # pragma: no cover
                    for session in self._dtls.sessions():
                        self._dtls.close(session)
                self.transport.close()
                self.transport = None

        def connection_lost(self, exc):  # pylint: disable=unused-argument
            # pylint: disable=line-too-long
            """See `connection_lost()`_

            .. _`connection_lost()`: https://docs.python.org/3/library/asyncio-protocol.html#asyncio.BaseProtocol.connection_lost
            """  # noqa: E501
            self._dtls = None

    def _create_server_protocol(self, *args, **kwargs):
        try:
            config = Config()
            _ = config["dtls_credentials"]["client_identity"]
            _ = config["dtls_credentials"]["psk"]
        except KeyError as exc:
            raise RuntimeError(f"DTLS credential option {exc} not found") from exc
        return self.DNSOverDTLSServer(self, *args, **kwargs)

    async def create_server(self, loop, *args, local_addr=None, **kwargs):
        """Creates an :py:class:`DNSOverDTLSServer` object.

        :param loop: the asyncio event loop the server should run in
        :type loop: :py:class:`asyncio.AbstractEventLoop`
        :param local_addr: A tuple for the created server to bind to. The first
                           element is the host part, the second element the
                           port.
        :type local_addr: :py:class:`typing.Tuple[str, int]`

        :returns: An :py:class:`DNSOverDTLSServer` object representing an
                  DNS over DTLS server.
        :rtype: :py:class:`DNSOverDTLSServer`
        """
        if local_addr is None:
            local_addr = ("localhost", self.DODTLS_PORT)
        if local_addr[1] is None:
            local_addr = (local_addr[0], self.DODTLS_PORT)

        _, protocol = await loop.create_datagram_endpoint(
            self._create_server_protocol,
            *args,
            local_addr=local_addr,
            **kwargs,
        )
        return protocol
