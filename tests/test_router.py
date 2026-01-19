import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.router import RouterAgent

def test_router():
    router = RouterAgent()
    
    queries = [
        ("What is Section 41 of CrPC?", "BNSS", "statute"),
        ("Explain Article 21 of Constitution", "Constitution", "statute"),
        ("Keshavananda Bharati v. State of Kerala", "Judgments", "case_law"),
        ("Murder punishment in IPC", "BNS", "statute"),
        ("How to file a police complaint?", None, "general")
    ]
    
    print("--- Router Agent Tests ---")
    for q, expected_corpus, expected_intent in queries:
        plan = router.route(q)
        print(f"\nQuery: {q}")
        print(f"  -> Corpus: {plan.target_corpus} (Expected: {expected_corpus})")
        print(f"  -> Intent: {plan.intent} (Expected: {expected_intent})")
        print(f"  -> Boosts: {plan.boost_terms}")
        
        # Basic assertions
        if plan.target_corpus != expected_corpus:
            print(f"  [FAIL] Corpus Mismatch!")
        elif plan.intent != expected_intent:
            print(f"  [FAIL] Intent Mismatch!")
        else:
            print(f"  [PASS]")

if __name__ == "__main__":
    test_router()
