import requests

url = "https://youtube-to-mp315.p.rapidapi.com/download"

querystring = {"url":"https://www.youtube.com/watch?v=6POZlJAZsok","format":"m4a"}

payload = {}
headers = {
	"x-rapidapi-key": "da67faa1b9msh8f6c295120f8e4ap162158jsn3038b3b9997e",
	"x-rapidapi-host": "youtube-to-mp315.p.rapidapi.com",
	"Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers, params=querystring)

print(response.json())