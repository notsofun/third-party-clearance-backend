def get_license_descriptions(licenses, data_list, desc_type:str = 'description'):
    """
    Extract license descriptions from a nested dictionary list based on license names.
    
    Args:
        licenses (list): List of license names to search for
        data_list (list): List of dictionaries containing license information
    
    Returns:
        list: List of descriptions corresponding to the input licenses
    """
    # Create a mapping of license names to their descriptions
    license_map = {}
    
    for item in data_list:
        if not isinstance(item, dict):
            continue
            
        # Check if this dictionary has license information
        if "License" in item and "description" in item:
            license_name = item["License"]
            description = item[desc_type]
            
            # Add the description to our map (handle multiple descriptions per license)
            if license_name in license_map:
                if description not in license_map[license_name]:  # Avoid duplicates
                    license_map[license_name].append(description)
            else:
                license_map[license_name] = [description]
    
    # Retrieve descriptions for each requested license
    result = []
    for license_name in licenses:
        if license_name in license_map:
            # Join all descriptions for this license with a separator
            descriptions = license_map[license_name]
            result.append("\n\n".join(descriptions))
        else:
            result.append(f"No description found for license: {license_name}")
    
    return result

def list_to_string(desc_list:list) -> str:

    final_str = ''
    for i in desc_list:
        mid = '- ' + i + '\n\n'
        final_str += mid

    return final_str