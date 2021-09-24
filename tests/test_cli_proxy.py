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
async def servers():
    yield proxy.servers
    await proxy.close_servers()


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
    'argv, mock_upstream, exp_transports, exp_credentials',
    [
        ([sys.argv[0], '-U', '9.9.9.9', '-u'], False, 1, None),
        ([sys.argv[0], '-U', '9.9.9.9', '-u', 'localhost'], False, 1, None),
        ([sys.argv[0], '-U', '9.9.9.9', '-u', 'localhost', '5353'], False, 1,
         None),
        ([sys.argv[0], '-U', '9.9.9.9', '53', '-u'], False, 1, None),
        ([sys.argv[0], '-U', 'tcp', '9.9.9.9', '53', '-u'], False, 1, None),
        ([sys.argv[0], '-U', '9.9.9.9', '-u', '-d'], False, 0, None),
        ([sys.argv[0], '-U', '9.9.9.9', '-u', '-c'], False, 0, None),
        (
            [sys.argv[0], '-U', '9.9.9.9', '-u', '-d',
             '--dtls-credentials', 'client_identifier', 'secretPSK'], False, 2,
            {
                'client_identity': 'client_identifier',
                'psk': 'secretPSK',
            }),
        (
            [sys.argv[0], '-U', '9.9.9.9', '-u', '-d', '-c',
             '--dtls-credentials', 'client_identifier', 'secretPSK'], False, 3,
            {
                'client_identity': 'client_identifier',
                'psk': 'secretPSK',
            }),
        ([sys.argv[0], '-U', '9.9.9.9', '-u', '-C', 'test.yaml'], False, 1,
          None),
        (
            [sys.argv[0], '-U', '9.9.9.9', '-u', '-d',
             '--dtls-credentials', 'client_identifier', 'secretPSK'], False, 2,
            {
                'client_identity': 'client_identifier',
                'psk': 'secretPSK',
            }),
        (
            [sys.argv[0], '-U', '9.9.9.9', '-u', '-c',
             '--dtls-credentials', 'client_identifier', 'secretPSK'], False, 2,
            {
                'client_identity': 'client_identifier',
                'psk': 'secretPSK',
            }),
        ([sys.argv[0], '-U', '9.9.9.9', '-u', '-C', 'test.yaml'], True, 1,
         None),
        ([sys.argv[0], '-U', '9.9.9.9', '-u', '-C', 'test.yaml'], True, 1,
         None),
    ]
)
async def test_sync_main__success(monkeypatch, mocker, servers, config, argv,
                                  mock_upstream,
                                  exp_transports, exp_credentials):
    monkeypatch.setattr(sys, 'argv', argv)
    assert not mock_upstream or '-C' in argv
    if '-C' in argv:
        if mock_upstream:
            mocker.patch('argparse.open',
                         mocker.mock_open(read_data="""
test: foobar
mock_dns_upstream: {}"""))
        else:
            mocker.patch('argparse.open',
                         mocker.mock_open(read_data="test: foobar"))
    # override default ports so we can run tests as non-root
    monkeypatch.setattr(proxy.HostPortAction, 'DEFAULT_PORTS', {
        'dtls': 5853,
        'udp': 5353,
        'coap': None,
    })
    if ('-c' in argv or '-d' in argv) and '--dtls-credentials' not in argv:
        with pytest.raises(RuntimeError):
            await proxy.main()
    else:
        await proxy.main()
        assert len(config['transports']) == exp_transports
        assert config.get('dtls_credentials') == exp_credentials
        assert len(servers) == exp_transports
        if '-C' in argv:
            assert config['test'] == 'foobar'
