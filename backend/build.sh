#!/bin/bash
composer install
npm install
npm run build
zip ../"deployment-`date`".zip -r * .[^.]* -x "vendor/*" -x "node_modules/*"
