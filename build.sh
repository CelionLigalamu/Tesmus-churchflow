#!/usr/bin/env bash
# Render runs this on every deploy (see render.yaml). Stop at the first error so
# a broken deploy never replaces the working site.
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py createcachetable

# First deploy only: create the Tesmus superuser from DJANGO_SUPERUSER_USERNAME,
# DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD if they are set. Remove
# those three settings from Render once you have signed in.
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ]; then
    python manage.py createsuperuser --no-input || echo "Superuser not created (it probably exists already)."
fi
