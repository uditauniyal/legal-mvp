import requests

files = [
    ("files", open(r"C:\Users\uniya\Downloads\the_code_of_criminal_procedure,_1973.pdf", "rb")),
    ("files", open(r"C:\Users\uniya\Downloads\a2019-35.pdf", "rb")),
    ("files", open(r"C:\Users\uniya\Downloads\repealedfileopen.pdf", "rb")),
]

resp = requests.post("http://127.0.0.1:8000/ingest", files=files)
print("Status:", resp.status_code)
print("Response:", resp.json())
