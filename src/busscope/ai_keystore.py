"""OS keyring adapter for provider API keys (Secret Service on Linux, issue #83)."""

from __future__ import annotations

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from busscope.ai_assistant import ProviderError

_SERVICE = "busscope-ai"


class KeyringKeyStore:
    """Store keys only in the OS keyring; failures surface without the key in them."""

    def get(self, provider_id: str) -> str | None:
        """Return the stored key, or None when absent."""
        try:
            return keyring.get_password(_SERVICE, provider_id)
        except KeyringError as error:
            raise ProviderError(f"OS keyring unavailable: {type(error).__name__}") from None

    def set(self, provider_id: str, key: str) -> None:
        """Store or replace the key."""
        try:
            keyring.set_password(_SERVICE, provider_id, key)
        except KeyringError as error:
            raise ProviderError(f"Cannot store the key: {type(error).__name__}") from None

    def delete(self, provider_id: str) -> None:
        """Forget the key; absent keys are not an error."""
        try:
            keyring.delete_password(_SERVICE, provider_id)
        except PasswordDeleteError:
            return
        except KeyringError as error:
            raise ProviderError(f"Cannot delete the key: {type(error).__name__}") from None
