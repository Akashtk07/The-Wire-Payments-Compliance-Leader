"""
Pytest tests for MT parser and MX translator.

Tests cover:
  - MT103 parsing success
  - MT103 → pacs.008 translation
  - MT202 → pacs.009 translation
  - MT202COV → pacs.009 with UndrlygCstmrCdtTrf block
  - MT202 with retail customer fields → ValidationException
"""

from __future__ import annotations

import asyncio
import sys
import os
import pytest

# Ensure the backend root is on the path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.mt_parser import SAMPLE_MT103, SAMPLE_MT202, SAMPLE_MT202COV, mt_parser
from services.mx_translator import ValidationException, mx_translator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(coro):
    """Run a coroutine synchronously in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Test 1: MT103 parse success
# ---------------------------------------------------------------------------


def test_mt103_parse_success():
    """Parsing SAMPLE_MT103 should return a dict with all key fields present."""
    result = mt_parser.parse(SAMPLE_MT103, "MT103")

    assert result["source_type"] == "MT103"
    assert "fields" in result
    assert "raw_tags" in result

    fields = result["fields"]

    # Required fields for MT103
    assert "transaction_reference" in fields, "Missing :20: transaction_reference"
    assert "bank_operation_code" in fields, "Missing :23B: bank_operation_code"
    assert "value_date_currency_amount" in fields, "Missing :32A: value_date_currency_amount"
    assert "ordering_customer" in fields, "Missing :50K: ordering_customer"
    assert "beneficiary_customer" in fields, "Missing :59: beneficiary_customer"
    assert "details_of_charges" in fields, "Missing :71A: details_of_charges"

    # Values should be non-empty strings
    assert fields["transaction_reference"]["value"].strip()
    assert fields["bank_operation_code"]["value"].strip()


# ---------------------------------------------------------------------------
# Test 2: MT103 → pacs.008
# ---------------------------------------------------------------------------


def test_mt103_to_pacs008():
    """Translating SAMPLE_MT103 should produce valid pacs.008 XML."""
    parsed = mt_parser.parse(SAMPLE_MT103, "MT103")
    xml_output, message_type = run(mx_translator.translate(parsed, "MT103"))

    assert message_type == "pacs.008.001.08"
    assert xml_output is not None
    assert len(xml_output) > 100

    # Namespace must be present
    assert "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08" in xml_output

    # Required XML elements
    assert "<Dbtr>" in xml_output, "pacs.008 must contain <Dbtr>"
    assert "<Cdtr>" in xml_output, "pacs.008 must contain <Cdtr>"
    assert "<IntrBkSttlmAmt" in xml_output, "pacs.008 must contain <IntrBkSttlmAmt>"
    assert "<UETR>" in xml_output, "pacs.008 must contain <UETR>"
    assert "<MsgId>" in xml_output, "pacs.008 must contain <MsgId>"


# ---------------------------------------------------------------------------
# Test 3: MT202 → pacs.009
# ---------------------------------------------------------------------------


def test_mt202_to_pacs009():
    """Translating SAMPLE_MT202 should produce valid pacs.009 XML."""
    parsed = mt_parser.parse(SAMPLE_MT202, "MT202")
    xml_output, message_type = run(mx_translator.translate(parsed, "MT202"))

    assert message_type == "pacs.009.001.08"
    assert xml_output is not None
    assert len(xml_output) > 100

    # Namespace must be present
    assert "urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08" in xml_output

    # Required XML elements for pacs.009
    assert "<IntrBkSttlmAmt" in xml_output, "pacs.009 must contain <IntrBkSttlmAmt>"
    assert "<UETR>" in xml_output, "pacs.009 must contain <UETR>"
    assert "<MsgId>" in xml_output, "pacs.009 must contain <MsgId>"

    # pacs.009 CORE must NOT have retail customer blocks
    assert "<UndrlygCstmrCdtTrf>" not in xml_output, (
        "pacs.009 CORE (MT202) must NOT contain <UndrlygCstmrCdtTrf>"
    )


# ---------------------------------------------------------------------------
# Test 4: MT202COV requires UndrlygCstmrCdtTrf
# ---------------------------------------------------------------------------


def test_mt202cov_requires_underlying_block():
    """MT202COV translation must produce <UndrlygCstmrCdtTrf> block."""
    parsed = mt_parser.parse(SAMPLE_MT202COV, "MT202COV")
    xml_output, message_type = run(mx_translator.translate(parsed, "MT202COV"))

    assert message_type == "pacs.009.001.08"
    assert "<UndrlygCstmrCdtTrf>" in xml_output, (
        "MT202COV translation must produce <UndrlygCstmrCdtTrf> block "
        "in the pacs.009 COV output"
    )


# ---------------------------------------------------------------------------
# Test 5: Prohibited field raises ValidationException
# ---------------------------------------------------------------------------


def test_prohibited_field_raises_validation_exception():
    """
    Injecting retail customer fields into an MT202 parsed dict should raise
    ValidationException when translating to pacs.009 CORE.
    """
    parsed = mt_parser.parse(SAMPLE_MT202, "MT202")

    # Inject a prohibited retail customer field — simulates a mis-tagged MT202
    parsed["fields"]["ordering_customer"] = {
        "tag": "50K",
        "value": "/GB29NWBK60161331926819\nACME CORP",
    }
    parsed["fields"]["beneficiary_customer"] = {
        "tag": "59",
        "value": "/US64SVBKUS6S3300622287\nJOHN DOE",
    }

    with pytest.raises(ValidationException) as exc_info:
        run(mx_translator.translate(parsed, "MT202"))

    exc = exc_info.value
    assert exc.message_type == "pacs.009.001.08"
    assert "CORE" in exc.message or "retail" in exc.message.lower() or "COV" in exc.message
    assert exc.action  # Action should be non-empty guidance


# ---------------------------------------------------------------------------
# Additional: MT202COV missing underlying block raises ValidationException
# ---------------------------------------------------------------------------


def test_mt202cov_missing_underlying_raises_validation_exception():
    """
    An MT202COV parsed dict with no underlying customer fields should raise
    ValidationException (COV variant requires UndrlygCstmrCdtTrf).
    """
    parsed = mt_parser.parse(SAMPLE_MT202, "MT202")
    # Manually set source_type to MT202COV but don't add customer fields
    parsed["source_type"] = "MT202COV"

    with pytest.raises(ValidationException) as exc_info:
        run(mx_translator.translate(parsed, "MT202COV"))

    exc = exc_info.value
    assert "UndrlygCstmrCdtTrf" in exc.field_name or "underlying" in exc.message.lower()
