from sqlalchemy import String,Boolean,Integer,DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped,mapped_column
from datetime import datetime
from ..db.session import Base

class URL(Base):
    __tablename__="urls"

    id:Mapped[int]=mapped_column(Integer,index=True,primary_key=True)
    original_url:Mapped[str]=mapped_column(String,nullable=False)
    short_code:Mapped[str]=mapped_column(String,nullable=False,unique=True,index=True)
    clicks:Mapped[int]=mapped_column(Integer,default=0)
    is_active:Mapped[bool]=mapped_column(Boolean,default=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())


