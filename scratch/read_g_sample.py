with open("scratch/google_sample.html", "r", encoding="utf-8") as f:
    text = f.read()
print("Length of html:", len(text))
print("Sample text:", text[:1000])
