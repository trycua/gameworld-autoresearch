"""Journaled, supervised public-image import with a retained campaign reservation."""

import asyncio
import json
from pathlib import Path
import re
import time

from fps_bench.campaign_ledger import LedgerConflict
from fps_bench.evaluation_contract import canonical, digest
from fps_bench.modal_scope import inspect_app_scope, validate_app_scope


RESERVATION_MICRO_USD = 25_000_000


class ModalImageBackend:
    async def scope(self, scope):
        return await inspect_app_scope(scope["workspace"], scope["environment"], scope["app"])

    async def build(self, image_ref, scope):
        import modal
        app = await modal.App.lookup.aio(scope["app"], environment_name=scope["environment"], create_if_missing=False)
        if app.app_id != scope["app_id"]:
            raise ValueError("App changed immediately before image import")
        image = modal.Image.from_registry(image_ref)
        with modal.enable_output():
            await image.build.aio(app)
        return image.object_id


class TrainingImageImport:
    def __init__(self, ledger, backend=None):
        self.ledger = ledger
        self.backend = backend or ModalImageBackend()
        with ledger.transaction() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS training_image_imports "
                               "(id TEXT PRIMARY KEY, specification TEXT NOT NULL, state TEXT NOT NULL, "
                               "image_id TEXT, error_type TEXT)")

    async def run(self, scope, manifest_path, expected_hash):
        data = Path(manifest_path).read_bytes()
        if len(data) > 1_000_000 or digest(data) != expected_hash:
            raise ValueError("Training image provenance differs from the trusted CI artifact hash")
        manifest = json.loads(data)
        image_ref = manifest.get("image", "")
        if (not re.fullmatch(r"ghcr\.io/trycua/gameworld-autoresearch@sha256:[0-9a-f]{64}", image_ref)
                or not re.fullmatch(r"[0-9a-f]{40}", manifest.get("source_revision", ""))
                or manifest.get("schema_version") != 1 or scope.get("isolation_policy") != "app-scoped"):
            raise ValueError("Expected pinned CI training image and explicit app scope")
        validate_app_scope(await asyncio.wait_for(self.backend.scope(scope), 30), scope)
        specification = {"scope": scope, "image": image_ref, "provenance_sha256": expected_hash,
                         "source_revision": manifest["source_revision"], "client_timeout_seconds": 900,
                         "reservation_micro_usd": RESERVATION_MICRO_USD,
                         "all_in_maximum_verified": False}
        identity = "image-import:" + digest(canonical(specification))
        encoded = canonical(specification).decode()
        with self.ledger.transaction() as connection:
            existing = connection.execute("SELECT * FROM training_image_imports WHERE id=?", (identity,)).fetchone()
            if existing:
                if existing["state"] == "complete":
                    return {"import_id": identity, "image_id": existing["image_id"], "specification": specification,
                            "billing_reconciled": False}
                raise LedgerConflict("Import already attempted; reconcile it, never repeat an ambiguous build")
            if connection.execute("SELECT 1 FROM training_image_imports WHERE state!='complete'").fetchone():
                raise LedgerConflict("Another image import is unresolved")
            self.ledger._reserve_in_transaction(connection, identity, "modal_micro_usd", RESERVATION_MICRO_USD,
                                                int(time.time()) + 3600)
            connection.execute("INSERT INTO training_image_imports VALUES (?,?,'submitted',NULL,NULL)", (identity, encoded))
            self.ledger._event(connection, "image_import_submitted", {"id": identity, "specification": specification})
        try:
            image_id = await asyncio.wait_for(self.backend.build(image_ref, scope), 900)
            if not isinstance(image_id, str) or not re.fullmatch(r"im-[A-Za-z0-9]+", image_id):
                raise ValueError("Invalid returned Modal image identity")
        except BaseException as error:
            with self.ledger.transaction() as connection:
                connection.execute("UPDATE training_image_imports SET state='unknown',error_type=? WHERE id=?",
                                   (type(error).__name__, identity))
                self.ledger._event(connection, "image_import_unresolved", {"id": identity, "error_type": type(error).__name__})
            raise
        with self.ledger.transaction() as connection:
            connection.execute("UPDATE training_image_imports SET state='complete',image_id=? WHERE id=?", (image_id, identity))
            self.ledger._event(connection, "image_import_completed", {"id": identity, "image_id": image_id})
        return {"import_id": identity, "image_id": image_id, "specification": specification, "billing_reconciled": False}
