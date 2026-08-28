"""
Rule templates - pre-built quality rule sets for different domains.
Users can select a template or customize from scratch.
"""

from typing import Dict, List, Any


class RuleTemplates:
    """Library of domain-specific quality rule templates."""
    
    @staticmethod
    def clinical_data() -> Dict[str, Any]:
        """Rules for clinical/healthcare datasets."""
        return {
            'name': 'Clinical Data',
            'description': 'Quality checks for healthcare and clinical records',
            'domain': 'healthcare',
            'rules': [
                {
                    'id': 'missing_id',
                    'type': 'missing_value',
                    'column_pattern': '.*id$|.*patient.*|.*record.*',
                    'enabled': True,
                    'severity': 'critical',
                    'description': 'Check for missing patient/record IDs'
                },
                {
                    'id': 'missing_measurement',
                    'type': 'missing_value',
                    'column_pattern': '.*value$|.*result$|.*amount$',
                    'enabled': True,
                    'severity': 'warning',
                    'threshold_warning': 5,  # Allow up to 5% missing
                    'threshold_critical': 20
                },
                {
                    'id': 'duplicate_measurement',
                    'type': 'duplicate',
                    'column_pattern': '.*id$|.*patient.*',
                    'enabled': True,
                    'severity': 'warning',
                    'allow_duplicates_with_different_date': True
                },
                {
                    'id': 'out_of_range',
                    'type': 'numeric_range',
                    'column_pattern': '.*value$|.*result$|ref_low|ref_high',
                    'enabled': True,
                    'severity': 'warning',
                    'use_reference_range': True
                },
                {
                    'id': 'unit_mismatch',
                    'type': 'unit_mismatch',
                    'value_column_pattern': '.*value$|.*result$',
                    'unit_column_pattern': '.*unit$',
                    'enabled': True,
                    'severity': 'warning',
                    'check_against_standard': True
                },
                {
                    'id': 'stale_data',
                    'type': 'date_range',
                    'column_pattern': '.*date$|.*received$|.*created$',
                    'enabled': True,
                    'severity': 'warning',
                    'max_age_days': 365
                }
            ]
        }
    
    @staticmethod
    def financial_data() -> Dict[str, Any]:
        """Rules for financial and accounting datasets."""
        return {
            'name': 'Financial Data',
            'description': 'Quality checks for financial transactions and records',
            'domain': 'finance',
            'rules': [
                {
                    'id': 'missing_transaction_id',
                    'type': 'missing_value',
                    'column_pattern': '.*transaction.*|.*reference.*|.*id$',
                    'enabled': True,
                    'severity': 'critical'
                },
                {
                    'id': 'missing_amount',
                    'type': 'missing_value',
                    'column_pattern': '.*amount$|.*price$|.*value$|.*balance$',
                    'enabled': True,
                    'severity': 'critical',
                    'threshold_critical': 1  # No missing amounts allowed
                },
                {
                    'id': 'negative_amount',
                    'type': 'numeric_range',
                    'column_pattern': '.*amount$|.*price$',
                    'enabled': True,
                    'severity': 'warning',
                    'allow_negative': False
                },
                {
                    'id': 'duplicate_transaction',
                    'type': 'duplicate',
                    'column_pattern': '.*transaction.*|.*id$',
                    'enabled': True,
                    'severity': 'critical'
                },
                {
                    'id': 'future_date',
                    'type': 'date_range',
                    'column_pattern': '.*date$|.*posted$|.*transaction.*date',
                    'enabled': True,
                    'severity': 'warning',
                    'check_future': True
                },
                {
                    'id': 'unusual_amount',
                    'type': 'outlier',
                    'column_pattern': '.*amount$|.*price$|.*value$',
                    'enabled': True,
                    'severity': 'info',
                    'method': 'iqr',
                    'multiplier': 2.0
                }
            ]
        }
    
    @staticmethod
    def inventory_data() -> Dict[str, Any]:
        """Rules for inventory and supply chain datasets."""
        return {
            'name': 'Inventory Data',
            'description': 'Quality checks for inventory, warehouse, and stock records',
            'domain': 'supply_chain',
            'rules': [
                {
                    'id': 'missing_sku',
                    'type': 'missing_value',
                    'column_pattern': '.*sku$|.*product.*id|.*item.*id',
                    'enabled': True,
                    'severity': 'critical'
                },
                {
                    'id': 'missing_quantity',
                    'type': 'missing_value',
                    'column_pattern': '.*quantity$|.*count$|.*stock$',
                    'enabled': True,
                    'severity': 'critical'
                },
                {
                    'id': 'negative_quantity',
                    'type': 'numeric_range',
                    'column_pattern': '.*quantity$|.*count$|.*stock$',
                    'enabled': True,
                    'severity': 'critical',
                    'allow_negative': False
                },
                {
                    'id': 'duplicate_sku_location',
                    'type': 'duplicate_composite',
                    'columns': ['sku', 'location', 'warehouse'],
                    'enabled': True,
                    'severity': 'warning'
                },
                {
                    'id': 'old_records',
                    'type': 'date_range',
                    'column_pattern': '.*date$|.*updated$|.*received$',
                    'enabled': True,
                    'severity': 'info',
                    'max_age_days': 730  # 2 years
                },
                {
                    'id': 'zero_quantity',
                    'type': 'numeric_value',
                    'column_pattern': '.*quantity$|.*count$',
                    'enabled': True,
                    'severity': 'info',
                    'flag_zero': True
                }
            ]
        }
    
    @staticmethod
    def web_analytics_data() -> Dict[str, Any]:
        """Rules for web analytics and event datasets."""
        return {
            'name': 'Web Analytics',
            'description': 'Quality checks for web events, user activity, and metrics',
            'domain': 'web_analytics',
            'rules': [
                {
                    'id': 'missing_event_id',
                    'type': 'missing_value',
                    'column_pattern': '.*event.*id|.*session.*|.*user.*id',
                    'enabled': True,
                    'severity': 'critical'
                },
                {
                    'id': 'missing_timestamp',
                    'type': 'missing_value',
                    'column_pattern': '.*timestamp|.*date$|.*time$',
                    'enabled': True,
                    'severity': 'critical'
                },
                {
                    'id': 'future_event',
                    'type': 'date_range',
                    'column_pattern': '.*timestamp|.*date$',
                    'enabled': True,
                    'severity': 'critical',
                    'check_future': True
                },
                {
                    'id': 'negative_metric',
                    'type': 'numeric_range',
                    'column_pattern': '.*count$|.*duration$|.*value$|.*amount$',
                    'enabled': True,
                    'severity': 'warning',
                    'allow_negative': False
                },
                {
                    'id': 'duplicate_event',
                    'type': 'duplicate',
                    'column_pattern': '.*event.*id',
                    'enabled': True,
                    'severity': 'info'
                },
                {
                    'id': 'unrealistic_duration',
                    'type': 'numeric_range',
                    'column_pattern': '.*duration.*|.*session.*length',
                    'enabled': True,
                    'severity': 'warning',
                    'max_value': 86400  # 24 hours in seconds
                }
            ]
        }
    
    @staticmethod
    def generic_data() -> Dict[str, Any]:
        """Generic rules that work with any dataset."""
        return {
            'name': 'Generic Data',
            'description': 'Basic quality checks that apply to any dataset',
            'domain': 'generic',
            'rules': [
                {
                    'id': 'missing_values',
                    'type': 'missing_value',
                    'column_pattern': '.*',
                    'enabled': True,
                    'severity': 'warning',
                    'threshold_warning': 10,
                    'threshold_critical': 50
                },
                {
                    'id': 'duplicates',
                    'type': 'duplicate',
                    'column_pattern': '.*id$|.*key$',
                    'enabled': True,
                    'severity': 'warning'
                },
                {
                    'id': 'outliers',
                    'type': 'outlier',
                    'column_pattern': '.*numeric.*|.*value.*|.*amount.*',
                    'enabled': False,  # Optional, disabled by default
                    'severity': 'info',
                    'method': 'iqr'
                }
            ]
        }
    
    @staticmethod
    def all_templates() -> Dict[str, Dict[str, Any]]:
        """Get all available templates."""
        return {
            'clinical': RuleTemplates.clinical_data(),
            'financial': RuleTemplates.financial_data(),
            'inventory': RuleTemplates.inventory_data(),
            'web_analytics': RuleTemplates.web_analytics_data(),
            'generic': RuleTemplates.generic_data()
        }
    
    @staticmethod
    def get_template(domain: str) -> Dict[str, Any]:
        """Get a specific template by domain name."""
        templates = RuleTemplates.all_templates()
        return templates.get(domain.lower(), RuleTemplates.generic_data())
    
    @staticmethod
    def list_templates() -> List[Dict[str, str]]:
        """Get list of available templates with descriptions."""
        templates = RuleTemplates.all_templates()
        return [
            {
                'id': k,
                'name': v['name'],
                'description': v['description'],
                'domain': v['domain'],
                'rule_count': len(v.get('rules', []))
            }
            for k, v in templates.items()
        ]
    
    @staticmethod
    def customize_template(base_template: str, 
                          enabled_rules: List[str] = None,
                          disabled_rules: List[str] = None,
                          rule_overrides: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a custom template based on a base template with overrides.
        
        Args:
            base_template: Name of base template (e.g., 'clinical')
            enabled_rules: List of rule IDs to enable
            disabled_rules: List of rule IDs to disable
            rule_overrides: Dict mapping rule ID to override config
        
        Returns:
            Customized template
        """
        template = RuleTemplates.get_template(base_template)
        custom_template = template.copy()
        custom_template['rules'] = template.get('rules', []).copy()
        
        # Apply enable/disable logic
        enabled_rules = set(enabled_rules or [])
        disabled_rules = set(disabled_rules or [])
        
        for rule in custom_template['rules']:
            rule_id = rule.get('id')
            
            if disabled_rules and rule_id in disabled_rules:
                rule['enabled'] = False
            elif enabled_rules and rule_id in enabled_rules:
                rule['enabled'] = True
            
            # Apply overrides
            if rule_overrides and rule_id in rule_overrides:
                rule.update(rule_overrides[rule_id])
        
        custom_template['name'] = f"Custom ({base_template})"
        custom_template['custom'] = True
        
        return custom_template
