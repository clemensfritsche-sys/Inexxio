from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ItemNameCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)


class ItemNameResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    is_active: bool
    created_at: datetime


class ItemSurfaceCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)


class ItemSurfaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    is_active: bool
    created_at: datetime


class ItemCategoryCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)


class ItemCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    is_active: bool
    created_at: datetime
