#!/usr/bin/env python3
"""Convert scanned PDF/image files to Markdown through Paddle OCR HTTP APIs."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Call Paddle OCR APIs and write Markdown output."
    )
    parser.add_argument(
        "--input-file",
        "--input-pdf",
        dest="input_file",
        required=True,
        help="Path to input PDF/image file.",
    )
    parser.add_argument("--output-md", required=True, help="Path to output markdown file.")
    parser.add_argument(
        "--output-json",
        help="Optional path to save raw OCR response JSON. Defaults to <output-md>.json",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("PADDLE_OCR_API_URL"),
        help="Paddle OCR API URL. Can use env PADDLE_OCR_API_URL.",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("PADDLE_OCR_API_KEY"),
        help="API key/token. Can use env PADDLE_OCR_API_KEY.",
    )
    parser.add_argument(
        "--auth-scheme",
        choices=("auto", "bearer", "token", "none"),
        default="auto",
        help="Authorization format. 'auto' -> token for layout-parsing-json, bearer otherwise.",
    )
    parser.add_argument(
        "--file-field",
        default="file",
        help="Multipart file field name. Default: file",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="HTTP timeout in seconds. Default: 180",
    )
    parser.add_argument(
        "--low-confidence",
        type=float,
        default=0.80,
        help="Lines below this confidence are marked [REVIEW]. Default: 0.80",
    )
    parser.add_argument(
        "--lang",
        default="ch",
        help="Language hint for generic modes. Default: ch",
    )
    parser.add_argument(
        "--mode",
        choices=("multipart-pdf", "json-base64", "layout-parsing-json"),
        default="layout-parsing-json",
        help="Request mode. Default: layout-parsing-json",
    )
    parser.add_argument(
        "--file-type",
        type=int,
        choices=(0, 1),
        help="For layout-parsing-json: 0 for PDF, 1 for image. Default: infer from file extension.",
    )
    parser.add_argument(
        "--use-doc-orientation-classify",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="For layout-parsing-json payload. Default: false",
    )
    parser.add_argument(
        "--use-doc-unwarping",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="For layout-parsing-json payload. Default: false",
    )
    parser.add_argument(
        "--use-chart-recognition",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="For layout-parsing-json payload. Default: false",
    )
    parser.add_argument(
        "--download-images",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Download images listed in markdown/images fields when available. Default: true",
    )
    parser.add_argument(
        "--assets-dir",
        help="Directory for downloaded images. Default: <output-md stem>_assets beside output file.",
    )
    parser.add_argument(
        "--extra-field",
        action="append",
        default=[],
        help="Extra field KEY=VALUE. Can be repeated.",
    )
    return parser.parse_args()


def parse_extra_fields(items: list[str]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid --extra-field format (need KEY=VALUE): {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid --extra-field key: {item}")
        fields[key] = _coerce_value(value.strip())
    return fields


def _coerce_value(value: str) -> Any:
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower == "null":
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def infer_file_type(file_path: Path) -> int:
    return 0 if file_path.suffix.lower() == ".pdf" else 1


def resolve_auth_header(mode: str, auth_scheme: str, api_key: str | None) -> str | None:
    if not api_key:
        return None
    if auth_scheme == "none":
        return None
    if auth_scheme == "auto":
        scheme = "token" if mode == "layout-parsing-json" else "bearer"
    else:
        scheme = auth_scheme
    if scheme == "token":
        return f"token {api_key}"
    return f"Bearer {api_key}"


def build_multipart_body(
    fields: dict[str, Any],
    file_field: str,
    file_path: Path,
) -> tuple[bytes, str]:
    boundary = f"----OpenClawBoundary{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for key, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8")
        )
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")

    content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    file_name = file_path.name
    file_bytes = file_path.read_bytes()
    chunks.append(f"--{boundary}\r\n".encode("utf-8"))
    chunks.append(
        (
            f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{file_name}"\r\n'
        ).encode("utf-8")
    )
    chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
    chunks.append(file_bytes)
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))

    return b"".join(chunks), boundary


def call_ocr_api(
    *,
    api_url: str,
    api_key: str | None,
    auth_scheme: str,
    mode: str,
    file_field: str,
    file_path: Path,
    lang: str,
    file_type: int | None,
    use_doc_orientation_classify: bool,
    use_doc_unwarping: bool,
    use_chart_recognition: bool,
    extra_fields: dict[str, Any],
    timeout: int,
) -> Any:
    headers = {"Accept": "application/json"}
    auth_header = resolve_auth_header(mode=mode, auth_scheme=auth_scheme, api_key=api_key)
    if auth_header:
        headers["Authorization"] = auth_header

    if mode == "multipart-pdf":
        fields = {"lang": lang}
        fields.update(extra_fields)
        body, boundary = build_multipart_body(fields, file_field=file_field, file_path=file_path)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        req = urllib.request.Request(api_url, data=body, headers=headers, method="POST")
    elif mode == "json-base64":
        payload = {
            "lang": lang,
            "filename": file_path.name,
            "file_base64": base64.b64encode(file_path.read_bytes()).decode("ascii"),
        }
        payload.update(extra_fields)
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        req = urllib.request.Request(api_url, data=body, headers=headers, method="POST")
    else:
        payload = {
            "file": base64.b64encode(file_path.read_bytes()).decode("ascii"),
            "fileType": file_type if file_type is not None else infer_file_type(file_path),
            "useDocOrientationClassify": use_doc_orientation_classify,
            "useDocUnwarping": use_doc_unwarping,
            "useChartRecognition": use_chart_recognition,
        }
        payload.update(extra_fields)
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        req = urllib.request.Request(api_url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OCR API HTTP error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OCR API network error: {exc.reason}") from exc

    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        snippet = raw[:800].decode("utf-8", errors="replace")
        raise RuntimeError(f"OCR API returned non-JSON response: {snippet}") from exc


def _as_lines_from_page(page_obj: Any) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    if isinstance(page_obj, dict):
        if isinstance(page_obj.get("lines"), list):
            for item in page_obj["lines"]:
                if isinstance(item, dict):
                    text = str(item.get("text", "")).strip()
                    conf = item.get("confidence")
                else:
                    text = str(item).strip()
                    conf = None
                if text:
                    lines.append({"text": text, "confidence": conf})
            return lines

        texts = page_obj.get("rec_texts")
        scores = page_obj.get("rec_scores")
        if isinstance(texts, list):
            for idx, text in enumerate(texts):
                txt = str(text).strip()
                if not txt:
                    continue
                conf = None
                if isinstance(scores, list) and idx < len(scores):
                    conf = scores[idx]
                lines.append({"text": txt, "confidence": conf})
            return lines

        if isinstance(page_obj.get("text"), str):
            txt = page_obj["text"].strip()
            if txt:
                lines.append({"text": txt, "confidence": page_obj.get("confidence")})
            return lines

    if isinstance(page_obj, str):
        txt = page_obj.strip()
        if txt:
            lines.append({"text": txt, "confidence": None})
    return lines


def _extract_page_like_list(payload: Any) -> list[Any] | None:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return None

    direct_keys = ("pages", "result", "results", "data", "ocr_results")
    for key in direct_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_page_like_list(value)
            if nested is not None:
                return nested
    return None


def normalize_ocr_response(payload: Any) -> list[list[dict[str, Any]]]:
    pages_raw = _extract_page_like_list(payload)
    if pages_raw is None:
        single_page = _as_lines_from_page(payload)
        return [single_page] if single_page else []

    pages: list[list[dict[str, Any]]] = []
    for page_obj in pages_raw:
        lines = _as_lines_from_page(page_obj)
        if lines:
            pages.append(lines)
        else:
            pages.append([])
    return pages


def confidence_value(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def render_generic_markdown(pages: list[list[dict[str, Any]]], low_confidence: float) -> str:
    out: list[str] = ["# OCR Markdown Output", ""]
    if not pages:
        out.append("_No text recognized from OCR response._")
        out.append("")
        return "\n".join(out)

    for idx, lines in enumerate(pages, start=1):
        out.append(f"## Page {idx}")
        out.append("")
        if not lines:
            out.append("_No text recognized on this page._")
            out.append("")
            continue
        for line in lines:
            text = str(line.get("text", "")).strip()
            if not text:
                continue
            score = confidence_value(line.get("confidence"))
            if score is not None and score < low_confidence:
                out.append(f"- [REVIEW score={score:.2f}] {text}")
            else:
                out.append(f"- {text}")
        out.append("")
    return "\n".join(out)


def extract_layout_parsing_results(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    result_obj = payload.get("result")
    if isinstance(result_obj, dict):
        layout_results = result_obj.get("layoutParsingResults")
        if isinstance(layout_results, list):
            return [item for item in layout_results if isinstance(item, dict)]
    layout_results = payload.get("layoutParsingResults")
    if isinstance(layout_results, list):
        return [item for item in layout_results if isinstance(item, dict)]
    return []


def download_binary(url: str, timeout: int) -> bytes:
    req = urllib.request.Request(url, headers={"Accept": "*/*"}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def safe_join(base_dir: Path, rel_path: str) -> Path:
    candidate = (base_dir / rel_path).resolve()
    base = base_dir.resolve()
    if str(candidate).startswith(str(base)):
        return candidate
    return (base_dir / Path(rel_path).name).resolve()


def render_layout_parsing_markdown(
    *,
    layout_results: list[dict[str, Any]],
    output_md: Path,
    download_images: bool,
    assets_dir: Path,
    timeout: int,
) -> str:
    out: list[str] = ["# OCR Markdown Output", ""]
    if not layout_results:
        out.append("_No layoutParsingResults found in response._")
        out.append("")
        return "\n".join(out)

    for idx, item in enumerate(layout_results):
        out.append(f"## Document {idx}")
        out.append("")
        markdown_obj = item.get("markdown", {})
        if isinstance(markdown_obj, dict):
            md_text = markdown_obj.get("text")
            if isinstance(md_text, str) and md_text.strip():
                out.append(md_text.rstrip())
                out.append("")
            else:
                out.append("_No markdown text returned._")
                out.append("")

            md_images = markdown_obj.get("images")
            if isinstance(md_images, dict):
                out.append("### Markdown Images")
                out.append("")
                for rel_path, url in md_images.items():
                    rel_path_str = str(rel_path)
                    url_str = str(url)
                    if download_images:
                        target = safe_join(assets_dir, rel_path_str)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            data = download_binary(url_str, timeout=timeout)
                            target.write_bytes(data)
                            out.append(f"- {target}")
                        except Exception as exc:  # noqa: BLE001
                            out.append(f"- [FAILED] {rel_path_str}: {exc}")
                    else:
                        out.append(f"- {rel_path_str}: {url_str}")
                out.append("")

        output_images = item.get("outputImages")
        if isinstance(output_images, dict):
            out.append("### Output Images")
            out.append("")
            for name, url in output_images.items():
                name_str = str(name)
                url_str = str(url)
                if download_images:
                    target = (assets_dir / f"{name_str}_{idx}.jpg").resolve()
                    target.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        data = download_binary(url_str, timeout=timeout)
                        target.write_bytes(data)
                        out.append(f"- {target}")
                    except Exception as exc:  # noqa: BLE001
                        out.append(f"- [FAILED] {name_str}: {exc}")
                else:
                    out.append(f"- {name_str}: {url_str}")
            out.append("")

    # Also save split docs similar to provided Paddle sample.
    split_dir = (output_md.parent / f"{output_md.stem}_split").resolve()
    split_dir.mkdir(parents=True, exist_ok=True)
    for idx, item in enumerate(layout_results):
        markdown_obj = item.get("markdown", {})
        if isinstance(markdown_obj, dict) and isinstance(markdown_obj.get("text"), str):
            split_file = split_dir / f"doc_{idx}.md"
            split_file.write_text(markdown_obj["text"], encoding="utf-8")
    out.append(f"_Split markdown docs saved in: {split_dir}_")
    out.append("")
    return "\n".join(out)


def main() -> int:
    args = parse_args()
    if not args.api_url:
        print("Missing API URL. Set --api-url or PADDLE_OCR_API_URL.", file=sys.stderr)
        return 2

    input_file = Path(args.input_file).expanduser().resolve()
    if not input_file.exists():
        print(f"Input file not found: {input_file}", file=sys.stderr)
        return 2

    try:
        extra_fields = parse_extra_fields(args.extra_field)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        payload = call_ocr_api(
            api_url=args.api_url,
            api_key=args.api_key,
            auth_scheme=args.auth_scheme,
            mode=args.mode,
            file_field=args.file_field,
            file_path=input_file,
            lang=args.lang,
            file_type=args.file_type,
            use_doc_orientation_classify=args.use_doc_orientation_classify,
            use_doc_unwarping=args.use_doc_unwarping,
            use_chart_recognition=args.use_chart_recognition,
            extra_fields=extra_fields,
            timeout=args.timeout,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output_md = Path(args.output_md).expanduser().resolve()
    output_md.parent.mkdir(parents=True, exist_ok=True)
    assets_dir = (
        Path(args.assets_dir).expanduser().resolve()
        if args.assets_dir
        else (output_md.parent / f"{output_md.stem}_assets").resolve()
    )

    layout_results = extract_layout_parsing_results(payload)
    if args.mode == "layout-parsing-json" or layout_results:
        markdown = render_layout_parsing_markdown(
            layout_results=layout_results,
            output_md=output_md,
            download_images=args.download_images,
            assets_dir=assets_dir,
            timeout=args.timeout,
        )
    else:
        pages = normalize_ocr_response(payload)
        markdown = render_generic_markdown(pages, low_confidence=args.low_confidence)

    output_md.write_text(markdown, encoding="utf-8")

    output_json = (
        Path(args.output_json).expanduser().resolve()
        if args.output_json
        else output_md.with_suffix(".json")
    )
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Markdown written: {output_md}")
    print(f"Raw OCR JSON written: {output_json}")
    if args.download_images and (args.mode == "layout-parsing-json" or layout_results):
        print(f"Assets directory: {assets_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
