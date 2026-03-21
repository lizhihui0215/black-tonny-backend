#!/bin/sh
set -eu

mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" <<SQL
CREATE DATABASE IF NOT EXISTS black_tonny_serving CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS black_tonny_capture CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON black_tonny_serving.* TO '${MYSQL_USER}'@'%';
GRANT ALL PRIVILEGES ON black_tonny_capture.* TO '${MYSQL_USER}'@'%';
FLUSH PRIVILEGES;
SQL
