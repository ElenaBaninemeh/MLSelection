import json
import pandas as pd
import os
import argparse

def parse_features(feature_definitions, feature_categories, feature_quality):
    # Standardize column names by stripping whitespace
    feature_definitions.columns = feature_definitions.columns.str.strip()
    feature_categories.columns = feature_categories.columns.str.strip()
    feature_quality.columns = feature_quality.columns.str.strip()
    
    # Build features dictionary
    features = {}
    
    # Map feature names to categories
    category_map = {row['[name]']: row['[category]'] for _, row in feature_categories.iterrows()}
    
    # Set the index for feature_quality based on '[FQ:Mapping]'
    feature_quality.set_index('[FQ:Mapping]', inplace=True)

    # Map feature impacts on qualities
    quality_map = {}
    for feature, qualities in feature_quality.iterrows():
        quality_map[feature] = qualities[qualities == 1].index.tolist()
    
    # Build the feature definitions
    for _, row in feature_definitions.iterrows():
        name = row['[name]']
        features[name] = {
            "dataType": row['[datatype]'],
            "description": row['[definition]'],
            "category": category_map.get(name, ""),
            "impactedQualities": quality_map.get(name, []),
            "parentFeature": None
        }
    
    return features

def parse_alternatives(alternative_definitions, feature_alternative, alternative_combination, features):
    # Build alternatives dictionary
    alternatives = {}
    
    # Map alternative descriptions
    alt_desc_map = {row['[name]']: row['[definition]'] for _, row in alternative_definitions.iterrows()}
    
    # Set '[FA:Mapping]' as the index in feature_alternative
    feature_alternative.set_index('[FA:Mapping]', inplace=True)
    
    # Dictionary to store values for non-Boolean features for normalization
    non_boolean_feature_values = {}

    # Process each alternative
    for alt_name in feature_alternative.columns:
        boolean_features = []
        non_boolean_features = {}
        
        for feature_name, value in feature_alternative[alt_name].items():
            feature_type = features.get(feature_name, {}).get('dataType', "")
            
            # Determine if the feature is Boolean or not
            if feature_type == 'Boolean':
                if value == 1:
                    boolean_features.append(feature_name)
            else:
                # This is a non-Boolean feature
                try:
                    # Convert to float, if possible; if empty or 'N/A', use 0
                    non_boolean_features[feature_name] = float(value) if value not in (None, '', 'N/A') else 0
                except ValueError:
                    non_boolean_features[feature_name] = 0

                # Collect values for normalization
                if feature_name not in non_boolean_feature_values:
                    non_boolean_feature_values[feature_name] = []
                non_boolean_feature_values[feature_name].append(non_boolean_features[feature_name])
        
        # Process feasible combinations for each alternative
        feasible_combinations = []
        if alt_name in alternative_combination.columns:
            feasible_combinations = alternative_combination[alternative_combination[alt_name] == 1]['[combination]'].tolist()
        
        # Construct initial alternative entity
        alternatives[alt_name] = {
            "url": alt_desc_map.get(alt_name, ""),
            "supportedBooleanFeatures": boolean_features,
            "supportedNonBooleanFeatures": non_boolean_features,
            "feasibleCombinations": feasible_combinations
        }
    
    # Normalize non-Boolean features across alternatives
    for feature_name, values in non_boolean_feature_values.items():
        min_val, max_val = min(values), max(values)
        for alt_name, alt_info in alternatives.items():
            if feature_name in alt_info["supportedNonBooleanFeatures"]:
                original_value = alt_info["supportedNonBooleanFeatures"][feature_name]
                # Normalize the value between 0 and 1
                alt_info["supportedNonBooleanFeatures"][feature_name] = (
                    (original_value - min_val) / (max_val - min_val) if max_val > min_val else 1.0
                )
    
    return alternatives

def build_decision_tree(features, alternatives):
    # Read base JSON file for qualityAttributes
    with open('decision-model.json') as f:
        decision_model = json.load(f)
    
    # Update features and alternatives
    decision_model['DecisionTree']['features'] = features
    decision_model['DecisionTree']['alternatives'] = alternatives
    
    return decision_model

def load_csv_files(folder_path):
    # Construct file paths for each CSV file in the specified folder
    feature_definitions_path = os.path.join(folder_path, 'Feature-definitions.csv')
    feature_categories_path = os.path.join(folder_path, 'Feature-categories.csv')
    alternative_definitions_path = os.path.join(folder_path, 'Alternative-definitions.csv')
    feature_alternative_path = os.path.join(folder_path, 'Feature-alternative.csv')
    alternative_combination_path = os.path.join(folder_path, 'Alternative-combination.csv')
    feature_quality_path = os.path.join(folder_path, 'Feature-quality.csv')

    # Load each CSV file into a DataFrame
    feature_definitions = pd.read_csv(feature_definitions_path)
    feature_categories = pd.read_csv(feature_categories_path)
    alternative_definitions = pd.read_csv(alternative_definitions_path)
    feature_alternative = pd.read_csv(feature_alternative_path)
    alternative_combination = pd.read_csv(alternative_combination_path)
    feature_quality = pd.read_csv(feature_quality_path)
    
    return feature_definitions, feature_categories, alternative_definitions, feature_alternative, alternative_combination, feature_quality

def main(folder_path):
    # Load CSV files from specified folder
    feature_definitions, feature_categories, alternative_definitions, feature_alternative, alternative_combination, feature_quality = load_csv_files(folder_path)
    
    # Parse the CSV data into structured JSON components
    features = parse_features(feature_definitions, feature_categories, feature_quality)
    alternatives = parse_alternatives(alternative_definitions, feature_alternative, alternative_combination, features)
    
    # Build the decision tree structure
    decision_tree = build_decision_tree(features, alternatives)
    
    # Save to JSON file
    with open('new-decision-model.json', 'w') as f:
        json.dump(decision_tree, f, indent=4)
    print("Data saved to new-decision-model.json")

if __name__ == "__main__":
    # Set up command-line argument for folder path
    parser = argparse.ArgumentParser(description="Generate JSON from CSV files in specified folder")
    parser.add_argument("folder_path", help="Path to the folder containing the CSV files")
    args = parser.parse_args()
    
    # Run main with folder path argument
    main(args.folder_path)
