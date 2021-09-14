#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

import argparse
import io
import pprint

import pytest

from aiodnsprox.config import Config

from .fixtures import config


def test_config__empty(config):
    assert not config
    assert 'test' not in config
    with pytest.raises(KeyError):
        assert config['test']
    assert config.get('test') is None
    assert config.get('test', 'foobar') == 'foobar'
    assert str(config) == '{}'
    assert repr(config) == '<Config: {}>'


def test_config__add_config(config):
    conf2 = Config()        # also test singleton/borg behavior here
    assert not config
    assert not conf2
    assert 'test' not in config
    assert 'test' not in conf2
    config.add_config({'test': 'foobar'})
    assert 'test' in config
    assert 'test' in conf2
    assert config['test'] == 'foobar'
    assert conf2['test'] == 'foobar'
    assert config.get('test') == 'foobar'
    assert conf2.get('test') == 'foobar'
    assert str(config) == pprint.pformat({'test': 'foobar'})
    assert str(conf2) == pprint.pformat({'test': 'foobar'})


def test_config__add_yaml_config(config):
    yaml_file = io.StringIO("test: foobar\n")
    config.add_yaml_config(yaml_file)
    assert config['test'] == 'foobar'


def test_config__add_args_config(config):
    args = argparse.Namespace(test='foobar',
                              a_namespace=argparse.Namespace(snafu=42),
                              nothing=None)
    config.add_args_config(args)
    assert config['test'] == 'foobar'
    assert config['a_namespace'] == {'snafu': 42}
    assert 'nothing' not in config
