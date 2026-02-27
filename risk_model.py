# file: risk_model.py

def calculate_risk(metadata, analysis):
    """
    Example scoring logic for PR risk.
    """
    risk = 0
    if analysis.get("complexity") == "high":
        risk += 50
    elif analysis.get("complexity") == "medium":
        risk += 20
    if analysis.get("security_risk"):
        risk += 30
    if metadata.get("touches_core"):
        risk += 10
    return min(risk, 100)