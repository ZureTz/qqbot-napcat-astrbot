.PHONY: init check up down logs status restart

init:
	python3 scripts/init.py

check:
	docker compose --env-file .env.example config --quiet
	python3 -m compileall -q scripts plugins

up: init
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs --tail=100 -f

status:
	docker compose ps

restart:
	docker compose restart
