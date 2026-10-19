import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class GeminiRateLimit(Exception):
    pass


class GeminiResponseError(ValueError):
    """A safe-to-display failure while decoding a Gemini response."""


def _byte_length(response):
    body = getattr(response, 'content', b'')
    return len(body.encode('utf-8')) if isinstance(body, str) else len(body or b'')


def _decode_position(error):
    return getattr(error, 'lineno', None), getattr(error, 'colno', None)


def _diagnostic(diagnostics, *, response, stage, top_level_keys=None,
                candidate_count=None, finish_reason=None, part_types=None,
                generated_text_length=0, error=None):
    if not diagnostics:
        return
    logger.info(
        'Gemini response diagnostic stage=%s upstream_status=%s content_type=%s response_bytes=%s '
        'top_level_keys=%s candidate_count=%s finish_reason=%s part_types=%s '
        'generated_text_length=%s decode_line=%s decode_column=%s',
        stage,
        response.status_code,
        response.headers.get('Content-Type', 'unknown'),
        _byte_length(response),
        top_level_keys,
        candidate_count,
        finish_reason,
        part_types or [],
        generated_text_length,
        _decode_position(error)[0] if error else None,
        _decode_position(error)[1] if error else None,
    )


def generate_json(prompt, schema, *, max_output_tokens=700, timeout=20,
                  required_fields=None, diagnostics=False):
    """Call Gemini without logging, returning, or exposing the configured key."""
    endpoint = f'https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent'
    response = requests.post(
        endpoint,
        headers={'x-goog-api-key': settings.GEMINI_API_KEY},
        json={
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {
                'maxOutputTokens': max_output_tokens,
                'responseFormat': {'text': {'mimeType': 'APPLICATION_JSON', 'schema': schema}},
            },
        },
        timeout=timeout,
    )
    if response.status_code == 429:
        raise GeminiRateLimit
    response.raise_for_status()
    try:
        envelope = response.json()
    except (ValueError, requests.exceptions.JSONDecodeError) as exc:
        _diagnostic(diagnostics, response=response, stage='http_envelope_json', error=exc)
        raise GeminiResponseError('Gemini returned an unreadable HTTP response.') from None
    if not isinstance(envelope, dict):
        _diagnostic(diagnostics, response=response, stage='http_envelope_structure')
        raise GeminiResponseError('Gemini returned an unexpected HTTP response structure.')

    candidates = envelope.get('candidates')
    candidate_count = len(candidates) if isinstance(candidates, list) else 0
    if not isinstance(candidates, list) or not candidates:
        _diagnostic(diagnostics, response=response, stage='empty_candidates',
                    top_level_keys=sorted(envelope), candidate_count=candidate_count)
        raise GeminiResponseError('Gemini returned no summary candidate.')
    candidate = candidates[0]
    if not isinstance(candidate, dict):
        _diagnostic(diagnostics, response=response, stage='candidate_structure',
                    top_level_keys=sorted(envelope), candidate_count=candidate_count)
        raise GeminiResponseError('Gemini returned an unexpected candidate structure.')

    finish_reason = candidate.get('finishReason')
    content = candidate.get('content')
    parts = content.get('parts') if isinstance(content, dict) else None
    part_types = [sorted(part.keys()) if isinstance(part, dict) else type(part).__name__ for part in parts] if isinstance(parts, list) else []
    text_parts = [part['text'] for part in parts if isinstance(part, dict) and isinstance(part.get('text'), str)] if isinstance(parts, list) else []
    generated_text = '\n'.join(text_parts)
    _diagnostic(diagnostics, response=response, stage='candidate_ready',
                top_level_keys=sorted(envelope), candidate_count=candidate_count,
                finish_reason=finish_reason, part_types=part_types,
                generated_text_length=len(generated_text))

    if finish_reason in {'MAX_TOKENS', 'TOKEN_LIMIT'}:
        raise GeminiResponseError('Gemini summary output was truncated. Please retry.')
    if not generated_text.strip():
        raise GeminiResponseError('Gemini returned an empty summary candidate.')
    try:
        value = json.loads(generated_text)
    except json.JSONDecodeError as exc:
        _diagnostic(diagnostics, response=response, stage='candidate_json',
                    top_level_keys=sorted(envelope), candidate_count=candidate_count,
                    finish_reason=finish_reason, part_types=part_types,
                    generated_text_length=len(generated_text), error=exc)
        raise GeminiResponseError('Gemini returned malformed summary JSON.') from None
    if not isinstance(value, dict):
        raise GeminiResponseError('Gemini summary must be a JSON object.')
    if required_fields:
        for field, expected_type in required_fields.items():
            item = value.get(field)
            valid = isinstance(item, expected_type)
            if expected_type is list:
                valid = valid and all(isinstance(entry, str) for entry in item)
            if not valid:
                raise GeminiResponseError('Gemini summary is missing a required field or has an invalid field type.')
    return value
