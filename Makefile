.PHONY: test up down logs health ingress-health migrate backup deploy

test:
	docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from edge2-test
	docker compose -f docker-compose.test.yml down --volumes --remove-orphans

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs --tail=200 -f edge2-app

health:
	curl --fail --silent --show-error http://127.0.0.1:$${EDGE2_APP_PORT:-8792}/health

ingress-health:
	curl --fail --silent --show-error http://127.0.0.1:$${EDGE2_INGRESS_PORT:-8793}/health

migrate:
	docker compose run --rm edge2-app python3 scripts/migrate.py

backup:
	./scripts/backup.sh

deploy:
	./scripts/deploy-remote.sh
