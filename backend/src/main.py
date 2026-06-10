""" Fast API application entry point. """
import os 
from fastapi import FastAPI
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from config import get_settings
