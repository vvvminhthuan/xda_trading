from datetime import datetime

class Embed:
    def __init__(self):
        self._title = None
        self._description = None
        self._color = None
        self._fields = []
        self._timestamp = datetime.utcnow().isoformat()
        self._footer = {"text": "Trading Bot System By XDA"}
        self._thumbnail = None

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value: str):
        if len(value.strip()) == 0:
            raise ValueError("Title không được rỗng")
        self._title = value
    
    @property
    def fields(self):
        return self._fields

    @fields.setter
    def fields(self, fields: list[dict]):
        if not isinstance(fields, list):
            raise TypeError("Field phải là một list các dict")
        # Validate từng item trong list
        validated_fields = []
        for i, field in enumerate(fields):
            if not isinstance(field, dict):
                raise TypeError(f"Field {i} phải là dict")
            
            # Validate required keys
            required_keys = ["name", "value", "inline"]
            for key in required_keys:
                if key not in field:
                    raise KeyError(f"Field {i} thiếu key '{key}'")
            
            # Validate types
            if not isinstance(field["name"], str):
                raise TypeError(f"Field {i} 'name' phải là string")
            if not isinstance(field["value"], str):
                raise TypeError(f"Field {i} 'value' phải là string")
            if not isinstance(field["inline"], bool):
                raise TypeError(f"Field {i} 'inline' phải là boolean")
            
            # Validate content
            if len(field["name"].strip()) == 0:
                raise ValueError(f"Field {i} 'name' không được rỗng") 
            if len(field["value"].strip()) == 0:
                raise ValueError(f"Field {i} 'value' không được rỗng")
            
            # Add validated field
            validated_fields.append({
                "name": field["name"].strip(),
                "value": field["value"].strip(), 
                "inline": field["inline"]
            })
        
        self._fields = validated_fields
    
    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, value: str):
        if len(value.strip()) == 0:
            raise ValueError("Description không được rỗng")
        self._description = value

    @property
    def timestamp(self):
        return self._timestamp
    
    @timestamp.setter
    def timestamp(self, value: str):
        try:
            # Validate format ISO8601
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            self._timestamp = value
        except ValueError:
            raise ValueError("Timestamp phải có định dạng ISO8601")
    
    @property
    def footer(self):
        return self._footer
    
    @footer.setter
    def footer(self, value: str):
        if len(value.strip()) == 0:
            raise ValueError("Footer text không được rỗng")
        self._footer = {"text": value}

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, value: int):
        if not isinstance(value, int):
            raise TypeError("Color phải là integer (hex code)")
        if value < 0 or value > 0xFFFFFF:
            raise ValueError("Color phải là integer từ 0 đến 0xFFFFFF")
        self._color = value

    @property
    def thumbnail(self):
        return self._thumbnail
    
    @thumbnail.setter
    def thumbnail(self, value: str):
        self._thumbnail = {"url": value}

    def __call__(self):
        return {
            "title": self._title,
            "description": self._description,
            "color": self._color,
            "fields": self._fields,
            "timestamp": self._timestamp,
            "footer": self._footer,
            "thumbnail": self._thumbnail
        }