from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from radar_core.enums import ScoringModel
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from sqlmodel import Session, select

TAXONOMY_PATH = Path(__file__).parent / "quality_framework_v1_0.yaml"


def seed_taxonomy(session: Session, yaml_path: Path = TAXONOMY_PATH) -> MethodologyVersion:
    """Seed a MethodologyVersion + its Categories/Criteria from `yaml_path`, once.

    If a MethodologyVersion with the same version_label already exists, it is
    returned as-is and nothing is re-inserted.
    """
    data: dict[str, Any] = yaml.safe_load(yaml_path.read_text())
    version_label = data["version_label"]

    existing = session.exec(
        select(MethodologyVersion).where(MethodologyVersion.version_label == version_label)
    ).first()
    if existing is not None:
        return existing

    methodology_version = MethodologyVersion(version_label=version_label, notes=data.get("notes"))
    session.add(methodology_version)
    session.flush()

    for category_data in data["categories"]:
        category = Category(
            methodology_version_id=methodology_version.id,
            name=category_data["name"],
            weight=category_data["weight"],
            order=category_data["order"],
        )
        session.add(category)
        session.flush()

        for criterion_data in category_data["criteria"]:
            criterion = Criterion(
                category_id=category.id,
                name=criterion_data["name"],
                description=criterion_data["description"],
                weight=criterion_data["weight"],
                scoring_model=ScoringModel(criterion_data["scoring_model"]),
            )
            session.add(criterion)

    session.commit()
    session.refresh(methodology_version)
    return methodology_version
