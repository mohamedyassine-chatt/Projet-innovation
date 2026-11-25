def verifier(signaux):
    return [{"tag": s["tag"], "type": "a_verifier", "message": s["a_verifier"],
             "page": s["page"]}
            for s in signaux if s.get("a_verifier")]