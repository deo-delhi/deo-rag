import requests
import json
import time

cases = [
    "CEO Vs Surendra Kumar Vakeel",
    "Cantonment Board, Meerut v. Narain Dass, (1969) 2 SCC 561.",
    "Mohan Agarwal vs UoI",
    "Sahodara Devi Vs GoI",
    "UoI Vs Dinshaw Anklaesari",
    "UoI Vs Robert Zomavia",
    "Usha Kapoor vs GoI"
]

def test_case(case_name):
    print(f"Testing case: {case_name}")
    url = "http://localhost:5200/ask"
    payload = {
        "question": f"summarise {case_name} case briefly in 500 words",
        "llm_model": "qwen2.5:3b-instruct-q5_k_m"
    }
    try:
        response = requests.post(url, json=payload, timeout=120)
        data = response.json()
        answer = data.get("answer", "")
        length = len(answer)
        
        if "Insufficient evidence" in answer or "The document does not contain this information" in answer:
            print(f"  [FAILED] - Model gave abstention answer")
            return False
        elif length < 200:
            print(f"  [FAILED] - Answer too short ({length} chars)")
            return False
        else:
            print(f"  [SUCCESS] - Answer length: {length} chars")
            # print(f"  Snippet: {answer[:100]}...")
            return True
    except Exception as e:
        print(f"  [ERROR] - {str(e)}")
        return False

results = []
for case in cases:
    success = test_case(case)
    results.append((case, success))
    time.sleep(2)

print("\nFinal Results:")
for case, success in results:
    status = "PASS" if success else "FAIL"
    print(f"{case}: {status}")

