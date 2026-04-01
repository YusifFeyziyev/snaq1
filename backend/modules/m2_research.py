def groq_analiz(axtaris_metn: str, ev_ad: str, qon_ad: str) -> dict:
    try:
        response = client.chat.completions.create(
            model=MODEL_M2,
            messages=[
                {"role": "system", "content": M2_PROMPT},
                {"role": "user", "content": f"""
Ev komandası: {ev_ad}
Qonaq komandası: {qon_ad}

AXTARIŞ NƏTİCƏLƏRİ:
{axtaris_metn}
"""}
            ],
            temperature=0.1,
            max_tokens=3000,
            timeout=120
        )
        content = response.choices[0].message.content.strip()

        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return None
    except Exception as e:
        return None
