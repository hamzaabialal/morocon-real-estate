.PHONY: migrate import test shell seed run celery beat scrape match agencies sarouty enrich

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

agencies:
	python manage.py scrape_sarouty_agencies

sarouty:
	python manage.py scrape_sarouty --start-id=850000 --end-id=950000

enrich:
	python manage.py enrich_from_yakeey --file=data/Yakeey.parquet
