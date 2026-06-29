from pydantic import BaseModel ,Field
from typing import Optional , Literal 

ActionType=Literal["SEARCH","TURN","STOP"]
class RobotCommand(BaseModel):
    action: ActionType
    x: Optional[float] = Field(default=None , ge=0.0, le=1.0)
    y: Optional[float] = Field(default=None , ge=0.0, le=1.0)
    distance: Optional[float] = None 
    angle: Optional[float] = None

# Visual team soll einen normalisierten X(auch Y) zwischen 0.0 und 1.0 
# actions sind "SEARCH","TURN","STOP" (momentan, könnte später erweitert werden)
# eigentlich ist Y hier noch nicht verwendet in Navigation , vielleicht später