import whisper
import librosa
import noisereduce as nr
import soundfile as sf
import numpy as np
import scipy.signal as signal
import spacy
import re
import requests

# Load models once
def load_models():
    """Load ML models only once"""
    model = whisper.load_model("large")
    nlp = spacy.load("en_core_web_trf")  # Use transformer-based model for better accuracy
    return model, nlp

model, nlp = load_models()

# Gazetteer for local places (can be expanded or replaced with an API query)
GAZETTEER = {"smallville", "rivertown", "hilltop", "springfield"}  # Example locations


def query_geonames(place_name):
    """Query GeoNames API for better place name resolution"""
    url = f"http://api.geonames.org/searchJSON?q={place_name}&maxRows=1&username=demo"  # Replace 'demo' with your GeoNames username
    try:
        response = requests.get(url)
        data = response.json()
        if data["geonames"]:
            return data["geonames"][0]["name"]
    except:
        pass
    return None


def preprocess_audio(input_path):
    """Audio preprocessing pipeline"""
    y, sr = librosa.load(input_path, sr=None, mono=True)
    
    # Noise reduction
    y_denoised = nr.reduce_noise(y=y, sr=sr)
    
    # Band-pass filter
    lowcut, highcut = 300, 3400
    nyquist = 0.5 * sr
    b, a = signal.butter(4, [lowcut/nyquist, highcut/nyquist], btype="band")
    y_filtered = signal.filtfilt(b, a, y_denoised)
    
    # Normalization
    y_normalized = y_filtered / np.max(np.abs(y_filtered))
    
    # Resampling
    y_resampled = librosa.resample(y_normalized, orig_sr=sr, target_sr=16000)
    return y_resampled, 16000


def transcribe_audio(audio_path):
    """Transcribe speech to text"""
    result = model.transcribe(audio_path, language='en', task='transcribe')
    return result["text"].strip()


def extract_geopolitical_entities(text):
    """Extract geopolitical entities using SpaCy and external sources"""
    doc = nlp(text)
    entities = {ent.text.lower() for ent in doc.ents if ent.label_ == "GPE"}
    
    # Check against gazetteer
    validated_entities = {place for place in entities if place in GAZETTEER}
    
    # Query GeoNames for missing places
    for place in entities - validated_entities:
        resolved_name = query_geonames(place)
        if resolved_name:
            validated_entities.add(resolved_name.lower())
    
    return list(validated_entities)


def text_to_command(text):
    """Convert transcribed text to geospatial commands"""
    text_lower = text.lower()
    places = extract_geopolitical_entities(text)
    
    # Command detection logic
    if "satellite" in text_lower:
        return "satellite"
    if "road layer" in text_lower:
        return "road layer"
    if re.search(r"zoom\s+in", text_lower):
        return "zoom in"
    if re.search(r"zoom\s+out", text_lower):
        return "zoom out"
    if nh_match := re.search(r"national highway (\d+)", text_lower):
        return f"NH{nh_match.group(1)}"
    if len(places) == 1:
        return places[0]
    if len(places) == 2:
        return f"{places[0]} {places[1]}"
    
    return "No valid command"


def process_audio(audio_path):
    """End-to-end processing pipeline"""
    processed_audio, sr = preprocess_audio(audio_path)
    temp_path = "temp_processed.wav"
    sf.write(temp_path, processed_audio, sr)
    
    transcription = transcribe_audio(temp_path)
    print("Transcription:", transcription)
    return text_to_command(transcription)