#!/bin/sh
mkdir -p storage/framework/sessions
mkdir -p storage/framework/cache
mkdir -p storage/framework/views
chmod -R 777 storage/framework

php artisan storage:link
php artisan config:cache

#php artisan key:generate
php artisan optimize:clear || :
php artisan cache:clear || :
php artisan config:clear || :
php artisan view:clear || :
