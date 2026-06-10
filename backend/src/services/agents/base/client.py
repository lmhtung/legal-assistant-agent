""" BaseAgent - abstract interface for all agents. """
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from langchain_core.messages import BaseMessage

