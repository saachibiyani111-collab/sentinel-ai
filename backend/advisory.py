"""
advisory.py  (Sentinel AI)

PS Item 5 (lite) -- Citizen Health Risk Advisory:
ward-level health advisories in English + Marathi, driven by the live
(alpha-differentiated) ward AQI.

Deliberately TEMPLATED, not LLM-generated: deterministic, demo-safe,
instant, and free. Templates follow CPCB's official National AQI health
breakpoints and associated health statements. Marathi chosen as the
regional language for Pune (PS: "regional languages -- Bengaluru in
Kannada, Chennai in Tamil, and so on").
"""

# CPCB National AQI bands -> (band_key, en_category, mr_category)
BANDS = [
    (0,   50,  "good",         "Good",         "\u091a\u093e\u0902\u0917\u0932\u0940"),
    (51,  100, "satisfactory", "Satisfactory", "\u0938\u092e\u093e\u0927\u093e\u0928\u0915\u093e\u0930\u0915"),
    (101, 200, "moderate",     "Moderate",     "\u092e\u0927\u094d\u092f\u092e"),
    (201, 300, "poor",         "Poor",         "\u0935\u093e\u0908\u091f"),
    (301, 400, "very_poor",    "Very Poor",    "\u0905\u0924\u093f\u0936\u092f \u0935\u093e\u0908\u091f"),
    (401, 500, "severe",       "Severe",       "\u0917\u0902\u092d\u0940\u0930"),
]

ADVISORIES = {
    "good": {
        "en": "Air quality is good. Ideal for all outdoor activities.",
        "mr": "\u0939\u0935\u0947\u091a\u0940 \u0917\u0941\u0923\u0935\u0924\u094d\u0924\u093e \u091a\u093e\u0902\u0917\u0932\u0940 \u0906\u0939\u0947. \u0938\u0930\u094d\u0935 \u092c\u093e\u0939\u094d\u092f \u0915\u094d\u0930\u093f\u092f\u093e\u0902\u0938\u093e\u0920\u0940 \u092f\u094b\u0917\u094d\u092f.",
        "sensitive_en": "No restrictions for sensitive groups.",
        "sensitive_mr": "\u0938\u0902\u0935\u0947\u0926\u0928\u0936\u0940\u0932 \u0917\u091f\u093e\u0902\u0938\u093e\u0920\u0940 \u0915\u094b\u0923\u0924\u0947\u0939\u0940 \u0928\u093f\u0930\u094d\u092c\u0902\u0927 \u0928\u093e\u0939\u0940\u0924.",
    },
    "satisfactory": {
        "en": "Air quality is satisfactory. Minor discomfort possible for very sensitive people.",
        "mr": "\u0939\u0935\u0947\u091a\u0940 \u0917\u0941\u0923\u0935\u0924\u094d\u0924\u093e \u0938\u092e\u093e\u0927\u093e\u0928\u0915\u093e\u0930\u0915 \u0906\u0939\u0947. \u0905\u0924\u093f\u0936\u092f \u0938\u0902\u0935\u0947\u0926\u0928\u0936\u0940\u0932 \u0935\u094d\u092f\u0915\u094d\u0924\u0940\u0902\u0928\u093e \u0925\u094b\u0921\u093e \u0924\u094d\u0930\u093e\u0938 \u0939\u094b\u090a \u0936\u0915\u0924\u094b.",
        "sensitive_en": "Sensitive individuals (asthma, heart conditions) should watch for symptoms.",
        "sensitive_mr": "\u0938\u0902\u0935\u0947\u0926\u0928\u0936\u0940\u0932 \u0935\u094d\u092f\u0915\u094d\u0924\u0940\u0902\u0928\u0940 (\u0926\u092e\u093e, \u0939\u0943\u0926\u092f\u0935\u093f\u0915\u093e\u0930) \u0932\u0915\u094d\u0937\u0923\u093e\u0902\u0915\u0921\u0947 \u0932\u0915\u094d\u0937 \u0926\u094d\u092f\u093e\u0935\u0947.",
    },
    "moderate": {
        "en": "Moderate pollution. People with lung/heart disease, children and elderly should limit prolonged outdoor exertion.",
        "mr": "\u092e\u0927\u094d\u092f\u092e \u092a\u094d\u0930\u0926\u0942\u0937\u0923. \u092b\u0941\u092b\u094d\u092b\u0941\u0938/\u0939\u0943\u0926\u092f\u0935\u093f\u0915\u093e\u0930 \u0905\u0938\u0932\u0947\u0932\u0947, \u0932\u0939\u093e\u0928 \u092e\u0941\u0932\u0947 \u0906\u0923\u093f \u0935\u0943\u0926\u094d\u0927\u093e\u0902\u0928\u0940 \u0926\u0940\u0930\u094d\u0918 \u092c\u093e\u0939\u094d\u092f \u0936\u094d\u0930\u092e \u091f\u093e\u0933\u093e\u0935\u0947\u0924.",
        "sensitive_en": "Sensitive groups: reduce outdoor exercise; keep inhalers accessible.",
        "sensitive_mr": "\u0938\u0902\u0935\u0947\u0926\u0928\u0936\u0940\u0932 \u0917\u091f: \u092c\u093e\u0939\u0947\u0930\u0940\u0932 \u0935\u094d\u092f\u093e\u092f\u093e\u092e \u0915\u092e\u0940 \u0915\u0930\u093e; \u0907\u0928\u0939\u0947\u0932\u0930 \u091c\u0935\u0933 \u0920\u0947\u0935\u093e.",
    },
    "poor": {
        "en": "Poor air quality. Avoid prolonged outdoor exertion. Consider N95 masks outdoors.",
        "mr": "\u0939\u0935\u0947\u091a\u0940 \u0917\u0941\u0923\u0935\u0924\u094d\u0924\u093e \u0935\u093e\u0908\u091f. \u0926\u0940\u0930\u094d\u0918 \u092c\u093e\u0939\u094d\u092f \u0936\u094d\u0930\u092e \u091f\u093e\u0933\u093e. \u092c\u093e\u0939\u0947\u0930 N95 \u092e\u093e\u0938\u094d\u0915 \u0935\u093e\u092a\u0930\u093e\u0935\u093e.",
        "sensitive_en": "Sensitive groups: stay indoors as much as possible; use air purifiers.",
        "sensitive_mr": "\u0938\u0902\u0935\u0947\u0926\u0928\u0936\u0940\u0932 \u0917\u091f: \u0936\u0915\u094d\u092f\u0924\u094b \u0918\u0930\u093e\u0924 \u0930\u093e\u0939\u093e; \u090f\u0905\u0930 \u092a\u094d\u092f\u0941\u0930\u093f\u092b\u093e\u092f\u0930 \u0935\u093e\u092a\u0930\u093e.",
    },
    "very_poor": {
        "en": "Very poor air. Avoid outdoor activity. Keep windows closed; use purifiers.",
        "mr": "\u0939\u0935\u093e \u0905\u0924\u093f\u0936\u092f \u0935\u093e\u0908\u091f. \u092c\u093e\u0939\u094d\u092f \u0915\u094d\u0930\u093f\u092f\u093e \u091f\u093e\u0933\u093e. \u0916\u093f\u0921\u0915\u094d\u092f\u093e \u092c\u0902\u0926 \u0920\u0947\u0935\u093e; \u092a\u094d\u092f\u0941\u0930\u093f\u092b\u093e\u092f\u0930 \u0935\u093e\u092a\u0930\u093e.",
        "sensitive_en": "Sensitive groups: remain indoors; seek medical help if breathless.",
        "sensitive_mr": "\u0938\u0902\u0935\u0947\u0926\u0928\u0936\u0940\u0932 \u0917\u091f: \u0918\u0930\u093e\u0924\u091a \u0930\u093e\u0939\u093e; \u0927\u093e\u092a \u0932\u093e\u0917\u0932\u094d\u092f\u093e\u0938 \u0935\u0948\u0926\u094d\u092f\u0915\u0940\u092f \u092e\u0926\u0924 \u0918\u094d\u092f\u093e.",
    },
    "severe": {
        "en": "SEVERE pollution. Health emergency conditions -- everyone should avoid outdoor exposure.",
        "mr": "\u0917\u0902\u092d\u0940\u0930 \u092a\u094d\u0930\u0926\u0942\u0937\u0923. \u0906\u0930\u094b\u0917\u094d\u092f \u0906\u0923\u0940\u092c\u093e\u0923\u0940 -- \u0938\u0930\u094d\u0935\u093e\u0902\u0928\u0940 \u092c\u093e\u0939\u0947\u0930 \u091c\u093e\u0923\u0947 \u091f\u093e\u0933\u093e\u0935\u0947.",
        "sensitive_en": "Sensitive groups: strict indoor isolation; emergency plan ready.",
        "sensitive_mr": "\u0938\u0902\u0935\u0947\u0926\u0928\u0936\u0940\u0932 \u0917\u091f: \u0915\u091f\u093e\u0915\u094d\u0937\u0930\u0940\u0928\u0947 \u0918\u0930\u093e\u0924 \u0930\u093e\u0939\u093e; \u0906\u092a\u0924\u094d\u0915\u093e\u0932\u0940\u0928 \u092f\u094b\u091c\u0928\u093e \u0924\u092f\u093e\u0930 \u0920\u0947\u0935\u093e.",
    },
}


def _band_for(aqi: float):
    a = max(0, min(500, aqi or 0))
    for lo, hi, key, en, mr in BANDS:
        if lo <= a <= hi:
            return key, en, mr
    return "severe", "Severe", ADVISORIES["severe"]["mr"]


def advisory_for(ward: str, aqi: float) -> dict:
    """Bilingual health advisory for one ward at the given AQI."""
    key, cat_en, cat_mr = _band_for(aqi)
    tpl = ADVISORIES[key]
    return {
        "ward": ward,
        "aqi": round(aqi, 1) if aqi is not None else None,
        "category": {"en": cat_en, "mr": cat_mr},
        "advisory": {"en": tpl["en"], "mr": tpl["mr"]},
        "sensitive_groups": {"en": tpl["sensitive_en"], "mr": tpl["sensitive_mr"]},
    }


def advisories_all(ward_aqis: dict) -> list[dict]:
    """Advisories for every ward. ward_aqis = {ward_name: aqi}."""
    return [advisory_for(w, a) for w, a in ward_aqis.items()]


if __name__ == "__main__":
    for ward, aqi in [("Revenue Colony Shivajinagar", 75.5),
                      ("Katraj Dairy", 33.0),
                      ("Test Severe", 420)]:
        a = advisory_for(ward, aqi)
        print(f"{a['ward']}  AQI {a['aqi']}  [{a['category']['en']} / {a['category']['mr']}]")
        print(f"  EN: {a['advisory']['en']}")
        print(f"  MR: {a['advisory']['mr']}\n")
