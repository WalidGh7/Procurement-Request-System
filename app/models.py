import re
from typing import Literal

from pydantic import BaseModel, field_validator, Field

from app.data.commodity_groups import COMMODITY_GROUPS

# Valid commodity group IDs
VALID_COMMODITY_IDS = {g["id"] for g in COMMODITY_GROUPS}

# VAT ID patterns for common formats (EU countries, US EIN, etc.)
VAT_ID_PATTERN = re.compile(
    r"^("
    r"[A-Z]{2}[0-9A-Z]{2,13}|"  # EU VAT (e.g., DE123456789, ATU12345678)
    r"[0-9]{2}-[0-9]{7}|"        # US EIN (e.g., 12-3456789)
    r"[0-9]{9,12}"               # Generic numeric (9-12 digits)
    r")$"
)


class OrderLine(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    unit_price: float = Field(..., gt=0, description="Must be greater than 0")
    amount: int = Field(..., gt=0, description="Must be greater than 0")
    unit: str = Field(..., min_length=1, max_length=50)
    total_price: float = Field(..., gt=0)


class ProcurementRequest(BaseModel):
    requestor_name: str = Field(..., min_length=1, max_length=200)
    title: str = Field(..., min_length=1, max_length=500)
    vendor_name: str = Field(..., min_length=1, max_length=200)
    vat_id: str = Field(..., min_length=1, max_length=20)
    commodity_group_id: str
    order_lines: list[OrderLine] = Field(..., min_length=1)
    total_cost: float = Field(..., gt=0)
    department: str = Field(..., min_length=1, max_length=100)

    @field_validator("vat_id")
    @classmethod
    def validate_vat_id(cls, v: str) -> str:
        """Validate VAT ID format"""
        v_clean = v.strip().upper().replace(" ", "")
        if not VAT_ID_PATTERN.match(v_clean):
            raise ValueError(
                "Invalid VAT ID format. Expected formats: "
                "EU VAT (e.g., DE123456789), US EIN (e.g., 12-3456789), "
                "or 9-12 digit number"
            )
        return v_clean

    @field_validator("commodity_group_id")
    @classmethod
    def validate_commodity_group(cls, v: str) -> str:
        """Validate commodity_group_id exists"""
        if v not in VALID_COMMODITY_IDS:
            raise ValueError(
                f"Invalid commodity_group_id '{v}'. "
                f"Must be one of the valid commodity group IDs (001-050)"
            )
        return v



class StatusUpdate(BaseModel):
    status: Literal["Open", "In Progress", "Closed"]
