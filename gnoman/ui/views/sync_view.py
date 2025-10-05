"""Placeholder view for sync view."""

from __future__ import annotations


class View:
    def render(self) -> None:
        raise NotImplementedError('Dashboard view rendering is not yet implemented')


__all__ = ['View']
