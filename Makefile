.PHONY: migrate import test shell seed run celery beat scrape match

migrate:
	python manage.py migrate

import:
	python manage.py import_yakeey --file=data/Yakeey.csv

test:
	pytest

shell:
	python manage.py shell

seed:
	python manage.py seed_morocco_cities

run:
	python manage.py runserver

celery:
	celery -A celery_app worker --loglevel=info

beat:
	celery -A celery_app beat --loglevel=info

scrape:
	python manage.py collect_agencies --pages=50

match:
	python manage.py match_agencies
