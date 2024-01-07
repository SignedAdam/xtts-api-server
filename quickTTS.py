import sys
import requests
import uuid
import os
from pydub import AudioSegment
from pydub.playback import play

def main():
    if len(sys.argv) < 2:
        print("Usage: quickTTS.py 'text' --voice='voice_model' --language='language_code'")
        return
    
    text = sys.argv[1]
    voice_model = "female.wav"
    language = "en"
    all_merge = False
    id = str(uuid.uuid4())[:8]

    for arg in sys.argv:
        if arg.startswith('--voice='):
            voice_model = arg.split('=')[1] or voice_model
        elif arg.startswith('--language='):
            language = arg.split('=')[1] or language
        elif arg.startswith('--am='):
            all_merge = arg.split('=')[1] or all_merge

    print(f"Text: {text}")
    print(f"Voice Model: {voice_model}")
    print(f"Language: {language}")
    print(f"All Merge: {all_merge}")
    print(f"ID: {id}")

    all_voice_models = [
        "female2.wav",
        "calm_female.wav",
        "female3.wav",
        "male.wav",
    ]

    if all_merge:
        # little experiment with merging AI voices
        os.makedirs(f"output/{id}", exist_ok=True)
        paths = convert_text_to_multiple_audio(id, text, all_voice_models, language)

        # merge the audio files but append them to each other
        first_part_path = f"output/{id}/output.wav"
        merge_audio_files(paths, first_part_path)

        # actually merge the audio files into each other without appending
        second_part_path = f"output/{id}/output2.wav"
        merge_audio_files_into_each_other(paths, second_part_path)

        # merge the two audio files (appended + merged) after each other for effect
        merge_audio_files([first_part_path, second_part_path], f"output/{id}_final_am.wav")
    else:
        convert_text_to_audio(text, voice_model, language, f"output/{id}_output.wav")

def convert_text_to_multiple_audio(id, text, voice_models, language="en"):
    # Convert text to audio for multiple voice models
    audio_paths = []
    for voice_model in voice_models:
        save_path = f"output/{id}/{voice_model}"
        convert_text_to_audio(text, voice_model, language, save_path)
        audio_paths.append(save_path)
    return audio_paths

def merge_audio_files(audio_paths, output_path="output/merged_output.wav"):
    from pydub import AudioSegment
    merged_audio = AudioSegment.empty()
    for audio_path in audio_paths:
        audio = AudioSegment.from_wav(audio_path)
        merged_audio += audio
    merged_audio.export(output_path, format="wav")

def merge_audio_files_into_each_other(audio_paths, output_path="output/merged_output.wav"):
    first_audio = AudioSegment.from_wav(audio_paths[0])
    for audio_path in audio_paths[1:]:
        next_audio = AudioSegment.from_wav(audio_path)
        first_audio = first_audio.overlay(next_audio)

    first_audio.export(output_path, format="wav")


def convert_text_to_audio(text, voice_model, language = "en", save_path = "output/output.wav"):
    # Make a POST request to the TTS server to convert text to audio
    url = "http://127.0.0.1:8020/tts_to_audio/"
    payload = {
        "text": text,
        "speaker_wav": voice_model,
        "language": language
    }
    
    try:
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(response.content)
            print("Audio transcribed successfully")
        else:
            print("Failed to transcribe audio")
            print(f"Error: {response.content}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()