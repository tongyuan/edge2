from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "app/api.py").read_text(encoding="utf-8")
INDEX = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
DOCK = (ROOT / "app/static/dock.html").read_text(encoding="utf-8")
DOCKING = (ROOT / "app/static/docking.js").read_text(encoding="utf-8")
MAP = (ROOT / "app/static/opportunity-map.js").read_text(encoding="utf-8")
NOTIFICATIONS = (ROOT / "app/static/notifications.js").read_text(encoding="utf-8")


class DockingContractTests(unittest.TestCase):
    def test_dock_routes_share_one_read_only_shell(self) -> None:
        self.assertIn('@application.get("/dock/inbox"', API)
        self.assertIn('@application.get("/dock/opportunity-map/{symbol}"', API)
        self.assertIn('STATIC_DIR / "dock.html"', API)
        self.assertIn('"Cache-Control": "no-store, max-age=0"', API)
        self.assertNotIn('@application.post("/dock/', API)

    def test_main_workspace_exposes_dock_actions(self) -> None:
        self.assertIn('id="notificationInboxDock"', INDEX)
        self.assertIn('/static/docking.js', INDEX)
        self.assertIn('openOpportunityMap', MAP)
        self.assertIn('opportunity-dock-button', MAP)
        self.assertNotIn('"Maximize"', MAP)

    def test_detached_windows_reuse_existing_canonical_clients(self) -> None:
        for expected in (
            'name: "edge-opportunity-map-dock"',
            'name: "edge-inbox-dock"',
            'trackDockedWindow',
            'openInMain',
        ):
            self.assertIn(expected, DOCKING)
        self.assertIn('/api/notifications/inbox?limit=50', NOTIFICATIONS)
        self.assertIn('/api/notifications/events?after=', NOTIFICATIONS)
        self.assertIn('BroadcastChannel', NOTIFICATIONS)

    def test_dock_shell_preserves_map_evidence_and_inbox_actions(self) -> None:
        for expected in (
            'id="dockOpportunityMap"',
            'id="dockInbox"',
            'id="notificationInboxList"',
            'id="notificationMarkAllRead"',
            'id="notificationClearInbox"',
            '/static/opportunity-map.js',
            '/static/notifications.js',
        ):
            self.assertIn(expected, DOCK)
        self.assertIn('ResizeObserver', MAP)
        self.assertIn('dock-event-details', MAP)
        self.assertIn('Return to EDGE', MAP)


if __name__ == "__main__":
    unittest.main()
