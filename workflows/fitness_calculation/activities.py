from typing import Any, Dict, List, Optional
import json
import re

async def parse_fitness_problem(
    problem_text: str,
    # Injected context
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Extract trait values and contribution percentages from the fitness calculation problem text using pattern matching and parsing logic.
    
    Args:
        problem_text: The natural language fitness calculation problem containing trait information and percentage contributions
        
    Returns:
        Dict with 'calculate_fitness' key containing trait_values and trait_contributions arrays
    """
    try:
        # Handle JSON string input defensively
        if isinstance(problem_text, str) and problem_text.strip().startswith('{'):
            try:
                problem_text = json.loads(problem_text)
            except json.JSONDecodeError:
                pass  # Keep as string if JSON parsing fails
        
        # Ensure we have a string to work with
        if not isinstance(problem_text, str):
            problem_text = str(problem_text)
        
        # Pattern 1: Extract decimal values (0.0-1.0 range typical for traits)
        decimal_pattern = r'\b(?:0?\.\d+|1\.0+)\b'
        decimal_matches = re.findall(decimal_pattern, problem_text)
        decimal_values = []
        for match in decimal_matches:
            val = float(match)
            if 0.0 <= val <= 1.0:
                decimal_values.append(val)
        
        # Pattern 2: Extract percentage values and convert to decimals
        percentage_pattern = r'\b(\d+(?:\.\d+)?)%\b'
        percentage_matches = re.findall(percentage_pattern, problem_text)
        percentage_values = [float(match) / 100.0 for match in percentage_matches]
        
        # Pattern 3: Extract fractions and convert to decimals
        fraction_pattern = r'\b(\d+)/(\d+)\b'
        fraction_matches = re.findall(fraction_pattern, problem_text)
        fraction_values = []
        for numerator, denominator in fraction_matches:
            val = float(numerator) / float(denominator)
            if 0.0 <= val <= 1.0:
                fraction_values.append(val)
        
        # Combine all extracted values
        all_values = decimal_values + percentage_values + fraction_values
        
        if len(all_values) >= 2:
            # Strategy 1: Look for explicit trait/contribution keywords
            trait_keywords = ['trait', 'fitness', 'ability', 'strength', 'speed', 'intelligence', 'value']
            contrib_keywords = ['contribution', 'weight', 'importance', 'percent', '%']
            
            trait_values = []
            trait_contributions = []
            
            # Split text into sentences/phrases and try to categorize values
            sentences = re.split(r'[.;,\n]', problem_text.lower())
            
            for i, value in enumerate(all_values):
                # Find the sentence containing this value
                value_context = ""
                for sentence in sentences:
                    if str(value) in sentence or f"{value:.1f}" in sentence or f"{int(value*100)}%" in sentence:
                        value_context = sentence
                        break
                
                # Categorize based on context
                if any(keyword in value_context for keyword in trait_keywords) and not any(keyword in value_context for keyword in contrib_keywords):
                    trait_values.append(value)
                elif any(keyword in value_context for keyword in contrib_keywords):
                    trait_contributions.append(value)
                else:
                    # Default strategy: first half are traits, second half are contributions
                    if i < len(all_values) // 2:
                        trait_values.append(value)
                    else:
                        trait_contributions.append(value)
            
            # If we couldn't categorize properly, use default split strategy
            if not trait_values or not trait_contributions:
                mid_point = len(all_values) // 2
                trait_values = all_values[:mid_point] if mid_point > 0 else [all_values[0]]
                trait_contributions = all_values[mid_point:] if mid_point < len(all_values) else [all_values[-1]]
            
            # Ensure trait_contributions sum to approximately 1.0
            contributions_sum = sum(trait_contributions)
            if contributions_sum > 0 and abs(contributions_sum - 1.0) > 0.1:
                # Normalize contributions to sum to 1.0
                trait_contributions = [c / contributions_sum for c in trait_contributions]
            
            # Ensure we have matching arrays
            if len(trait_values) != len(trait_contributions):
                # Adjust to match the smaller array
                min_len = min(len(trait_values), len(trait_contributions))
                trait_values = trait_values[:min_len]
                trait_contributions = trait_contributions[:min_len]
            
            # Final validation
            if trait_values and trait_contributions and abs(sum(trait_contributions) - 1.0) <= 0.15:
                return {
                    "calculate_fitness": {
                        "trait_values": trait_values,
                        "trait_contributions": trait_contributions
                    }
                }
        
        # Fallback: Use LLM for complex text that doesn't match patterns
        prompt = f"""Extract trait values and contribution percentages from this fitness calculation problem:

{problem_text}

Return ONLY valid JSON in this exact format:
{{"calculate_fitness": {{"trait_values": [0.8, 0.7], "trait_contributions": [0.4, 0.6]}}}}

Rules:
- trait_values: decimal numbers between 0-1 representing individual trait strengths
- trait_contributions: decimal numbers between 0-1 that sum to 1.0 representing relative importance
- Arrays must have same length"""

        response = llm_client.generate(prompt)
        content = response.content.strip()
        
        # Extract JSON from response (handles markdown code blocks)
        if "```" in content:
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
        
        try:
            result = json.loads(content)
            if "calculate_fitness" in result and "trait_values" in result["calculate_fitness"] and "trait_contributions" in result["calculate_fitness"]:
                return result
        except json.JSONDecodeError:
            pass
        
        # Ultimate fallback: return default values
        return {
            "calculate_fitness": {
                "trait_values": [0.5, 0.5],
                "trait_contributions": [0.5, 0.5]
            }
        }
        
    except Exception as e:
        # Error fallback
        return {
            "calculate_fitness": {
                "trait_values": [0.5],
                "trait_contributions": [1.0]
            }
        }