"""Appels à Claude avec sortie JSON garantie, cache disque et suivi des coûts."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Callable

import anthropic

from .config import AppConfig

# Tarifs Claude Opus 5.5 ($ par million de tokens) pour l'estimation affichée.
PRICE_IN, PRICE_OUT, PRICE_CACHE_READ, PRICE_CACHE_WRITE = 4.0, 20.0, 0.20, 5.0


# Nature de l'erreur, pour décider quoi faire : redécouper la requête (tronque, json, refus) ou
# s'arrêter et reprendre plus tard (auth, limite, reseau, api).
LLM_ERROR_KINDS = ("tronque", "refus", "json", "auth", "limite", "reseau", "api")


class LLMError(RuntimeError):
    def __init__(self, message: str = "", kind: str = "api"):
        super().__init__(message)
        self.kind = kind if kind in LLM_ERROR_KINDS else "api"


def claude_available(cfg: AppConfig) -> bool:
    return bool(cfg.api_key() or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


class LLM:
    def __init__(self, cfg: AppConfig, cache_dir: Path | None = None, log: Callable[[str], None] | None = None):
        self.cfg = cfg
        self.client = anthropic.Anthropic(api_key=cfg.api_key() or None, max_retries=4, timeout=900)
        self.cache_dir = cache_dir
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)
        self.log = log or (lambda _msg: None)
        self._lock = threading.Lock()
        self.usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "calls": 0}

    def cost(self) -> float:
        u = self.usage
        return (
            u["input"] * PRICE_IN
            + u["output"] * PRICE_OUT
            + u["cache_read"] * PRICE_CACHE_READ
            + u["cache_write"] * PRICE_CACHE_WRITE
        ) / 1e6

    def ask_json(
        self,
        *,
        system: str,
        content: str | list,
        schema: dict,
        effort: str = "medium",
        max_tokens: int = 64000,
        label: str = "claude",
    ) -> dict:
        """Envoie une requête et renvoie le JSON (validé par le schéma côté API)."""
        key_material = json.dumps(
            [self.cfg.model, system, content, schema, effort], ensure_ascii=False, sort_keys=True
        )
        digest = hashlib.sha256(key_material.encode("utf-8")).hexdigest()[:24]
        cache_file = self.cache_dir / f"{label}_{digest}.json" if self.cache_dir else None
        if cache_file and cache_file.exists():
            return json.loads(cache_file.read_text("utf-8"))

        params = {
            "model": self.cfg.model,
            "max_tokens": max_tokens,
            # Le prompt système (chaîne, style, bibliothèque) est identique d'un appel à
            # l'autre : il est mis en cache côté API, les appels suivants coûtent ~10 fois moins.
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": content}],
            "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        }
        message = self._stream(params, use_fallbacks=self.cfg.use_fallbacks)
        # Compté même si la réponse est inutilisable (refus, tronquée) : ces tokens sont facturés.
        self._account(message, label)

        if message.stop_reason == "refusal":
            details = getattr(message, "stop_details", None)
            raise LLMError(f"Claude a refusé la requête ({label}) : {getattr(details, 'explanation', '')}", kind="refus")
        if message.stop_reason == "max_tokens":
            raise LLMError(f"Réponse tronquée ({label}) : augmenter max_tokens ou réduire le lot.", kind="tronque")
        text = "".join(block.text for block in message.content if block.type == "text")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Réponse JSON illisible ({label}) : {exc}", kind="json") from exc

        if cache_file:
            cache_file.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        return data

    def _stream(self, params: dict, use_fallbacks: bool):
        request = dict(params)
        if use_fallbacks:
            # Si un filtre de sécurité refuse (faux positif), l'API relance sur un autre modèle.
            request["betas"] = ["server-side-fallback-2026-07-01"]
            request["fallbacks"] = "default"
        try:
            with self.client.beta.messages.stream(**request) as stream:
                return stream.get_final_message()
        except anthropic.AuthenticationError as exc:
            raise LLMError("Clé API Anthropic invalide : vérifie-la dans les réglages.", kind="auth") from exc
        except anthropic.PermissionDeniedError as exc:
            raise LLMError(f"Accès refusé par l'API Anthropic : {exc.message}", kind="auth") from exc
        except anthropic.BadRequestError as exc:
            if use_fallbacks:
                self.log(f"Requête refusée avec les fallbacks ({exc.message}) : nouvel essai sans.")
                return self._stream(params, use_fallbacks=False)
            raise LLMError(f"Requête invalide : {exc.message}", kind="api") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("Limite de débit de l'API atteinte : réessaie dans quelques minutes.", kind="limite") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Erreur de l'API Anthropic ({exc.status_code}) : {exc.message}", kind="api") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("Impossible de joindre l'API Anthropic : vérifie la connexion internet.", kind="reseau") from exc

    def _account(self, message, label: str) -> None:
        u = message.usage
        with self._lock:
            self.usage["calls"] += 1
            self.usage["input"] += u.input_tokens or 0
            self.usage["output"] += u.output_tokens or 0
            self.usage["cache_read"] += getattr(u, "cache_read_input_tokens", 0) or 0
            self.usage["cache_write"] += getattr(u, "cache_creation_input_tokens", 0) or 0
        self.log(
            f"Claude [{label}] : {u.input_tokens} tokens lus, {u.output_tokens} écrits "
            f"(cache {getattr(u, 'cache_read_input_tokens', 0) or 0}) — total ≈ {self.cost():.2f} $"
        )


# ------------------------------------------------------------ helpers de schéma
def obj(properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required if required is not None else list(properties),
        "additionalProperties": False,
    }


def arr(items: dict) -> dict:
    return {"type": "array", "items": items}


def enum(*values: str) -> dict:
    return {"type": "string", "enum": list(values)}


STR = {"type": "string"}
INT = {"type": "integer"}
NUM = {"type": "number"}
BOOL = {"type": "boolean"}
