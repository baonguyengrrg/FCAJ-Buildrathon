#!/bin/bash
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

echo "⏳ Đang đợi Floci sẵn sàng..."
until curl -s http://localhost:4566 > /dev/null; do
    sleep 1
done

echo "Bat dau khoi tao..."

# S3
aws --endpoint-url=http://localhost:4566 s3 mb s3://lab-media-storage 2>/dev/null || true
aws --endpoint-url=http://localhost:4566 s3 mb s3://lab-ai-datasets 2>/dev/null || true

# DynamoDB
aws --endpoint-url=http://localhost:4566 dynamodb create-table \
    --table-name MediaMetadata \
    --attribute-definitions AttributeName=FileID,AttributeType=S \
    --key-schema AttributeName=FileID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST 2>/dev/null || true

# SQS
aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name ai-processing-queue 2>/dev/null || true

# SNS
aws --endpoint-url=http://localhost:4566 sns create-topic --name media-alerts 2>/dev/null || true

echo "Hoan tat thiet lap"