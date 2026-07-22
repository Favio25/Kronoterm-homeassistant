"""Shared authentication helpers for the Kronoterm cloud services."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

import aiohttp

from .const import REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)

AUTH_MODE_BASIC = "basic"
AUTH_MODE_WEB = "web"


def _login_url(base_url: str) -> str:
    """Return the web-login endpoint matching a Kronoterm API endpoint."""
    if "/dhws/" in base_url:
        return "https://cloud.kronoterm.com/dhws/?login=1"
    return "https://cloud.kronoterm.com/?login=1"


async def _async_handshake(
    session: aiohttp.ClientSession,
    *,
    base_url: str,
    menu_params: Mapping[str, str],
    headers: Mapping[str, str],
    auth: aiohttp.BasicAuth | None,
    attempts: int,
) -> bool:
    """Confirm that the session can read the menu endpoint."""
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

    for attempt in range(attempts):
        try:
            async with session.get(
                base_url,
                auth=auth,
                params=menu_params,
                headers=headers,
                timeout=timeout,
            ) as response:
                if response.status != 200:
                    continue
                payload: Any = await response.json(content_type=None)
                if isinstance(payload, dict) and payload.get("hp_id") is not None:
                    return True
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError) as err:
            _LOGGER.debug(
                "Kronoterm cloud handshake attempt %d/%d failed: %s",
                attempt + 1,
                attempts,
                type(err).__name__,
            )

        if attempt < attempts - 1:
            await asyncio.sleep(1.5 * (attempt + 1))

    return False


async def _async_web_login(
    session: aiohttp.ClientSession,
    *,
    base_url: str,
    username: str,
    password: str,
) -> bool:
    """Create a PHP web session; a later handshake validates the login."""
    login_url = _login_url(base_url)
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://cloud.kronoterm.com",
        "Referer": login_url,
        "User-Agent": "Mozilla/5.0",
    }

    try:
        async with session.post(
            login_url,
            data={"username": username, "password": password},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            allow_redirects=True,
        ) as response:
            return response.status in (200, 302)
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        _LOGGER.debug("Kronoterm web login failed: %s", type(err).__name__)
        return False


async def async_authenticate_cloud(
    session: aiohttp.ClientSession,
    *,
    base_url: str,
    menu_params: Mapping[str, str],
    basic_headers: Mapping[str, str],
    web_headers: Mapping[str, str],
    username: str,
    password: str,
    attempts: int = 1,
) -> str | None:
    """Authenticate and return the confirmed authentication mode.

    Basic authentication is attempted first for older cloud endpoints. If it
    fails, the browser-style PHP login is attempted and must be confirmed by a
    successful unauthenticated menu request using the resulting cookie.
    """
    auth = aiohttp.BasicAuth(username, password)
    if await _async_handshake(
        session,
        base_url=base_url,
        menu_params=menu_params,
        headers=basic_headers,
        auth=auth,
        attempts=attempts,
    ):
        return AUTH_MODE_BASIC

    if not await _async_web_login(
        session,
        base_url=base_url,
        username=username,
        password=password,
    ):
        return None

    if await _async_handshake(
        session,
        base_url=base_url,
        menu_params=menu_params,
        headers=web_headers,
        auth=None,
        attempts=attempts,
    ):
        return AUTH_MODE_WEB

    return None
