from utils.itemFilter import ContentNormalizer

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
        if "License" in item and desc_type in item:
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
    seen_descriptions = set()
    
    for license_name in licenses:
        if isinstance(license_name, dict):
            license_name = license_name['name']

        for key in license_map.keys():
            lic_list = ContentNormalizer.remove_n(key)
            if license_name in lic_list:
                # Join all descriptions for this license with a separator
                descriptions = license_map[key]
                joined_desc = "\n\n".join(descriptions)
                
                # 去重检查
                if joined_desc not in seen_descriptions:
                    result.append(joined_desc)
                    seen_descriptions.add(joined_desc)
    
    return result

def list_to_string(desc_list:list) -> str:

    final_str = ''
    for i in desc_list:
        if isinstance(i, dict):
            i = i['content']

        mid = '- ' + i + '\n\n'
        final_str += mid

    return final_str