#!/usr/bin/env bash
set -e
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is a public servant?"}' | jq

curl -s -X POST 'http://localhost:8000/query?format=html' \
  -H "Content-Type: application/json" \
  -d '{"query": "What is a public servant?"}' > out.html
echo "Open out.html in a browser."