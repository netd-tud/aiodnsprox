# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

import argparse
import pprint
import typing
import yaml


class Singleton(type):  # see https://stackoverflow.com/q/6760685
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args,
                                                                 **kwargs)
        return cls._instances[cls]


class Config(metaclass=Singleton):
    def __init__(self):
        self._sections = {}

    def __str__(self):
        return pprint.pformat(self._sections)

    def __repr__(self):
        return f'<{type(self).__name__}: {self._sections}>'

    def __len__(self):
        return len(self._sections)

    def __contains__(self, key: str) -> bool:
        return key in self._sections

    def __getitem__(self, key: str) -> typing.Mapping:
        return self._sections[key]

    def get(self, key: str, default=None) -> typing.Mapping:
        return self._sections.get(key, default)

    def add_config(self, config: typing.Mapping) -> None:
        self._sections.update(config)

    def add_yaml_config(self, yaml_file) -> None:
        self.add_config(yaml.load(yaml_file, yaml.loader.FullLoader))

    def add_args_config(self, args) -> None:
        self.add_config({k: vars(v)
                         if isinstance(v, argparse.Namespace) else v
                         for k, v in vars(args).items() if v is not None})
