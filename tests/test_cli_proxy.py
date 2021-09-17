#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

import sys

import pytest

from aiodnsprox.cli import proxy

from .fixtures import config


@pytest.fixture
def servers():
    yield proxy.servers
    proxy.close_servers()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'argv',
    [[sys.argv[0], '-u'], [sys.argv[0], '-U', 'localhost']]
)
async def test_sync_main__runtime_error(monkeypatch, servers, config, argv):
    monkeypatch.setattr(sys, 'argv', argv)
    with pytest.raises(RuntimeError):
        await proxy.main()
    assert not servers


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'argv',
    [
        [sys.argv[0], '-U', '9.9.9.9', '-u', 'localhost', '53', 'more'],
        [sys.argv[0], '-U', 'udp', '9.9.9.9', '53', 'more', '-u'],
    ]
)
async def test_sync_main__value_error(monkeypatch, servers, config, argv):
    monkeypatch.setattr(sys, 'argv', argv)
    with pytest.raises(ValueError):
        await proxy.main()
    assert not config
    assert not servers


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'argv, exp_transports, exp_credentials',
    [
        ([sys.argv[0], '-U', '9.9.9.9', '-u'], 1, None),
        ([sys.argv[0], '-U', '9.9.9.9', '-u', 'localhost'], 1, None),
        ([sys.argv[0], '-U', '9.9.9.9', '-u', 'localhost', '5353'], 1, None),
        ([sys.argv[0], '-U', '9.9.9.9', '53', '-u'], 1, None),
        ([sys.argv[0], '-U', 'tcp', '9.9.9.9', '53', '-u'], 1, None),
        ([sys.argv[0], '-U', '9.9.9.9', '-u', '-d'], 2, None),
        ([sys.argv[0], '-U', '9.9.9.9', '-u', '-c', 'test.yaml'], 1, None),
        (
            [sys.argv[0], '-U', '9.9.9.9', '-u', '-d',
             '-C', 'client_identifier', 'secretPSK'], 2,
            {
                'client_identity': 'client_identifier',
                'psk': 'secretPSK',
            }),
    ]
)
async def test_sync_main__success(monkeypatch, mocker, servers, config, argv,
                                  exp_transports, exp_credentials):
    monkeypatch.setattr(sys, 'argv', argv)
    if '-c' in argv:
        mocker.patch('argparse.open',
                     mocker.mock_open(read_data="test: foobar"))
    # override default ports so we can run tests as non-root
    monkeypatch.setattr(proxy.HostPortAction, 'DEFAULT_PORTS', {
        'dtls': 5853,
        'udp': 5353,
    })
    if '-d' in argv and '-C' not in argv:
        with pytest.raises(RuntimeError):
            await proxy.main()
    else:
        await proxy.main()
        assert len(config['transports']) == exp_transports
        assert config.get('dtls_credentials') == exp_credentials
        assert len(servers) == exp_transports
        if '-c' in argv:
            assert config['test'] == 'foobar'
