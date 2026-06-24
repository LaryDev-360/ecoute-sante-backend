.PHONY: install migrate seed run test db-up db-down

VENV = venv/bin/activate
PYTHON = venv/bin/python

install:
	python3 -m venv venv
	. $(VENV) && pip install -r requirements/dev.txt

db-up:
	docker compose up -d db

db-down:
	docker compose down

makemigrations:
	$(PYTHON) manage.py makemigrations

migrate:
	$(PYTHON) manage.py migrate

seed: migrate
	$(PYTHON) manage.py seed_if_empty --force

seed-fresh: migrate
	$(PYTHON) manage.py seed_facilities
	$(PYTHON) manage.py seed_data

run:
	$(PYTHON) manage.py runserver 8004

test:
	$(PYTHON) manage.py test --settings=config.settings.test
