from radar_audit.normalizers import CRITERION_NORMALIZERS
from radar_audit.normalizers.shared import get_criterion
from radar_audit.taxonomy.seed import seed_taxonomy


def test_registry_has_exactly_the_twelve_tooled_criteria():
    assert len(CRITERION_NORMALIZERS) == 12


def test_registry_excludes_the_two_deferred_llm_judgment_criteria():
    assert (
        "Architecture & design",
        "Consistency of architectural style",
    ) not in CRITERION_NORMALIZERS
    assert ("Testing & reliability", "Test quality / relevance") not in CRITERION_NORMALIZERS


def test_every_registry_key_resolves_to_a_seeded_criterion(db_session):
    methodology_version = seed_taxonomy(db_session)

    for category_name, criterion_name in CRITERION_NORMALIZERS:
        criterion = get_criterion(db_session, methodology_version.id, category_name, criterion_name)
        assert criterion.name == criterion_name


def test_every_registry_value_is_callable():
    for normalizer in CRITERION_NORMALIZERS.values():
        assert callable(normalizer)
