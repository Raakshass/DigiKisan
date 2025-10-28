from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

class PriceDataModel(BaseModel):
    """Model for storing cached price data from AgMarkNet"""
    
    # AgMarkNet identifiers
    commodity_code: str = Field(..., description="AgMarkNet commodity code (e.g., '23' for wheat)")
    commodity_name: str = Field(..., description="Human readable commodity name")
    district_code: str = Field(..., description="AgMarkNet district code")
    district_name: str = Field(..., description="Human readable district name")
    market_name: str = Field(..., description="Market name")
    date: str = Field(..., description="Market date in YYYY-MM-DD format")
    
    # Price information
    modal_price: Optional[float] = Field(None, description="Modal price per quintal")
    min_price: Optional[float] = Field(None, description="Minimum price per quintal")
    max_price: Optional[float] = Field(None, description="Maximum price per quintal")
    
    # Metadata
    data_source: str = Field(default="agmarknet", description="Source of the data")
    scraped_at: datetime = Field(default_factory=datetime.now, description="When data was scraped")
    quality_score: float = Field(default=1.0, description="Data quality indicator (0-1)")
    
    class Config:
        # Allow ObjectId to be used
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }

class UserSessionModel(BaseModel):
    """Model for tracking user sessions and queries"""
    
    session_id: str = Field(..., description="Unique session identifier")
    user_ip: Optional[str] = Field(None, description="User IP address")
    user_agent: Optional[str] = Field(None, description="User browser/device info")
    
    # Current conversation state
    current_slots: dict = Field(default_factory=dict, description="Current slot filling state")
    conversation_history: List[dict] = Field(default_factory=list, description="Message history")
    session_state: str = Field(default="new", description="Current session state")
    
    # Timestamps
    started_at: datetime = Field(default_factory=datetime.now, description="Session start time")
    last_activity: datetime = Field(default_factory=datetime.now, description="Last activity time")
    completed_queries: int = Field(default=0, description="Number of completed queries")
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }

class QueryAnalyticsModel(BaseModel):
    """Model for tracking query analytics"""
    
    query_id: str = Field(..., description="Unique query identifier")
    session_id: Optional[str] = Field(None, description="Associated session ID")
    
    # Query details
    commodity: Optional[str] = Field(None, description="Queried commodity")
    district: Optional[str] = Field(None, description="Queried district")
    date_requested: Optional[str] = Field(None, description="Requested date")
    
    # Performance metrics
    response_time_ms: Optional[int] = Field(None, description="Query response time")
    data_source_used: str = Field(..., description="cached or scraped")
    success: bool = Field(True, description="Whether query was successful")
    
    # Geographic and temporal context
    timestamp: datetime = Field(default_factory=datetime.now, description="Query timestamp")
    time_of_day: str = Field(..., description="morning/afternoon/evening")
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
