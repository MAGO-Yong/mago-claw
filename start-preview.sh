#!/bin/bash
# 预览服务器保活脚本
# 用法：bash start-preview.sh
PORT=8899
DIR=/home/node/.openclaw/workspace

# 检查是否已经在跑
if curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/ 2>/dev/null | grep -q "200\|404"; then
  echo "Server already running on port $PORT"
  exit 0
fi

cd $DIR
nohup python3 -m http.server $PORT > /tmp/httpserver.log 2>&1 &
sleep 1
echo "Started on http://10.40.56.49:$PORT"
