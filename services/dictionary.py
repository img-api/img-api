import os
import json
import requests

file_name = "dictionary_alpha_arrays.json"

url = "https://raw.githubusercontent.com/matthewreagan/WebstersEnglishDictionary/master/" + file_name

print(" LOADING " + url)
print(requests.__version__)

if not os.path.exists(file_name):
    r = requests.get(url, allow_redirects=True)
    open(file_name, 'wb').write(r.content)

print(os.path.getsize(file_name))

print(" PARSING ")
with open(file_name) as json_file:
    data = json.load(json_file)

print(" PROCESSING ")
words = []
for letter in data:
    for word in letter.keys():
        if " " in word:
            print(" IGNORE SPACE " + word)
            continue

        if len(word) <= 2 or len(word) >= 8:
            print(" IGNORE " + word)
        else:
            words.append(word)

with open('my_dictionary.py', 'w') as json_file:
    json_file.write("words=")
    json.dump(words, json_file)