"""
Dynamic schema detection - infer column types and semantic roles from data.
Supports auto-detection of numeric, categorical, date, ID, and other column types.
"""

import pandas as pd
import re
from typing import Dict, List, Tuple, Any
from datetime import datetime


class SchemaDetector:
    """Auto-detect column types and semantic roles from CSV data."""
    
    # Patterns for detecting specific column types
    ID_PATTERNS = [
        r'.*id$', r'^id_.*', r'.*_id$', r'.*record.*id', r'.*patient.*id',
        r'.*user.*id', r'.*customer.*id', r'.*account.*id', r'.*code$'
    ]
    
    DATE_PATTERNS = [
        r'.*date$', r'^date_.*', r'.*_date$', r'.*timestamp',
        r'.*time$', r'.*created', r'.*modified', r'.*received'
    ]
    
    NUMERIC_PATTERNS = [
        r'.*amount$', r'.*price$', r'.*value$', r'.*count$',
        r'.*rate$', r'.*percentage$', r'.*score$', r'.*ref_.*',
        r'.*_low$', r'.*_high$', r'.*reference'
    ]
    
    CATEGORICAL_PATTERNS = [
        r'.*status$', r'.*type$', r'.*category$', r'.*source$',
        r'.*name$', r'.*title$', r'.*description$', r'.*unit$'
    ]
    
    def __init__(self, df: pd.DataFrame, max_unique_ratio: float = 0.1):
        """
        Initialize schema detector.
        
        Args:
            df: Pandas DataFrame to analyze
            max_unique_ratio: If unique values / row count > this, treat as ID
        """
        self.df = df
        self.max_unique_ratio = max_unique_ratio
        self.schema = {}
        self.semantic_types = {}
    
    def detect_schema(self) -> Dict[str, Dict[str, Any]]:
        """
        Auto-detect schema for all columns.
        
        Returns:
            Dict mapping column name to type info:
            {
                'column_name': {
                    'inferred_type': 'numeric|categorical|date|text|id',
                    'python_type': 'int|float|str|datetime',
                    'confidence': 0.0-1.0,
                    'semantic_role': 'id|date|measurement|dimension|other',
                    'null_count': int,
                    'unique_count': int,
                    'sample_values': list
                }
            }
        """
        self.schema = {}
        
        for col in self.df.columns:
            col_data = self.df[col]
            
            # Basic statistics
            null_count = col_data.isna().sum()
            unique_count = col_data.nunique()
            sample_values = col_data.dropna().unique()[:5].tolist()
            
            # Try type inference
            inferred_type, confidence = self._infer_type(col, col_data)
            semantic_role = self._detect_semantic_role(col, col_data, inferred_type)
            
            self.schema[col] = {
                'inferred_type': inferred_type,
                'python_type': str(col_data.dtype),
                'confidence': confidence,
                'semantic_role': semantic_role,
                'null_count': int(null_count),
                'unique_count': int(unique_count),
                'sample_values': [str(v) for v in sample_values],
                'null_ratio': float(null_count / len(col_data)) if len(col_data) > 0 else 0
            }
        
        return self.schema
    
    def _infer_type(self, col_name: str, col_data: pd.Series) -> Tuple[str, float]:
        """
        Infer the data type of a column.
        
        Returns:
            (type: str, confidence: float)
        """
        col_name_lower = col_name.lower()
        col_data_clean = col_data.dropna()
        
        # Empty column
        if len(col_data_clean) == 0:
            return 'unknown', 0.5
        
        # Check if it's a date
        if self._is_date(col_data_clean):
            return 'date', 0.95
        
        # Check if it's numeric
        if self._is_numeric(col_data_clean):
            return 'numeric', 0.95
        
        # Check if it's categorical (limited unique values)
        if len(col_data_clean.unique()) / len(col_data_clean) < 0.1:
            return 'categorical', 0.8
        
        # Check if it's an ID (high uniqueness)
        if len(col_data_clean.unique()) / len(col_data_clean) > 0.5:
            return 'id', 0.7
        
        # Default to text
        return 'text', 0.6
    
    def _is_date(self, col_data: pd.Series) -> bool:
        """Check if column contains dates."""
        # Try to parse as datetime
        try:
            pd.to_datetime(col_data, errors='coerce')
            # If most values parse successfully, it's a date
            parsed = pd.to_datetime(col_data, errors='coerce')
            success_ratio = (1 - parsed.isna().sum() / len(col_data))
            return success_ratio > 0.7
        except:
            return False
    
    def _is_numeric(self, col_data: pd.Series) -> bool:
        """Check if column contains numeric values."""
        try:
            pd.to_numeric(col_data, errors='coerce')
            numeric = pd.to_numeric(col_data, errors='coerce')
            success_ratio = (1 - numeric.isna().sum() / len(col_data))
            return success_ratio > 0.9
        except:
            return False
    
    def _detect_semantic_role(self, col_name: str, col_data: pd.Series, 
                               inferred_type: str) -> str:
        """
        Detect the semantic role of a column (ID, date, measurement, dimension, etc).
        """
        col_name_lower = col_name.lower()
        
        # Check ID patterns
        for pattern in self.ID_PATTERNS:
            if re.match(pattern, col_name_lower):
                return 'id'
        
        # Check date patterns
        for pattern in self.DATE_PATTERNS:
            if re.match(pattern, col_name_lower):
                return 'date'
        
        # Check numeric measurement patterns
        for pattern in self.NUMERIC_PATTERNS:
            if re.match(pattern, col_name_lower):
                return 'measurement'
        
        # Based on type
        if inferred_type == 'date':
            return 'date'
        elif inferred_type == 'numeric':
            return 'measurement'
        elif inferred_type == 'categorical':
            return 'dimension'
        
        return 'other'
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of detected schema."""
        if not self.schema:
            self.detect_schema()
        
        summary = {
            'total_columns': len(self.schema),
            'by_type': {},
            'by_role': {},
            'data_quality': {
                'columns_with_nulls': 0,
                'avg_null_ratio': 0.0,
                'columns_with_high_null': 0  # > 50%
            }
        }
        
        null_ratios = []
        
        for col_name, col_info in self.schema.items():
            # Count by type
            t = col_info['inferred_type']
            summary['by_type'][t] = summary['by_type'].get(t, 0) + 1
            
            # Count by role
            r = col_info['semantic_role']
            summary['by_role'][r] = summary['by_role'].get(r, 0) + 1
            
            # Quality metrics
            if col_info['null_count'] > 0:
                summary['data_quality']['columns_with_nulls'] += 1
            
            if col_info['null_ratio'] > 0.5:
                summary['data_quality']['columns_with_high_null'] += 1
            
            null_ratios.append(col_info['null_ratio'])
        
        if null_ratios:
            summary['data_quality']['avg_null_ratio'] = sum(null_ratios) / len(null_ratios)
        
        return summary
    
    def recommend_rules(self) -> List[Dict[str, Any]]:
        """
        Based on detected schema, recommend quality rules to apply.
        
        Returns:
            List of recommended rule configurations
        """
        if not self.schema:
            self.detect_schema()
        
        recommended_rules = []
        
        for col_name, col_info in self.schema.items():
            role = col_info['semantic_role']
            col_type = col_info['inferred_type']
            null_ratio = col_info['null_ratio']
            
            # Rule 1: Missing value check
            if null_ratio > 0:
                recommended_rules.append({
                    'type': 'missing_value',
                    'column': col_name,
                    'enabled': True,
                    'threshold_warning': int(null_ratio * 100) + 10,
                    'threshold_critical': int(null_ratio * 100) + 25
                })
            
            # Rule 2: Duplicate check for IDs
            if role == 'id':
                recommended_rules.append({
                    'type': 'duplicate',
                    'column': col_name,
                    'enabled': True,
                    'allow_nulls': null_ratio > 0
                })
            
            # Rule 3: Date range check for date columns
            if role == 'date' or col_type == 'date':
                recommended_rules.append({
                    'type': 'date_range',
                    'column': col_name,
                    'enabled': True,
                    'check_future': True,
                    'max_age_days': 365
                })
            
            # Rule 4: Numeric range check
            if col_type == 'numeric':
                try:
                    col_vals = pd.to_numeric(self.df[col_name], errors='coerce').dropna()
                    if len(col_vals) > 0:
                        q1 = col_vals.quantile(0.25)
                        q3 = col_vals.quantile(0.75)
                        iqr = q3 - q1
                        lower_bound = q1 - 1.5 * iqr
                        upper_bound = q3 + 1.5 * iqr
                        
                        recommended_rules.append({
                            'type': 'outlier',
                            'column': col_name,
                            'enabled': True,
                            'method': 'iqr',
                            'lower_bound': float(lower_bound),
                            'upper_bound': float(upper_bound)
                        })
                except:
                    pass
            
            # Rule 5: Cardinality check for categorical
            if col_type == 'categorical':
                recommended_rules.append({
                    'type': 'cardinality',
                    'column': col_name,
                    'enabled': False,  # Optional
                    'max_unique': col_info['unique_count'] * 2  # Allow 2x observed
                })
        
        return recommended_rules


def detect_csv_schema(file_path: str, max_rows: int = 10000) -> Tuple[Dict, Dict]:
    """
    Convenience function to detect schema from a CSV file.
    
    Returns:
        (schema: dict, summary: dict)
    """
    df = pd.read_csv(file_path, nrows=max_rows)
    detector = SchemaDetector(df)
    schema = detector.detect_schema()
    summary = detector.get_summary()
    return schema, summary
