import importlib
import json
import sys

import pytest

pytest.importorskip("sqlalchemy")


def test_save_and_get_latest_profile(tmp_path, monkeypatch):
    db_file = tmp_path / "deal_profiles.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")

    session_module = importlib.import_module("db.session")
    importlib.reload(session_module)

    session_module.Base.metadata.clear()
    sys.modules.pop("models", None)
    sys.modules.pop("models.entities", None)
    models_module = importlib.import_module("models.entities")

    init_db_module = importlib.import_module("db.init_db")
    importlib.reload(init_db_module)
    init_db_module.init_db()

    deal_profile_service = importlib.import_module("services.deal_profile_service")
    importlib.reload(deal_profile_service)

    session = session_module.SessionLocal()
    try:
        project = models_module.ProspectusProject(name="Deal Profile Project")
        session.add(project)
        session.flush()

        template = models_module.Template(
            name="Deal Profile Template",
            status="draft",
            sha256="a" * 64,
            file_path="storage/templates/deal_profile.docx",
        )
        session.add(template)
        session.commit()

        first = deal_profile_service.save_profile(
            project_id=project.id,
            schema_id="talabat_v1",
            template_id=template.id,
            inputs_raw={"issuer": {"name": "Issuer A"}},
            inputs_normalized={"issuer": {"name": "Issuer A"}},
        )
        second = deal_profile_service.save_profile(
            project_id=project.id,
            schema_id="talabat_v1",
            template_id=template.id,
            inputs_raw={"issuer": {"name": "Issuer B"}},
            inputs_normalized={"issuer": {"name": "Issuer B"}},
        )

        latest = deal_profile_service.get_latest_profile(project.id, "talabat_v1", template.id)

        assert first.id != second.id
        assert latest is not None
        assert latest.id == second.id
        assert json.loads(latest.inputs_raw_json)["issuer"]["name"] == "Issuer B"
    finally:
        session.close()
