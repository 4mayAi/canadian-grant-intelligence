from youtube_transcript_api import YouTubeTranscriptApi

video_id = "pg6TOXyiIuo"
try:
    api = YouTubeTranscriptApi()
    transcript = api.fetch(video_id)
    lines = []
    for entry in transcript:
        # Convert start time to MM:SS
        start = entry.start
        minutes = int(start // 60)
        seconds = int(start % 60)
        timestamp = f"{minutes:02d}:{seconds:02d}"
        # Normalize newlines in text
        text = entry.text.replace("\n", " ")
        lines.append(f"[{timestamp}] {text}")

    output = "\n".join(lines)
    with open("scratch/transcript_output.txt", "w", encoding="utf-8") as f:
        f.write(output)
    print("Transcript written successfully to scratch/transcript_output.txt!")
except Exception as e:
    print(f"Error: {e}")
