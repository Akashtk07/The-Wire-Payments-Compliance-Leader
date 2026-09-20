"""
Deterministic SWIFT MT field parser.

Parses the block structure {1:…}{2:…}{3:…}{4:…}{5:…} and extracts
all relevant tagged fields for each supported MT message type.

Supported types:
    MT103, MT103STP           — Customer Credit Transfer (CBPR+)
    MT202, MT202COV           — FI Credit Transfer CORE/COV (CBPR+)
    MT204                     — FI Debit Advice (CBPR+)
    MT205, MT205COV           — Canadian domestic FI Transfer/Cover (LYNX legacy)
    MT103RETURN, MT202RETURN  — Payment Returns (CBPR+)
    MT205RETURN               — Payment Return (LYNX legacy)
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Sample MT103 for testing
# ---------------------------------------------------------------------------

SAMPLE_MT103 = (
    "{1:F01BANKGB2LAXXX0000000000}"
    "{2:I103BANKUS33XXXXN}"
    "{3:{108:MT103SAMPLEREF}}"
    "{4:\n"
    ":20:TXREF20260523001\n"
    ":23B:CRED\n"
    ":32A:260523USD10000,00\n"
    ":33B:USD10000,00\n"
    ":50K:/GB29NWBK60161331926819\n"
    "ACME CORPORATION\n"
    "1 HIGH STREET\n"
    "LONDON GB\n"
    ":52A:BARCGB22XXX\n"
    ":53B:/D/12345678\n"
    ":54A:CHASUS33XXX\n"
    ":57A:BOFAUS3NXXX\n"
    ":59:/US64SVBKUS6S3300622287\n"
    "JOHN DOE\n"
    "123 MAIN STREET\n"
    "NEW YORK US\n"
    ":70:INVOICE 2026-INV-001\n"
    ":71A:SHA\n"
    ":72:/BNF/PAYMENT FOR SERVICES\n"
    "-}"
    "{5:{CHK:ABCDEF012345}}"
)

SAMPLE_MT202 = (
    "{1:F01BANKGB2LAXXX0000000000}"
    "{2:I202BANKUS33XXXXN}"
    "{3:{108:MT202SAMPLEREF}}"
    "{4:\n"
    ":20:COVREF20260523001\n"
    ":21:TXREF20260523001\n"
    ":32A:260523USD10000,00\n"
    ":52A:BARCGB22XXX\n"
    ":53A:CHASUS33XXX\n"
    ":54A:CITIUS33XXX\n"
    ":57A:BOFAUS3NXXX\n"
    ":58A:WELLUS44XXX\n"
    "-}"
    "{5:{CHK:ABCDEF012345}}"
)

SAMPLE_MT202COV = (
    "{1:F01BANKGB2LAXXX0000000000}"
    "{2:I202BANKUS33XXXXN}"
    "{3:{108:MT202COVSAMPLEREF}}"
    "{4:\n"
    ":20:COVREF20260523002\n"
    ":21:TXREF20260523001\n"
    ":32A:260523USD10000,00\n"
    ":52A:BARCGB22XXX\n"
    ":53A:CHASUS33XXX\n"
    ":54A:CITIUS33XXX\n"
    ":57A:BOFAUS3NXXX\n"
    ":58A:WELLUS44XXX\n"
    ":50K:/GB29NWBK60161331926819\n"
    "ACME CORPORATION\n"
    ":59:/US64SVBKUS6S3300622287\n"
    "JOHN DOE\n"
    "-}"
    "{5:{CHK:ABCDEF012345}}"
)

# Payment Return sample — maps to pacs.004.001.09
SAMPLE_MT103RETURN = (
    "{1:F01BANKUS33XXXX0000000000}"
    "{2:I103BANKGB2LXXXXN}"
    "{3:{108:RETURNREF001}{121:f9e4a3b2-1c5d-4e7f-8a9b-0d1e2f3a4b5c}}"
    "{4:\n"
    ":20:RETREF20260523001\n"
    ":21:TXREF20260523001\n"
    ":32A:260523USD10000,00\n"
    ":52A:BOFAUS3NXXX\n"
    ":57A:BARCGB22XXX\n"
    ":58A:BANKGB2LXXX\n"
    ":72:/RETN/AM09\n"
    "-}"
    "{5:{CHK:ABCDEF012346}}"
)

SAMPLE_MT202RETURN = SAMPLE_MT103RETURN  # Reuse for sample purposes

# LYNX Canada domestic interbank sample (MT205 — same structure as MT202)
SAMPLE_MT205 = (
    "{1:F01ROYCCAT2XXXX0000000000}"
    "{2:I205TDOMCATTXXXXN}"
    "{3:{108:MT205SAMPLEREF}{121:a1b2c3d4-e5f6-4789-abcd-ef0123456789}}"
    "{4:\n"
    ":20:LYNXREF20260523001\n"
    ":21:RELREF20260523001\n"
    ":32A:260523CAD250000,00\n"
    ":52A:ROYCCAT2XXX\n"
    ":58A:TDOMCATTXXX\n"
    ":72:/LYNXSYS/RTGS-CAD-DOMESTIC\n"
    "-}"
    "{5:{CHK:ABCDEF012347}}"
)

# LYNX domestic cover payment sample (MT205COV)
SAMPLE_MT205COV = (
    "{1:F01ROYCCAT2XXXX0000000000}"
    "{2:I205TDOMCATTXXXXN}"
    "{3:{108:MT205COVSMPLREF}{119:COV}{121:b2c3d4e5-f6a7-4890-bcde-f01234567890}}"
    "{4:\n"
    ":20:LYNXCOV20260523001\n"
    ":21:UNDERLYING001\n"
    ":32A:260523CAD10000,00\n"
    ":52A:ROYCCAT2XXX\n"
    ":58A:TDOMCATTXXX\n"
    ":50K:/CA12345678901234567890\n"
    "ACME CORP CANADA\n"
    "TORONTO ON\n"
    ":59:/CA98765432109876543210\n"
    "JANE DOE\n"
    "VANCOUVER BC\n"
    ":72:/LYNXSYS/RTGS-CAD-COV\n"
    "-}"
    "{5:{CHK:ABCDEF012348}}"
)

# LYNX domestic return sample (MT205RETURN)
SAMPLE_MT205RETURN = (
    "{1:F01TDOMCATTXXXX0000000000}"
    "{2:I205ROYCCAT2XXXXN}"
    "{3:{108:LYNXRETREF001}{121:c3d4e5f6-a7b8-4901-cdef-012345678901}}"
    "{4:\n"
    ":20:LYNXRETREF001\n"
    ":21:LYNXREF20260523001\n"
    ":32A:260523CAD250000,00\n"
    ":52A:TDOMCATTXXX\n"
    ":58A:ROYCCAT2XXX\n"
    ":72:/RETN/AM09\n"
    "/LYNXSYS/RTGS-CAD-RETURN\n"
    "-}"
    "{5:{CHK:ABCDEF012349}}"
)

# ---------------------------------------------------------------------------
# Internal block-extraction helpers
# ---------------------------------------------------------------------------

_BLOCK_RE = re.compile(r"\{(\d):(.*?)\}", re.DOTALL)
_TAG_RE = re.compile(r":(\d{1,2}[A-Z]?):(.*?)(?=:\d{1,2}[A-Z]?:|$)", re.DOTALL)


def _extract_blocks(raw: str) -> Dict[str, str]:
    """Return {block_number: content} for blocks 1-5."""
    blocks: Dict[str, str] = {}
    for match in _BLOCK_RE.finditer(raw):
        num, content = match.group(1), match.group(2)
        blocks[num] = content.strip()
    return blocks


def _extract_block4_tags(block4: str) -> Dict[str, str]:
    """
    Extract all :TAG: fields from block 4, PRESERVING internal newlines.

    SWIFT MT multi-line fields use newlines to separate structural parts:
      Line 1 : /account-number   (for :50K:, :59:, :52A:, etc.)
      Line 2 : Name
      Line 3+: Address lines

    Collapsing these to spaces (old behaviour) destroyed the structure and
    caused broken name/address extraction — the root cause of PARTIAL status.
    We now keep newlines intact; downstream parsers split on '\\n'.
    Returns {tag: raw_value_with_preserved_newlines}.
    """
    # Normalise block: strip leading/trailing whitespace and the trailing dash
    text = block4.strip().rstrip("-").strip()
    tags: Dict[str, str] = {}

    # Split on tag boundaries (^:20:, ^:32A:, ^:50K:, etc.)
    pattern = re.compile(r"^:(\d{1,2}[A-Z]?C?):\s?", re.MULTILINE)
    positions = [(m.start(), m.group(1)) for m in pattern.finditer(text)]

    for i, (start, tag) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        # Value starts right after the :TAG: marker
        value_start = text.index(":", start) + len(tag) + 2  # skip :TAG:
        raw_value = text[value_start:end]

        # Normalize per-line trailing whitespace; drop blank lines at start/end
        # but KEEP newlines between content lines — they are semantically significant
        lines = [ln.rstrip() for ln in raw_value.split("\n")]
        # Remove leading blank lines (artefact of :TAG:\n)
        while lines and not lines[0].strip():
            lines.pop(0)
        # Remove trailing blank lines
        while lines and not lines[-1].strip():
            lines.pop()
        # Remove the trailing dash if it crept in as a last line
        if lines and lines[-1].strip() == "-":
            lines.pop()

        tags[tag] = "\n".join(lines)

    return tags



# ---------------------------------------------------------------------------
# Per-message-type field mappings
# ---------------------------------------------------------------------------

# Maps human-readable field names → one or more possible tag codes (first match wins)
_MT103_FIELDS: Dict[str, list[str]] = {
    "transaction_reference": ["20"],
    "bank_operation_code": ["23B"],
    "value_date_currency_amount": ["32A"],
    "instructed_amount": ["33B"],
    "ordering_customer": ["50K", "50A", "50F"],
    "ordering_institution": ["52A", "52D"],
    "sender_correspondent": ["53A", "53B", "53D"],
    "receiver_correspondent": ["54A", "54B", "54D"],
    "intermediary_institution": ["56A", "56D"],
    "account_with_institution": ["57A", "57B", "57D"],
    "beneficiary_customer": ["59", "59A", "59F"],
    "remittance_info": ["70"],
    "details_of_charges": ["71A"],
    "sender_to_receiver_info": ["72"],
}

_MT202_FIELDS: Dict[str, list[str]] = {
    "transaction_reference": ["20"],
    "related_reference": ["21"],
    "value_date_currency_amount": ["32A"],
    "ordering_institution": ["52A", "52D"],
    "sender_correspondent": ["53A", "53B", "53D"],
    "receiver_correspondent": ["54A", "54B", "54D"],
    "intermediary_institution": ["56A", "56D"],
    "account_with_institution": ["57A", "57B", "57D"],
    "beneficiary_institution": ["58A", "58D"],
}

_MT202COV_EXTRA: Dict[str, list[str]] = {
    "underlying_ordering_customer": ["50K", "50A", "50F"],
    "underlying_beneficiary": ["59", "59A", "59F"],
}

_MT204_FIELDS: Dict[str, list[str]] = {
    "transaction_reference": ["20"],
    "total_amount": ["19"],
    "account": ["25"],
    "account_with_institution": ["57A", "57B"],
}

_MT103RETURN_FIELDS: Dict[str, list[str]] = {
    "transaction_reference": ["20"],
    "related_reference": ["21"],
    "value_date_currency_amount": ["32A"],
    "ordering_institution": ["52A", "52D"],
    "account_with_institution": ["57A", "57B", "57D"],
    "beneficiary_institution": ["58A", "58D"],
    "sender_to_receiver_info": ["72"],  # :72: carries /RETN/ and return reason code
}


def _resolve_fields(
    tags: Dict[str, str],
    field_map: Dict[str, list[str]],
) -> Dict[str, Any]:
    """
    For each field name in field_map, find the first matching tag in `tags`
    and record both the tag code used and its value.
    """
    result: Dict[str, Any] = {}
    for field_name, candidates in field_map.items():
        for candidate in candidates:
            if candidate in tags:
                result[field_name] = {
                    "tag": candidate,
                    "value": tags[candidate],
                }
                break
    return result


# ---------------------------------------------------------------------------
# Public parser class
# ---------------------------------------------------------------------------


class MTParser:
    """Deterministic SWIFT MT block/field parser."""

    def parse(self, raw_mt: str, source_type: str) -> Dict[str, Any]:
        """
        Parse *raw_mt* according to *source_type*.

        Returns a structured dict containing:
          - `source_type`: the requested MT type
          - `blocks`: raw block content (1-5)
          - `fields`: resolved field name → {tag, value} mapping
          - `raw_tags`: all :TAG: values extracted from block 4

        Raises `ValueError` on unrecognised source_type or parse failure.
        """
        source_type = source_type.upper()
        supported = {
            "MT103", "MT103STP",
            "MT202", "MT202COV", "MT204",
            "MT205", "MT205COV",
            "MT103RETURN", "MT202RETURN", "MT205RETURN",
        }
        if source_type not in supported:
            raise ValueError(
                f"Unsupported source_type '{source_type}'. "
                f"Must be one of: {sorted(supported)}"
            )

        blocks = _extract_blocks(raw_mt)
        if "4" not in blocks:
            raise ValueError(
                "Block 4 not found in raw MT message. "
                "Ensure the message includes a {4:…} block."
            )

        raw_tags = _extract_block4_tags(blocks["4"])

        if not raw_tags:
            raise ValueError(
                "No tagged fields found in block 4. "
                "Message may be malformed or empty."
            )

        # Select field map
        if source_type in ("MT103", "MT103STP"):
            field_map = _MT103_FIELDS
        elif source_type in ("MT202", "MT205"):
            # MT205 is structurally identical to MT202 (LYNX domestic = same fields)
            field_map = _MT202_FIELDS
        elif source_type in ("MT202COV", "MT205COV"):
            # MT205COV mirrors MT202COV
            field_map = {**_MT202_FIELDS, **_MT202COV_EXTRA}
        elif source_type == "MT204":
            field_map = _MT204_FIELDS
        elif source_type in ("MT103RETURN", "MT202RETURN", "MT205RETURN"):
            field_map = _MT103RETURN_FIELDS
        else:
            raise ValueError(f"Unhandled source_type: {source_type}")

        fields = _resolve_fields(raw_tags, field_map)

        # For MT204, also collect all 20C / 32B debit sub-items
        if source_type == "MT204":
            fields["debit_items"] = self._parse_mt204_debit_items(raw_tags)

        # Parse block 1 header for basic BIC info
        block1 = blocks.get("1", "")
        sender_bic = self._extract_sender_bic(block1)

        return {
            "source_type": source_type,
            "sender_bic": sender_bic,
            "blocks": blocks,
            "fields": fields,
            "raw_tags": raw_tags,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_sender_bic(block1: str) -> str:
        """Extract the 12-character logical terminal address from block 1."""
        # Block 1 format: F01<LTAddress><SessionNum><SeqNum>
        # LTAddress is positions 3..14 (12 chars)
        if len(block1) >= 15:
            return block1[3:15]
        return block1

    @staticmethod
    def _parse_mt204_debit_items(raw_tags: Dict[str, str]) -> list[Dict[str, str]]:
        """
        MT204 can have multiple :20C: / :32B: pairs.
        Since our tag extractor takes the last seen value, we do a secondary pass.
        Returns a list of {ref, currency_amount} dicts.
        """
        # For simplicity, return any single 20C/32B found
        items = []
        if "20C" in raw_tags:
            items.append(
                {
                    "ref": raw_tags.get("20C", ""),
                    "currency_amount": raw_tags.get("32B", ""),
                }
            )
        return items


# Module-level convenience instance
mt_parser = MTParser()
