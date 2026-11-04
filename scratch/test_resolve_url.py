import requests

g_url = "https://news.google.com/rss/articles/CBMimAFBVV95cUxNdzVDcUxWNnJiY0wwVk95WWVKU3l1UzNGSjVsYnRCa0oxNnY5cldaZEVFZEtUSk5xYWNWUTNoZEZ4S09pMXRPQUxDUy1ZbWduOGt6V1BIV2FEOUlSQXBCREhmOVIwYjgwMUY1V3dCLWNVck1sbmY0OHNyUXJNMmFMTnBnNWRqWFphaVRhRDRlM0xudWhQM1B4YtIBngFBVV95cUxQQl85R0VkeTlIMWl5SEN2bVV2ellhTE42MmNEODBhTjJRRjQxTkg5b1pUNGpHd3ZpWjBMb3Y1YnFXVWxzblc2Y013NHBRbExOc1U2aVQ2bV9DSTJVbGVVX0VjUjNpRG5ndzZBME5TQkR0bWRTNUhKdFlvOVZMUUtBWVZSQkFQX0FQRVF6Q3JTUFZySFdOdTJ5S2RfVHhUUQ?oc=5"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

try:
    r = requests.get(g_url, headers=headers, timeout=5, allow_redirects=True)
    print("Resolved URL:", r.url)
except Exception as e:
    print("Error:", e)
