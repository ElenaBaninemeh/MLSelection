import re
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import os
from itertools import combinations
from collections import defaultdict

#-------------------------------------------------------------------------------------------------------------

PRIORITY_WEIGHTS = {
    "must": 1.0,
    "should": 0.7,
    "could": 0.3,
    "wont": 1.0
}

VALUE_MAPPING = {
    "None": 0,
    "Low": 0,
    "Medium": 0.5,
    "High": 1.0
}

#-------------------------------------------------------------------------------------------------------------
def load_dss_config():
    """
    Loads and returns the contents of dss-config.json as a Python variable.
    """
    config_path = os.path.join(settings.BASE_DIR, 'static', 'DSS-config', 'dss-config.json')

    try:
        # Open and load JSON file contents
        with open(config_path, 'r') as config_file:
            data = json.load(config_file)
        
        # Return data as a Python variable (list of dictionaries)
        return data

    except FileNotFoundError:
        print(f"Error: File not found at path {config_path}")
        return []

    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in file at path {config_path}")
        return []
#-------------------------------------------------------------------------------------------------------------
def load_feature_data(filename):
    json_path = os.path.join(settings.BASE_DIR, 'static', 'KB/JSON', filename)
    with open(json_path, 'r') as json_file:
        data = json.load(json_file)
    root_key = list(data.keys())[0]
    return data, root_key
#-------------------------------------------------------------------------------------------------------------
PRIORITY_WEIGHTS = {
    "must": 1.0,
    "should": 0.7,
    "could": 0.3,
    "wont": 1.0
}

VALUE_MAPPING = {
    "None": 0,
    "Low": 0,
    "Medium": 0.5,
    "High": 1.0
}

#-------------------------------------------------------------------------------------------------------------
def generate_feasible_alternative_combinations(feasible_alternatives, must_features, wont_features, feature_data, alternatives):
    """
    Generates feasible alternative combinations by progressively combining alternatives (from 2 up to 5),
    stopping once five combinations with scores above 90% are found.
    """
    if feasible_alternatives:
        print("Feasible alternatives already exist. No need to combine.")
        return []

    feasible_combinations = []
    evaluated_combinations = set()  # To avoid duplicate evaluations
    found_high_score_combinations = 0  # To count combinations with scores above 90%

    # Filter alternatives with the "feasibleCombinations" key
    combinable_alternatives = {
        name: info for name, info in alternatives.items() if 'feasibleCombinations' in info
    }
    print(f"Number of alternatives that can be combined: {len(combinable_alternatives)}")

    # Generate combinations, starting from pairs and increasing group size up to 5
    for group_size in range(2, 6):
        for group in combinations(combinable_alternatives.keys(), group_size):
            sorted_combination = tuple(sorted(group))
            if sorted_combination in evaluated_combinations:
                continue
            evaluated_combinations.add(sorted_combination)

            combined_boolean_features = set()
            combined_non_boolean_features = {}
            for alt_name in group:
                alt_info = combinable_alternatives[alt_name]
                combined_boolean_features.update(alt_info.get('supportedBooleanFeatures', []))
                
                # For non-Boolean features, take the maximum value across alternatives
                for feature, value in alt_info.get('supportedNonBooleanFeatures', {}).items():
                    combined_non_boolean_features[feature] = max(
                        combined_non_boolean_features.get(feature, 0), value
                    )

            # Check "must" and "wont" feature constraints
            if all(feature in combined_boolean_features for feature in must_features) and \
               not any(feature in combined_boolean_features for feature in wont_features):
                
                # Check non-Boolean feature requirements for "must" and "wont" constraints
                must_valid = all(
                    feature in feature_data and feature_data[feature].get('dataType') != 'Boolean' and
                    combined_non_boolean_features.get(feature, 0) >= VALUE_MAPPING.get(feature_data[feature].get('value'), 0)
                    for feature in must_features if feature in feature_data
                )
                wont_valid = all(
                    feature in feature_data and feature_data[feature].get('dataType') != 'Boolean' and
                    combined_non_boolean_features.get(feature, float('inf')) <= VALUE_MAPPING.get(feature_data[feature].get('value'), float('inf'))
                    for feature in wont_features if feature in feature_data
                )

                if must_valid and wont_valid:
                    score = calculate_combination_score(combined_boolean_features, combined_non_boolean_features, feature_data)
                    
                    if score >= 0:
                        # Construct the feasible combination entry
                        combined_name = " + ".join(sorted(group))
                        feasible_combination = {
                            "url": combined_name,
                            "supportedBooleanFeatures": list(combined_boolean_features),
                            "supportedNonBooleanFeatures": combined_non_boolean_features,
                            "score": score
                        }

                        feasible_combinations.append(feasible_combination)
                        found_high_score_combinations += 1

                        # Stop if we have five high-scoring combinations
                        if found_high_score_combinations >= 5:
                            print(f"Found five feasible combinations with scores above 90% at group size {group_size}.")
                            return feasible_combinations

    print(f"Total feasible combinations found: {len(feasible_combinations)}")
    return feasible_combinations

def calculate_combination_score(boolean_features, non_boolean_features, feature_data):
    """
    Calculates a score for a combination of alternatives based on the presence of "should" and "could" requirements.
    """
    score = 0
    for feature, req_info in feature_data.items():
        priority = req_info.get('priority', '').lower()
        feature_weight = PRIORITY_WEIGHTS.get(priority, 0)

        # Score based on the presence of "should" and "could" features
        if priority in ["should", "could"]:
            if feature in boolean_features or (feature in non_boolean_features and 
                non_boolean_features.get(feature) >= VALUE_MAPPING.get(req_info.get('value'), 0)):
                score += feature_weight

    # Normalize the score to a 0-100 scale
    return (score / sum(PRIORITY_WEIGHTS.get(k, 0) for k in ["should", "could"])) * 100 if PRIORITY_WEIGHTS else 0





#-------------------------------------------------------------------------------------------------------------

@csrf_exempt
def evaluate(request):
    """
    Evaluates the feature data sent by the client.
    Expects JSON data with 'fileInfo' (containing title and filename) 
    and 'featureData' (containing feature requirements).
    """

    print("evaluation page")


    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        # Parse the JSON data from the request
        data = json.loads(request.body)

        items = load_dss_config()

        # Retrieve file information and feature requirements separately
        file_info = data.get('fileInfo', {})
        feature_data = data.get('featureData', {})

        # Extract title and filename from file_info
        filename = file_info.get('filename')
        selected_title = file_info.get('title')

        # Ensure filename is provided
        if not filename:
            return JsonResponse({'status': 'error', 'message': 'Filename not provided in request.'}, status=400)

        # Construct the path to the JSON file
        json_path = os.path.join(settings.BASE_DIR, 'static', 'KB', 'JSON', filename)

        # Check if the JSON file exists
        if not os.path.exists(json_path):
            return JsonResponse({'status': 'error', 'message': f"File '{filename}' not found on server."}, status=404)

        # Load the JSON data from the file
        try:
            feature_data_from_file, root_key = load_feature_data(filename)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON format in feature file.'}, status=400)

        # Extract necessary sections for evaluation
        features = feature_data_from_file[root_key].get('features', {})
        quality_attributes = feature_data_from_file[root_key].get('qualityAttributes', {})
        alternatives = feature_data_from_file[root_key].get('alternatives', {})



        # Step 1: Identify "must-have" and "won't-have" features based on priority
        must_features = [
            f for f, v in feature_data.items()
            if isinstance(v, dict) and v.get('priority', '').lower() == 'must'
        ]
        wont_features = [
            f for f, v in feature_data.items()
            if isinstance(v, dict) and v.get('priority', '').lower() == 'wont'
        ]

        # Step 2: Filter feasible alternatives based on "must-have" and "won't-have" requirements
        feasible_alternatives = filter_feasible_alternatives(alternatives, must_features, wont_features, feature_data, features)

        # Step 3: Calculate characteristic weights for features based on their priority
        characteristic_weights = calculate_characteristic_weights(feature_data, features, quality_attributes)

        # Step 4: Calculate feature impact factors based on the calculated characteristic weights
        feature_impact_factors = calculate_feature_importance(feature_data, features, characteristic_weights, quality_attributes)

        # Step 5: Calculate scores for each feasible alternative based on feature impact factors
        alternative_scores = calculate_alternative_scores(feasible_alternatives, feature_data, feature_impact_factors, alternatives)

        # Step 6: Organize supported features by type for each feasible alternative
        supported_features_by_type = get_supported_features_by_type(feasible_alternatives, feature_data, alternatives)

        #step 7: graph graph visualization generaion
        nodes,edges = graph_visualization_generation(feasible_alternatives, feature_data, quality_attributes, features, alternatives)

        #print("Combination generation started!")
        # Step 7: Generate combined feasible alternative combinations
        #combined_feasible_alternative_combinations = generate_feasible_alternative_combinations(
        #    feasible_alternatives, must_features, wont_features, feature_data, alternatives
        #)

        #print("Combination generation finished!")

        #print({'combined_feasible_alternative_combinations': combined_feasible_alternative_combinations})

        # Return the processed results as a JSON response

        print(feasible_alternatives)

        return JsonResponse({
            'status': 'success',
            'characteristic_weights': characteristic_weights,
            'feature_impact_factors': feature_impact_factors,
            'feasible_alternatives': feasible_alternatives,
            'alternative_scores': alternative_scores,
            'supported_features_by_type': supported_features_by_type,
            'feature_requirements': feature_data,  # Original feature requirements for reference
            'graph_visualization': {"nodes":nodes,"edges":edges}
            #'combined_feasible_alternative_combinations': combined_feasible_alternative_combinations
        })

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON format in request body.'}, status=400)
    except TypeError as e:
        print(f"TypeError encountered: {e}")
        return JsonResponse({'status': 'error', 'message': f'Unhandled error: {e}'}, status=500)
    except Exception as e:
        print(f"Unhandled exception: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f'Unhandled error: {str(e)}'}, status=500)

#-------------------------------------------------------------------------------------------------------------
def filter_feasible_alternatives(alternatives, must_features, wont_features, feature_requirements, features):
    feasible_alternatives = []

    if (len(must_features) ==0  and len( wont_features) == 0):
        print(alternatives)
        return alternatives



    for alt_name, alt_info in alternatives.items():
        # Boolean "must" feature check
        for feature in must_features:
            if features[feature]['dataType'] == "Boolean":
                if feature not in alt_info['supportedBooleanFeatures']:
                    #print(f"{alt_name} excluded due to missing Boolean 'must' feature '{feature}'.")
                    break  # Skip to the next alternative
        else:
            # Non-Boolean "must" feature check
            for feature in must_features:
                if features[feature]['dataType'] != "Boolean":
                    req_value = feature_requirements[feature].get('value')
                    alt_value = alt_info['supportedNonBooleanFeatures'].get(feature)

                    # Normalize values using VALUE_MAPPING if they are strings
                    req_value = VALUE_MAPPING.get(req_value, req_value) if isinstance(req_value, str) else req_value
                    alt_value = VALUE_MAPPING.get(alt_value, alt_value) if isinstance(alt_value, str) else alt_value

                    #print(f"Checking non-Boolean 'must' feature '{feature}' for '{alt_name}': required = {req_value}, alternative = {alt_value}")
                    
                    # Exclude if the alternative's value is lower than required for "must" features
                    if req_value is not None and (alt_value is None or req_value > alt_value):
                        #print(f"{alt_name} excluded due to non-Boolean 'must' feature '{feature}' (requirement not met).")
                        break
            else:
                # Boolean "won't" feature check
                for feature in wont_features:
                    if features[feature]['dataType'] == "Boolean" and feature in alt_info['supportedBooleanFeatures']:
                        #print(f"{alt_name} excluded due to supported Boolean 'won't' feature '{feature}'.")
                        break
                else:
                    # Non-Boolean "won't" feature check
                    for feature in wont_features:
                        if features[feature]['dataType'] != "Boolean":
                            req_value = feature_requirements[feature].get('value')
                            alt_value = alt_info['supportedNonBooleanFeatures'].get(feature)

                            # Normalize values using VALUE_MAPPING if they are strings
                            req_value = VALUE_MAPPING.get(req_value, req_value) if isinstance(req_value, str) else req_value
                            alt_value = VALUE_MAPPING.get(alt_value, alt_value) if isinstance(alt_value, str) else alt_value

                            #print(f"Checking non-Boolean 'won't' feature '{feature}' for '{alt_name}': required = {req_value}, alternative = {alt_value}")
                            
                            # Exclude if the alternative's value is higher than allowed for "wont" features
                            if alt_value is not None and req_value is not None and alt_value >= req_value:
                                #print(f"{alt_name} excluded due to non-Boolean 'won't' feature '{feature}' (requirement not met).")
                                break
                    else:
                        # If all checks pass, add alternative to feasible list
                        feasible_alternatives.append(alt_name)

    return feasible_alternatives


#-------------------------------------------------------------------------------------------------------------

def calculate_alternative_scores(feasible_alternatives, feature_requirements, feature_impact_factors, alternatives):
    alternative_scores = {}
    max_possible_score = sum(feature_impact_factors.values())  # Total score if all features are fully supported

    for alt_name in feasible_alternatives:
        alt_info = alternatives.get(alt_name)
        if alt_info is None:
            continue

        score = max_possible_score  # Start with the maximum possible score

        # Deduct points based on unmet feature requirements
        for feature, req_info in feature_requirements.items():
            priority = req_info.get('priority', '').lower()  # Handle missing priorities
            feature_score = feature_impact_factors.get(feature, 0)

            if priority in ["should", "could"]:
                # Check if the feature is supported as a Boolean feature
                if feature in alt_info.get('supportedBooleanFeatures', []):
                    continue  # No deduction, feature is supported

                # Check if the feature is supported as a non-Boolean feature with the required value
                elif feature in alt_info.get('supportedNonBooleanFeatures', {}):
                    alt_value = VALUE_MAPPING.get(alt_info['supportedNonBooleanFeatures'].get(feature), 0)
                    req_value = VALUE_MAPPING.get(req_info.get('value'), 0)
                    if req_value <= alt_value:
                        continue  # No deduction, non-Boolean feature requirement is met

                # Deduct feature score if neither Boolean nor non-Boolean conditions are met
                score -= feature_score

            elif priority == 'wont':
                # Penalize if a "wont" feature is found among supported features
                if feature in alt_info.get('supportedBooleanFeatures', []):
                    score -= feature_score
                elif feature in alt_info.get('supportedNonBooleanFeatures', {}):
                    alt_value = VALUE_MAPPING.get(alt_info['supportedNonBooleanFeatures'].get(feature), 0)
                    req_value = VALUE_MAPPING.get(req_info.get('value'), 0)
                    if alt_value > req_value:
                        score -= feature_score  # Deduct if non-Boolean "wont" condition is not met

        # Normalize the score as a percentage of the max possible score
        alternative_scores[alt_name] = (score / max_possible_score) * 100 if max_possible_score > 0 else 0

    return alternative_scores

#-------------------------------------------------------------------------------------------------------------

def get_supported_features_by_type(feasible_alternatives, feature_requirements, alternatives):
    supported_features_by_type = {}

    for alt_name in feasible_alternatives:
        alt_info = alternatives.get(alt_name)
        if alt_info is None:
            continue

        # Use set to eliminate any duplicates within the Boolean features
        supported_boolean = set(alt_info.get('supportedBooleanFeatures', []))
        supported_non_boolean = alt_info.get('supportedNonBooleanFeatures', {})

        # Filter features according to feature_requirements to avoid redundancies
        boolean_features_in_requirements = [
            feature for feature in supported_boolean if feature in feature_requirements
        ]
        non_boolean_features_in_requirements = {
            feature: value for feature, value in supported_non_boolean.items() if feature in feature_requirements
        }


        # Separate "won't" features based on priority in feature_requirements
        wont_features = [
            feature for feature in feature_requirements
            if feature_requirements[feature].get('priority') == 'wont'
        ]


        # Store filtered features without duplicates
        supported_features_by_type[alt_name] = {
            'boolean_features': sorted(boolean_features_in_requirements),
            'non_boolean_features': non_boolean_features_in_requirements,
            'wont_features': wont_features
        }

    return supported_features_by_type 


#-------------------------------------------------------------------------------------------------------------

def calculate_characteristic_weights(data, features, quality_attributes):
    subchar_weights = {}
    for feature_name, feature_info in data.items():
        priority = feature_info['priority']
        weight = PRIORITY_WEIGHTS.get(priority, 0)
        impacted_qualities = features[feature_name].get('impactedQualities', [])
        for subchar in impacted_qualities:
            subchar_weights[subchar] = subchar_weights.get(subchar, 0) + weight

    characteristic_weights = {}
    for subchar, weight in subchar_weights.items():
        parent_char = quality_attributes[subchar]['parent'][0]
        characteristic_weights[parent_char] = characteristic_weights.get(parent_char, 0) + weight

    total_weight = sum(characteristic_weights.values())
    return {k: v / total_weight for k, v in characteristic_weights.items()} if total_weight > 0 else characteristic_weights

#-------------------------------------------------------------------------------------------------------------

def calculate_feature_importance(data, features, characteristic_weights, quality_attributes):
    subchar_weights = propagate_subcharacteristic_weights(characteristic_weights, quality_attributes)
    feature_impact_factors = {}
    for feature_name, feature_info in data.items():
        impacted_qualities = features[feature_name].get('impactedQualities', [])
        impact_factor = sum(subchar_weights[subchar] for subchar in impacted_qualities if subchar in subchar_weights)
        feature_impact_factors[feature_name] = impact_factor

    total_feature_weight = sum(feature_impact_factors.values())
    return {k: (v / total_feature_weight) * 100 for k, v in feature_impact_factors.items()} if total_feature_weight > 0 else feature_impact_factors

#-------------------------------------------------------------------------------------------------------------

def propagate_subcharacteristic_weights(characteristic_weights, quality_attributes):
    subchar_weights = {}
    for subchar, attr_info in quality_attributes.items():
        if 'parent' in attr_info and attr_info['parent']:
            parent_char = attr_info['parent'][0]
            if parent_char in characteristic_weights:
                related_subchars = [
                    sub for sub, info in quality_attributes.items()
                    if 'parent' in info and info['parent'] and info['parent'][0] == parent_char
                ]
                if related_subchars:
                    subchar_weight = characteristic_weights[parent_char] / len(related_subchars)
                    subchar_weights[subchar] = subchar_weight
    return subchar_weights

#-------------------------------------------------------------------------------------------------------------
@csrf_exempt
def load_features(request, filename="index.json"):
    if request.method == 'POST':
        items=load_dss_config()
        selected_title = request.POST.get('title')
        decision_model_path = next(
            (item['decisionModel_path'] for item in items if item.get('title') == selected_title and 'decisionModel_path' in item),
            filename  # Default to filename if path is not found
        )

        json_path = os.path.join(settings.BASE_DIR, 'static', 'KB', 'JSON', decision_model_path)
        
        print (json_path)

        try:
            with open(json_path, 'r') as json_file:
                data = json.load(json_file)
            root_key = list(data.keys())[0]
            features = data.get(root_key, {}).get("features", {})

            # Logging to check loaded data
            print(f"Loaded data for {selected_title}: {len(features)} features loaded.")
            print(decision_model_path)

            return render(request, 'DSS/requirements_analysis_and_decision_making.html', {
                'features': json.dumps(features),
                'selected_filename': decision_model_path
            })

        except FileNotFoundError:
            return render(request, 'DSS/requirements_analysis_and_decision_making.html', {
                'error': f"File not found at path: {json_path}"
            })
        except json.JSONDecodeError:
            return render(request, 'DSS/requirements_analysis_and_decision_making.html', {
                'error': f"Invalid JSON format in file: {decision_model_path}"
            })

    return render(request, 'DSS/requirements_analysis_and_decision_making.html', {'error': 'Invalid request. Only POST requests are accepted.'})

#-------------------------------------------------------------------------------------------------------------
@csrf_exempt
def view_decision_model(request):
    if request.method == 'POST':
        title = request.POST.get('title')

        # Load configuration and JSON data as before
        items = load_dss_config()
        decision_model_path = next(
            (item['decisionModel_path'] for item in items if item.get('title') == title and 'decisionModel_path' in item),
            'index.json'  # Default to 'index.json' if path is not found
        )

        json_path = os.path.join(settings.BASE_DIR, 'static', 'KB', 'JSON', decision_model_path)
        
        try:
            with open(json_path, 'r') as json_file:
                data = json.load(json_file)
            root_key = list(data.keys())[0]
            features = data.get(root_key, {}).get("features", {})
            alternatives = data.get(root_key, {}).get("alternatives", {})

            # Process alternatives to add feature descriptions
            modified_alternatives = {}
            for alt_name, alt_info in alternatives.items():
                modified_alternatives[alt_name] = {
                    "url": alt_info.get("url", ""),
                    "supportedBooleanFeatures": [],
                    "supportedNonBooleanFeatures": alt_info.get("supportedNonBooleanFeatures", {}),
                    "feasibleCombinations": alt_info.get("feasibleCombinations", [])
                }

                for feature in alt_info.get("supportedBooleanFeatures", []):
                    feature_description = features.get(feature, {}).get("description", "")
                    feature_category = features.get(feature, {}).get("category", "")
                    modified_alternatives[alt_name]["supportedBooleanFeatures"].append({
                        "name": feature,
                        "category": feature_category,
                        "description": feature_description
                    })

        except FileNotFoundError:
            return render(request, 'DSS/alternative_list.html', {'error': f"File '{decision_model_path}' not found."})
        except json.JSONDecodeError:
            return render(request, 'DSS/alternative_list.html', {'error': 'Invalid JSON format in feature file.'})

        #print(modified_alternatives)

        # Render the alternative list template with modified_alternatives
        return render(request, 'DSS/alternative_list.html', {
            'title': title,
            'modified_alternatives': modified_alternatives
        })

    return render(request, 'DSS/alternative_list.html', {'error': 'Invalid request. Only POST requests are accepted.'})

#-------------------------------------------------------------------------------------------------------------
@csrf_exempt
def categorized_team_view(request):
    import os, json
    from django.conf import settings

    json_path = os.path.join(settings.BASE_DIR, 'static', 'DSS-config', 'team.json')

    with open(json_path, 'r') as file:
        team_data = json.load(file)

    lab = team_data.get("lab", {})
    members = lab.get("members", [])
    projects = lab.get("projects", [])

    # ✅ Sort members by JSON-defined "id"
    members = sorted(members, key=lambda x: x.get("id", 0))

    # Separate projects
    active_projects = [p for p in projects if p.get("projectStatus") == "active"]
    finished_projects = [p for p in projects if p.get("projectStatus") == "finished"]

    return render(request, 'DSS/team.html', {
        "lab": lab,
        "members": members,
        "active_projects": active_projects,
        "finished_projects": finished_projects
    })
#-------------------------------------------------------------------------------------------------------------
@csrf_exempt

def workshop(request):
    """
    Render the AI4RSE workshop program page.
    """
    return render(request, "DSS/ai4rse_workshop.html")

#-------------------------------------------------------------------------------------------------------------

@csrf_exempt
def categorized_publications_view(request):
    # Define the path to the JSON file
    json_path = os.path.join(settings.BASE_DIR, 'static', 'DSS-config', 'publications.json')

    # Load and process the JSON file
    with open(json_path, 'r') as file:
        publications = json.load(file)

    # Categorize publications by type and sort each category by year (descending)
    categorized_publications = {}
    for publication in publications:
        pub_type = publication.get("type")
        if pub_type not in categorized_publications:
            categorized_publications[pub_type] = []
        categorized_publications[pub_type].append(publication)

    # Sort each category by year (in descending order)
    for pub_type, items in categorized_publications.items():
        categorized_publications[pub_type] = sorted(items, key=lambda x: x.get("year", 0), reverse=True)

    # Render the categorized publications to the HTML template
    return render(request, 'DSS/publications.html', {'categorized_publications': categorized_publications})
#-------------------------------------------------------------------------------------------------------------
def graph_visualization_generation(feasible_alternatives, feature_data, quality_attributes, features, alternatives):
    """
    Generates nodes and edges for graph visualization based on feasible alternatives,
    features, and quality attributes.
    """
    nodes = []
    edges = []
    node_ids = {}
    current_id = 1  # Start node IDs from 1



    # Add nodes for quality attributes
    for quality, details in quality_attributes.items():
        node = {
            "id": current_id,
            "label": quality,
            "type": "Quality Attribute",
            "description": details.get("description", ""),
            "parent": details.get("parent", []),
        }
        node_ids[quality] = current_id
        nodes.append(node)
        current_id += 1

    # Add nodes for features
    for feature, details in feature_data.items():
        node = {
            "id": current_id,
            "label": feature,
            "type": "Feature",
            "priority": details.get("priority", ""),
            "description": details.get("description", ""),
        }
        node_ids[feature] = current_id
        nodes.append(node)
        current_id += 1

    # Add nodes for feasible alternatives
    for alt_name in feasible_alternatives:
        node = {
            "id": current_id,
            "label": alt_name,
            "type": "Alternative",
            "description": f"Alternative: {alt_name}",
        }
        node_ids[alt_name] = current_id
        nodes.append(node)
        current_id += 1


    # Create edges to show relationships
    for feature, details in feature_data.items():
        # Link each feature to its impacted quality attributes
        for quality in details.get("impactedQualities", []):
            if quality in node_ids:
                edges.append({"from": node_ids[feature], "to": node_ids[quality], "title": "Impact"})

        # Link each feasible alternative to the features it supports
        for alt_name in feasible_alternatives:
            if feature in feature_data and alt_name in node_ids:
                edges.append({"from": node_ids[alt_name], "to": node_ids[feature], "title": "Supports"})












    return nodes, edges

#---------------------------------------------------------------------------------------------------------------------import re
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import os
from itertools import combinations

#-------------------------------------------------------------------------------------------------------------

PRIORITY_WEIGHTS = {
    "must": 1.0,
    "should": 0.7,
    "could": 0.3,
    "wont": 1.0
}

VALUE_MAPPING = {
    "None": 0,
    "Low": 0,
    "Medium": 0.5,
    "High": 1.0
}

#-------------------------------------------------------------------------------------------------------------
def load_dss_config():
    """
    Loads and returns the contents of dss-config.json as a Python variable.
    """
    config_path = os.path.join(settings.BASE_DIR, 'static', 'DSS-config', 'dss-config.json')

    try:
        # Open and load JSON file contents
        with open(config_path, 'r') as config_file:
            data = json.load(config_file)
        
        # Return data as a Python variable (list of dictionaries)
        return data

    except FileNotFoundError:
        print(f"Error: File not found at path {config_path}")
        return []

    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in file at path {config_path}")
        return []
#-------------------------------------------------------------------------------------------------------------
def load_feature_data(filename):
    json_path = os.path.join(settings.BASE_DIR, 'static', 'KB/JSON', filename)
    with open(json_path, 'r') as json_file:
        data = json.load(json_file)
    root_key = list(data.keys())[0]
    return data, root_key
#-------------------------------------------------------------------------------------------------------------
PRIORITY_WEIGHTS = {
    "must": 1.0,
    "should": 0.7,
    "could": 0.3,
    "wont": 1.0
}

VALUE_MAPPING = {
    "None": 0,
    "Low": 0,
    "Medium": 0.5,
    "High": 1.0
}

#-------------------------------------------------------------------------------------------------------------
from itertools import combinations

def generate_feasible_alternative_combinations(feasible_alternatives, must_features, wont_features, feature_data, alternatives):
    """
    Generates feasible alternative combinations by progressively combining alternatives (from 2 up to 5),
    stopping once five combinations with scores above 90% are found.
    """
    if feasible_alternatives:
        print("Feasible alternatives already exist. No need to combine.")
        return []

    feasible_combinations = []
    evaluated_combinations = set()  # To avoid duplicate evaluations
    found_high_score_combinations = 0  # To count combinations with scores above 90%

    # Filter alternatives with the "feasibleCombinations" key
    combinable_alternatives = {
        name: info for name, info in alternatives.items() if 'feasibleCombinations' in info
    }
    print(f"Number of alternatives that can be combined: {len(combinable_alternatives)}")

    # Generate combinations, starting from pairs and increasing group size up to 5
    for group_size in range(2, 6):
        for group in combinations(combinable_alternatives.keys(), group_size):
            sorted_combination = tuple(sorted(group))
            if sorted_combination in evaluated_combinations:
                continue
            evaluated_combinations.add(sorted_combination)

            combined_boolean_features = set()
            combined_non_boolean_features = {}
            for alt_name in group:
                alt_info = combinable_alternatives[alt_name]
                combined_boolean_features.update(alt_info.get('supportedBooleanFeatures', []))
                
                # For non-Boolean features, take the maximum value across alternatives
                for feature, value in alt_info.get('supportedNonBooleanFeatures', {}).items():
                    combined_non_boolean_features[feature] = max(
                        combined_non_boolean_features.get(feature, 0), value
                    )

            # Check "must" and "wont" feature constraints
            if all(feature in combined_boolean_features for feature in must_features) and \
               not any(feature in combined_boolean_features for feature in wont_features):
                
                # Check non-Boolean feature requirements for "must" and "wont" constraints
                must_valid = all(
                    feature in feature_data and feature_data[feature].get('dataType') != 'Boolean' and
                    combined_non_boolean_features.get(feature, 0) >= VALUE_MAPPING.get(feature_data[feature].get('value'), 0)
                    for feature in must_features if feature in feature_data
                )
                wont_valid = all(
                    feature in feature_data and feature_data[feature].get('dataType') != 'Boolean' and
                    combined_non_boolean_features.get(feature, float('inf')) <= VALUE_MAPPING.get(feature_data[feature].get('value'), float('inf'))
                    for feature in wont_features if feature in feature_data
                )

                if must_valid and wont_valid:
                    score = calculate_combination_score(combined_boolean_features, combined_non_boolean_features, feature_data)
                    
                    if score >= 0:
                        # Construct the feasible combination entry
                        combined_name = " + ".join(sorted(group))
                        feasible_combination = {
                            "url": combined_name,
                            "supportedBooleanFeatures": list(combined_boolean_features),
                            "supportedNonBooleanFeatures": combined_non_boolean_features,
                            "score": score
                        }

                        feasible_combinations.append(feasible_combination)
                        found_high_score_combinations += 1

                        # Stop if we have five high-scoring combinations
                        if found_high_score_combinations >= 5:
                            print(f"Found five feasible combinations with scores above 90% at group size {group_size}.")
                            return feasible_combinations

    print(f"Total feasible combinations found: {len(feasible_combinations)}")
    return feasible_combinations

def calculate_combination_score(boolean_features, non_boolean_features, feature_data):
    """
    Calculates a score for a combination of alternatives based on the presence of "should" and "could" requirements.
    """
    score = 0
    for feature, req_info in feature_data.items():
        priority = req_info.get('priority', '').lower()
        feature_weight = PRIORITY_WEIGHTS.get(priority, 0)

        # Score based on the presence of "should" and "could" features
        if priority in ["should", "could"]:
            if feature in boolean_features or (feature in non_boolean_features and 
                non_boolean_features.get(feature) >= VALUE_MAPPING.get(req_info.get('value'), 0)):
                score += feature_weight

    # Normalize the score to a 0-100 scale
    return (score / sum(PRIORITY_WEIGHTS.get(k, 0) for k in ["should", "could"])) * 100 if PRIORITY_WEIGHTS else 0





#-------------------------------------------------------------------------------------------------------------

@csrf_exempt
def evaluate(request):
    """
    Evaluates the feature data sent by the client.
    Expects JSON data with 'fileInfo' (containing title and filename) 
    and 'featureData' (containing feature requirements).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        # Parse the JSON data from the request
        data = json.loads(request.body)

        items = load_dss_config()

        # Retrieve file information and feature requirements separately
        file_info = data.get('fileInfo', {})
        feature_data = data.get('featureData', {})

        # Extract title and filename from file_info
        filename = file_info.get('filename')
        selected_title = file_info.get('title')

        # Ensure filename is provided
        if not filename:
            return JsonResponse({'status': 'error', 'message': 'Filename not provided in request.'}, status=400)

        # Construct the path to the JSON file
        json_path = os.path.join(settings.BASE_DIR, 'static', 'KB', 'JSON', filename)

        # Check if the JSON file exists
        if not os.path.exists(json_path):
            return JsonResponse({'status': 'error', 'message': f"File '{filename}' not found on server."}, status=404)

        # Load the JSON data from the file
        try:
            feature_data_from_file, root_key = load_feature_data(filename)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON format in feature file.'}, status=400)

        # Extract necessary sections for evaluation
        features = feature_data_from_file[root_key].get('features', {})
        quality_attributes = feature_data_from_file[root_key].get('qualityAttributes', {})
        alternatives = feature_data_from_file[root_key].get('alternatives', {})

        # Step 1: Identify "must-have" and "won't-have" features based on priority
        must_features = [
            f for f, v in feature_data.items()
            if isinstance(v, dict) and v.get('priority', '').lower() == 'must'
        ]
        wont_features = [
            f for f, v in feature_data.items()
            if isinstance(v, dict) and v.get('priority', '').lower() == 'wont'
        ]

        # Step 2: Filter feasible alternatives based on "must-have" and "won't-have" requirements
        feasible_alternatives = filter_feasible_alternatives(alternatives, must_features, wont_features, feature_data, features)

        # Step 3: Calculate characteristic weights for features based on their priority
        characteristic_weights = calculate_characteristic_weights(feature_data, features, quality_attributes)

        # Step 4: Calculate feature impact factors based on the calculated characteristic weights
        feature_impact_factors = calculate_feature_importance(feature_data, features, characteristic_weights, quality_attributes)

        # Step 5: Calculate scores for each feasible alternative based on feature impact factors
        alternative_scores = calculate_alternative_scores(feasible_alternatives, feature_data, feature_impact_factors, alternatives)

        # Step 6: Organize supported features by type for each feasible alternative
        supported_features_by_type = get_supported_features_by_type(feasible_alternatives, feature_data, alternatives)

        #step 7: graph graph visualization generaion
        nodes,edges = graph_visualization_generation(feasible_alternatives, feature_data, quality_attributes, features, alternatives)

        #print("Combination generation started!")
        # Step 7: Generate combined feasible alternative combinations
        #combined_feasible_alternative_combinations = generate_feasible_alternative_combinations(
        #    feasible_alternatives, must_features, wont_features, feature_data, alternatives
        #)

        #print("Combination generation finished!")

        #print({'combined_feasible_alternative_combinations': combined_feasible_alternative_combinations})

        # Return the processed results as a JSON response
        return JsonResponse({
            'status': 'success',
            'characteristic_weights': characteristic_weights,
            'feature_impact_factors': feature_impact_factors,
            'feasible_alternatives': feasible_alternatives,
            'alternative_scores': alternative_scores,
            'supported_features_by_type': supported_features_by_type,
            'feature_requirements': feature_data,  # Original feature requirements for reference
            'graph_visualization': {"nodes":nodes,"edges":edges}
            #'combined_feasible_alternative_combinations': combined_feasible_alternative_combinations
        })

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON format in request body.'}, status=400)
    except TypeError as e:
        print(f"TypeError encountered: {e}")
        return JsonResponse({'status': 'error', 'message': f'Unhandled error: {e}'}, status=500)
    except Exception as e:
        print(f"Unhandled exception: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f'Unhandled error: {str(e)}'}, status=500)

#-------------------------------------------------------------------------------------------------------------
def filter_feasible_alternatives(alternatives, must_features, wont_features, feature_requirements, features):
    feasible_alternatives = []

    for alt_name, alt_info in alternatives.items():
        # Boolean "must" feature check
        for feature in must_features:
            if features[feature]['dataType'] == "Boolean":
                if feature not in alt_info['supportedBooleanFeatures']:
                    #print(f"{alt_name} excluded due to missing Boolean 'must' feature '{feature}'.")
                    break  # Skip to the next alternative
        else:
            # Non-Boolean "must" feature check
            for feature in must_features:
                if features[feature]['dataType'] != "Boolean":
                    req_value = feature_requirements[feature].get('value')
                    alt_value = alt_info['supportedNonBooleanFeatures'].get(feature)

                    # Normalize values using VALUE_MAPPING if they are strings
                    req_value = VALUE_MAPPING.get(req_value, req_value) if isinstance(req_value, str) else req_value
                    alt_value = VALUE_MAPPING.get(alt_value, alt_value) if isinstance(alt_value, str) else alt_value

                    #print(f"Checking non-Boolean 'must' feature '{feature}' for '{alt_name}': required = {req_value}, alternative = {alt_value}")
                    
                    # Exclude if the alternative's value is lower than required for "must" features
                    if req_value is not None and (alt_value is None or req_value > alt_value):
                        #print(f"{alt_name} excluded due to non-Boolean 'must' feature '{feature}' (requirement not met).")
                        break
            else:
                # Boolean "won't" feature check
                for feature in wont_features:
                    if features[feature]['dataType'] == "Boolean" and feature in alt_info['supportedBooleanFeatures']:
                        #print(f"{alt_name} excluded due to supported Boolean 'won't' feature '{feature}'.")
                        break
                else:
                    # Non-Boolean "won't" feature check
                    for feature in wont_features:
                        if features[feature]['dataType'] != "Boolean":
                            req_value = feature_requirements[feature].get('value')
                            alt_value = alt_info['supportedNonBooleanFeatures'].get(feature)

                            # Normalize values using VALUE_MAPPING if they are strings
                            req_value = VALUE_MAPPING.get(req_value, req_value) if isinstance(req_value, str) else req_value
                            alt_value = VALUE_MAPPING.get(alt_value, alt_value) if isinstance(alt_value, str) else alt_value

                            #print(f"Checking non-Boolean 'won't' feature '{feature}' for '{alt_name}': required = {req_value}, alternative = {alt_value}")
                            
                            # Exclude if the alternative's value is higher than allowed for "wont" features
                            if alt_value is not None and req_value is not None and alt_value >= req_value:
                                #print(f"{alt_name} excluded due to non-Boolean 'won't' feature '{feature}' (requirement not met).")
                                break
                    else:
                        # If all checks pass, add alternative to feasible list
                        feasible_alternatives.append(alt_name)

    return feasible_alternatives


#-------------------------------------------------------------------------------------------------------------

def calculate_alternative_scores(feasible_alternatives, feature_requirements, feature_impact_factors, alternatives):
    alternative_scores = {}
    max_possible_score = sum(feature_impact_factors.values())  # Total score if all features are fully supported

    for alt_name in feasible_alternatives:
        alt_info = alternatives.get(alt_name)
        if alt_info is None:
            continue

        score = max_possible_score  # Start with the maximum possible score

        # Deduct points based on unmet feature requirements
        for feature, req_info in feature_requirements.items():
            priority = req_info.get('priority', '').lower()  # Handle missing priorities
            feature_score = feature_impact_factors.get(feature, 0)

            if priority in ["should", "could"]:
                # Check if the feature is supported as a Boolean feature
                if feature in alt_info.get('supportedBooleanFeatures', []):
                    continue  # No deduction, feature is supported

                # Check if the feature is supported as a non-Boolean feature with the required value
                elif feature in alt_info.get('supportedNonBooleanFeatures', {}):
                    alt_value = VALUE_MAPPING.get(alt_info['supportedNonBooleanFeatures'].get(feature), 0)
                    req_value = VALUE_MAPPING.get(req_info.get('value'), 0)
                    if req_value <= alt_value:
                        continue  # No deduction, non-Boolean feature requirement is met

                # Deduct feature score if neither Boolean nor non-Boolean conditions are met
                score -= feature_score

            elif priority == 'wont':
                # Penalize if a "wont" feature is found among supported features
                if feature in alt_info.get('supportedBooleanFeatures', []):
                    score -= feature_score
                elif feature in alt_info.get('supportedNonBooleanFeatures', {}):
                    alt_value = VALUE_MAPPING.get(alt_info['supportedNonBooleanFeatures'].get(feature), 0)
                    req_value = VALUE_MAPPING.get(req_info.get('value'), 0)
                    if alt_value > req_value:
                        score -= feature_score  # Deduct if non-Boolean "wont" condition is not met

        # Normalize the score as a percentage of the max possible score
        alternative_scores[alt_name] = (score / max_possible_score) * 100 if max_possible_score > 0 else 0

    return alternative_scores

#-------------------------------------------------------------------------------------------------------------

def get_supported_features_by_type(feasible_alternatives, feature_requirements, alternatives):
    supported_features_by_type = {}

    for alt_name in feasible_alternatives:
        alt_info = alternatives.get(alt_name)
        if alt_info is None:
            continue

        # Use set to eliminate any duplicates within the Boolean features
        supported_boolean = set(alt_info.get('supportedBooleanFeatures', []))
        supported_non_boolean = alt_info.get('supportedNonBooleanFeatures', {})

        # Filter features according to feature_requirements to avoid redundancies
        boolean_features_in_requirements = [
            feature for feature in supported_boolean if feature in feature_requirements
        ]
        non_boolean_features_in_requirements = {
            feature: value for feature, value in supported_non_boolean.items() if feature in feature_requirements
        }


        # Separate "won't" features based on priority in feature_requirements
        wont_features = [
            feature for feature in feature_requirements
            if feature_requirements[feature].get('priority') == 'wont'
        ]


        # Store filtered features without duplicates
        supported_features_by_type[alt_name] = {
            'boolean_features': sorted(boolean_features_in_requirements),
            'non_boolean_features': non_boolean_features_in_requirements,
            'wont_features': wont_features
        }

    return supported_features_by_type 


#-------------------------------------------------------------------------------------------------------------

def calculate_characteristic_weights(data, features, quality_attributes):
    subchar_weights = {}
    for feature_name, feature_info in data.items():
        priority = feature_info['priority']
        weight = PRIORITY_WEIGHTS.get(priority, 0)
        impacted_qualities = features[feature_name].get('impactedQualities', [])
        for subchar in impacted_qualities:
            subchar_weights[subchar] = subchar_weights.get(subchar, 0) + weight

    characteristic_weights = {}
    for subchar, weight in subchar_weights.items():
        parent_char = quality_attributes[subchar]['parent'][0]
        characteristic_weights[parent_char] = characteristic_weights.get(parent_char, 0) + weight

    total_weight = sum(characteristic_weights.values())
    return {k: v / total_weight for k, v in characteristic_weights.items()} if total_weight > 0 else characteristic_weights

#-------------------------------------------------------------------------------------------------------------

def calculate_feature_importance(data, features, characteristic_weights, quality_attributes):
    subchar_weights = propagate_subcharacteristic_weights(characteristic_weights, quality_attributes)
    feature_impact_factors = {}
    for feature_name, feature_info in data.items():
        impacted_qualities = features[feature_name].get('impactedQualities', [])
        impact_factor = sum(subchar_weights[subchar] for subchar in impacted_qualities if subchar in subchar_weights)
        feature_impact_factors[feature_name] = impact_factor

    total_feature_weight = sum(feature_impact_factors.values())
    return {k: (v / total_feature_weight) * 100 for k, v in feature_impact_factors.items()} if total_feature_weight > 0 else feature_impact_factors

#-------------------------------------------------------------------------------------------------------------

def propagate_subcharacteristic_weights(characteristic_weights, quality_attributes):
    subchar_weights = {}
    for subchar, attr_info in quality_attributes.items():
        if 'parent' in attr_info and attr_info['parent']:
            parent_char = attr_info['parent'][0]
            if parent_char in characteristic_weights:
                related_subchars = [
                    sub for sub, info in quality_attributes.items()
                    if 'parent' in info and info['parent'] and info['parent'][0] == parent_char
                ]
                if related_subchars:
                    subchar_weight = characteristic_weights[parent_char] / len(related_subchars)
                    subchar_weights[subchar] = subchar_weight
    return subchar_weights

#-------------------------------------------------------------------------------------------------------------
@csrf_exempt
def load_features(request, filename="index.json"):
    if request.method == 'POST':
        items=load_dss_config()
        selected_title = request.POST.get('title')
        decision_model_path = next(
            (item['decisionModel_path'] for item in items if item.get('title') == selected_title and 'decisionModel_path' in item),
            filename  # Default to filename if path is not found
        )

        json_path = os.path.join(settings.BASE_DIR, 'static', 'KB', 'JSON', decision_model_path)
        
        print (json_path)

        try:
            with open(json_path, 'r') as json_file:
                data = json.load(json_file)
            root_key = list(data.keys())[0]
            features = data.get(root_key, {}).get("features", {})

            # Logging to check loaded data
            print(f"Loaded data for {selected_title}: {len(features)} features loaded.")
            print(decision_model_path)

            return render(request, 'DSS/requirements_analysis_and_decision_making.html', {
                'features': json.dumps(features),
                'selected_filename': decision_model_path
            })

        except FileNotFoundError:
            return render(request, 'DSS/requirements_analysis_and_decision_making.html', {
                'error': f"File not found at path: {json_path}"
            })
        except json.JSONDecodeError:
            return render(request, 'DSS/requirements_analysis_and_decision_making.html', {
                'error': f"Invalid JSON format in file: {decision_model_path}"
            })

    return render(request, 'DSS/requirements_analysis_and_decision_making.html', {'error': 'Invalid request. Only POST requests are accepted.'})

#-------------------------------------------------------------------------------------------------------------

@csrf_exempt
def mcdm_decision_models(request):
    items=load_dss_config()


    # Organize items by category
    organized_items = defaultdict(list)

    for item in items:
        organized_items[item['category']].append(item)

    # Convert the defaultdict to a list of tuples for Django template compatibility
    organized_items = list(organized_items.items())

    print("landing page")
    
    return render(request, 'DSS/mcdm_decision_models.html', {'organized_items': organized_items})

#-------------------------------------------------------------------------------------------------------------
@csrf_exempt
def view_decision_model(request):
    if request.method == 'POST':
        title = request.POST.get('title')

        # Load configuration and JSON data as before
        items = load_dss_config()
        decision_model_path = next(
            (item['decisionModel_path'] for item in items if item.get('title') == title and 'decisionModel_path' in item),
            'index.json'  # Default to 'index.json' if path is not found
        )

        json_path = os.path.join(settings.BASE_DIR, 'static', 'KB', 'JSON', decision_model_path)
        
        try:
            with open(json_path, 'r') as json_file:
                data = json.load(json_file)
            root_key = list(data.keys())[0]
            features = data.get(root_key, {}).get("features", {})
            alternatives = data.get(root_key, {}).get("alternatives", {})

            # Process alternatives to add feature descriptions
            modified_alternatives = {}
            for alt_name, alt_info in alternatives.items():
                modified_alternatives[alt_name] = {
                    "url": alt_info.get("url", ""),
                    "supportedBooleanFeatures": [],
                    "supportedNonBooleanFeatures": alt_info.get("supportedNonBooleanFeatures", {}),
                    "feasibleCombinations": alt_info.get("feasibleCombinations", [])
                }

                for feature in alt_info.get("supportedBooleanFeatures", []):
                    feature_description = features.get(feature, {}).get("description", "")
                    feature_category = features.get(feature, {}).get("category", "")
                    modified_alternatives[alt_name]["supportedBooleanFeatures"].append({
                        "name": feature,
                        "category": feature_category,
                        "description": feature_description
                    })

        except FileNotFoundError:
            return render(request, 'DSS/alternative_list.html', {'error': f"File '{decision_model_path}' not found."})
        except json.JSONDecodeError:
            return render(request, 'DSS/alternative_list.html', {'error': 'Invalid JSON format in feature file.'})

        #print(modified_alternatives)

        # Render the alternative list template with modified_alternatives
        return render(request, 'DSS/alternative_list.html', {
            'title': title,
            'modified_alternatives': modified_alternatives
        })

    return render(request, 'DSS/alternative_list.html', {'error': 'Invalid request. Only POST requests are accepted.'})

#-------------------------------------------------------------------------------------------------------------

@csrf_exempt
def categorized_publications_view(request):
    # Define the path to the JSON file
    json_path = os.path.join(settings.BASE_DIR, 'static', 'DSS-config', 'publications.json')

    # Load and process the JSON file
    with open(json_path, 'r') as file:
        publications = json.load(file)

    # Categorize publications by type and sort each category by year (descending)
    categorized_publications = {}
    for publication in publications:
        pub_type = publication.get("type")
        if pub_type not in categorized_publications:
            categorized_publications[pub_type] = []
        categorized_publications[pub_type].append(publication)

    # Sort each category by year (in descending order)
    for pub_type, items in categorized_publications.items():
        categorized_publications[pub_type] = sorted(items, key=lambda x: x.get("year", 0), reverse=True)

    # Render the categorized publications to the HTML template
    return render(request, 'DSS/publications.html', {'categorized_publications': categorized_publications})
#-------------------------------------------------------------------------------------------------------------
def graph_visualization_generation(feasible_alternatives, feature_data, quality_attributes, features, alternatives):
    """
    Generates nodes and edges for a hierarchical graph visualization with:
    root -> relevant characteristics -> relevant subcharacteristics -> features -> alternatives.
    """
    nodes = []
    edges = []
    node_ids = {}
    current_id = 1  # Start node IDs from 1

    # Step 0: Create the root node "Decision Graph"
    root_node = {
        "id": current_id,
        "label": "Decision Graph",
        "type": "root",
        "level": 0,
        "color": "#f4d03f",
        "shape": "circle",
        "description": "Root node for the decision graph."
    }
    root_id = current_id
    nodes.append(root_node)
    node_ids[("Decision Graph", 0)] = current_id
    current_id += 1

    # Step 1: Identify relevant characteristics and subcharacteristics based on feature impact
    relevant_characteristics = set()
    relevant_subcharacteristics = set()

    # Gather relevant subcharacteristics impacted by features in feature_data
    for feature in feature_data:
        impacted_qualities = features.get(feature, {}).get('impactedQualities', [])
        relevant_subcharacteristics.update(impacted_qualities)

    # Gather characteristics that have at least one relevant subcharacteristic
    for subchar in relevant_subcharacteristics:
        parent_chars = quality_attributes.get(subchar, {}).get("parent", [])
        relevant_characteristics.update(parent_chars)

    # Step 2: Add relevant characteristic nodes and connect them to the root
    for char_name in relevant_characteristics:
        if char_name in quality_attributes and not quality_attributes[char_name].get("parent"):  # Top-level characteristics only
            node = {
                "id": current_id,
                "label": char_name,
                "type": "characteristic",
                "level": 1,
                "color": "#f0b27a",
                "shape": "box",
                "description": quality_attributes[char_name].get("description", "")
            }
            nodes.append(node)
            node_ids[(char_name, 1)] = current_id  # Use composite key (name, level) for unique identification
            edges.append({
                "from": root_id,
                "to": current_id,
                "title": "Root Connection"
            })
            current_id += 1

    # Step 3: Add relevant subcharacteristics and connect them to their parent characteristics
    for subchar in relevant_subcharacteristics:
        details = quality_attributes.get(subchar)
        if details and details.get("parent"):
            node = {
                "id": current_id,
                "label": subchar,
                "type": "subcharacteristic",
                "level": 2,
                "color": "#d7bde2",
                "shape": "box",
                "description": details.get("description", "")
            }
            nodes.append(node)
            node_ids[(subchar, 2)] = current_id  # Use composite key (name, level)

            # Connect subcharacteristics to their relevant parent characteristics
            for parent in details["parent"]:
                if (parent, 1) in node_ids:  # Ensure connection only with characteristic nodes
                    edges.append({
                        "from": node_ids[(parent, 1)],
                        "to": current_id,
                        "title": "Is Subcharacteristic Of"
                    })
            current_id += 1

    # Step 4: Add nodes for features in feature_data and connect to relevant subcharacteristics
    for feature, details in feature_data.items():
        feature_details = features.get(feature, {})
        node = {
            "id": current_id,
            "label": feature,
            "type": "feature",
            "level": 3,
            "color": "#a2d9ce",
            "shape": "box",
            "priority": details.get("priority", ""),
            "description": feature_details.get("description", "")
        }
        nodes.append(node)
        node_ids[(feature, 3)] = current_id  # Use composite key (name, level)
        
        # Link each feature to its impacted quality subcharacteristics
        impacted_qualities = feature_details.get("impactedQualities", [])
        for quality in impacted_qualities:
            if (quality, 2) in node_ids:  # Ensure connection only with subcharacteristic nodes
                edges.append({
                    "from": node_ids[(quality, 2)],
                    "to": current_id,
                    "title": "Impacts"
                })
        current_id += 1

    # Step 5: Add nodes for feasible alternatives and connect to supported features
    for alt_name in feasible_alternatives:
        alt_info = alternatives.get(alt_name)
        if alt_info:
            node = {
                "id": current_id,
                "label": alt_name,
                "type": "alternative",
                "level": 4,
                "color": "#7fb3d5",
                "shape": "box",
                "description": f"Alternative: {alt_name}"
            }
            nodes.append(node)
            node_ids[(alt_name, 4)] = current_id  # Use composite key (name, level)
            
            # Connect each alternative to the features it supports
            supported_features = alt_info.get("supportedBooleanFeatures", []) + list(alt_info.get("supportedNonBooleanFeatures", {}).keys())
            for feature in supported_features:
                if (feature, 3) in node_ids:  # Ensure connection only with feature nodes
                    edges.append({
                        "from": node_ids[(feature, 3)],
                        "to": current_id,
                        "title": "Supports"
                    })
            current_id += 1

    return nodes, edges

#---------------------------------------------------------------------------------------------------------------------

@csrf_exempt
def landing_page(request):

    print("landing page")
    
    return render(request, 'DSS/landing-page.html', {'organized_items': {}})
#-------------------------------------------------------------------------------------------------------------