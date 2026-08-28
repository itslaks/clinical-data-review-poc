"""
Configuration UI for Streamlit app - allows users to:
1. Upload CSV and auto-detect schema
2. Review and adjust column types
3. Select/customize quality rules
4. Save/load configurations
5. Run analysis with custom rules
"""

import json
import os
import streamlit as st
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any

try:
    from src.schema_detector import SchemaDetector
    from src.rule_templates import RuleTemplates
except ImportError:  # pragma: no cover - direct script execution fallback
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from schema_detector import SchemaDetector
    from rule_templates import RuleTemplates


CONFIG_DIR = Path(__file__).parent / "configurations"


def ensure_config_dir():
    """Create configurations directory if it doesn't exist."""
    CONFIG_DIR.mkdir(exist_ok=True)


def save_configuration(config_name: str, config_data: Dict[str, Any]):
    """Save a configuration to JSON file."""
    ensure_config_dir()
    config_path = CONFIG_DIR / f"{config_name}.json"
    with open(config_path, 'w') as f:
        json.dump(config_data, f, indent=2)
    return config_path


def load_configuration(config_name: str) -> Dict[str, Any]:
    """Load a configuration from JSON file."""
    config_path = CONFIG_DIR / f"{config_name}.json"
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    return None


def list_saved_configurations() -> List[str]:
    """List all saved configuration files."""
    ensure_config_dir()
    configs = [f.stem for f in CONFIG_DIR.glob("*.json")]
    return sorted(configs)


def render_schema_review_panel(uploaded_file, df_preview: pd.DataFrame = None):
    """
    Render panel for reviewing and adjusting auto-detected schema.
    
    Returns:
        schema_info: Dict with column info and adjusted types
    """
    st.subheader("📋 Schema Detection & Adjustment")
    
    if uploaded_file is None:
        st.info("Upload a CSV file to see schema detection")
        return None
    
    # Auto-detect schema
    detector = SchemaDetector(df_preview)
    schema = detector.detect_schema()
    summary = detector.get_summary()
    
    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Columns", summary['total_columns'])
    with col2:
        st.metric("Numeric Columns", summary['by_type'].get('numeric', 0))
    with col3:
        st.metric("Categorical Columns", summary['by_type'].get('categorical', 0))
    with col4:
        st.metric("ID/Key Columns", summary['by_type'].get('id', 0))
    
    st.divider()
    
    # Display and allow adjustment of each column
    st.write("**Detected Column Types** - Adjust if needed:")
    
    adjusted_schema = {}
    col_configs = {}
    
    for col_name, col_info in schema.items():
        with st.expander(f"🔹 {col_name} ({col_info['inferred_type']})", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Detected Type:** {col_info['inferred_type']}")
                st.write(f"**Confidence:** {col_info['confidence']:.1%}")
                st.write(f"**Unique Values:** {col_info['unique_count']}")
                st.write(f"**Null Count:** {col_info['null_count']} ({col_info['null_ratio']:.1%})")
            
            with col2:
                # Allow user to override type
                type_options = ['numeric', 'categorical', 'date', 'text', 'id']
                new_type = st.selectbox(
                    f"Override type for {col_name}?",
                    options=type_options,
                    index=type_options.index(col_info['inferred_type']) 
                           if col_info['inferred_type'] in type_options else 0,
                    key=f"type_{col_name}"
                )
                
                # Allow user to override semantic role
                role_options = ['id', 'date', 'measurement', 'dimension', 'other']
                new_role = st.selectbox(
                    f"Semantic role for {col_name}?",
                    options=role_options,
                    index=role_options.index(col_info['semantic_role']) 
                          if col_info['semantic_role'] in role_options else 4,
                    key=f"role_{col_name}"
                )
                
                # Show sample values
                st.write(f"**Sample Values:** {', '.join(col_info['sample_values'][:3])}")
            
            adjusted_schema[col_name] = {
                **col_info,
                'overridden_type': new_type if new_type != col_info['inferred_type'] else None,
                'overridden_role': new_role if new_role != col_info['semantic_role'] else None
            }
    
    return adjusted_schema


def render_rules_configuration_panel(schema_info: Dict = None) -> List[Dict[str, Any]]:
    """
    Render panel for selecting and configuring quality rules.
    
    Returns:
        List of rule configurations to apply
    """
    st.subheader("⚙️ Quality Rules Configuration")
    
    # Step 1: Select template or build custom
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Step 1: Choose a Template**")
        templates_list = RuleTemplates.list_templates()
        template_names = [t['name'] for t in templates_list]
        template_ids = [t['id'] for t in templates_list]
        
        selected_template = st.radio(
            "Select a rule template or start with custom:",
            options=template_ids,
            format_func=lambda x: next(t['name'] for t in templates_list if t['id'] == x),
            key="template_select"
        )
    
    with col2:
        st.info(f"Template includes {next(t['rule_count'] for t in templates_list if t['id'] == selected_template)} rules")
    
    st.divider()
    
    # Step 2: Get base template or start with generic
    base_template = RuleTemplates.get_template(selected_template)
    rules_config = [rule.copy() for rule in base_template.get('rules', [])]
    
    st.write("**Step 2: Review & Customize Rules**")
    
    # Allow enabling/disabling rules
    customized_rules = []
    
    for idx, rule in enumerate(rules_config):
        with st.expander(f"{'✅' if rule.get('enabled') else '❌'} {rule.get('id')} - {rule.get('type')}", 
                          expanded=rule.get('enabled', True)):
            
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                # Enable/disable toggle
                enabled = st.checkbox(
                    "Enable this rule",
                    value=rule.get('enabled', True),
                    key=f"enable_{idx}"
                )
                rule['enabled'] = enabled
                
                st.write(f"**Type:** {rule.get('type')}")
                st.write(f"**Severity:** {rule.get('severity', 'warning')}")
            
            with col2:
                st.write(f"**Description:** {rule.get('description', 'N/A')}")
                
                # Show column pattern if applicable
                if 'column_pattern' in rule:
                    st.write(f"**Applies to:** {rule['column_pattern']}")
                if 'column' in rule:
                    st.write(f"**Column:** {rule['column']}")
            
            with col3:
                # Customize parameters if applicable
                if 'threshold_warning' in rule:
                    rule['threshold_warning'] = st.number_input(
                        "Warning %", 
                        value=rule['threshold_warning'],
                        key=f"thresh_warn_{idx}"
                    )
                if 'threshold_critical' in rule:
                    rule['threshold_critical'] = st.number_input(
                        "Critical %",
                        value=rule['threshold_critical'],
                        key=f"thresh_crit_{idx}"
                    )
                if 'max_age_days' in rule:
                    rule['max_age_days'] = st.number_input(
                        "Max age (days)",
                        value=rule['max_age_days'],
                        key=f"max_age_{idx}"
                    )
                if 'max_unique' in rule:
                    rule['max_unique'] = st.number_input(
                        "Max unique",
                        value=rule['max_unique'],
                        key=f"max_uniq_{idx}"
                    )
            
            customized_rules.append(rule)
    
    return customized_rules


def render_configuration_save_load_panel(schema_info: Dict, rules_config: List[Dict]) -> Dict[str, Any]:
    """
    Render panel for saving and loading configurations.
    
    Returns:
        Complete configuration object
    """
    st.subheader("💾 Save & Load Configurations")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**Save Current Configuration**")
        config_name = st.text_input(
            "Configuration name",
            placeholder="e.g., clinical_v1, financial_strict",
            key="save_config_name"
        )
        
        if st.button("Save Configuration", key="save_btn"):
            if config_name:
                config_data = {
                    'name': config_name,
                    'schema': schema_info,
                    'rules': rules_config
                }
                save_configuration(config_name, config_data)
                st.success(f"✅ Configuration saved as '{config_name}'")
            else:
                st.warning("Please enter a configuration name")
    
    with col2:
        st.write("**Load Saved Configuration**")
        saved_configs = list_saved_configurations()
        
        if saved_configs:
            selected_config = st.selectbox(
                "Choose a saved configuration",
                options=saved_configs,
                key="load_config_select"
            )
            
            if st.button("Load Configuration", key="load_btn"):
                loaded = load_configuration(selected_config)
                if loaded:
                    st.success(f"✅ Loaded configuration '{selected_config}'")
                    return loaded
        else:
            st.info("No saved configurations yet")
    
    with col3:
        st.write("**Configuration Management**")
        if saved_configs:
            config_to_delete = st.selectbox(
                "Delete a configuration",
                options=saved_configs,
                key="delete_config_select"
            )
            if st.button("Delete", key="delete_btn"):
                config_path = CONFIG_DIR / f"{config_to_delete}.json"
                if config_path.exists():
                    config_path.unlink()
                    st.success(f"✅ Deleted '{config_to_delete}'")
                    st.rerun()
    
    # Return current configuration
    return {
        'name': config_name or 'unnamed',
        'schema': schema_info,
        'rules': rules_config
    }


def render_full_configuration_wizard():
    """
    Render the complete configuration wizard - all steps in sequence.
    """
    st.markdown("### 🎯 Data Quality Configuration Wizard")
    
    # Step 1: File Upload
    st.markdown("**Step 1: Upload Your Data**")
    uploaded_file = st.file_uploader(
        "Choose a CSV file",
        type=['csv'],
        help="Upload your dataset for schema detection and analysis"
    )
    
    if uploaded_file is None:
        st.info("📁 Upload a CSV file to begin configuration")
        return None
    
    # Load and preview
    df_preview = pd.read_csv(uploaded_file, nrows=100)
    
    st.success(f"✅ Loaded {len(df_preview)} preview rows (shape: {df_preview.shape})")
    
    with st.expander("Preview Data", expanded=False):
        st.dataframe(df_preview.head(10), use_container_width=True)
    
    st.divider()
    
    # Step 2: Schema review
    schema_info = render_schema_review_panel(uploaded_file, df_preview)
    
    if schema_info is None:
        return None
    
    st.divider()
    
    # Step 3: Rules configuration
    rules_config = render_rules_configuration_panel(schema_info)
    
    st.divider()
    
    # Step 4: Save/load
    full_config = render_configuration_save_load_panel(schema_info, rules_config)
    
    st.divider()
    
    # Summary
    st.markdown("### 📊 Configuration Summary")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Schema Columns", len(schema_info))
    with col2:
        enabled_rules = sum(1 for r in rules_config if r.get('enabled'))
        st.metric("Active Rules", enabled_rules)
    with col3:
        st.metric("Total Rules", len(rules_config))
    
    # Return full configuration for use in pipeline
    return full_config
