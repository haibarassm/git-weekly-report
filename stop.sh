#!/bin/bash

CONTAINER_NAME="report-generator"

echo "停止并删除容器..."
docker rm -f ${CONTAINER_NAME}

echo "完成！"
