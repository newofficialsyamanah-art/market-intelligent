with open("app/models.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('        return None"\n', '        return None\n')

with open("app/models.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Fixed line 716 in app/models.py!")

