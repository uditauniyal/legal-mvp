"""Layman scenarios — written the way frightened people actually type.

WHY AN EARLIER VERSION OF THIS FILE WAS WRONG
    It contained well-formed paragraphs with clean grammar, complete
    chronology and an explicit question at the end:

        "I gave my television to a service centre for a small display issue.
         When I got it back it was not switching on at all..."

    That is a LAWYER'S SUMMARY of a situation. It is not a person typing at
    11pm. Real queries are fragmentary, mis-spelled, missing the fact that
    decides the case, and frequently ask no question at all.

WHAT REAL DISTRESS LOOKS LIKE IN TEXT
    fragmentary        sentences that stop and restart
    mis-spelled        ordinary typing errors, no autocorrect
    incomplete         the crucial fact is simply absent
    non-linear         jumps between the event, the aftermath, the fear
    delayed            "it happened 3 years back but"
    power-aware        the other party is an employer, official, elder, landlord
    money-aware        "i cant afford a lawyer" appears before the facts do
    partial disclosure shame stops the sentence before it finishes
    no question        they describe, then stop, because they don't know what to ask
    code-mixed         Indian English rhythm; Hindi words in Roman script

WHY EACH PROPERTY MATTERS FOR THE MEASUREMENT
    Retrieval works by comparing MEANING. A query's meaning becomes one point
    in space. Fragmented, emotional, partly-mis-spelled text produces a vague
    point that sits near nothing in particular. Statutory language is the exact
    opposite: formal, complete, precise.

    So the gap between how a person writes and how the law is written IS the
    retrieval problem. These queries measure that gap instead of assuming it.

THE `messiness` FIELD
    1 = fairly clear    2 = typical    3 = very fragmented / barely coherent

    Recorded so failure can be correlated with messiness. If accuracy falls as
    messiness rises, that is the access-to-justice claim as a number.

A NOTE ON THE SENSITIVE ONES
    Several describe assault, domestic violence and coercion. They are written
    plainly and without detail beyond what a person seeking help would give,
    because those are exactly the queries a legal-aid system must handle and
    exactly the users least able to phrase things precisely.

GOLD LABELS
    `primary` is the provision the situation is chiefly about; `secondary`
    lists others a competent answer should raise. Where the correct section is
    genuinely arguable, needs_review=True and it should not be counted until
    a human has checked it. Several here are deliberately under-specified —
    for those the RIGHT behaviour may be to ask a question rather than answer.
"""

# (text, expected_corpus, primary, secondary, topic, needs_review, messiness)
SCENARIOS: list[tuple[str, str, list[str], list[str], str, bool, int]] = [

    # ---- barely-formed, high distress -----------------------------------
    ("i was sexually assaulted and this happened but it has been long time now and the person "
     "is in position. i dont have money for lawyer. i dont know if i can still do something",
     "EITHER", ["IPC 376"], ["IPC 354", "CRPC 468"], "delayed reporting, power imbalance", True, 3),

    ("my sir at work has been doing things. i didnt say anything before because i needed the "
     "job. now he is saying he will make sure i dont get anywhere. i have some messages but "
     "not everything. what happens if i complain",
     "EITHER", ["IPC 354A"], ["IPC 506", "IPC 509"], "workplace harassment, retaliation fear", True, 3),

    ("husband beats. this is since 2 yrs. i went to police once they said settle at home. "
     "my parents also saying adjust. i have small baby. where to go",
     "EITHER", ["IPC 498A"], ["IPC 323", "CRPC 154"], "domestic violence, refused FIR", False, 3),

    ("some men in my area they say things when i pass. one of them followed till my gate "
     "twice. i told my brother he said dont make issue. i am scared to go for tuition now",
     "EITHER", ["IPC 354D"], ["IPC 509"], "stalking, family discouraging complaint", True, 3),

    # ---- fragmented, missing the deciding fact ---------------------------
    ("police took my brother. no paper nothing. they are saying come tomorrow. "
     "he is only 19. what to do sir",
     "CRPC", ["CRPC 41"], ["CRPC 50"], "arrest without warrant, no date given", False, 3),

    ("its been 3 days since they took my father. still not in court. they keep saying wait. "
     "he has bp problem needs tablets",
     "CRPC", ["CRPC 57"], ["CRPC 56"], "detention beyond 24 hours", False, 2),

    ("false case my cousin has filed. property matter. i think arrest can happen anytime. "
     "i am only earning person",
     "CRPC", ["CRPC 438"], [], "anticipatory bail, incomplete facts", False, 2),

    ("went 3 times to thana. everytime writer says come later or its civil matter. "
     "last time didnt even take application",
     "CRPC", ["CRPC 154"], ["CRPC 156"], "refusal to register FIR", False, 2),

    # ---- money as the first concern --------------------------------------
    ("i cannot afford advocate. that is main problem. the thing is my employer has not paid "
     "4 months salary and now he is saying i took company items which is false. he is "
     "threatening police case",
     "EITHER", ["IPC 499"], ["IPC 506", "IPC 406"], "false accusation, no means", True, 2),

    ("no money for case. landlord took deposit 60000 and not returning since i left. "
     "he is saying painting charges but no bill nothing. its 8 months now",
     "EITHER", ["IPC 406"], ["IPC 420"], "deposit withheld, cannot afford litigation", True, 2),

    # ---- delayed, unclear timeline ---------------------------------------
    ("this happened few years back i think 2021 or 2022. my uncle took my share of land "
     "papers saying he will do registry. now he is saying i gave it willingly. "
     "elders in family are on his side",
     "EITHER", ["IPC 420"], ["IPC 406", "IPC 465"], "family property fraud, vague date", True, 3),

    ("long back my sister passed away at inlaws place. they said accident in kitchen. "
     "before that she used to tell me on phone about car demand and once he had hit her. "
     "we could not reach in time they did everything fast",
     "EITHER", ["IPC 304B"], ["IPC 498A", "CRPC 174"], "dowry death, delayed, vague timeline", True, 3),

    # ---- code-mixed / Indian English rhythm ------------------------------
    ("ek aadmi ne mujhse paise liye saying double karke dega. 2 lakh diya 3 times me. "
     "kuch mahine wapas kiya then stopped. ab bol raha hai market down hai. "
     "colony me aur logo ka bhi paisa hai uske paas",
     "EITHER", ["IPC 420"], ["IPC 415", "IPC 406"], "cheating, code-mixed Hinglish", False, 3),

    ("mera phone train me chori ho gaya. bag neeche se kata tha. bahut bheed thi. "
     "complaint karne ka koi fayda hai kya",
     "EITHER", ["IPC 379"], ["IPC 378"], "theft, code-mixed", False, 2),

    # ---- describes, asks nothing -----------------------------------------
    ("neighbour and my brother were fighting about parking. neighbour went in came back with "
     "rod. hit on head. brother is in icu doctors saying bleeding. now their family saying "
     "my brother started",
     "EITHER", ["IPC 326"], ["IPC 325", "IPC 307"], "grievous hurt, no question asked", False, 2),

    ("loan app. i took small amount emergency. mostly repaid. now they call 20 times daily. "
     "called my sister also. called my old office. yesterday one said they will come home. "
     "they sent my photo to some contacts",
     "EITHER", ["IPC 506"], ["IPC 503", "IPC 500"], "loan app harassment, no question", False, 2),

    ("society group me koi post kar raha hai that i took money from funds. totally false. "
     "i was never in committee even. now neighbours not talking. my daughter friends parents "
     "also avoiding",
     "EITHER", ["IPC 500"], ["IPC 499"], "defamation in a group, code-mixed", False, 2),

    # ---- partial disclosure, sentence stops -------------------------------
    ("something happened at a relative's house when i was younger. i never told anyone. "
     "now he is coming to functions again and everyone treats him normally. "
     "i dont know if anything can be done after so long or if i should even",
     "EITHER", ["IPC 354"], ["IPC 376", "CRPC 468"], "historic abuse, partial disclosure", True, 3),

    ("my wife's family. there are things happening. i dont want to say everything here "
     "but she is not safe there and they wont let me take her. can police help or not",
     "EITHER", ["CRPC 97"], ["IPC 340", "IPC 498A"], "wrongful confinement, withheld facts", True, 3),

    # ---- authority as the other party --------------------------------------
    ("a person from municipality came and said my shop board is illegal and asked for money "
     "otherwise he will seal. i have all permissions. he came again yesterday",
     "EITHER", ["IPC 384"], ["IPC 383", "IPC 161"], "extortion by official", True, 2),

    ("teacher in my son school slapped him and now school is saying nothing happened and "
     "asking us to withdraw complaint. principal is not meeting us. my son is scared to go",
     "EITHER", ["IPC 323"], ["IPC 506"], "assault by teacher, institution shielding", True, 2),

    # ---- the medium-mess middle ------------------------------------------
    ("Bought fridge from showroom. Stopped cooling in 15 days. Company technician came twice, "
     "each time working 2 days then again same. Now saying only repair not replace. "
     "Showroom saying company problem. I have bill and warranty.",
     "CPA", ["CPA 2"], ["CPA 35", "CPA 39"], "defective goods", False, 1),

    ("Gave TV to service centre for display issue only. Came back not switching on at all. "
     "Now they want 9000 for motherboard which was working before. Job card says display only.",
     "CPA", ["CPA 2"], ["CPA 35"], "deficiency in service", False, 1),

    ("Booked flat 2021, paid 18 lakh. Builder kept giving new dates, now site abandoned. "
     "Not picking calls. Other buyers same situation, some went consumer court some saying "
     "police case. What is right thing",
     "EITHER", ["IPC 420"], ["IPC 406", "CPA 2"], "builder default: criminal or consumer", True, 1),

    ("Got call saying from bank card will be blocked. He knew my name and last digits so I "
     "believed. Asked OTP to verify. Within a minute 90000 gone in two transactions. "
     "Bank saying I shared OTP so my fault.",
     "EITHER", ["IPC 420"], ["IPC 419", "IPC 415"], "OTP fraud, bank denying liability", True, 1),

    # ---- multi-issue tangles ------------------------------------------------
    ("Contractor took 3 lakh advance for house renovation. Did maybe quarter work with bad "
     "material then stopped coming. When I asked money back he shouted in front of neighbours "
     "and said he knows people and I should be careful. Same thing he did to two other "
     "families in our lane.",
     "EITHER", ["IPC 420"], ["IPC 406", "IPC 506", "CPA 2"],
     "cheating + intimidation + service", True, 1),

    ("tenant not paying since 8 months. when i said vacate he changed the lock. i went with "
     "my brother he threatened and said he will file false case on me. water connection also "
     "he broke. i am senior citizen this is my only income",
     "EITHER", ["IPC 506"], ["IPC 441", "IPC 425"], "trespass + intimidation + mischief", True, 2),

    ("shop shutter lock broken at night, cash box and 40000 stock gone. cctv is there in lane "
     "but that shopkeeper saying recording over. police took complaint but no update. "
     "i have loan on this shop",
     "EITHER", ["IPC 457"], ["IPC 380"], "burglary, evidence lost", True, 2),

    ("jeweller took my mother's bangles for polishing before engagement. gave small slip only. "
     "after 10 days shop closed number switched off. other shopkeepers saying he moved",
     "EITHER", ["IPC 406"], ["IPC 403", "IPC 420"], "breach of trust", False, 2),

    ("wedding function fight started between two groups. my uncle went to separate and someone "
     "stabbed. he died on the way. 50 people were there nobody admitting. some are relatives "
     "so family not wanting to name",
     "EITHER", ["IPC 302"], ["IPC 300", "IPC 149"], "murder in crowd, unwilling witnesses", True, 2),
]
