from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
NGINX = (ROOT / "infra/nginx/edge2-ngrok.conf.template").read_text(encoding="utf-8")
NGROK_UNIT = (ROOT / "ops/systemd/edge-ngrok.service").read_text(encoding="utf-8")
DEPLOY_SCRIPT = (ROOT / "scripts/deploy-remote.sh").read_text(encoding="utf-8")


class IngressContractTests(unittest.TestCase):
    def test_ingress_is_loopback_only_and_uses_a_separate_port(self) -> None:
        self.assertIn('"127.0.0.1:${EDGE2_INGRESS_PORT:-8793}:8080"', COMPOSE)
        self.assertNotIn('"0.0.0.0:${EDGE2_INGRESS_PORT', COMPOSE)

    def test_ingress_secret_comes_from_edge2_environment(self) -> None:
        self.assertIn("EDGE2_UPSTREAM_WEBHOOK_SECRET: ${WEBHOOK_SECRET:?", COMPOSE)
        self.assertIn("NGINX_ENVSUBST_FILTER: ^EDGE2_UPSTREAM_WEBHOOK_SECRET$", COMPOSE)
        self.assertIn(
            'proxy_set_header X-EDGE2-Webhook-Secret "${EDGE2_UPSTREAM_WEBHOOK_SECRET}";',
            NGINX,
        )

    def test_only_exact_webhook_path_is_proxied(self) -> None:
        self.assertIn("location = /webhook/tradingview", NGINX)
        self.assertIn("set $edge2_app http://edge2-app:8790;", NGINX)
        self.assertIn("proxy_pass $edge2_app/webhook/tradingview;", NGINX)
        self.assertIn("limit_except POST", NGINX)
        self.assertRegex(NGINX, re.compile(r"location / \{\s+return 404;", re.MULTILINE))

    def test_https_ingress_exposes_the_pwa_and_notification_api(self) -> None:
        for location in (
            "location = / {",
            "location = /manifest.webmanifest {",
            "location = /service-worker.js {",
            "location /static/ {",
            "location /api/ {",
        ):
            self.assertIn(location, NGINX)
        self.assertIn("proxy_pass $edge2_app/manifest.webmanifest;", NGINX)
        self.assertIn("proxy_pass $edge2_app/service-worker.js;", NGINX)
        self.assertGreaterEqual(NGINX.count("proxy_pass $edge2_app$request_uri;"), 2)
        self.assertNotIn("proxy_cache", NGINX)

    def test_webhook_secret_remains_scoped_to_the_exact_webhook_location(self) -> None:
        self.assertEqual(NGINX.count("X-EDGE2-Webhook-Secret"), 1)
        webhook_block = re.search(
            r"location = /webhook/tradingview \{(?P<body>.*?)\n    \}",
            NGINX,
            re.DOTALL,
        )
        self.assertIsNotNone(webhook_block)
        self.assertIn("X-EDGE2-Webhook-Secret", webhook_block.group("body"))

    def test_ingress_rediscovers_app_after_container_replacement(self) -> None:
        self.assertIn("resolver 127.0.0.11", NGINX)
        self.assertIn("proxy_pass $edge2_app/health;", NGINX)

    def test_ngrok_hostname_is_retained_and_targets_ingress(self) -> None:
        self.assertIn("http://127.0.0.1:8793", NGROK_UNIT)
        self.assertIn(
            "--url=https://unretroactively-latticed-fidela.ngrok-free.dev",
            NGROK_UNIT,
        )
        self.assertNotIn("127.0.0.1:8765", NGROK_UNIT)

    def test_remote_deploy_verifies_the_ingress(self) -> None:
        self.assertIn("REMOTE_INGRESS_HEALTH_URL", DEPLOY_SCRIPT)
        self.assertIn("EDGE 2.0 app and ingress healthy", DEPLOY_SCRIPT)
        self.assertIn("--force-recreate --no-deps edge2-ingress", DEPLOY_SCRIPT)

    def test_remote_deploy_uses_git_as_code_transport(self) -> None:
        self.assertNotIn("rsync ", DEPLOY_SCRIPT)
        self.assertNotIn("scp ", DEPLOY_SCRIPT)
        self.assertIn('push origin "${BRANCH}"', DEPLOY_SCRIPT)
        self.assertIn('git pull --ff-only origin "${branch}"', DEPLOY_SCRIPT)
        self.assertIn("git status --porcelain", DEPLOY_SCRIPT)
        self.assertIn("EDGE2_REMOTE_SHA", DEPLOY_SCRIPT)

    def test_no_literal_webhook_secret_is_committed(self) -> None:
        combined = COMPOSE + NGINX + NGROK_UNIT
        self.assertNotIn("replace-with-an-independent-long-random-secret", combined)
        self.assertNotRegex(combined, re.compile(r"X-EDGE2-Webhook-Secret:\s+[A-Za-z0-9_-]{20,}"))


if __name__ == "__main__":
    unittest.main()
