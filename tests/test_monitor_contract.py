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
        self.assertIn("MRZ Monitor", HTML)
        self.assertIn('class="workspace-sidebar"', HTML)
        self.assertIn('class="workspace-header"', HTML)
        self.assertIn('data-route-panel="overview"', HTML)
        self.assertIn('data-route-panel="watchlists"', HTML)
        self.assertNotIn("Views", HTML)
        self.assertNotIn("masthead-descriptor", HTML)

    def test_notification_inbox_remains_durable_and_distinct(self) -> None:
        self.assertIn('id="notificationInboxButton"', HTML)
        self.assertIn('id="notificationInboxDialog"', HTML)
        self.assertIn('id="notificationInboxList" aria-live="polite"', HTML)
        self.assertIn('/api/notifications/inbox?limit=50', NOTIFICATIONS)
        self.assertIn('/api/notifications/inbox/${notificationId}/read', NOTIFICATIONS)
        self.assertIn('/api/notifications/inbox/${notificationId}/dismiss', NOTIFICATIONS)
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
        self.assertIn('id="detailLatestEvent"', HTML)
        self.assertIn('id="detailPressure"', HTML)
        self.assertIn("detail.migration?.has_migrated", WORKSPACE)
        self.assertIn("/api/symbols/${encodeURIComponent(symbol)}", WORKSPACE)

    def test_pressure_tools_moved_below_pressure_route(self) -> None:
        pressure = HTML.split('data-route-panel="pressure"', 1)[1].split(
            'data-route-panel="events"', 1
        )[0]
        self.assertIn("PRESSURE MAP", pressure)
        self.assertIn("LOCATION HEATMAP", pressure)
        self.assertIn("PEER PRESSURE", pressure)
        watchlists = HTML.split('data-route-panel="watchlists"', 1)[1].split(
            'data-route-panel="attention"', 1
        )[0]
        self.assertNotIn("LOCATION HEATMAP", watchlists)


if __name__ == "__main__":
    unittest.main()
