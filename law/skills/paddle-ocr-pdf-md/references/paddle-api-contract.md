# Paddle OCR API Contract

This skill supports three request modes. Recommended mode for your current endpoint is `layout-parsing-json`.

## 1) layout-parsing-json (recommended)

- HTTP method: `POST`
- Content-Type: `application/json`
- Auth: `Authorization: token <TOKEN>` (use `--auth-scheme token`)
- Required payload fields:
  - `file` (base64 of full file bytes)
  - `fileType` (`0` for PDF, `1` for image)
- Optional payload fields:
  - `useDocOrientationClassify` (bool)
  - `useDocUnwarping` (bool)
  - `useChartRecognition` (bool)
  - extra custom fields from `--extra-field KEY=VALUE`

Expected response shape:

```json
{
  "result": {
    "layoutParsingResults": [
      {
        "markdown": {
          "text": "...",
          "images": { "relative/path.png": "https://..." }
        },
        "outputImages": { "name": "https://..." }
      }
    ]
  }
}
```

## 2) multipart-pdf (generic fallback)

- HTTP method: `POST`
- Content-Type: `multipart/form-data`
- Required file field: configurable by `--file-field` (default `file`)
- Optional `lang` + extra fields

## 3) json-base64 (generic fallback)

- HTTP method: `POST`
- Content-Type: `application/json`
- Body fields:
  - `lang`
  - `filename`
  - `file_base64`
  - extra fields

## Authentication

- `--auth-scheme auto`: use `token` for `layout-parsing-json`, use `bearer` for others.
- `--auth-scheme token`: `Authorization: token <api_key>`
- `--auth-scheme bearer`: `Authorization: Bearer <api_key>`
