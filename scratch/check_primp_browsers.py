import primp

browsers = [
    'chrome_100', 'chrome_104', 'chrome_107', 'chrome_109', 'chrome_114',
    'chrome_116', 'chrome_117', 'chrome_118', 'chrome_119', 'chrome_120',
    'chrome_123', 'chrome_126', 'chrome_130', 'chrome_131',
    'safari_15', 'safari_16', 'safari_17', 'safari_18',
    'safari_ios_15', 'safari_ios_16', 'safari_ios_17', 'safari_ios_18',
    'okhttp_3', 'okhttp_4', 'okhttp_5', 'edge_101', 'edge_120'
]
valid = []
for b in browsers:
    try:
        primp.Client(impersonate=b)
        valid.append(b)
    except Exception:
        pass
print("Valid impersonations in primp:", valid)
