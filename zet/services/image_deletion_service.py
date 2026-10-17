"""Confirmation of destructive image actions using recorded metadata only."""
import hashlib
import json


class ImageDeletionConfirmation(ValueError):
    def __init__(self, images):
        super().__init__("Confirm removal of these images and their recorded references.")
        self.images = images

    def detail(self):
        return {"code": "IMAGE_CONFIRMATION_REQUIRED", "message": str(self), "images": self.images}


def confirm_image_deletion(connection, asset_ids, confirm_ids=None, expected_versions=None):
    images = []
    for asset_id in sorted(set(asset_ids)):
        row = connection.execute("SELECT asset_id,label,checksum,file_name,status FROM assets WHERE asset_id=?", (asset_id,)).fetchone()
        if row is None:
            raise ValueError("An image was removed; review the deletion again.")
        version = hashlib.sha256(json.dumps([row[k] for k in ("asset_id", "checksum", "file_name", "status")]).encode()).hexdigest()
        usages = [dict(u) for u in connection.execute(
            "SELECT DISTINCT u.consumer_id,u.locator FROM asset_usages u LEFT JOIN logical_references lr "
            "ON lr.reference_key=u.reference_key WHERE u.status='current' AND "
            "(u.asset_id=? OR (u.asset_id IS NULL AND lr.asset_id=?)) ORDER BY u.consumer_id,u.locator",
            (asset_id, asset_id)).fetchall()]
        images.append({"id": asset_id, "label": row["label"] or row["file_name"], "version": version, "usages": usages})
    if (confirm_ids is None or set(confirm_ids) != {i["id"] for i in images}
            or any((expected_versions or {}).get(i["id"]) != i["version"] for i in images)):
        raise ImageDeletionConfirmation(images)
