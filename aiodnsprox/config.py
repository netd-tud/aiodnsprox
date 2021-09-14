# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

import typing


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

    def __contains__(self, key: str) -> bool:
        return key in self._sections

    def __getitem__(self, key: str) -> typing.Mapping:
        return self._sections[key]

    def get(self, key: str, default=None) -> typing.Mapping:
        return self._sections.get(key, default)

    def add_config(self, config: typing.Mapping) -> None:
        self._sections.update(config)
