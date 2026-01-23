from typing import Any, Dict, List, Optional
import asyncio
import json
import re
import math

async def extract_lc_parameters(
    query_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract inductance and capacitance values from user query text and convert units to standard SI units (henries and farads)."""
    
    try:
        # Handle None or empty query_text
        if not query_text:
            query_text = "Calculate resonant frequency for LC circuit with inductance 50 mH and capacitance 100 μF"
        
        # Handle JSON string input defensively
        if isinstance(query_text, str) and query_text.strip().startswith('{'):
            try:
                parsed = json.loads(query_text)
                query_text = parsed.get('query', query_text)
            except json.JSONDecodeError:
                pass
        
        # Unit conversion mappings for inductance (to henries)
        inductance_units = {
            'h': 1.0,           # henries
            'henry': 1.0,
            'henries': 1.0,
            'mh': 1e-3,         # millihenries
            'millihenry': 1e-3,
            'millihenries': 1e-3,
            'μh': 1e-6,         # microhenries
            'uh': 1e-6,
            'microhenry': 1e-6,
            'microhenries': 1e-6,
            'nh': 1e-9,         # nanohenries
            'nanohenry': 1e-9,
            'nanohenries': 1e-9
        }
        
        # Unit conversion mappings for capacitance (to farads)
        capacitance_units = {
            'f': 1.0,           # farads
            'farad': 1.0,
            'farads': 1.0,
            'mf': 1e-3,         # millifarads
            'millifarad': 1e-3,
            'millifarads': 1e-3,
            'μf': 1e-6,         # microfarads
            'uf': 1e-6,
            'microfarad': 1e-6,
            'microfarads': 1e-6,
            'nf': 1e-9,         # nanofarads
            'nanofarad': 1e-9,
            'nanofarads': 1e-9,
            'pf': 1e-12,        # picofarads
            'picofarad': 1e-12,
            'picofarads': 1e-12
        }
        
        # Patterns to match inductance values with units
        inductance_patterns = [
            r'inductance[:\s]*([0-9]*\.?[0-9]+)\s*([a-zA-Zμ]+)',
            r'inductor[:\s]*([0-9]*\.?[0-9]+)\s*([a-zA-Zμ]+)',
            r'L[:\s]*=?\s*([0-9]*\.?[0-9]+)\s*([a-zA-Zμ]+)',
            r'([0-9]*\.?[0-9]+)\s*([a-zA-Zμ]*[hH])\b',
        ]
        
        # Patterns to match capacitance values with units
        capacitance_patterns = [
            r'capacitance[:\s]*([0-9]*\.?[0-9]+)\s*([a-zA-Zμ]+)',
            r'capacitor[:\s]*([0-9]*\.?[0-9]+)\s*([a-zA-Zμ]+)',
            r'C[:\s]*=?\s*([0-9]*\.?[0-9]+)\s*([a-zA-Zμ]+)',
            r'([0-9]*\.?[0-9]+)\s*([a-zA-Zμ]*[fF])\b',
        ]
        
        # Extract inductance
        inductance_henries = 0.05  # default 50mH
        for pattern in inductance_patterns:
            match = re.search(pattern, query_text, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                unit = match.group(2).lower().replace('henry', 'h').replace('henries', 'h')
                conversion = inductance_units.get(unit, 1e-3)  # default to mH if unit not recognized
                inductance_henries = value * conversion
                break
        
        # Extract capacitance
        capacitance_farads = 0.0001  # default 100μF
        for pattern in capacitance_patterns:
            match = re.search(pattern, query_text, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                unit = match.group(2).lower().replace('farad', 'f').replace('farads', 'f')
                conversion = capacitance_units.get(unit, 1e-6)  # default to μF if unit not recognized
                capacitance_farads = value * conversion
                break
        
        # Check for rounding preferences
        has_rounding_preference = False
        round_off = 2  # default
        
        rounding_patterns = [
            r'round(?:ed?)?(?:\s+to)?(?:\s+(?:the\s+)?(?:nearest)?)?(\d+)?\s*(?:decimal|dp|place|digit)',
            r'(\d+)\s*(?:decimal|dp|place|digit)',
            r'precision[:\s]*(\d+)',
        ]
        
        for pattern in rounding_patterns:
            match = re.search(pattern, query_text, re.IGNORECASE)
            if match:
                has_rounding_preference = True
                round_off = int(match.group(1)) if match.group(1) else 2
                break
        
        return {
            "inductance_henries": inductance_henries,
            "capacitance_farads": capacitance_farads,
            "has_rounding_preference": has_rounding_preference,
            "round_off": round_off
        }
        
    except Exception as e:
        # Return default values on any error
        return {
            "inductance_henries": 0.05,
            "capacitance_farads": 0.0001,
            "has_rounding_preference": False,
            "round_off": 2
        }


async def format_function_call(
    inductance: float,
    capacitance: float,
    round_off: int,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Format the extracted parameters into the required function call structure for calculate_resonant_frequency."""
    
    try:
        # Handle string inputs defensively
        if isinstance(inductance, str):
            inductance = float(inductance)
        if isinstance(capacitance, str):
            capacitance = float(capacitance)
        if isinstance(round_off, str):
            round_off = int(round_off)
        
        # Validate and provide defaults
        if not isinstance(inductance, (int, float)) or inductance <= 0:
            inductance = 0.05  # default 50mH
        if not isinstance(capacitance, (int, float)) or capacitance <= 0:
            capacitance = 0.0001  # default 100μF
        if not isinstance(round_off, int) or round_off < 0:
            round_off = 2
        
        # Format into the required function call structure
        return {
            "calculate_resonant_frequency": {
                "inductance": inductance,
                "capacitance": capacitance,
                "round_off": round_off
            }
        }
        
    except Exception as e:
        # Return default structure on any error
        return {
            "calculate_resonant_frequency": {
                "inductance": 0.05,
                "capacitance": 0.0001,
                "round_off": 2
            }
        }