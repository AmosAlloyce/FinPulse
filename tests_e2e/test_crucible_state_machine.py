"""
Tests for Act 3: The DLQ Poison Packet Crucible State Machine.
Validates the full anomaly isolation, contract patch, DLQ replay, and reset lifecycle.
"""

from tests_e2e.locators import FinPulseLocators
from tests_e2e.pages.finpulse_page import FinPulsePage


def test_crucible_initial_state(driver, app_server):
    """Verify initial baseline state of the DLQ crucible before user interaction."""
    page = FinPulsePage(driver, app_server)
    page.open()

    assert page.get_crucible_badge_text() == "Pipeline: normal streaming"
    assert page.is_inject_button_enabled() is True
    assert page.is_patch_button_enabled() is False
    assert page.is_replay_button_enabled() is False

    console_text = page.get_crucible_console_text()
    assert "Kafka consumer listening on topic" in console_text
    assert "Spark micro-batch metric: 2,000 valid events processed" in console_text

    quarantine_classes = page.get_node_classes(FinPulseLocators.NODE_QUARANTINE)
    assert "quarantine-state" not in quarantine_classes
    assert "replayed-state" not in quarantine_classes


def test_crucible_poison_injection_transition(driver, app_server):
    """Verify state transitions when an intentional poison packet is injected."""
    page = FinPulsePage(driver, app_server)
    page.open()

    page.inject_poison_packet()

    assert "poison quarantined" in page.get_crucible_badge_text()
    assert page.is_inject_button_enabled() is False
    assert page.is_patch_button_enabled() is True
    assert page.is_replay_button_enabled() is False

    console_text = page.get_crucible_console_text()
    assert "Pydantic EventEnvelope schema rejected message" in console_text
    assert "s3://finpulse-lakehouse/quarantine/events/" in console_text

    quarantine_classes = page.get_node_classes(FinPulseLocators.NODE_QUARANTINE)
    assert "quarantine-state" in quarantine_classes


def test_crucible_end_to_end_replay_lifecycle(driver, app_server):
    """Verify full end-to-end recovery: Inject -> Patch Contract -> Replay DLQ Partition."""
    page = FinPulsePage(driver, app_server)
    page.open()

    # Step 1: Inject poison
    page.inject_poison_packet()
    assert "quarantine-state" in page.get_node_classes(FinPulseLocators.NODE_QUARANTINE)

    # Step 2: Patch contract schema
    page.apply_schema_patch()
    assert page.is_patch_button_enabled() is False
    assert page.is_replay_button_enabled() is True
    console_text_after_patch = page.get_crucible_console_text()
    assert "Patch applied: Contract corrected to schema_version='1.0'" in console_text_after_patch

    # Step 3: Replay DLQ partition
    page.replay_dlq_partition()
    assert "reconciled" in page.get_crucible_badge_text()
    assert page.is_replay_button_enabled() is False

    console_text_after_replay = page.get_crucible_console_text()
    assert "Writing repaired record to Silver layer" in console_text_after_replay
    assert "Gold marts refreshed" in console_text_after_replay

    silver_classes = page.get_node_classes(FinPulseLocators.NODE_SILVER)
    assert "replayed-state" in silver_classes


def test_crucible_reset_flow(driver, app_server):
    """Verify resetting the crucible returns all nodes, badges, and buttons to default."""
    page = FinPulsePage(driver, app_server)
    page.open()

    # Run through full recovery first
    page.inject_poison_packet()
    page.apply_schema_patch()
    page.replay_dlq_partition()

    # Now reset
    page.reset_crucible()

    assert page.get_crucible_badge_text() == "Pipeline: normal streaming"
    assert page.is_inject_button_enabled() is True
    assert page.is_patch_button_enabled() is False
    assert page.is_replay_button_enabled() is False

    quarantine_classes = page.get_node_classes(FinPulseLocators.NODE_QUARANTINE)
    silver_classes = page.get_node_classes(FinPulseLocators.NODE_SILVER)
    assert "quarantine-state" not in quarantine_classes
    assert "replayed-state" not in quarantine_classes
    assert "replayed-state" not in silver_classes
