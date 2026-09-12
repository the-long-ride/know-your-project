from uuid import NAMESPACE_URL, uuid5


def entity_uuid(project: str, canonical_name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"kyp:{project}:entity:{canonical_name.strip().casefold()}"))
