#!/bin/bash
(service mariadb start >/dev/null 2>&1 || (nohup mysqld_safe --user=mysql >/home/claude/tools/mysqld.log 2>&1 &))
for i in $(seq 1 20); do mysql -uroot -proot -e "select 1" >/dev/null 2>&1 && break; sleep 2; done
for p in 13000 11000 12000; do redis-cli -p $p ping >/dev/null 2>&1 || su frappe -c "redis-server --port $p --daemonize yes --save '' --appendonly no" >/dev/null; done
mysql -uroot -proot -e "select 'mariadb ok'" 2>&1 | tail -1
