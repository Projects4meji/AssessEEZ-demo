#!/bin/sh
echo "Configuration CLoudwatch"
cp .platform/files/app_log.json /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.d/laravel.json
systemctl restart amazon-cloudwatch-agent.service
