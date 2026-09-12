import json
import logging

logger = logging.getLogger("know_your_project")
_FORBIDDEN = {
    "content",
    "source_content",
    "episode_body",
    "token",
    "password",
    "azdo_token",
}


def audit(event: str, **fields: object) -> None:
    bad = _FORBIDDEN.intersection(fields)
    if bad:
        raise ValueError(f"sensitive audit fields: {sorted(bad)}")
    logger.info(json.dumps({"event": event, **fields}, default=str, sort_keys=True))
