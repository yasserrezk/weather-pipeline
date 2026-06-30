import json

def save_json(data, filepath="data/raw/weather.json"):
    """Saves the provided data into a JSON file."""
    try:
        with open(filepath, "w") as file:
            json.dump(data, file, indent=4)  # Added indent for readability
        print(f"Data successfully saved to {filepath}")
    except IOError as e:
        print(f"Error saving file: {e}")
