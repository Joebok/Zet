"""Shared backdrop linking policy; historical snapshots default to reference."""
def backdrop_reference(detail):
    return (detail.get("kind") == "backdrop" and detail.get("source_snapshot", {}).get("image_file")
            and detail.get("backdrop_link_mode", "reference") == "reference")
