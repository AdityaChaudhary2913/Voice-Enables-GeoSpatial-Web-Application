import whisper

# Load Whisper Large model
model = whisper.load_model("large")
print("Model loaded successfully!")

file_path = "/Users/anshgupta/Desktop/geospatial-apps-master/recordings/recording_20250207_004719.wav"

# Transcribe the audio
result = model.transcribe(file_path)

# Print the transcription
print("Transcription:\n", result["text"])

import spacy
nlp=spacy.load("en_core_web_lg")

doc=nlp(result["text"])

for ent in doc.ents:
  if ent.label_=="GPE":
    print(ent.text)