from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
WORKSPACE = (ROOT / "app/static/workspace.js").read_text(encoding="utf-8")
NOTIFICATIONS = (ROOT / "app/static/notifications.js").read_text(encoding="utf-8")
SERVICE_WORKER = (ROOT / "app/static/service-worker.js").read_text(encoding="utf-8")
REPOSITORY = (ROOT / "app/repository.py").read_text(encoding="utf-8")


class MonitorContractTests(unittest.TestCase):
    def test_monitor_is_a_compact_routed_workspace(self) -> None:
        self.assertIn("EDGE Intel · Group Radar", HTML)
        self.assertIn("<strong>EDGE Intel</strong>", HTML)
        self.assertIn("/static/edge-intel-radar-icon-192.png", HTML)
        self.assertIn('class="workspace-sidebar"', HTML)
        self.assertIn('class="workspace-header"', HTML)
        self.assertIn('data-route-panel="overview"', HTML)
        self.assertIn('data-route-panel="watchlists"', HTML)
        self.assertNotIn("Views", HTML)
        self.assertNotIn("masthead-descriptor", HTML)

    def test_event_history_supports_symbol_and_type_search(self) -> None:
        self.assertIn('id="eventSymbolSearch"', HTML)
        self.assertIn('placeholder="Search symbol…"', HTML)
        self.assertIn('id="eventTypeFilter"', HTML)
        self.assertIn('String(event.symbol || "").toUpperCase().includes(symbolQuery)', WORKSPACE)
        self.assertIn('addEventListener("input", renderEvents)', WORKSPACE)
        self.assertNotIn('value="historical-pressure">Historical Pressure', HTML)
        self.assertNotIn('filter === "historical-pressure"', WORKSPACE)
        self.assertIn("!RETIRED_PRESSURE_EVENT_TYPES.has(event.event_type)", WORKSPACE)
        self.assertIn("Operational MRZ activations, migrations, and near-miss events.", HTML)

    def test_pressure_is_absent_from_the_operator_interface(self) -> None:
        self.assertNotIn('data-route-panel="pressure-history"', HTML)
        self.assertNotIn("Historical Pressure records", HTML)
        self.assertNotIn('/api/mrz/pressure-history?limit=500', WORKSPACE)
        self.assertNotIn('href="/mrz/pressure-history"', HTML)

    def test_removed_pressure_checkbox_is_cache_safe(self) -> None:
        self.assertNotIn('id="prefPressure"', HTML)
        self.assertNotIn('$("#prefPressure").checked', WORKSPACE)
        self.assertIn('if (activation) activation.checked', WORKSPACE)
        self.assertIn('if (migration) migration.checked', WORKSPACE)
        self.assertIn('if (nearMiss) nearMiss.checked', WORKSPACE)
        self.assertIn("mobile-navigation-20261114", HTML)

    def test_notification_inbox_remains_durable_and_distinct(self) -> None:
        self.assertIn('id="notificationInboxButton"', HTML)
        self.assertIn('id="notificationInboxDialog"', HTML)
        self.assertIn('id="notificationInboxList" aria-live="polite"', HTML)
        self.assertIn('/api/notifications/inbox?limit=50', NOTIFICATIONS)
        self.assertIn('/api/notifications/inbox/${notificationId}/read', NOTIFICATIONS)
        self.assertIn('/api/notifications/inbox/${notificationId}/dismiss', NOTIFICATIONS)
        self.assertIn('/api/notifications/inbox/mark-all-read', NOTIFICATIONS)
        self.assertIn('/api/notifications/inbox/clear', NOTIFICATIONS)
        self.assertIn('id="notificationMarkAllRead"', HTML)
        self.assertIn('id="notificationClearInbox"', HTML)
        self.assertNotIn("Clear all read", HTML)
        self.assertIn("Clear Notification Inbox?", NOTIFICATIONS)
        self.assertIn("Canonical EDGE events and history are retained.", NOTIFICATIONS)
        self.assertIn('item.is_read ? "" : " unread"', NOTIFICATIONS)

    def test_system_push_click_marks_canonical_inbox_identity_read(self) -> None:
        self.assertIn('payload.source_event_key', SERVICE_WORKER)
        self.assertIn('/api/notifications/inbox/read-by-source', SERVICE_WORKER)
        self.assertIn('self.clients.openWindow(targetUrl)', SERVICE_WORKER)

    def test_board_uses_canonical_authority_activation_and_pressure(self) -> None:
        for key in (
            '"activated_at": iso(anchor["activated_at"])',
            '"core_mrz_lower": number(anchor["core_mrz_lower"])',
            '"core_mrz_upper": number(anchor["core_mrz_upper"])',
            '"structural_location": anchor["structural_location"]',
        ):
            self.assertIn(key, REPOSITORY)
        self.assertIn("pressureBySymbol()", WORKSPACE)
        self.assertIn("currentAuthorityRow", WORKSPACE)
        self.assertIn("relativeTime(item.activatedAt)", WORKSPACE)

    def test_current_and_previous_authority_are_available_in_symbols(self) -> None:
        self.assertIn('id="detailRange"', HTML)
        self.assertIn('id="detailPrevious"', HTML)
        self.assertNotIn('id="detailLatestEvent"', HTML)
        self.assertNotIn('id="detailPressure"', HTML)
        self.assertNotIn('id="detailPressureEvidence"', HTML)
        self.assertNotIn('id="detailPressureTimeline"', HTML)
        self.assertNotIn("Pressure Timeline", HTML)
        self.assertIn("Open Events History", HTML)
        self.assertNotIn('$("#detailPressure")', WORKSPACE)
        self.assertIn("detail.migration?.has_migrated", WORKSPACE)
        self.assertIn("/api/symbols/${encodeURIComponent(symbol)}", WORKSPACE)

    def test_standalone_pressure_is_removed_and_location_distribution_remains(self) -> None:
        self.assertNotIn('data-route-panel="pressure"', HTML)
        self.assertNotIn("PRESSURE MAP", HTML)
        distribution = HTML.split('data-route-panel="location-distribution"', 1)[1].split(
            'data-route-panel="events"', 1
        )[0]
        self.assertIn("Location Distribution", distribution)
        self.assertIn('id="locationTaxonomyCards"', distribution)
        watchlists = HTML.split('data-route-panel="watchlists"', 1)[1].split(
            'data-route-panel="attention"', 1
        )[0]
        self.assertNotIn("LOCATION DISTRIBUTION", watchlists)


if __name__ == "__main__":
    unittest.main()
