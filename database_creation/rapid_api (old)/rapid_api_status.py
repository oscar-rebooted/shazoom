import requests

audio_id = "b535b91c-0412-41a4-aeb5-9bf65d6bbe56"
url = f"https://youtube-to-mp315.p.rapidapi.com/status/{audio_id}"

headers = {
	"x-rapidapi-key": "da67faa1b9msh8f6c295120f8e4ap162158jsn3038b3b9997e",
	"x-rapidapi-host": "youtube-to-mp315.p.rapidapi.com"
}

response = requests.get(url, headers=headers)

print(response.json())