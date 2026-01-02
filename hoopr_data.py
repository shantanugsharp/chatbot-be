import json


data = open("hoopr_data_v2.json", "r", encoding="utf-8")
data = json.load(data)
track_code_vs_track_data = {}
for i in data:
  track_code_vs_track_data[int(i["trackCode"])] = i

def get_track_name(track_code):
  track_code = int(track_code)
  if track_code in track_code_vs_track_data:
    return track_code_vs_track_data[track_code]["name"]
  return None

def get_keywords(track_code):
  track_code = int(track_code)
  if track_code in track_code_vs_track_data:
    return track_code_vs_track_data[track_code]["keywords"]
  return None

def get_lyrics(track_code):
  track_code = int(track_code)
  if track_code in track_code_vs_track_data:
    return track_code_vs_track_data[track_code]["lyrics"]
  return None

def get_artist(track_code):
  track_code = int(track_code)
  if track_code in track_code_vs_track_data:
    return track_code_vs_track_data[track_code]["artist_names"]
  return None

def get_song_description(track_code):
  track_code = int(track_code)
  if track_code in track_code_vs_track_data:
    return track_code_vs_track_data[track_code]["description"]
  return None

def get_song_tags(track_code):
  track_code = int(track_code)
  if track_code in track_code_vs_track_data:
    return track_code_vs_track_data[track_code]["displayTags"]