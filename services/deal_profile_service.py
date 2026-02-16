import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from db.session import SessionLocal
from models import DealProfile


def get_latest_profile(project_id: int, schema_id: str, template_id: int | None = None) -> DealProfile | None:
    session = SessionLocal()
    try:
        query = session.query(DealProfile).filter(
            DealProfile.project_id == project_id,
            DealProfile.schema_id == schema_id,
        )
        if template_id is not None:
            query = query.filter(DealProfile.template_id == template_id)

        return query.order_by(DealProfile.updated_at.desc(), DealProfile.id.desc()).first()
    finally:
        session.close()


def save_profile(
    project_id: int,
    schema_id: str,
    template_id: int | None,
    inputs_raw: str | Mapping[str, Any],
    inputs_normalized: str | Mapping[str, Any],
) -> DealProfile:
    raw_json = inputs_raw if isinstance(inputs_raw, str) else json.dumps(dict(inputs_raw))
    normalized_json = inputs_normalized if isinstance(inputs_normalized, str) else json.dumps(dict(inputs_normalized))

    session = SessionLocal()
    try:
        now = datetime.utcnow()
        profile = DealProfile(
            project_id=project_id,
            template_id=template_id,
            schema_id=schema_id,
            inputs_raw_json=raw_json,
            inputs_normalized_json=normalized_json,
            created_at=now,
            updated_at=now,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
        session.expunge(profile)
        return profile
    finally:
        session.close()
