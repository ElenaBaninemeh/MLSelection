import xml.etree.ElementTree as ET
import json
import os

def parse_xml_to_json(xml_file):
    # Parse the XML file
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    # Automatically determine the root key based on the XML structure
    root_key = root.tag
    
    # Initialize the JSON structure
    json_data = {
        root_key: {
            "problemDescription": "",
            "qualityAttributes": {},
            "features": {},
            "alternatives": {}
        }
    }
    
    # Dictionaries to store node information
    qualities = {}
    features = {}
    alternatives = {}
    non_boolean_feature_values = {}
    
    # Helper function to extract parent relationships and quality impacts
    def extract_parents_and_impacts(node):
        parent_ids = []
        impact_ids = []
        values = {}
        
        for link in node.findall("link"):
            parent_id = link.attrib.get("Parent")
            value = link.attrib.get("Value")
            if value == "1":
                impact_ids.append(parent_id)
            parent_ids.append(parent_id)
            values[parent_id] = value if value else None
        
        return parent_ids, impact_ids, values

    # Step 1: Process Characteristics
    for node in root.findall("node"):
        level = node.attrib.get("Level")
        if level == "Characteristic":
            node_id = node.attrib["ID"]
            title = node.attrib["Title"]
            description = node.attrib.get("Description", "")
            qualities[node_id] = {
                "name": title,
                "description": description,
                "type": "Characteristic",
                "parent": []
            }

    # Step 2: Process Subcharacteristics
    for node in root.findall("node"):
        level = node.attrib.get("Level")
        if level == "Subcharacteristic":
            node_id = node.attrib["ID"]
            title = node.attrib["Title"]
            description = node.attrib.get("Description", "")
            parent_ids, _, _ = extract_parents_and_impacts(node)
            parent_names = [qualities[pid]["name"] for pid in parent_ids if pid in qualities]
            
            qualities[node_id] = {
                "name": title,
                "description": description,
                "type": "Subcharacteristic",
                "parent": parent_names
            }

    # Step 3: Process Features and Subfeatures
    for node in root.findall("node"):
        level = node.attrib.get("Level")
        data_type = node.attrib.get("DataType", "")
        
        if level == "Feature":
            node_id = node.attrib["ID"]
            title = node.attrib["Title"]
            description = node.attrib.get("Description", "")
            category = node.attrib.get("Order", "NULL")
            upper_level = node.attrib.get("UpperLevel", "NULL")
            
            parent_feature = features.get(upper_level, {}).get("name") if upper_level != "NULL" else None
            parent_ids, impact_ids, _ = extract_parents_and_impacts(node)
            impacted_qualities = [qualities[pid]["name"] for pid in impact_ids if pid in qualities]
            
            features[node_id] = {
                "name": title,
                "dataType": data_type,
                "description": description,
                "category": category if category != "NULL" else "",
                "impactedQualities": impacted_qualities,
                "parentFeature": parent_feature
            }
            features[node_id] = {k: v for k, v in features[node_id].items() if v is not None}

    # Step 4: Process Alternatives
    for node in root.findall("node"):
        level = node.attrib.get("Level")
        if level == "Alternative":
            node_id = node.attrib["ID"]
            title = node.attrib["Title"]
            description = node.attrib.get("Description", "")
            
            parent_ids, _, values = extract_parents_and_impacts(node)
            boolean_features = [features[pid]["name"] for pid in parent_ids if pid in features and features[pid]["dataType"] == "Boolean"]
            non_boolean_features = {}
            
            for pid in parent_ids:
                if pid in features and features[pid]["dataType"] != "Boolean":
                    try:
                        non_boolean_features[features[pid]["name"]] = float(values[pid]) if values[pid] not in (None, '', 'N/A') else 0
                    except ValueError:
                        non_boolean_features[features[pid]["name"]] = 0
            
            for feature, value in non_boolean_features.items():
                if feature not in non_boolean_feature_values:
                    non_boolean_feature_values[feature] = []
                non_boolean_feature_values[feature].append(value)
            
            alternatives[title] = {
                "url": description,
                "supportedBooleanFeatures": boolean_features,
                "supportedNonBooleanFeatures": non_boolean_features
            }

    # Normalize non-Boolean features
    for feature, values in non_boolean_feature_values.items():
        min_val, max_val = min(values), max(values)
        for alt_name, alt_info in alternatives.items():
            if feature in alt_info["supportedNonBooleanFeatures"]:
                original_value = alt_info["supportedNonBooleanFeatures"][feature]
                normalized_value = (original_value - min_val) / (max_val - min_val) if max_val > min_val else 1.0
                alt_info["supportedNonBooleanFeatures"][feature] = normalized_value

    # Populate JSON structure
    for node_id, quality in qualities.items():
        json_data[root_key]["qualityAttributes"][quality["name"]] = {
            "type": quality["type"],
            "description": quality["description"],
            "parent": quality["parent"]
        }

    for node_id, feature in features.items():
        json_data[root_key]["features"][feature["name"]] = {
            "dataType": feature["dataType"],
            "description": feature["description"],
            "category": feature["category"],
            "impactedQualities": feature["impactedQualities"],
            "parentFeature": feature.get("parentFeature")
        }

    json_data[root_key]["alternatives"] = alternatives
    return json_data

# Convert and save as JSON file
def convert_and_save(xml_file):
    # Parse XML and get JSON structure
    json_data = parse_xml_to_json(xml_file)
    
    # Set JSON file name based on input XML file name
    json_file = os.path.splitext(xml_file)[0] + '.json'
    
    # Write JSON data to file
    with open(json_file, 'w') as f:
        json.dump(json_data, f, indent=4)
    print(f"Data saved to {json_file}")

# Usage example
xml_file_path = 'SWAP_KB.xml'  # Ensure this file is in the current directory
convert_and_save(xml_file_path)
