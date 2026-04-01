# Service Analysis JSON Response Examples

This document provides representative examples of JSON responses from the Xray AI service analysis
API. Use these to understand the structure of `serviceAnomalies`, `callAnomalies`, and `exceptions`.

## Example 1: Service and Call Anomalies (clue-marketing-platform)

This example shows a service with critical issues in its own provided API (`saveMessageApi`) and its
downstream calls (`chattrade-service-default.bizMenuCommit`).

```json
{
  "service": "clue-marketing-platform",
  "startTime": "2026-03-26T13:20:00",
  "endTime": "2026-03-26T13:36:00",
  "serviceAnomalies": [
    {
      "target": "saveMessageApi",
      "status": "critical",
      "metrics": [
        {
          "metric": "RPC 服务请求QPS",
          "status": "critical",
          "outliers": [],
          "anomalyZones": [],
          "timeSeries": [
            { "timestamp": "2026-03-26 13:20:00", "value": 0 },
            { "timestamp": "2026-03-26 13:23:00", "value": 0.016666666666666666 },
            { "timestamp": "2026-03-26 13:36:00", "value": 0.016666666666666666 }
          ]
        }
      ]
    },
    {
      "target": "operateCard",
      "status": "critical",
      "metrics": [
        {
          "metric": "RPC 服务请求QPS",
          "status": "normal",
          "outliers": [],
          "anomalyZones": [],
          "timeSeries": [
            { "timestamp": "2026-03-26 12:50:00", "value": 0.06666666666666667 },
            { "timestamp": "2026-03-26 13:36:00", "value": 0.2 }
          ]
        },
        {
          "metric": "RPC 服务成功率",
          "status": "critical",
          "outliers": [],
          "anomalyZones": [],
          "timeSeries": [
            { "timestamp": "2026-03-26 13:33:00", "value": 1 },
            { "timestamp": "2026-03-26 13:34:00", "value": 0.8571428571428571 },
            { "timestamp": "2026-03-26 13:35:00", "value": 0.3333333333333333 },
            { "timestamp": "2026-03-26 13:36:00", "value": 0.4 }
          ]
        }
      ]
    }
  ],
  "callAnomalies": [
    {
      "target": "chattrade-service-default.bizMenuCommit",
      "status": "critical",
      "metrics": [
        {
          "metric": "RPC 客户端请求QPS",
          "status": "normal",
          "outliers": [],
          "anomalyZones": [],
          "timeSeries": [{ "timestamp": "2026-03-26 13:36:00", "value": 0.016666666666666666 }]
        },
        {
          "metric": "RPC 客户端平均耗时",
          "status": "critical",
          "outliers": [],
          "anomalyZones": [],
          "timeSeries": [
            { "timestamp": "2026-03-26 13:34:00", "value": 23.004887 },
            { "timestamp": "2026-03-26 13:36:00", "value": 71.958952 }
          ]
        }
      ]
    }
  ]
}
```

## Example 2: Internal Exceptions (mewtwo-service-default)

This example focuses on internal Java exceptions, showing `outliers` and `timeSeries` for SQL and
Spring related errors.

```json
{
  "service": "mewtwo-service-default",
  "startTime": "2026-03-26T10:40:00",
  "endTime": "2026-03-26T10:59:00",
  "exceptions": [
    {
      "target": "java.sql.SQLIntegrityConstraintViolationException",
      "status": "critical",
      "metrics": [
        {
          "metric": "java.sql.SQLIntegrityConstraintViolationException",
          "status": "critical",
          "outliers": [
            { "timestamp": "2026-03-26 10:47:00", "value": 95 },
            { "timestamp": "2026-03-26 10:53:00", "value": 202 },
            { "timestamp": "2026-03-26 10:59:00", "value": 190 }
          ],
          "timeSeries": [
            { "timestamp": "2026-03-26 10:39:00", "value": 2 },
            { "timestamp": "2026-03-26 10:59:00", "value": 190 }
          ]
        }
      ]
    },
    {
      "target": "java.sql.SQLException",
      "status": "critical",
      "metrics": [
        {
          "metric": "java.sql.SQLException",
          "status": "critical",
          "outliers": [
            { "timestamp": "2026-03-26 10:43:00", "value": 16 },
            { "timestamp": "2026-03-26 10:45:00", "value": 16 }
          ],
          "timeSeries": [
            { "timestamp": "2026-03-26 10:39:00", "value": 8 },
            { "timestamp": "2026-03-26 10:59:00", "value": 10 }
          ]
        }
      ]
    },
    {
      "target": "org.springframework.dao.DuplicateKeyException",
      "status": "critical",
      "metrics": [
        {
          "metric": "org.springframework.dao.DuplicateKeyException",
          "status": "critical",
          "outliers": [
            { "timestamp": "2026-03-26 10:49:00", "value": 99 },
            { "timestamp": "2026-03-26 10:53:00", "value": 202 },
            { "timestamp": "2026-03-26 10:59:00", "value": 190 }
          ],
          "timeSeries": [
            { "timestamp": "2026-03-26 10:39:00", "value": 0 },
            { "timestamp": "2026-03-26 10:59:00", "value": 190 }
          ]
        }
      ]
    }
  ]
}
```
