"""
Simple bencode implementation that can be used as a fallback
if the bencode.py package has issues.
"""

class BTFailure(Exception):
    """Base exception for bencode errors"""
    pass

def encode(data):
    """Encode Python data structures into bencode format"""
    if isinstance(data, int):
        return f"i{data}e".encode()
    elif isinstance(data, str):
        return f"{len(data)}:{data}".encode()
    elif isinstance(data, bytes):
        return f"{len(data)}:".encode() + data
    elif isinstance(data, list):
        result = b"l"
        for item in data:
            result += encode(item)
        return result + b"e"
    elif isinstance(data, dict):
        result = b"d"
        # Sort keys for consistent encoding
        for key in sorted(data.keys()):
            # Bencode requires dict keys to be strings
            if isinstance(key, str):
                k = key.encode() if isinstance(key, str) else key
                result += encode(k)
                result += encode(data[key])
            elif isinstance(key, bytes):
                result += encode(key)
                result += encode(data[key])
            else:
                # Convert non-string keys to strings
                str_key = str(key)
                result += encode(str_key)
                result += encode(data[key])
        return result + b"e"
    else:
        raise BTFailure(f"Cannot encode {type(data)} objects")

def decode(data):
    """Decode bencode data into Python data structures"""
    if not isinstance(data, bytes):
        data = data.encode('utf-8')
        
    def parse_item(data, index):
        if data[index:index+1] == b'i':
            # Integer
            end = data.find(b'e', index)
            if end == -1:
                raise BTFailure("Invalid integer format")
            try:
                value = int(data[index+1:end])
                return value, end + 1
            except ValueError:
                raise BTFailure("Invalid integer format")
                
        elif data[index:index+1] == b'l':
            # List
            result = []
            index += 1
            while data[index:index+1] != b'e':
                item, index = parse_item(data, index)
                result.append(item)
            return result, index + 1
            
        elif data[index:index+1] == b'd':
            # Dictionary
            result = {}
            index += 1
            while data[index:index+1] != b'e':
                key, index = parse_item(data, index)
                value, index = parse_item(data, index)
                
                if isinstance(key, bytes):
                    try:
                        key = key.decode('utf-8')
                    except UnicodeDecodeError:
                        # Keep as bytes if not valid UTF-8
                        pass
                        
                result[key] = value
            return result, index + 1
            
        else:
            # String/bytes
            try:
                colon = data.find(b':', index)
                if colon == -1:
                    raise BTFailure("Invalid string format")
                    
                length = int(data[index:colon])
                string_data = data[colon+1:colon+1+length]
                
                if len(string_data) != length:
                    raise BTFailure(f"String length mismatch: expected {length}, got {len(string_data)}")
                    
                # Try to decode as UTF-8, fall back to bytes
                try:
                    return string_data.decode('utf-8'), colon + 1 + length
                except UnicodeDecodeError:
                    return string_data, colon + 1 + length
                    
            except ValueError:
                raise BTFailure("Invalid string length")
    
    try:
        result, _ = parse_item(data, 0)
        return result
    except Exception as e:
        raise BTFailure(f"Error decoding bencode data: {e}")
