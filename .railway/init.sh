#!/bin/bash

# 更新系統包列表
apt-get update

# 安裝 ODBC 相關依賴
apt-get install -y unixodbc unixodbc-dev