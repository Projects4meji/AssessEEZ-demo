#!/usr/bin/env bash
echo "PHP dependencies Installation "
yum -y install libzip libzip-devel php-xml php-gd
yum -y install php-{cgi,curl,mbstring,gd,mysqlnd,gettext,json,xml,fpm,intl,zip}
